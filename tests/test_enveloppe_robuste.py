"""
L'ENVELOPPE DES GRANDEURS NON IDENTIFIABLES.

POURQUOI CE FICHIER EXISTE
--------------------------
L'enveloppe publiee etait l'UNION, sur une soixantaine de tirages du
bulletin, des domaines compatibles de chaque tirage. Deux defauts
mesures :

  - ELLE NE CONVERGEAIT PAS. De 120 a 240 tirages, la largeur mediane
    croissait encore de 10,5 % et la pire de 120 %. Au reglage de 60,
    certaines grandeurs etaient jusqu'a 20 % TROP ETROITES. Le chiffre
    publie dependait donc d'un reglage, et la docstring promettait une
    garantie qui n'existait pas.

  - ELLE COUTAIT L'ESSENTIEL DU TEMPS : deux programmes lineaires par
    grandeur ET par tirage, pres de 1 800 pour un lot.

Un min/max sur echantillon n'est pas un estimateur stable. Ce module le
documentait deja pour les grandeurs fermes, qui retiennent un percentile
pour cette raison exacte.

LA METHODE RETENUE
------------------
Un seul polytope, sans aucun tirage :

    { x : x >= 0, somme(x) <= 1, | W (A x - b) | <= k }

« tous les melanges dont le bulletin predit tombe a moins de k
ecarts-types de celui qu'on a mesure ». Exact, reproductible, deux
programmes lineaires par grandeur en tout.

CE QUE CES TESTS GARDENT
------------------------
  1. la REPRODUCTIBILITE, qui est la propriete pour laquelle on a
     change de methode : deux graines doivent donner le meme chiffre ;
  2. le rayon CALCULE et non code en dur, car il depend du nombre
     d'elements doses ;
  3. le traitement du polytope VIDE, qui est un resultat et non une
     panne.
"""

from __future__ import annotations

import numpy as np
import pytest

from klastos.elements import ATOMIC_MASS, ELEMENTS, formula_mass
from klastos.generator import DEFAULT_NOISE
from klastos.identifiability import (UnboundedCompatibleSet, bornes_robustes,
                                     rayon_minimal, rayon_robuste)
from klastos.phases import (PHASES, cathode_indicator, indicator,
                            stoichiometry_matrix)
from klastos.uncertainty import UncertaintyConfig, propagate

DOSES = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F"]
SAIN = {"NMC811": 0.40, "C_total": 0.33, "Cu_metal": 0.10, "Al_metal": 0.07,
        "PVDF": 0.05, "LiPF6": 0.03, "Fe_metal": 0.02}
HORS_MODELE = {
    "Li2CO3": {"Li": 2.0, "C": 1.0, "O": 3.0},
    "NiO": {"Ni": 1.0, "O": 1.0},
}


def bulletin(melange, doses=DOSES):
    b = {el: 0.0 for el in ELEMENTS}
    for nom, frac in melange.items():
        comp = (PHASES[nom]["composition"] if nom in PHASES
                else HORS_MODELE[nom])
        M = formula_mass(comp)
        for el, n in comp.items():
            b[el] += frac * ATOMIC_MASS[el] * n / M
    return np.array([b[el] for el in doses])


def avec(phase, part):
    m = dict(SAIN)
    m["NMC811"] = round(m["NMC811"] - part, 10)
    m[phase] = part
    return m


def pieces(melange, doses=DOSES):
    b = bulletin(melange, doses)
    A, els, cles = stoichiometry_matrix(elements=doses)
    sigma = np.maximum(DEFAULT_NOISE.sigmas(b, doses), 1e-5)
    return A, b, sigma, cles


# ==========================================================================
# 1. La reproductibilite, raison d'etre du changement
# ==========================================================================

def test_deux_graines_donnent_exactement_la_meme_enveloppe():
    """
    LA PROPRIETE POUR LAQUELLE ON A CHANGE DE METHODE.

    L'ancienne enveloppe etait un min/max sur tirages : elle dependait
    de la graine et du nombre de tirages. Deux analyses du meme bulletin
    ne donnaient pas le meme chiffre, et un client qui relancait
    obtenait une fourchette differente.
    """
    b = bulletin(SAIN)
    bd = {el: b[i] * 100 for i, el in enumerate(DOSES)}
    sorties = []
    for graine in (1, 999):
        r = propagate(bd, elements=DOSES,
                      config=UncertaintyConfig(seed=graine, n_draws=60))
        sorties.append({x.key: (x.total_lower, x.total_upper)
                        for x in r.results if not x.identifiable})
    a, z = sorties
    assert set(a) == set(z)
    for cle in a:
        assert a[cle] == pytest.approx(z[cle], abs=1e-12), (
            f"{cle} : l'enveloppe depend encore de la graine, "
            f"{a[cle]} contre {z[cle]}")


@pytest.mark.parametrize("n_bound", [5, 20, 60])
def test_l_enveloppe_ne_depend_plus_du_nombre_de_tirages(n_bound):
    """
    Le corollaire. `n_bound_draws` ne pilote plus que la decomposition
    entre incertitude analytique et structurelle ; l'enveloppe publiee
    doit etre insensible a ce reglage.
    """
    b = bulletin(SAIN)
    bd = {el: b[i] * 100 for i, el in enumerate(DOSES)}
    ref = propagate(bd, elements=DOSES,
                    config=UncertaintyConfig(seed=3, n_draws=60,
                                             n_bound_draws=20))
    autre = propagate(bd, elements=DOSES,
                      config=UncertaintyConfig(seed=3, n_draws=60,
                                               n_bound_draws=n_bound))
    a = {x.key: (x.total_lower, x.total_upper)
         for x in ref.results if not x.identifiable}
    z = {x.key: (x.total_lower, x.total_upper)
         for x in autre.results if not x.identifiable}
    for cle in a:
        assert a[cle] == pytest.approx(z[cle], abs=1e-12), cle


# ==========================================================================
# 2. Le rayon est calcule, jamais code en dur
# ==========================================================================

def test_le_rayon_depend_du_nombre_d_elements_doses():
    """
    Une boite a 90 % par element couvrirait 0,9^10 = 35 % conjointement
    sur dix elements. Le rayon resout donc pour la couverture CONJOINTE,
    et il grandit avec le nombre d'elements. Figer une constante rendrait
    le bulletin a douze elements trop optimiste.
    """
    dix, douze = rayon_robuste(10), rayon_robuste(12)
    assert dix == pytest.approx(2.56, abs=0.01)
    assert douze == pytest.approx(2.62, abs=0.01)
    assert douze > dix


def test_une_couverture_plus_exigeante_elargit_le_rayon():
    assert rayon_robuste(10, 0.99) > rayon_robuste(10, 0.90)


@pytest.mark.parametrize("n, couverture", [(0, 0.9), (-1, 0.9),
                                           (10, 0.0), (10, 1.0)])
def test_les_entrees_absurdes_echouent_fort(n, couverture):
    with pytest.raises(ValueError):
        rayon_robuste(n, couverture)


# ==========================================================================
# 3. Le polytope vide est un resultat, pas une panne
# ==========================================================================

def test_le_rayon_minimal_vaut_zero_quand_le_modele_explique_tout():
    """Bulletin parfait, toutes les phases au modele : il existe un
    melange qui reproduit le bulletin EXACTEMENT."""
    A, b, sigma, _ = pieces(SAIN)
    assert rayon_minimal(A, b, sigma) == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize("phase, part, mini", [
    ("Li2CO3", 0.03, 1.0),    # explique, mais plus tout a fait exactement
    ("Li2CO3", 0.10, 3.5),    # hors d'atteinte du rayon vise
    ("NiO", 0.08, 2.0),
])
def test_le_rayon_minimal_mesure_l_inadequation_du_modele(phase, part, mini):
    """
    Il se lit comme une phrase : « il a fallu admettre X ecarts-types
    d'erreur analytique pour que le modele explique ce bulletin ». Plus
    la phase manquante pese, plus X grandit.
    """
    A, b, sigma, _ = pieces(avec(phase, part))
    k = rayon_minimal(A, b, sigma)
    assert k >= mini, (
        f"{part*100:.0f} % de {phase} hors modele : rayon minimal {k:.2f}, "
        f"au moins {mini} attendu")


def test_un_polytope_vide_n_interrompt_pas_l_analyse():
    """
    Un lot que le modele n'explique pas doit rester ANALYSABLE : le
    rapport doit pouvoir refuser proprement en nommant son remede, et un
    operateur doit pouvoir regarder pourquoi. Une exception au milieu de
    `propagate` priverait des deux.
    """
    b = bulletin(avec("Li2CO3", 0.10))
    bd = {el: b[i] * 100 for i, el in enumerate(DOSES)}
    r = propagate(bd, elements=DOSES,
                  config=UncertaintyConfig(seed=1, n_draws=40))
    assert r.meta["rayon_minimal"] > r.meta["rayon_vise"], (
        "ce lot devrait exiger un rayon superieur au rayon vise")
    ouvertes = [x for x in r.results if not x.identifiable]
    assert ouvertes, "aucune grandeur ouverte : l'enveloppe n'a rien produit"
    for x in ouvertes:
        assert x.total_lower <= x.total_upper


def test_les_deux_rayons_voyagent_dans_le_rapport():
    """Le rayon visé et celui qu'il a fallu. Leur écart EST le
    diagnostic ; le ranger sans le transmettre le rendrait inutile."""
    b = bulletin(SAIN)
    bd = {el: b[i] * 100 for i, el in enumerate(DOSES)}
    r = propagate(bd, elements=DOSES,
                  config=UncertaintyConfig(seed=1, n_draws=40))
    assert r.meta["rayon_vise"] == pytest.approx(rayon_robuste(len(DOSES)))
    assert r.meta["rayon_minimal"] == pytest.approx(0.0, abs=1e-6)


# ==========================================================================
# 4. Le polytope dit bien ce qu'il prétend dire
# ==========================================================================

def test_un_rayon_plus_large_ne_retrecit_jamais_les_bornes():
    """
    Monotonie : admettre plus d'erreur analytique ne peut qu'agrandir
    l'ensemble des melanges compatibles. Une inversion signalerait une
    erreur de signe dans les inegalites.
    """
    A, b, sigma, cles = pieces(SAIN)
    c = cathode_indicator(cles)
    precedent = None
    for k in (0.5, 1.0, 2.56, 4.0):
        lo, hi = bornes_robustes(A, b, sigma, c, k=k)
        if precedent is not None:
            assert lo <= precedent[0] + 1e-9, f"k={k} : borne basse remontee"
            assert hi >= precedent[1] - 1e-9, f"k={k} : borne haute descendue"
        precedent = (lo, hi)


def test_le_plafond_de_masse_borne_une_phase_que_rien_d_autre_ne_borne():
    """
    CE TEST A ETE REECRIT APRES UNE MUTATION QUI N'A PAS MORDU.

    Il portait sur un bulletin a dix elements et verifiait que la borne
    haute des cathodes reste sous 100 %. Retirer le plafond ne changeait
    rien, et pour une raison qui n'a rien d'un hasard : avec dix
    elements doses, CHAQUE phase du modele en contient au moins un, donc
    les inegalites du polytope la bornent deja. Le test etait vide.

    Le plafond devient necessaire des qu'un bulletin pauvre laisse une
    phase sans aucun element dose. Avec Li et Ni seuls, le cuivre
    metallique n'apparait dans aucune equation : rien ne l'empeche de
    partir a l'infini. C'est ce cas-la qu'il faut garder.
    """
    doses = ["Li", "Ni"]
    A, b, sigma, cles = pieces(SAIN, doses)
    cuivre = indicator(["Cu_metal"], phase_keys=cles)

    avec_plafond = bornes_robustes(A, b, sigma, cuivre, k=2.0,
                                   total_mass_cap=1.0)
    assert avec_plafond[1] <= 1.0 + 1e-9, (
        "le plafond de masse n'est pas applique")

    with pytest.raises(UnboundedCompatibleSet):
        bornes_robustes(A, b, sigma, cuivre, k=2.0, total_mass_cap=None)


def test_aucune_fraction_de_phase_negative_n_est_admise():
    """Une phase ne peut pas peser moins que rien. La borne basse d'un
    indicateur de phase est donc toujours positive ou nulle."""
    A, b, sigma, cles = pieces(SAIN)
    for phase in ("C_total", "Cu_metal", "LFP"):
        lo, _ = bornes_robustes(A, b, sigma,
                                indicator([phase], phase_keys=cles),
                                k=rayon_robuste(len(DOSES)))
        assert lo >= -1e-9, f"{phase} : fraction negative admise ({lo})"


def test_le_polytope_contient_la_solution_centrale():
    """
    Garde-fou elementaire : le melange que le solveur retient pour le
    bulletin tel quel doit appartenir au domaine. S'il n'y est pas, les
    inegalites ne decrivent pas ce qu'on croit.
    """
    from klastos.solver import solve, SolverConfig
    A, b, sigma, cles = pieces(SAIN)
    r = solve({el: b[i] * 100 for i, el in enumerate(DOSES)},
              elements=DOSES, config=SolverConfig())
    c = cathode_indicator(cles)
    lo, hi = bornes_robustes(A, b, sigma, c, k=rayon_robuste(len(DOSES)))
    valeur = float(c @ r.x)
    assert lo - 1e-9 <= valeur <= hi + 1e-9, (
        f"la solution centrale donne {valeur*100:.2f} %, hors du domaine "
        f"[{lo*100:.2f} ; {hi*100:.2f}]")
