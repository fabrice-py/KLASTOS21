"""
Tests des bandes de plausibilite sur les compositions predites.

Defaut d'origine, trouve le 22 octobre 2026 sur un lot reel : ni le
phosphore ni le fluor n'etant doses, le solveur a predit 17,79 % de FLUOR en
retenant 14,3 % de LiPF6 et 11,8 % de PVDF. Le materiau de reference
certifie OREAS donne un fluor a 2,44 % : la prediction valait sept fois la
valeur d'un materiau reel, et rien ne l'a signale. `is_exploitable` valait
True, et le lot serait parti en valorisation avec 110 % de masse.

Le generateur synthetique ne pouvait pas reveler ce trou : il produit des
lots coherents par construction, et `make_lot` refuse meme un bouclage
superieur a 1.
"""

from __future__ import annotations

import pathlib

import numpy as np
import pytest

from klastos import i18n
from klastos.phases import PHASE_KEYS
from klastos.plausibility import (ANCRAGES_CERTIFIES,
                                  FACTEUR_PLAUSIBILITE, FACTEUR_VALIDE,
                                  SANS_ANCRAGE_DOCUMENTE, bandes,
                                  verifier_predictions)
from klastos.service import Demande, analyser

#: Fractions de phases rapportees sur le lot reel BM1. Le reste du melange
#: est complete pour que la somme reste realiste ; seules LiPF6 et PVDF
#: portent le fluor, donc seules elles pilotent la prediction.
PHASES_BM1 = {"LiPF6": 0.143, "PVDF": 0.118, "NMC811": 0.40, "C_total": 0.25}

#: Teneurs certifiees du materiau OREAS, en %. Le fluor y EST dose.
OREAS_F_PCT = 2.44
OREAS_P_PCT = 0.350


def _x_depuis(fractions: dict[str, float]) -> tuple[np.ndarray, list[str]]:
    keys = list(PHASE_KEYS)
    x = np.zeros(len(keys))
    for phase, v in fractions.items():
        x[keys.index(phase)] = v
    return x, keys


# ==========================================================================
# 1. Ce que les bandes valent, et ce qu'elles ne valent pas
# ==========================================================================

def test_les_ancrages_viennent_d_un_seul_certificat():
    """
    UN POINT N'EST PAS UNE BANDE. Une valeur sur un seul materiau ne
    decrit pas une population : elle dit seulement qu'un materiau reel
    existe a ce niveau-la. Le test fige cette modestie pour qu'un ajout
    silencieux d'ancrages inventes echoue.

    Le certificat porte DEUX valeurs utilisables en principe, F et P, et
    une seule est retenue. Le phosphore a ete ecarte sur mesure, pas par
    prudence vague : voir `test_le_phosphore_n_est_pas_ancre_et_c_est_mesure`.
    """
    assert set(ANCRAGES_CERTIFIES) == {"F"}, (
        "aucun ancrage ne doit etre ajoute sans certificat a l'appui")
    assert ANCRAGES_CERTIFIES["F"] == pytest.approx(OREAS_F_PCT / 100.0)
    # Le certificat porte aussi P = 0,350 %, et ce n'est PAS un ancrage.
    # Voir `test_le_phosphore_n_est_pas_ancre_et_c_est_mesure`.
    assert "P" not in ANCRAGES_CERTIFIES
    assert "P" in SANS_ANCRAGE_DOCUMENTE, (
        "un element ecarte doit l'etre pour une raison ecrite")


def test_aucune_borne_n_est_declaree_validee():
    """
    Le facteur n'est pas arbitre, donc aucune borne ne peut l'etre. Le
    rapport doit porter cette mention, comme il porte « NON ARBITRE » sur
    l'age maximal d'un taux de change.
    """
    assert FACTEUR_VALIDE is False
    for bande in bandes().values():
        assert bande.validated is False, bande.element
        assert "OREAS" in bande.source
        assert "un seul materiau" in bande.source


def test_la_borne_haute_derive_de_l_ancrage_et_du_facteur():
    for el, ancre in ANCRAGES_CERTIFIES.items():
        bande = bandes(facteur=4.0)[el]
        assert bande.high == pytest.approx(ancre * 4.0)
        assert bande.low == 0.0, (
            "la borne basse est zero : un element non dose peut etre absent")


def test_les_bandes_suivent_le_facteur():
    """
    Les bandes sont CALCULEES et non figees dans une constante. Une table
    figee aurait ignore un changement de facteur en silence.
    """
    etroite = bandes(facteur=1.5)["F"].high
    large = bandes(facteur=6.0)["F"].high
    assert etroite < large
    assert large / etroite == pytest.approx(4.0)


# ==========================================================================
# 2. Ce qui est controle, et ce qui ne l'est pas
# ==========================================================================

def test_un_element_dose_n_est_jamais_controle():
    """
    La regle qui epargne le lot OREAS. Une teneur dosee est une MESURE, pas
    une prediction : la refuser reviendrait a contester le laboratoire. Le
    controle ne porte que sur ce que le solveur invente.
    """
    x, keys = _x_depuis(PHASES_BM1)
    # Meme melange, mais le bulletin dose F et P.
    c = verifier_predictions(x, keys, ["Li", "Ni", "Mn", "Co", "Al", "Fe",
                                       "Cu", "C", "F", "P"])
    assert c.depassements == (), (
        "un element dose a ete signale : le controle sort de son role")
    assert not c


def test_un_element_sans_ancrage_est_declare_non_controle():
    """
    « N'invente aucune borne pour les elements sans ancrage. » L'absence de
    controle est DECLAREE, elle n'est pas un satisfecit : c'est la regle du
    projet, ne jamais afficher ce que la donnee ne porte pas.

    H et O n'ont pas d'ancrage certifie, et l'oxygene n'est jamais dose
    (protocole 2.6). Ils doivent donc ressortir comme non controles, et
    jamais comme conformes.
    """
    x, keys = _x_depuis(PHASES_BM1)
    c = verifier_predictions(x, keys, ["Li", "Ni", "Mn", "Co", "Al", "Fe",
                                       "Cu", "C"])
    assert "O" in c.non_controles
    assert "H" in c.non_controles
    for el in c.non_controles:
        assert el not in ANCRAGES_CERTIFIES, (
            f"{el} a un ancrage : il devait etre controle, pas ecarte")


# ==========================================================================
# 3. Le lot reel
# ==========================================================================

def test_la_prediction_de_fluor_du_lot_reel_est_signalee():
    """
    Le cas de non-regression. 17,7 % de fluor predit contre 2,44 %
    certifie : un facteur sept, qu'aucun reglage raisonnable ne doit
    laisser passer.
    """
    x, keys = _x_depuis(PHASES_BM1)
    c = verifier_predictions(x, keys, ["Li", "Ni", "Mn", "Co", "Al", "Fe",
                                       "Cu", "C"])
    assert c, "la prediction de fluor du lot reel n'est plus signalee"

    fluor = next(d for d in c.depassements if d.element == "F")
    assert fluor.fraction == pytest.approx(0.1773, abs=5e-4)
    assert fluor.facteur_observe > 7.0
    assert fluor.fraction > fluor.borne


def test_le_depassement_nomme_la_phase_porteuse():
    """
    « Depassement -> le rapport nomme l'element ET la phase porteuse
    responsable. » Sans le nom de la phase, l'utilisateur sait qu'un
    chiffre est faux mais pas ou agir.

    Sur ce melange, LiPF6 est a 75,04 % de fluor et PVDF a 59,34 % : la
    phase porteuse majoritaire est donc LiPF6, et c'est elle qu'il faut
    nommer.
    """
    x, keys = _x_depuis(PHASES_BM1)
    c = verifier_predictions(x, keys, ["Li", "Ni", "Mn", "Co", "Al", "Fe",
                                       "Cu", "C"])
    fluor = next(d for d in c.depassements if d.element == "F")
    assert fluor.phase == "LiPF6"
    assert fluor.phase_fraction == pytest.approx(0.143)


def test_le_phosphore_n_est_pas_ancre_et_c_est_mesure():
    """
    Ce test affirmait l'inverse, et il celebrait un FAUX POSITIF.

    Une premiere version ancrait le phosphore sur le certificat - P =
    0,350 % - et se felicitait de voir le melange de BM1 signale a 8,3 fois
    cette valeur. Mesure sur 1 200 lots que les profils du projet declarent
    plausibles, phosphore non dose : 45,8 % etaient signales, et 100 % des
    lots riches en LFP.

    La cause est chimique et elle condamne l'ancrage : LFP est LiFePO4, le
    phosphore y est un element MAJEUR. Les profils du projet produisent
    jusqu'a 11,70 % de P, soit 33 fois la teneur du certificat, parce que le
    materiau OREAS ne contient quasiment pas de LFP.

    Le phosphore est donc declare non controle, et le dire est la seule
    honnetete disponible : l'outil ne sait pas borner cette prediction.
    """
    x, keys = _x_depuis(PHASES_BM1)
    c = verifier_predictions(x, keys, ["Li", "Ni", "Mn", "Co", "Al", "Fe",
                                       "Cu", "C"])
    assert all(d.element != "P" for d in c.depassements), (
        "le phosphore est de nouveau signale : la bande a ete rendue, et "
        "elle refuse 100 % des lots LFP")
    assert "P" in c.non_controles, (
        "le phosphore doit etre DECLARE non controle, pas passe sous "
        "silence")


def test_aucun_lot_plausible_du_projet_n_est_refuse():
    """
    Le test de faux positifs qui manquait, et dont l'absence a laisse
    passer la bande de phosphore.

    Il porte sur les lots que le generateur du projet declare plausibles,
    avec F et P non doses - la situation de BM1. Aucun ne doit etre
    signale. Le generateur n'est pas un oracle du reel, mais refuser ce
    qu'il juge normal est un signe sur pour une borne mal posee.
    """
    from klastos.generator import NOISE_FREE, make_lot

    DOSES = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "Cu", "C"]
    refuses = []
    for profil in ("gigafactory_nmc", "mixed_ev", "consumer_electronics",
                   "lfp_heavy"):
        for graine in range(60):
            lot = make_lot(rng=graine, profile=profil, noise=NOISE_FREE,
                           closure=1.0)
            c = verifier_predictions(lot.x_true, lot.phase_keys, DOSES)
            for d in c.depassements:
                refuses.append(f"{profil}/{graine} : {d.element} a "
                               f"{d.fraction * 100:.2f} %")
    assert not refuses, (
        f"{len(refuses)} lot(s) plausible(s) refuse(s), par exemple "
        f"{refuses[:3]}")


# ==========================================================================
# 4. Sur le chemin unique, de bout en bout
# ==========================================================================

BULLETIN_COMPLET = pathlib.Path("data/exemples/bulletin_coherent.csv")


@pytest.fixture
def bulletin_sans_f_ni_p(tmp_path):
    """
    Le bulletin d'exemple prive de ses colonnes F et P.

    C'est la reproduction exacte de la situation du lot reel : meme
    matiere, meme tout, seule la COUVERTURE du bulletin change. Le fluor y
    est mesure a 1,70 % ; sans la colonne, le solveur le predit a 8,92 %.
    """
    lignes = BULLETIN_COMPLET.read_text(encoding="utf-8").splitlines()
    entetes = lignes[0].split(",")
    valeurs = lignes[1].split(",")
    garde = [i for i, e in enumerate(entetes)
             if not e.startswith(("P (", "F ("))]
    f = tmp_path / "sans_fp.csv"
    f.write_text(
        ",".join(entetes[i] for i in garde) + "\n"
        + ",".join(valeurs[i] for i in garde) + "\n",
        encoding="utf-8")
    return f


def _analyser(chemin, **kw):
    return analyser(Demande(bulletin=str(chemin),
                            provenance="vehicule_electrique",
                            attestee=True, tirages=30, **kw))


def test_un_bulletin_complet_ne_declenche_rien():
    """Le pendant positif : F et P doses, donc aucune prediction a juger."""
    a = _analyser(BULLETIN_COMPLET)
    assert "F" in a.lecture.measured_elements
    assert "P" in a.lecture.measured_elements
    assert a.plausibilite.depassements == ()


def test_retirer_les_colonnes_f_et_p_fait_apparaitre_l_alerte(
        bulletin_sans_f_ni_p):
    """
    La demonstration du defaut, sur le chemin unique. Le fluor MESURE vaut
    1,70 % ; sans sa colonne, le modele lui en attribue cinq fois plus et
    le signale desormais.
    """
    a = _analyser(bulletin_sans_f_ni_p)
    assert "F" not in a.lecture.measured_elements
    assert a.plausibilite, "aucune alerte alors que F et P sont predits"

    fluor = next(d for d in a.plausibilite.depassements if d.element == "F")
    assert fluor.fraction > 3.0 * 0.0170, (
        "le fluor predit devrait depasser largement sa valeur mesuree")
    assert fluor.phase in ("PVDF", "LiPF6")


def test_le_rapport_nomme_l_element_et_la_phase(bulletin_sans_f_ni_p):
    """L'avertissement doit atteindre le document, pas rester dans l'objet."""
    a = _analyser(bulletin_sans_f_ni_p)
    fluor = next(d for d in a.plausibilite.depassements if d.element == "F")

    vise = [w for w in a.rapport.warnings if "F" in w and fluor.phase in w]
    assert vise, (
        f"aucun avertissement ne nomme a la fois F et {fluor.phase} ; "
        f"avertissements : {a.rapport.warnings}")
    avert = vise[0]
    assert "NON ARBITRÉ" in avert, (
        "le rapport doit dire que la borne n'est pas arbitree")


def test_l_avertissement_est_bilingue(bulletin_sans_f_ni_p):
    fr = _analyser(bulletin_sans_f_ni_p, langue="fr")
    en = _analyser(bulletin_sans_f_ni_p, langue="en")
    a_fr = [w for w in fr.rapport.warnings if "implausible" in w.lower()]
    a_en = [w for w in en.rapport.warnings if "implausible" in w.lower()]
    assert a_fr and a_en
    assert a_fr[0] != a_en[0]
    assert "NOT ARBITRATED" in a_en[0]
    # Le francais ne doit pas fuir dans le rapport anglais.
    assert "matériau certifié" not in a_en[0]


def test_le_facteur_est_expose_comme_les_seuils_de_bouclage(
        bulletin_sans_f_ni_p):
    """
    « Expose le seuil en parametre comme les seuils de bouclage. » Un
    reglage non arbitre doit pouvoir se discuter sans toucher au code.
    """
    large = _analyser(bulletin_sans_f_ni_p, facteur_plausibilite=50.0)
    assert large.plausibilite.depassements == (), (
        "un facteur tres large doit tout laisser passer")

    etroit = _analyser(bulletin_sans_f_ni_p, facteur_plausibilite=1.0)
    assert etroit.plausibilite.depassements, (
        "un facteur de 1 doit signaler toute prediction au-dessus de "
        "l'ancrage")


def test_le_facteur_par_defaut_attrape_le_lot_reel():
    """
    Garde sur la valeur par defaut. Le lot reel est a 7,3 fois l'ancrage :
    tout facteur par defaut au-dela le laisserait passer, et le defaut
    serait de retour sans qu'aucun autre test ne bouge.
    """
    assert FACTEUR_PLAUSIBILITE < 7.0, (
        f"un facteur par defaut de {FACTEUR_PLAUSIBILITE} ne signalerait "
        f"plus la prediction de fluor du lot reel (7,3 x l'ancrage)")


def test_la_cle_de_l_avertissement_existe_dans_les_deux_langues():
    for langue in ("fr", "en"):
        texte = i18n.t("rapport.avert.prediction_implausible", langue,
                       element="F", valeur=17.73, facteur=7.3, ancrage=2.44,
                       phase="LiPF6", part=14.3, borne=7.32, ecart=3.0)
        assert "F" in texte and "LiPF6" in texte


# ==========================================================================
# 5. L'arbitrage du facteur : l'encadrement par la chimie
# ==========================================================================
#
# Le facteur 3 n'est pas un chiffre rond choisi au hasard. Le fluor d'une
# black mass ne vient que de deux phases, donc le plafond chimique de
# n'importe quel scenario se calcule exactement. Ces tests RECALCULENT
# l'encadrement depuis la stoechiometrie plutot que de recopier la prose du
# protocole : sinon ils ne verifieraient que ma capacite a transcrire.

def _fluor(pvdf: float, lipf6: float) -> float:
    """Le fluor total d'un melange, calcule depuis la stoechiometrie."""
    from klastos.phases import stoichiometry_matrix

    A, els, keys = stoichiometry_matrix()
    i = els.index("F")
    return (pvdf * A[i, keys.index("PVDF")]
            + lipf6 * A[i, keys.index("LiPF6")])


def test_les_deux_phases_porteuses_de_fluor_sont_celles_annoncees():
    """
    Tout l'encadrement repose sur ces deux teneurs. Si une phase change de
    formule, les bornes ci-dessous ne veulent plus rien dire.
    """
    from klastos.phases import stoichiometry_matrix

    A, els, keys = stoichiometry_matrix()
    i = els.index("F")
    assert A[i, keys.index("PVDF")] == pytest.approx(0.5934, abs=1e-4)
    assert A[i, keys.index("LiPF6")] == pytest.approx(0.7504, abs=1e-4)
    # Et aucune autre phase ne porte de fluor : sinon le calcul serait faux.
    porteuses = {keys[j] for j in range(len(keys)) if A[i, j] > 0}
    assert porteuses == {"PVDF", "LiPF6"}


def test_le_facteur_tombe_dans_l_encadrement_chimique():
    """
    LE test de l'arbitrage. Le protocole 2.6 quinquies enferme le facteur
    dans [2,75 ; 3,68], et ces deux bornes sont des SCENARIOS :

      borne basse  un lot mal seche, 5 % de PVDF et 5 % d'electrolyte,
                   atteint 6,72 % de fluor. Descendre sous ce rapport
                   signalerait un lot que le procede explique.
      borne haute  un sechage tres defaillant, 8 % d'electrolyte, atteint
                   8,97 %. Depasser ce rapport laisserait passer un lot que
                   rien n'explique.

    Si le facteur sort de cet encadrement, ce n'est plus celui que le
    protocole justifie.
    """
    ancre = ANCRAGES_CERTIFIES["F"]
    basse = _fluor(0.05, 0.05) / ancre       # lot mal seche
    haute = _fluor(0.05, 0.08) / ancre       # sechage tres defaillant

    assert basse == pytest.approx(2.75, abs=0.02)
    assert haute == pytest.approx(3.68, abs=0.02)
    assert basse < FACTEUR_PLAUSIBILITE < haute, (
        f"le facteur {FACTEUR_PLAUSIBILITE} est sorti de l'encadrement "
        f"[{basse:.2f} ; {haute:.2f}] que le protocole justifie")


def test_le_facteur_tolere_un_lot_mal_seche():
    """
    La propriete qui rend le seuil utilisable. Un retrait d'electrolyte
    imparfait est un defaut de procede courant, pas une donnee fausse : il
    ne doit pas declencher d'alerte.
    """
    borne = ANCRAGES_CERTIFIES["F"] * FACTEUR_PLAUSIBILITE
    assert _fluor(0.05, 0.05) < borne, (
        "un lot a 5 % d'electrolyte residuel est signale : le seuil refuse "
        "un defaut de procede ordinaire")


@pytest.mark.parametrize("nom,pvdf,lipf6", [
    ("sechage tres defaillant", 0.05, 0.08),
    ("liant double", 0.10, 0.02),
])
def test_le_facteur_refuse_ce_qu_aucun_procede_n_explique(nom, pvdf, lipf6):
    borne = ANCRAGES_CERTIFIES["F"] * FACTEUR_PLAUSIBILITE
    assert _fluor(pvdf, lipf6) > borne, f"{nom} n'est plus signale"


def test_le_plafond_des_profils_passe_largement():
    """
    Les profils du generateur plafonnent a 5 % de PVDF et 2 % d'electrolyte,
    soit 4,47 % de fluor. C'est ce plafond qui explique les 0 % de faux
    positifs mesures : il est a 1,64 fois sous la borne.
    """
    borne = ANCRAGES_CERTIFIES["F"] * FACTEUR_PLAUSIBILITE
    plafond = _fluor(0.05, 0.02)
    assert plafond == pytest.approx(0.0447, abs=1e-4)
    assert borne / plafond > 1.5, (
        "la marge entre le plafond plausible et la borne est tombee sous "
        "1,5 : des lots sains vont commencer a etre signales")


def test_le_facteur_reste_non_arbitre_tant_que_les_deux_questions_tiennent():
    """
    Le plafond de 4,47 % derive des bornes du generateur, que le protocole
    1.1 qualifie d'hypotheses metier NON SOURCEES. Un seuil arbitre contre
    des hypotheses non sourcees serait un seuil blanchi.

    Ce test tombera le jour ou quelqu'un passera le drapeau a True, et c'est
    voulu : il faudra alors avoir les deux reponses du geometallurgiste, et
    le dire dans le protocole.
    """
    assert FACTEUR_VALIDE is False, (
        "le facteur a ete declare arbitre : les deux questions du protocole "
        "2.6 quinquies ont-elles recu une reponse ecrite ?")


# ==========================================================================
# 6. Le protocole porte l'arbitrage
# ==========================================================================

@pytest.fixture(scope="module")
def protocole():
    import re

    texte = pathlib.Path("PROTOCOLE.md").read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", texte.replace("**", "").replace("`", ""))


def test_le_protocole_porte_le_tableau_des_scenarios(protocole):
    for attendu in ("5 % d'électrolyte résiduel", "Liant doublé",
                    "6,72 %", "7,43 %", "8,97 %", "17,73 %"):
        assert attendu in protocole, f"« {attendu} » absent du protocole"


def test_le_protocole_pose_les_deux_questions_fermees(protocole):
    """
    Le livrable de l'arbitrage n'est pas un chiffre, c'est une question
    qu'un geometallurgiste tranche sans ouvrir un chantier.
    """
    assert "[2,75 ; 3,68]" in protocole
    assert "ne peut pas descendre sous" in protocole
    assert "ne peut pas dépasser" in protocole


def test_le_protocole_dit_pourquoi_le_facteur_n_est_pas_arbitre(protocole):
    assert "hypothèses métier, non sourcées" in protocole
    assert "validated=False" in protocole
