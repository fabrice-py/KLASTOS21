"""
L'ERREUR DE MODELE DANS L'INTERVALLE PUBLIE.

POURQUOI CE FICHIER EXISTE
--------------------------
`propagate` assemblait deux incertitudes : la dispersion analytique et le
domaine compatible. Les deux sont CONDITIONNELLES a une hypothese que rien
ne verifiait - que les quatorze phases du modele sont les bonnes.

Quand elles ne le sont pas, l'intervalle publie excluait la valeur vraie.
Mesure sur bulletins synthetiques PARFAITS, avant correctif :

    8 % de NiO hors modele    Ni vrai 21,73 %   publie 15,47 - 17,69
    10 % de Li2CO3            Li vrai  4,16 %   publie  2,29 -  2,58

Un outil dont la fourchette exclut la verite est pire qu'un outil absent :
il vend une confiance qui n'existe pas.

LE CORRECTIF, ET POURQUOI IL N'A PAS DE PARAMETRE
-------------------------------------------------
La grandeur publiee pour un element est la teneur RECONSTRUITE, (A @ x).
Le laboratoire, lui, a rendu un DOSAGE. L'ecart entre les deux est
exactement le residu sur cet element : l'erreur de modele se MESURE, elle
n'a pas a etre postulee. L'intervalle reunit donc les deux distributions.

Un facteur d'elargissement arbitraire aurait demande un arbitrage, puis
aurait derive. Celui-ci ne peut pas deriver : il n'a rien a regler.

EFFET DE BORD, ET C'EST UNE CORRECTION
--------------------------------------
Meme lorsque le modele est juste, l'intervalle s'elargit un peu. Ce n'est
pas un cout, c'est une fausse precision qui disparait : la deconvolution
agit comme un filtre, et elle rendait sur le lithium un intervalle PLUS
ETROIT que l'incertitude du laboratoire. Un contrat de raffinage paie sur
le dosage ; annoncer mieux que le bulletin n'est pas defendable.
"""

from __future__ import annotations

import numpy as np
import pytest

from klastos.elements import ATOMIC_MASS, ELEMENTS, formula_mass
from klastos.generator import DEFAULT_NOISE
from klastos.phases import PHASES
from klastos.uncertainty import UncertaintyConfig, propagate

HORS_MODELE = {
    "Li2CO3": {"Li": 2.0, "C": 1.0, "O": 3.0},
    "NMC811_delithie": {"Li": 0.75, "Ni": 0.8, "Mn": 0.1, "Co": 0.1, "O": 2.0},
    "NiO": {"Ni": 1.0, "O": 1.0},
}
DOSES = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F"]
SAIN = {"NMC811": 0.40, "C_total": 0.33, "Cu_metal": 0.10, "Al_metal": 0.07,
        "PVDF": 0.05, "LiPF6": 0.03, "Fe_metal": 0.02}

#: Peu de tirages : ces tests mesurent une COUVERTURE, pas une precision
#: de percentile. Les bornes bougent de quelques millemes entre 60 et 400
#: tirages, et les ecarts qu'on teste se comptent en points.
CONFIG = UncertaintyConfig(seed=20261103, n_draws=120, n_bound_draws=20)


def bulletin(melange: dict[str, float]) -> dict[str, float]:
    b = {el: 0.0 for el in ELEMENTS}
    for nom, frac in melange.items():
        comp = (PHASES[nom]["composition"] if nom in PHASES
                else HORS_MODELE[nom])
        M = formula_mass(comp)
        for el, n in comp.items():
            b[el] += frac * ATOMIC_MASS[el] * n / M
    return {el: v * 100.0 for el, v in b.items()}


def rapport(melange):
    b = bulletin(melange)
    return propagate({el: b[el] for el in DOSES}, elements=DOSES,
                     config=CONFIG)


def avec(phase: str, part: float) -> dict:
    m = dict(SAIN)
    m["NMC811"] = round(m["NMC811"] - part, 10)
    m[phase] = part
    assert abs(sum(m.values()) - 1.0) < 1e-9
    return m


DELITHIEE = {**{k: v for k, v in SAIN.items() if k != "NMC811"},
             "NMC811_delithie": 0.40}


# ==========================================================================
# 1. La couverture, qui est la seule chose qui compte
# ==========================================================================

CAS_COUVERTURE = [
    ("modele juste", SAIN, "Li"),
    ("modele juste", SAIN, "Ni"),
    ("3 % de Li2CO3", avec("Li2CO3", 0.03), "Li"),
    ("5 % de Li2CO3", avec("Li2CO3", 0.05), "Li"),
    ("10 % de Li2CO3", avec("Li2CO3", 0.10), "Li"),
    ("10 % de Li2CO3", avec("Li2CO3", 0.10), "Ni"),
    ("8 % de NiO", avec("NiO", 0.08), "Ni"),
    ("8 % de NiO", avec("NiO", 0.08), "Co"),
    ("cathode delithiee", DELITHIEE, "Li"),
    ("cathode delithiee", DELITHIEE, "Ni"),
]


@pytest.mark.parametrize("titre, melange, element",
                         CAS_COUVERTURE,
                         ids=[f"{t}-{e}" for t, _, e in CAS_COUVERTURE])
def test_l_intervalle_publie_contient_la_teneur_vraie(titre, melange, element):
    """
    Le bulletin est PARFAIT : aucun bruit analytique. La teneur vraie est
    donc exactement la teneur dosee, et toute exclusion ne peut venir que
    du modele.
    """
    r = rapport(melange).by_key()[f"el_{element}"]
    vrai = bulletin(melange)[element] / 100.0
    assert r.total_lower <= vrai <= r.total_upper, (
        f"{titre} : {element} vrai a {vrai*100:.3f} %, publie "
        f"[{r.total_lower*100:.3f} ; {r.total_upper*100:.3f}] - "
        f"la verite est hors de l'intervalle")


# ==========================================================================
# 2. Le mecanisme : ni magique, ni gratuit
# ==========================================================================

@pytest.mark.parametrize("element", ["Li", "Ni", "Co", "Cu"])
def test_chaque_teneur_elementaire_porte_son_dosage(element):
    """
    Les deux bornes du dosage sont la DONNEE du correctif. Sans elles,
    l'elargissement serait opaque et le rapport ne pourrait pas montrer
    les deux colonnes cote a cote.
    """
    r = rapport(SAIN).by_key()[f"el_{element}"]
    assert r.assay_lower is not None, f"el_{element} : dosage absent"
    assert r.assay_upper is not None
    assert r.assay_lower < r.assay_upper


def test_les_grandeurs_non_elementaires_n_ont_pas_de_dosage():
    """
    Une phase ou un agregat n'est pas mesure par le laboratoire : il n'y
    a pas de dosage a lui opposer. Pretendre le contraire reviendrait a
    fabriquer une mesure.
    """
    par_cle = rapport(SAIN).by_key()
    for cle in ("cathodes_totales", "C_total", "Cu_metal"):
        if cle not in par_cle:
            continue
        r = par_cle[cle]
        assert r.assay_lower is None, f"{cle} porte un dosage inexistant"
        assert r.assay_upper is None


@pytest.mark.parametrize("element", ["Li", "Ni", "Co", "Cu"])
def test_l_intervalle_publie_contient_toujours_celui_du_laboratoire(element):
    """
    LE PLANCHER D'HONNETETE.

    KLASTOS21 ne peut pas annoncer sur un element une precision que le
    bulletin ne porte pas. Avant correctif il le faisait : la
    deconvolution agit comme un filtre, et l'intervalle publie sur le
    lithium etait PLUS ETROIT que la bande analytique du laboratoire.
    """
    r = rapport(SAIN).by_key()[f"el_{element}"]
    assert r.total_lower <= r.assay_lower, (
        f"el_{element} : borne basse publiee ({r.total_lower*100:.3f}) "
        f"au-dessus de celle du laboratoire ({r.assay_lower*100:.3f})")
    assert r.total_upper >= r.assay_upper, (
        f"el_{element} : borne haute publiee ({r.total_upper*100:.3f}) "
        f"sous celle du laboratoire ({r.assay_upper*100:.3f})")


def test_une_phase_manquante_elargit_l_intervalle():
    """
    Le pendant du test precedent. Si la reunion n'elargissait jamais
    rien, les tests de couverture pourraient passer par hasard, sur un
    intervalle deja large.
    """
    sain = rapport(SAIN).by_key()["el_Li"]
    casse = rapport(avec("Li2CO3", 0.10)).by_key()["el_Li"]
    largeur_saine = sain.total_upper - sain.total_lower
    largeur_cassee = casse.total_upper - casse.total_lower
    assert largeur_cassee > largeur_saine * 1.5, (
        f"une phase manquante a 10 % n'elargit presque pas : "
        f"{largeur_saine*100:.3f} -> {largeur_cassee*100:.3f} pt")


def test_le_surcout_reste_mesure_quand_le_modele_est_juste():
    """
    L'elargissement doit etre le PLANCHER du laboratoire, pas une marge
    de securite deguisee. Sur un lot sain, l'intervalle publie ne doit
    pas s'eloigner beaucoup de la bande analytique.
    """
    for element in ("Li", "Ni", "Co"):
        r = rapport(SAIN).by_key()[f"el_{element}"]
        publie = r.total_upper - r.total_lower
        labo = r.assay_upper - r.assay_lower
        assert publie <= labo * 2.0, (
            f"el_{element} : intervalle publie {publie*100:.3f} pt contre "
            f"{labo*100:.3f} pt au laboratoire, soit un facteur "
            f"{publie/labo:.2f}. Le terme d'erreur de modele s'est "
            f"transforme en marge de securite.")
