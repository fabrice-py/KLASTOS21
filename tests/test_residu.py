"""
Le garde-fou d'ADEQUATION DU MODELE.

POURQUOI CE FICHIER EXISTE
--------------------------
Le bouclage de masse verifie que la somme des phases approche 100 %. Il ne
verifie PAS que ce sont les bonnes phases. Un lot contenant une phase
absente du modele - carbonate de lithium, oxyde de nickel, cathode
delithiee - boucle normalement pendant que le prix se trompe de plusieurs
centaines d'euros la tonne. Mesure sur bulletins synthetiques parfaits,
avant correctif :

    10 % de Li2CO3 hors modele   bouclage 95,47 %  -> OK   -493 EUR/t
     8 % de NiO    hors modele   bouclage 95,92 %  -> OK   -462 EUR/t

Le residu par element voyait ces ecarts depuis toujours. Il etait calcule,
range dans `max_element_residual`, affiche par la seule ligne de commande,
et il ne commandait rien.

CE QUE CES TESTS GARDENT
------------------------
Trois choses, et la troisieme est la plus fragile :

  1. que le seuillage porte sur la statistique REDUITE, pas sur le residu
     brut en points massiques - le brut ne separe pas les distributions ;
  2. que le refus parte effectivement du rapport, et nomme son remede ;
  3. que la calibration tienne : aucun lot sain ne doit alerter, quelle que
     soit sa chimie.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from klastos import i18n
from klastos.elements import ATOMIC_MASS, ELEMENTS, formula_mass
from klastos.generator import DEFAULT_NOISE
from klastos.phases import PHASES
from klastos.report import ReportRefused, build_report
from klastos.solver import (RESIDU_ALERTE, RESIDU_REJET, STATUT_ALERTE,
                            STATUT_OK, STATUT_REJET, ResidualCheck,
                            SolverConfig, check_residual, solve)
from klastos.uncertainty import UncertaintyConfig, propagate

# --------------------------------------------------------------------------
# Materiel d'essai
# --------------------------------------------------------------------------

#: Phases volontairement ABSENTES de `PHASES`, et toutes reelles. C'est le
#: materiau du test : sans elles, on ne mesurerait que le bruit.
#:
#: LE CARBONATE DE LITHIUM Y EST RESTE, ET C'EST UNE DECISION MESUREE.
#: Il a ete ajoute au modele, puis RETIRE. L'ajout supprimait bien
#: l'angle mort, mais il cassait deux choses qu'aucune mesure synthetique
#: ne montrait :
#:
#:   - « Cathodes totales » cessait d'etre ferme meme avec l'oxygene
#:     dose, ce qui retirait a l'outil son argument le plus concret ;
#:   - les bandes de plausibilite cessaient d'alerter sur le fluor et le
#:     phosphore - le controle qui avait attrape le seul defaut jamais
#:     trouve sur des donnees REELLES.
#:
#: Le garde-fou ci-dessous refuse desormais ce lot bruyamment, et la
#: valorisation retient le dosage : l'angle mort est couvert sans
#: toucher au modele.
HORS_MODELE: dict[str, dict[str, float]] = {
    "Li2CO3": {"Li": 2.0, "C": 1.0, "O": 3.0},
    "NMC811_delithie": {"Li": 0.75, "Ni": 0.8, "Mn": 0.1, "Co": 0.1, "O": 2.0},
    "NiO": {"Ni": 1.0, "O": 1.0},
    "CMC_SBR": {"C": 6.0, "H": 10.0, "O": 5.0},
}

#: Un bulletin reel ne porte ni oxygene ni hydrogene.
DOSES = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F"]

SAIN = {"NMC811": 0.40, "C_total": 0.33, "Cu_metal": 0.10, "Al_metal": 0.07,
        "PVDF": 0.05, "LiPF6": 0.03, "Fe_metal": 0.02}

#: Six chimies realistes, toutes entierement decrites par le modele. Elles
#: servent a verifier que le seuil ne depend pas du type de lot.
CHIMIES_SAINES = {
    "NMC811": SAIN,
    "NMC111": {"NMC111": 0.36, "C_total": 0.36, "Cu_metal": 0.11,
               "Al_metal": 0.08, "PVDF": 0.05, "LiPF6": 0.02,
               "Fe_metal": 0.02},
    "LFP": {"LFP": 0.42, "C_total": 0.34, "Cu_metal": 0.11,
            "Al_metal": 0.07, "PVDF": 0.04, "LiPF6": 0.02},
    "LCO": {"LCO": 0.45, "C_total": 0.30, "Cu_metal": 0.12, "Al_metal": 0.06,
            "PVDF": 0.04, "LiPF6": 0.02, "Fe_metal": 0.01},
    "NMC+LFP": {"NMC622": 0.22, "LFP": 0.20, "C_total": 0.33,
                "Cu_metal": 0.10, "Al_metal": 0.07, "PVDF": 0.05,
                "LiPF6": 0.02, "Fe_metal": 0.01},
    "carbone riche": {"NMC532": 0.22, "C_total": 0.48, "Cu_metal": 0.13,
                      "Al_metal": 0.08, "PVDF": 0.06, "LiPF6": 0.02,
                      "Fe_metal": 0.01},
}


def bulletin(melange: dict[str, float]) -> dict[str, float]:
    """Bulletin elementaire EXACT d'un melange, en pourcents massiques."""
    b = {el: 0.0 for el in ELEMENTS}
    for nom, frac in melange.items():
        comp = (PHASES[nom]["composition"] if nom in PHASES
                else HORS_MODELE[nom])
        M = formula_mass(comp)
        for el, n in comp.items():
            b[el] += frac * ATOMIC_MASS[el] * n / M
    return {el: v * 100.0 for el, v in b.items()}


def resoudre(melange: dict[str, float], doses: list[str] = None):
    doses = doses or DOSES
    b = bulletin(melange)
    return solve({el: b[el] for el in doses}, elements=doses,
                 config=SolverConfig())


def avec(base: dict, phase: str, part: float) -> dict:
    """`base` dont on remplace `part` de cathode par une phase hors modele."""
    m = dict(base)
    m["NMC811"] = round(m["NMC811"] - part, 10)
    m[phase] = part
    assert abs(sum(m.values()) - 1.0) < 1e-9
    return m


# ==========================================================================
# 1. La statistique : pourquoi elle est reduite
# ==========================================================================

def test_le_seuillage_porte_sur_la_statistique_reduite():
    """
    `residual_weighted` est une NORME : elle croit avec le nombre
    d'elements doses. Seuiller la norme brute rendrait le garde-fou plus
    severe sur un bulletin a douze elements que sur un bulletin a dix,
    pour une raison qui n'a rien a voir avec la qualite du lot.
    """
    dix = check_residual(3.0, 10)
    douze = check_residual(3.0, 12)
    assert dix.reduced > douze.reduced, (
        "la reduction n'a pas lieu : la meme norme donne la meme valeur "
        "sur deux bulletins de tailles differentes")
    assert dix.reduced == pytest.approx(3.0 / math.sqrt(10))
    assert douze.reduced == pytest.approx(3.0 / math.sqrt(12))


@pytest.mark.parametrize("reduit, attendu", [
    (0.0, STATUT_OK),
    (RESIDU_ALERTE - 1e-9, STATUT_OK),
    (RESIDU_ALERTE, STATUT_ALERTE),
    (RESIDU_REJET - 1e-9, STATUT_ALERTE),
    (RESIDU_REJET, STATUT_REJET),
    (10.0, STATUT_REJET),
])
def test_les_bornes_des_trois_statuts(reduit, attendu):
    """
    Les deux seuils sont INCLUSIFS, comme ceux du bouclage. Un test sur
    les bornes exactes evite qu'un `>` devienne un `>=` au detour d'une
    relecture sans que rien ne le signale.
    """
    c = check_residual(reduit * math.sqrt(10), 10)
    assert c.status == attendu


def test_un_residu_ne_se_normalise_pas_sur_zero_element():
    """Division par zero deguisee. Elle doit echouer fort, et le dire."""
    with pytest.raises(ValueError, match="zero element"):
        check_residual(1.0, 0)


def test_le_statut_de_rejet_est_le_seul_a_rendre_le_lot_inexploitable():
    assert check_residual(0.0, 10).is_exploitable
    assert check_residual(RESIDU_ALERTE * math.sqrt(10), 10).is_exploitable
    assert not check_residual(RESIDU_REJET * math.sqrt(10), 10).is_exploitable


# ==========================================================================
# 2. La calibration : aucun lot sain ne doit alerter
# ==========================================================================

@pytest.mark.parametrize("nom", sorted(CHIMIES_SAINES))
def test_aucune_chimie_saine_n_alerte_sur_un_bulletin_exact(nom):
    """
    Le seuil doit valoir pour toutes les chimies, pas pour celle sur
    laquelle il a ete calibre. Six compositions, de la NMC811 dominante a
    la LFP pure.
    """
    r = resoudre(CHIMIES_SAINES[nom])
    assert r.residu.status == STATUT_OK, (
        f"{nom} : lot entierement decrit par le modele, et pourtant "
        f"{r.residu.status} a {r.residu.reduced:.3f}")


@pytest.mark.parametrize("nom", sorted(CHIMIES_SAINES))
def test_le_bruit_analytique_seul_ne_declenche_pas_le_rejet(nom):
    """
    Le garde-fou doit vivre sous bruit reel, pas seulement sur des
    bulletins parfaits. Mesure a l'appui : sur 250 lots sains bruites a
    6 %, le 99e centile de la statistique reduite va de 0,59 a 1,01 selon
    la chimie. Le seuil de REJET a 1,5 doit rester hors d'atteinte.

    Le seuil d'ALERTE, lui, peut etre touche : c'est son role d'etre
    sensible, et 1 a 5 % de lots sains signales est le prix accepte.
    """
    melange = CHIMIES_SAINES[nom]
    b = np.array([bulletin(melange)[el] / 100.0 for el in DOSES])
    rng = np.random.default_rng(20261103)
    sigma = DEFAULT_NOISE.sigmas(b, DOSES)
    rejets = 0
    for _ in range(60):
        tire = np.maximum(0.0, b + rng.normal(0.0, 1.0, b.shape) * sigma)
        r = solve({el: tire[i] * 100.0 for i, el in enumerate(DOSES)},
                  elements=DOSES, config=SolverConfig())
        rejets += int(r.residu.status == STATUT_REJET)
    assert rejets == 0, (
        f"{nom} : {rejets} lots sains sur 60 rejetes par le seul bruit "
        f"analytique. Le seuil de rejet est sous le plancher de bruit.")


# ==========================================================================
# 3. La detection : ce qu'il attrape, et ce qu'il manque
# ==========================================================================

@pytest.mark.parametrize("phase, part, attendu", [
    # Les deux ecarts les plus couteux, mesures a -493 et -462 EUR/t.
    ("Li2CO3", 0.10, STATUT_REJET),
    ("NiO", 0.08, STATUT_ALERTE),
    # Un ecart moyen, -174 EUR/t.
    ("Li2CO3", 0.05, STATUT_ALERTE),
])
def test_une_phase_absente_du_modele_est_signalee(phase, part, attendu):
    r = resoudre(avec(SAIN, phase, part))
    assert r.residu.status == attendu, (
        f"{part*100:.0f} % de {phase} hors modele : attendu {attendu}, "
        f"obtenu {r.residu.status} a {r.residu.reduced:.3f}")
    # Le bouclage, lui, ne voit rien. C'est tout l'interet du controle.
    assert r.closure.status == STATUT_OK, (
        "le bouclage a change de comportement : le test ne demontre plus "
        "que le residu voit ce que le bouclage manque")


def test_la_cathode_delithiee_est_signalee():
    """
    Le fait chimique le plus central de la black mass face a la poudre de
    cathode neuve, et celui que `PHASES` ne prevoit pas : le modele fixe
    Li = 1,0 par unite de formule.
    """
    m = {k: v for k, v in SAIN.items() if k != "NMC811"}
    m["NMC811_delithie"] = 0.40
    r = resoudre(m)
    assert r.residu.status != STATUT_OK
    assert r.closure.status == STATUT_OK


@pytest.mark.parametrize("phase, part", [("Li2CO3", 0.03), ("NiO", 0.04)])
def test_les_petits_ecarts_passent_encore_et_c_est_documente(phase, part):
    """
    CE TEST GARDE UNE LIMITE, PAS UNE REUSSITE.

    A 3 % de Li2CO3 (-81 EUR/t) et 4 % de NiO (-198 EUR/t), le controle
    ne declenche pas. Ce n'est donc PAS une preuve que le modele est
    juste : c'est un plancher. Le jour ou l'un de ces cas se met a
    alerter - seuil abaisse, phase ajoutee au modele, bruit affine - ce
    test echoue et oblige a relire la documentation plutot qu'a la
    laisser mentir.
    """
    r = resoudre(avec(SAIN, phase, part))
    assert r.residu.status == STATUT_OK, (
        f"{part*100:.0f} % de {phase} est desormais detecte. Bonne "
        f"nouvelle - mettre a jour le commentaire des seuils dans "
        f"solver.py et le tableau de detection du rapport d'audit.")


def test_une_phase_invisible_reste_invisible():
    """
    Le liant aqueux CMC/SBR n'apporte que carbone, hydrogene et oxygene,
    dont deux ne sont jamais doses. Il se confond exactement avec du
    carbone. Aucun controle elementaire ne peut le voir, et il ne faut
    pas pretendre le contraire : son effet sur le prix est nul, seule la
    masse inexpliquee en temoigne.
    """
    m = dict(SAIN)
    m["C_total"] = round(m["C_total"] - 0.05, 10)
    m["CMC_SBR"] = 0.05
    r = resoudre(m)
    assert r.residu.status == STATUT_OK
    assert r.residu.reduced == pytest.approx(0.0, abs=1e-4)


# ==========================================================================
# 4. Le refus, et sa prose
# ==========================================================================

def _rapport(melange, **kwargs):
    b = bulletin(melange)
    rep = propagate({el: b[el] for el in DOSES}, elements=DOSES,
                    config=UncertaintyConfig(seed=1, n_draws=40,
                                             n_bound_draws=8))
    return build_report("LOT-RESIDU", "Client Test", rep, None, [], **kwargs)


def test_le_rapport_refuse_un_lot_que_le_modele_n_explique_pas():
    with pytest.raises(ReportRefused) as capture:
        _rapport(avec(SAIN, "Li2CO3", 0.10))
    message = str(capture.value)
    # LE REFUS NOMME SON REMEDE. C'est la discipline du projet : un refus
    # qui ne dit pas quoi faire fait perdre un client.
    assert "DRX" in message or "XRD" in message, (
        f"le refus ne nomme aucun remede : {message}")


def test_un_lot_sain_passe_le_rapport():
    """Le pendant du test ci-dessus. Sans lui, un refus systematique
    passerait le precedent sans rien dire."""
    rapport = _rapport(SAIN)
    assert rapport.lot_id == "LOT-RESIDU"


def test_le_mode_demonstration_leve_le_refus_comme_pour_le_bouclage():
    """
    Le refus doit se comporter comme celui du bouclage, pas autrement :
    deux portes voisines avec deux clefs differentes se desynchronisent.
    """
    rapport = _rapport(avec(SAIN, "Li2CO3", 0.10), allow_demo=True)
    assert rapport is not None


def test_le_rapport_porte_la_ligne_d_adequation():
    from klastos.report import LIGNE_RESIDU, SECTION_DIAGNOSTIC
    rapport = _rapport(SAIN)
    diag = next(s for s in rapport.sections if s.cle == SECTION_DIAGNOSTIC)
    ligne = diag.ligne(LIGNE_RESIDU)
    assert ligne is not None, "la ligne d'adequation du modele est absente"
    assert ligne.severity == STATUT_OK


@pytest.mark.parametrize("langue", ["fr", "en"])
@pytest.mark.parametrize("statut", [STATUT_OK, STATUT_ALERTE, STATUT_REJET])
def test_chaque_statut_a_un_texte_dans_les_deux_langues(langue, statut):
    """
    L'invariant du projet : UNE CLE N'EST JAMAIS UN TEXTE AFFICHE. Une
    cle manquante doit echouer ici, pas s'afficher au client.
    """
    c = ResidualCheck(reduced=0.0, n_elements=10, status=statut)
    rendu = c.message_dans(langue)
    assert rendu and not rendu.startswith("journal."), (
        f"{c.cle_message} manque au catalogue en {langue}")
    assert i18n.t("rapport.refus.residu", langue, valeur=2.0, seuil=1.5)
    assert i18n.t("rapport.mention.residu_alerte", langue,
                  valeur=1.0, seuil=0.9)


# ==========================================================================
# 5. LE MODELE NE DOIT PAS POUVOIR TOUT EXPLIQUER
# --------------------------------------------------------------------------
# Un garde-fou d'adequation ne vaut que si le modele PEUT echouer. Avec
# dix elements doses, chaque phase ajoutee ouvre une direction nulle : au
# dela d'un certain nombre de colonnes, le systeme ajuste n'importe quel
# bulletin exactement et le controle devient du theatre.
#
# Ce n'est pas une crainte, c'est une mesure. Quatre phases ont ete
# ajoutees - Li2CO3, NiO, Co3O4, MnO - puis TOUTES retirees.
#
#   variante                deg   « Cathodes totales »   detecte delith.
#   quatorze phases           4            3,1 pt              oui
#   + Li2CO3                  5            3,1 pt              oui
#   + Li2CO3 + NiO            6           33,5 pt              NON
#   + les quatre              8           36,6 pt              NON
#
# Des la deuxieme phase, le systeme a trop de colonnes pour dix equations
# et ajuste n'importe quel bulletin : verifie sur huit especes
# candidates, toutes devenues invisibles.
#
# Li2CO3 seul semblait gratuit sur cette table. IL NE L'ETAIT PAS, et
# seule la suite complete l'a montre - aucune mesure synthetique ne
# pouvait le voir :
#
#   - « Cathodes totales » cessait d'etre ferme meme avec l'oxygene
#     dose, ce qui retirait a l'outil son argument le plus concret ;
#   - les bandes de plausibilite cessaient d'alerter sur le fluor et le
#     phosphore, c'est-a-dire le controle qui avait attrape le seul
#     defaut jamais trouve sur des donnees REELLES.
#
# L'angle mort est couvert autrement, et mieux : le garde-fou
# d'adequation refuse le lot bruyamment, et la valorisation retient le
# dosage du laboratoire plutot que la reconstruction du modele.
#
# Les tests ci-dessous gardent cette frontiere. Ils echouent si quelqu'un
# ajoute une phase sans refaire la mesure - sur la suite ENTIERE, pas sur
# un jeu synthetique.
# ==========================================================================

def test_le_modele_garde_son_pouvoir_de_refus():
    """
    Avec huit especes candidates hors modele, toutes devenaient
    invisibles des que la deuxieme phase etait ajoutee. Le jour ou ce
    test echoue, le garde-fou d'adequation ne refuse plus rien.
    """
    r = resoudre(avec(SAIN, "NiO", 0.10))
    assert not r.residu.is_exploitable, (
        "un lot a 10 % d'oxyde de nickel hors modele n'est plus refuse : "
        "le modele a trop de colonnes pour le nombre d'elements doses")


def test_la_grandeur_phare_du_rapport_reste_etroite():
    """
    « Cathodes totales » est la grandeur sur laquelle repose le discours
    commercial. Mesuree a 3,1 points de large sur un lot sain ; elle
    passait a 33,5 points des l'ajout d'une deuxieme phase.
    """
    import numpy as np
    from klastos.identifiability import (compatible_bounds, null_space,
                                         standard_functionals)
    from klastos.phases import stoichiometry_matrix

    A, els, cles = stoichiometry_matrix(elements=DOSES)
    N = null_space(A)
    cath = next(f for f in standard_functionals(cles, elements=els)
                if f.key == "cathodes_totales")
    r = resoudre(SAIN)
    lo, hi = compatible_bounds(r.x, N, cath.c)
    largeur = (hi - lo) * 100.0
    assert largeur < 10.0, (
        f"le domaine de « Cathodes totales » fait {largeur:.1f} points. "
        f"Une phase a probablement ete ajoutee sans refaire la mesure du "
        f"commentaire de phases.py : au-dela de Li2CO3, la grandeur perd "
        f"tout sens.")


def test_le_nombre_de_phases_est_sous_surveillance():
    """
    CE TEST GARDE UNE DECISION, PAS UN CALCUL.

    Il echoue des qu'on touche a la liste des phases - c'est son but. Le
    message dit quoi faire : refaire la mesure avant de changer le
    chiffre, pas l'inverse.
    """
    from klastos.phases import PHASE_KEYS
    assert len(PHASE_KEYS) == 14, (
        f"{len(PHASE_KEYS)} phases au lieu de 14. Avant d'ajuster ce "
        f"chiffre, faire tourner la suite ENTIERE : l'ajout du seul "
        f"carbonate de lithium passait tous les tests synthetiques et "
        f"cassait pourtant le controle de plausibilite sur le fluor, "
        f"ainsi que le caractere ferme de « Cathodes totales » avec "
        f"oxygene dose.")


# ==========================================================================
# 6. LA DOCUMENTATION EST VERIFIEE, PAS SEULEMENT RELUE
# --------------------------------------------------------------------------
# Les 1 500 tests de ce projet verifient ce que le code FAIT. Aucun ne
# verifiait ce que les commentaires DISENT qu'il fait - et c'est par ce
# trou que sont passees deux erreurs :
#
#   - le commentaire des seuils citait des taux de detection recopies
#     d'une colonne mesuree a un AUTRE seuil, et les sous-estimait de 3 a
#     10 points ;
#   - celui de `DEPARTAGE_NUMERIQUE` affirmait que le retirer serait
#     defendable, sur un raisonnement faux.
#
# Une prose fausse dans un fichier technique est pire qu'une prose
# absente : elle se cite, elle se propage, et elle fonde des decisions.
# Le test ci-dessous recalcule la table documentee et la compare.
# ==========================================================================

#: Taux de detection cites dans le commentaire des seuils, en pourcents.
#: ILS SONT LA POUR ETRE COMPARES A LA MESURE, pas pour decorer.
DETECTION_DOCUMENTEE = {
    "Li2CO3-10": 100.0,
    "NiO-8": 95.0,
    "Li2CO3-5": 88.0,
    "delithiee": 62.0,
    "Li2CO3-3": 42.0,
    "NiO-4": 34.0,
}


def _taux_de_detection(melange, n=300, graine=20261103):
    """Part des lots bruites qui atteignent le seuil d'ALERTE."""
    b = np.array([bulletin(melange)[el] / 100.0 for el in DOSES])
    rng = np.random.default_rng(graine)
    sigma = DEFAULT_NOISE.sigmas(b, DOSES)
    atteints = 0
    for _ in range(n):
        tire = np.maximum(0.0, b + rng.normal(0.0, 1.0, b.shape) * sigma)
        r = solve({el: tire[i] * 100.0 for i, el in enumerate(DOSES)},
                  elements=DOSES, config=SolverConfig())
        atteints += int(r.residu.reduced >= RESIDU_ALERTE)
    return atteints / n * 100.0


def _cas_documente(cle):
    if cle == "delithiee":
        m = {k: v for k, v in SAIN.items() if k != "NMC811"}
        m["NMC811_delithie"] = 0.40
        return m
    phase, part = cle.rsplit("-", 1)
    return avec(SAIN, phase, int(part) / 100.0)


@pytest.mark.parametrize("cle", sorted(DETECTION_DOCUMENTEE))
def test_les_taux_de_detection_documentes_sont_les_vrais(cle):
    """
    LE COMMENTAIRE DES SEUILS EST UNE AFFIRMATION, DONC IL SE VERIFIE.

    Il annonce ce que le garde-fou attrape et ce qu'il manque. C'est sur
    cette table qu'on decide de faire confiance - ou non - a un lot qui
    passe. Une table fausse vaut moins qu'une table absente.

    La tolerance est large : ces taux viennent d'un tirage, et quelques
    points de battement sont normaux. Un ecart de dix points ne l'est
    pas, et c'est exactement ce qu'avait la premiere redaction.
    """
    attendu = DETECTION_DOCUMENTEE[cle]
    mesure = _taux_de_detection(_cas_documente(cle))
    assert abs(mesure - attendu) <= 5.0, (
        f"{cle} : le commentaire de `solver.py` annonce {attendu:.0f} %, "
        f"la mesure donne {mesure:.1f} %. Corriger le COMMENTAIRE avant "
        f"d'elargir cette tolerance.")
