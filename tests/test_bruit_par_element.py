"""
Le modele de bruit sait porter un bruit PAR ELEMENT, sans changer le defaut.

Contexte, et c'est une investigation plus qu'une correction. `rel_sigma`
vaut 6 % uniformes, calibre sur LNE-LiB01 dont le certificat donne des
incertitudes elargies de 10 a 15 % - soit 5 a 7,5 % type a k = 2. Le
certificat OREAS donne des ecarts-types relatifs par element allant de
0,51 % sur le nickel a 18,57 % sur le phosphore. L'ecart est d'un ordre de
grandeur sur le nickel, et inverse sur le phosphore.

Les deux ne mesurent pas la meme chose, et aucun des deux ne mesure la
grandeur dont l'outil a besoin - l'erreur d'UN bulletin, par UN laboratoire,
sur un lot client HETEROGENE. Voir PROTOCOLE.md § 1.3 bis.

DONC LE DEFAUT NE BOUGE PAS. Ces tests verifient deux choses contraires :
que la structure sait porter un bruit par element, et que rien n'a change
tant qu'on ne le demande pas explicitement.

Mesure a l'appui du danger : sur le lot OREAS, le passage aux RSD par
element resserre l'intervalle de prix maximal de 84 % - de 761 a 121 USD/t
de largeur. Un bruit plus etroit resserre le prix annonce, et c'est la
direction dangereuse.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import re

import numpy as np
import pytest

from klastos.generator import DEFAULT_NOISE, NOISE_FREE, NoiseModel, make_lot
from klastos.service import (Demande, analyser, charger_prix, charger_termes)
from klastos.solver import element_weights, solve_lot
from klastos.uncertainty import resample_bulletin

#: RSD par element, colonne 1SD du certificat OREAS. Fractions.
RSD_OREAS: dict[str, float] = {
    "Ni": 0.0051, "Li": 0.0099, "Co": 0.0105, "Mn": 0.0108, "C": 0.0230,
    "Al": 0.0286, "Fe": 0.0360, "Cu": 0.0368, "F": 0.0570, "P": 0.1857,
}

BRUT_OREAS = pathlib.Path("data/exemples/bulletin_reel_OREAS_brut.csv")


def _par_element(table: dict[str, float] = None) -> NoiseModel:
    return NoiseModel(rel_sigma_par_element=tuple(
        (table or RSD_OREAS).items()))


# ==========================================================================
# 1. Le defaut ne bouge pas
# ==========================================================================

def test_le_defaut_ne_porte_aucune_table_par_element():
    """
    La garde la plus importante du fichier. Si cette assertion tombe, le
    modele par defaut a change de nature sans arbitrage.
    """
    assert DEFAULT_NOISE.rel_sigma_par_element == ()
    assert DEFAULT_NOISE.rel_sigma == pytest.approx(0.06)
    assert DEFAULT_NOISE.validated is True


def test_sans_table_le_sigma_relatif_reste_un_scalaire():
    """
    Un vecteur constant donnerait le meme resultat mathematique, mais la
    verification « rien n'a bouge par defaut » serait moins directe. On
    exige donc le scalaire.
    """
    assert DEFAULT_NOISE.rel_sigma_pour(["Ni", "Co"]) == 0.06
    assert isinstance(DEFAULT_NOISE.rel_sigma_pour(["Ni"]), float)


def test_les_poids_par_defaut_sont_identiques_bit_pour_bit():
    """
    La formule `rel_sigma * |b| + abs_sigma` vivait recopiee dans
    `solver.element_weights` et `uncertainty.resample_bulletin`. Elle est
    passee dans `NoiseModel.sigmas`, et le refactoring ne doit avoir change
    aucun chiffre.
    """
    b = np.array([0.2311, 0.0609, 0.0234, 0.0244, 0.0035])
    els = ["Ni", "Co", "Cu", "F", "P"]

    ancienne = 1.0 / np.maximum(
        DEFAULT_NOISE.rel_sigma * np.abs(b) + DEFAULT_NOISE.abs_sigma, 1e-5)
    nouvelle = element_weights(b, DEFAULT_NOISE, 1e-5, elements=els)

    assert np.array_equal(ancienne, nouvelle), (
        "les poids par defaut ont change : le refactoring a touche un "
        "chiffre")


def test_un_lot_reste_reproductible_a_la_graine_pres():
    a = solve_lot(make_lot(rng=3, profile="mixed_ev"))
    b = solve_lot(make_lot(rng=3, profile="mixed_ev"))
    assert np.allclose(a.x, b.x)


def test_le_bruit_nul_reste_nul():
    assert NOISE_FREE.rel_sigma_pour(["Ni"]) == 0.0
    assert np.all(NOISE_FREE.sigmas(np.array([0.2, 0.1]), ["Ni", "Co"]) == 0.0)


# ==========================================================================
# 2. La structure sait porter un bruit par element
# ==========================================================================

def test_une_table_donne_un_sigma_par_element():
    modele = _par_element()
    sigmas = modele.rel_sigma_pour(["Ni", "P"])
    assert isinstance(sigmas, np.ndarray)
    assert sigmas[0] == pytest.approx(0.0051)
    assert sigmas[1] == pytest.approx(0.1857)
    assert sigmas[0] < sigmas[1] / 30, (
        "l'ecart nickel/phosphore du certificat doit survivre a la lecture")


def test_un_element_absent_de_la_table_retombe_sur_le_sigma_uniforme():
    """
    Le certificat ne couvre pas les douze elements du modele : l'oxygene et
    l'hydrogene n'y figurent pas. Ils doivent garder le sigma uniforme
    plutot que de recevoir zero, ce qui leur donnerait un poids infini.
    """
    modele = _par_element()
    sigmas = modele.rel_sigma_pour(["Ni", "O", "H"])
    assert sigmas[0] == pytest.approx(0.0051)
    assert sigmas[1] == pytest.approx(modele.rel_sigma)
    assert sigmas[2] == pytest.approx(modele.rel_sigma)


def test_sans_la_liste_d_elements_la_table_est_inoperante():
    """
    Un appelant qui ne dit pas quels elements il manipule ne peut pas
    recevoir un sigma par element : il recoit le scalaire. Mieux vaut un
    bruit uniforme qu'un bruit applique au mauvais element.
    """
    assert _par_element().rel_sigma_pour(None) == pytest.approx(0.06)


def test_le_modele_reste_hashable():
    """
    `NoiseModel` est `frozen`, donc hashable, et `SolverConfig` l'est aussi.
    Un dictionnaire comme champ aurait casse cette propriete - d'ou le tuple
    de paires.
    """
    assert hash(_par_element()) == hash(_par_element())
    assert hash(DEFAULT_NOISE) is not None


# ==========================================================================
# 3. La table est reellement honoree par les trois consommateurs
# ==========================================================================

def test_la_ponderation_du_solveur_honore_la_table():
    b = np.array([0.2311, 0.0035])
    els = ["Ni", "P"]
    uniforme = element_weights(b, DEFAULT_NOISE, 1e-5, elements=els)
    par_el = element_weights(b, _par_element(), 1e-5, elements=els)
    assert par_el[0] > uniforme[0], (
        "le nickel, mieux mesure, doit peser plus")
    assert par_el[1] < uniforme[1], (
        "le phosphore, moins bien mesure, doit peser moins")


def test_le_reechantillonnage_honore_la_table():
    b = np.array([0.2311, 0.0035])
    els = ["Ni", "P"]

    def dispersion(modele):
        rng = np.random.default_rng(11)
        tirages = np.array([resample_bulletin(b, rng, modele, elements=els)
                            for _ in range(600)])
        return tirages.std(axis=0)

    uniforme = dispersion(DEFAULT_NOISE)
    par_el = dispersion(_par_element())
    assert par_el[0] < uniforme[0] / 5, (
        "le nickel devrait etre bien plus serre avec son RSD de 0,51 %")


def test_le_bruitage_du_generateur_honore_la_table():
    """
    Le troisieme consommateur. Sans ce test, une table pourrait etre
    honoree par deux des trois et personne ne le verrait.
    """
    modele = _par_element()
    b_true = np.array([0.23, 0.0035])
    els = ["Ni", "P"]

    ecarts = []
    for liste in (None, els):
        rng = np.random.default_rng(5)
        tirages = np.array([modele.apply(b_true, rng, elements=liste)[0]
                            for _ in range(400)])
        ecarts.append(tirages.std(axis=0))
    uniforme, par_el = ecarts
    assert par_el[0] < uniforme[0] / 5, (
        "`apply` ignore la table : le nickel est bruite comme avant")


def test_la_formule_du_sigma_n_est_plus_recopiee():
    """
    Garde de source. La formule vivait a deux endroits, et un bruit par
    element n'aurait honore que celui des deux qu'on aurait pense a
    modifier - exactement le defaut a trois tetes du bouclage.

    Le test lit la SOURCE : un consommateur fautif passerait tous les tests
    de comportement en apparence, puisqu'au defaut la formule donne le meme
    resultat.
    """
    racine = pathlib.Path(__file__).resolve().parent.parent / "klastos"
    motif = re.compile(r"\.rel_sigma\s*\*\s*np\.abs")
    fautifs = []
    for chemin in sorted(racine.glob("*.py")):
        if chemin.name == "generator.py":
            continue        # le modele a le droit de connaitre sa formule
        for n, ligne in enumerate(
                chemin.read_text(encoding="utf-8").splitlines(), 1):
            if motif.search(ligne):
                fautifs.append(f"{chemin.name}:{n}")
    assert not fautifs, (
        f"ces modules recalculent le sigma au lieu d'appeler "
        f"`NoiseModel.sigmas` : {fautifs}")


# ==========================================================================
# 4. L'enjeu mesure : ce que le resserrement couterait
# ==========================================================================

@pytest.fixture(scope="module")
def valorisations():
    """
    Le lot OREAS value deux fois, avec les deux modeles de bruit.

    Mode demonstration : les conditions commerciales d'exemple datent de
    2024 et sont perimees. C'est une MESURE, pas un rapport client.
    """
    prix = charger_prix("data/prix_client_exemple.csv")
    termes = charger_termes("data/payable_terms.json", "exw_europe")
    base = dict(bulletin=str(BRUT_OREAS), separateur=";",
                provenance="non_declaree", tirages=400, graine=7,
                prix=prix, termes=termes, autoriser_demo=True,
                emis_le=dt.date(2026, 9, 5))
    uniforme = analyser(Demande(**base)).valorisation
    par_el = analyser(Demande(**base, bruit=_par_element())).valorisation
    return uniforme, par_el


def test_le_resserrement_est_massif_et_donc_a_arbitrer(valorisations):
    """
    Le chiffre qui decide si l'enjeu vaut l'investigation : il le vaut.

    Passer de 6 % uniformes aux RSD par element resserre l'intervalle de
    prix maximal de pres de 84 % - de 761 a 121 USD/t de largeur, soit de
    ±9 % a ±1,5 % du milieu. Ce n'est pas un ajustement de detail, c'est un
    changement de ce que l'outil pretend savoir.

    Le test ne verifie pas une valeur exacte - elle depend de la graine et
    des prix d'exemple - mais l'ORDRE DE GRANDEUR. Si le resserrement
    devenait negligeable, la section du protocole serait a reecrire.
    """
    uniforme, par_el = valorisations
    large = uniforme.max_price_high - uniforme.max_price_low
    serre = par_el.max_price_high - par_el.max_price_low

    assert serre < large, "le bruit par element devrait resserrer"
    resserrement = 1.0 - serre / large
    assert resserrement > 0.6, (
        f"resserrement de {100*resserrement:.1f} % seulement : la section "
        f"1.3 bis du protocole annonce un ordre de grandeur plus grand")


def test_le_defaut_reste_le_modele_large(valorisations):
    """
    La garde qui protege du danger nomme par la seance : « Ne resserre rien
    sans que je l'aie valide. » Le modele par defaut doit rester le large.
    """
    uniforme, par_el = valorisations
    assert (uniforme.max_price_high - uniforme.max_price_low) > (
        par_el.max_price_high - par_el.max_price_low), (
        "le defaut s'est mis a produire l'intervalle serre : le bruit a ete "
        "resserre sans arbitrage")


# ==========================================================================
# 5. Le protocole porte l'investigation
# ==========================================================================

@pytest.fixture(scope="module")
def protocole():
    texte = pathlib.Path("PROTOCOLE.md").read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", texte.replace("**", "").replace("`", ""))


def test_le_protocole_expose_la_contradiction(protocole):
    for attendu in ("1.3 bis", "LNE-LiB01", "OREAS", "18,57", "0,51"):
        assert attendu in protocole, f"« {attendu} » absent du protocole"


def test_le_protocole_nomme_les_trois_statistiques(protocole):
    """
    Le livrable de la seance est un texte qui distingue les trois grandeurs.
    Sans elles, la section ne ferait que constater l'ecart.
    """
    for attendu in ("incertitude d'une valeur certifiée", "homogénéité",
                    "reproductibilité interlaboratoires"):
        assert attendu in protocole, f"« {attendu} » absent du protocole"


def test_le_protocole_porte_la_mesure_du_resserrement(protocole):
    assert "84" in protocole
    assert "761" in protocole and "121" in protocole


def test_le_protocole_dit_pourquoi_le_modele_ne_bouge_pas(protocole):
    assert "6 % uniformes" in protocole
    assert "direction" in protocole and "dangereuse" in protocole


def test_le_protocole_deconseille_la_table_oreas(protocole):
    """
    Decision du 23 octobre 2026. La capacite par element existe, et le
    protocole doit dire qu'on ne la remplit PAS avec ce certificat - sinon
    la section se lit comme une invitation a le faire.
    """
    assert "Ne pas adopter la table" in protocole
    assert "extrapole une précision de trace" in protocole
    assert "r = −0,59" in protocole or "−0,59" in protocole


def test_le_protocole_ne_solde_pas_abs_sigma_sur_une_coincidence(protocole):
    """
    J'ai failli recommander de declarer `abs_sigma` source : l'ajustement
    global donne 214 ppm contre 200 ppm au modele. La verification par
    fenetre de concentration a montre que c'etait une coincidence - 3,6 ppm
    sur les traces, 748 ppm sur les majeurs, et l'estimateur direct sur les
    traces vaut 1,9 ppm, soit cent fois moins.

    Le protocole doit porter ce demenagement, et `abs_sigma` rester a
    valider.
    """
    assert "coïncidence" in protocole
    assert "1,9 ppm" in protocole
    debut = protocole.index("1.3 Paramètres analytiques")
    fin = protocole.index("1.3 bis")
    assert "abs_sigma | 0,02 % massique | à valider" in protocole[debut:fin]


def test_le_protocole_ne_pretend_plus_que_tout_est_non_valide(protocole):
    """
    Divergence doc/code corrigee au passage. La section 1.3 annoncait
    `validated=False` pour l'ensemble du modele de bruit, alors que le code
    porte `validated=True` depuis que `rel_sigma` est source sur LNE-LiB01.
    Deux des trois parametres restent a valider, et le tableau le dit.
    """
    assert DEFAULT_NOISE.validated is True

    debut = protocole.index("1.3 Paramètres analytiques")
    fin = protocole.index("1.3 bis")
    section = protocole[debut:fin]

    # L'assertion ne porte PAS sur l'absence de « validated=False » : la
    # section cite cette valeur pour raconter l'erreur corrigee, et c'est
    # le style du depot. Ce qui compte est qu'elle affirme l'etat COURANT
    # et qu'elle distingue les trois parametres.
    assert "validated=True" in section, (
        "la section doit dire que le modele porte validated=True")
    assert "sourcé — LNE-LiB01" in section, (
        "rel_sigma doit y etre declare source")
    assert section.count("à valider") == 2, (
        f"deux parametres restent a valider, la section en annonce "
        f"{section.count('à valider')}")
    assert "rel_sigma" in section and "abs_sigma" in section \
        and "lod" in section
