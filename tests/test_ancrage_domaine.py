"""
LE DOMAINE COMPATIBLE NE DOIT PAS DEPENDRE DE SON ANCRAGE.

POURQUOI CE FICHIER EXISTE
--------------------------
`compatible_bounds` parametre le domaine relativement a un representant
x0 : l'ensemble des solutions s'ecrit `{ x0 + N t >= 0 }`. Ce
parametrage est legitime - c'est un systeme de coordonnees - mais le
PLAFOND DE MASSE y entrait par la mauvaise porte.

Les phases ne peuvent pas peser plus que l'echantillon, d'ou un plafond
a 1. Seulement, le representant retenu par le solveur peut depasser 1 :
c'est le sur-bouclage, que le rapport signale par ailleurs. Un plafond
strict aurait alors exclu le point de depart lui-meme, et le code le
relevait donc a `max(1, somme(x0))`.

Consequence : le domaine PUBLIE dependait du sommet ou NNLS avait
atterri. Mesure sur deux representants egalement valides du meme
bulletin - tous deux ajustent exactement, tous deux positifs :

    somme 101,3833 %   « Cathodes totales » [40,000 ; 43,116]  3,116 pt
    somme 100,0000 %   « Cathodes totales » [40,000 ; 40,000]  0,000 pt

Meme analyse, deux reponses. Le domaine le plus large etait un ARTEFACT :
il admettait des compositions pesant plus que l'echantillon, uniquement
parce que le representant de depart pesait davantage.

LE CORRECTIF, ET CELUI QUI A ETE ESSAYE PUIS ABANDONNE
------------------------------------------------------
Premiere tentative : relever le plafond a la masse MINIMALE atteignable,
propriete de l'ensemble affine et non d'un de ses points. L'invariance
etait acquise, mais au prix d'un plafond DUR a 1. Combine a un
ajustement exact, il sur-determine le systeme : le domaine se reduit a
un point sur tout lot qui boucle bien, et les scenarios de conseil
deviennent infaisables. Mesure, puis abandonne.

Retenu : RETIRER le plafond de la famille ancree. La contrainte physique
n'a pas disparu - elle est portee par le polytope robuste, qui produit
l'intervalle publie et n'a aucun ancrage. Ici, ou l'on decrit
l'indetermination a bulletin donne, la retirer rend le domaine invariant
SANS le degenerer.

Et le correctif ne change aucun chiffre publie : sur l'ancrage courant,
le plafond relache n'etait de toute facon pas contraignant. Ce qui
disparait, c'est le cas pathologique - un ancrage qui atterrit sur le
bord et annonce 0,000 point de large.

CE QUE CES TESTS GARDENT
------------------------
  1. l'INVARIANCE, qui est la propriete pour laquelle on a change ;
  2. que le plafond n'exclue jamais l'ensemble des solutions ;
  3. que l'intervalle PUBLIE n'ait pas bouge - il vient du polytope
     robuste, deja sans ancrage, et ce correctif ne doit pas l'effleurer.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.optimize import linprog

from klastos.elements import ATOMIC_MASS, ELEMENTS, formula_mass
from klastos.identifiability import (compatible_bounds, null_space,
                                     standard_functionals)
from klastos.phases import PHASES, cathode_indicator, stoichiometry_matrix
from klastos.solver import SolverConfig, solve

DOSES = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F"]
LOT = {"NMC811": .40, "C_total": .33, "Cu_metal": .10, "Al_metal": .07,
       "PVDF": .05, "LiPF6": .03, "Fe_metal": .02}
LOURD = {"LCO": .45, "C_total": .30, "Cu_metal": .12, "Al_metal": .06,
         "PVDF": .04, "LiPF6": .02, "Fe_metal": .01}


def vecteur(melange):
    b = {el: 0.0 for el in ELEMENTS}
    for ph, fr in melange.items():
        comp = PHASES[ph]["composition"]
        M = formula_mass(comp)
        for el, n in comp.items():
            b[el] += fr * ATOMIC_MASS[el] * n / M
    return np.array([b[el] for el in DOSES])


def pieces(melange=LOT):
    v = vecteur(melange)
    A, els, cles = stoichiometry_matrix(elements=DOSES)
    r = solve({el: v[i] * 100 for i, el in enumerate(DOSES)},
              elements=DOSES, config=SolverConfig())
    return A, null_space(A), cles, r.x, v


def ancres(x0, N, combien=4, graine=3):
    """
    Plusieurs representants du MEME ensemble affine.

    Chacun ajuste le bulletin aussi exactement que l'original, puisque
    `A @ (N t) = 0`. Ils sont obtenus par PROGRAMMATION LINEAIRE, dans
    des directions tirees au hasard, et non en poussant x0 au hasard :
    avec sept phases a zero sur quatorze, presque toute poussee en rend
    une negative, et la boucle ne se termine jamais. Le defaut a ete
    trouve en laissant ce fichier tourner dix minutes.
    """
    rng = np.random.default_rng(graine)
    k = N.shape[1]
    out = [x0]
    for _ in range(combien * 4):
        if len(out) >= combien:
            break
        direction = rng.normal(0.0, 1.0, k)
        r = linprog(direction, A_ub=-N, b_ub=x0,
                    bounds=[(-10.0, 10.0)] * k, method="highs")
        if not r.success:
            continue
        cand = x0 + N @ r.x
        if (cand >= -1e-9).all():
            out.append(np.maximum(cand, 0.0))
    assert len(out) >= 2, "aucun ancrage alternatif trouve"
    return out


# ==========================================================================
# 1. L'invariance, raison d'etre du correctif
# ==========================================================================

def test_le_domaine_ne_depend_plus_du_representant_choisi():
    """
    LA PROPRIETE POUR LAQUELLE ON A CHANGE.

    Quatre ancrages du meme ensemble affine doivent rendre exactement le
    meme domaine. Avant, deux d'entre eux donnaient 3,116 et 0,000 point
    de large pour la meme grandeur.
    """
    A, N, cles, x0, _ = pieces()
    cath = cathode_indicator(cles)
    bornes = [compatible_bounds(x, N, cath) for x in ancres(x0, N)]
    for i, (lo, hi) in enumerate(bornes[1:], start=1):
        assert (lo, hi) == pytest.approx(bornes[0], abs=1e-7), (
            f"ancrage {i} : domaine [{lo*100:.3f} ; {hi*100:.3f}] contre "
            f"[{bornes[0][0]*100:.3f} ; {bornes[0][1]*100:.3f}] pour le "
            f"premier. Le domaine depend de nouveau de son ancrage.")


def test_l_invariance_vaut_pour_toutes_les_grandeurs_du_rapport():
    """
    Une invariance verifiee sur une seule grandeur ne prouve rien : le
    plafond pourrait n'affecter que certaines directions.
    """
    A, N, cles, x0, _ = pieces()
    autres = ancres(x0, N, combien=3)
    for f in standard_functionals(cles, elements=DOSES):
        ref = compatible_bounds(x0, N, f.c)
        for x in autres[1:]:
            assert compatible_bounds(x, N, f.c) == pytest.approx(
                ref, abs=1e-7), f.key


# ==========================================================================
# 2. Le plafond n'exclut jamais l'ensemble des solutions
# ==========================================================================

@pytest.mark.parametrize("melange", [LOT, LOURD], ids=["NMC811", "LCO"])
def test_le_domaine_reste_calculable_quel_que_soit_le_bouclage(melange):
    """
    Un lot qui sur-boucle ne doit pas rendre le domaine infaisable. Le
    plafond se releve alors jusqu'a la masse minimale atteignable, ce
    qui le garde tenable sans le rendre dependant de l'ancrage.
    """
    A, N, cles, x0, _ = pieces(melange)
    for f in standard_functionals(cles, elements=DOSES):
        lo, hi = compatible_bounds(x0, N, f.c)
        assert lo <= hi + 1e-9, f.key


def test_le_plafond_physique_vit_desormais_dans_le_polytope_robuste():
    """
    La contrainte « les phases ne pesent pas plus que l'echantillon » n'a
    pas disparu : elle est posee la ou elle n'a pas d'ancrage, donc la ou
    elle ne peut pas rendre le domaine dependant d'un representant.

    Ce test garde la repartition des roles. Si le plafond revenait par
    defaut dans la famille ancree, la dependance a l'ancrage reviendrait
    avec lui.
    """
    import inspect
    from klastos import identifiability as I

    for fonc in ("compatible_bounds", "conditional_bounds"):
        defaut = inspect.signature(
            getattr(I, fonc)).parameters["total_mass_cap"].default
        assert defaut is None, (
            f"{fonc} replafonne par defaut : la dependance a l'ancrage "
            f"revient avec le plafond")

    for fonc in ("contraintes_robustes", "bornes_robustes", "rayon_minimal"):
        defaut = inspect.signature(
            getattr(I, fonc)).parameters["total_mass_cap"].default
        assert defaut == 1.0, (
            f"{fonc} a perdu le plafond physique : l'intervalle publie "
            f"admettrait des compositions plus lourdes que l'echantillon")


# ==========================================================================
# 3. Ce que ce correctif ne doit PAS toucher
# ==========================================================================

def test_l_intervalle_publie_ne_depend_pas_de_ce_plafond():
    """
    `total_lower` et `total_upper` viennent du polytope robuste, qui n'a
    aucun ancrage. Ce correctif porte sur la DECOMPOSITION affichee -
    la part structurelle - et ne doit pas effleurer le chiffre qui part
    chez le client.

    Valeurs relevees avant le correctif, sur le lot d'essai.
    """
    from klastos.uncertainty import UncertaintyConfig, propagate
    v = vecteur(LOT)
    r = propagate({el: v[i] * 100 for i, el in enumerate(DOSES)},
                  elements=DOSES,
                  config=UncertaintyConfig(seed=1, n_draws=200))
    attendu = {
        "cathodes_totales": 16.556,
        "nmc_lco": 39.123,
        "C_total": 13.653,
        "PVDF": 7.568,
        "LiPF6": 3.712,
    }
    for cle, largeur in attendu.items():
        obtenu = r.by_key()[cle].total_width * 100
        assert obtenu == pytest.approx(largeur, abs=0.01), (
            f"{cle} : l'intervalle publie fait {obtenu:.3f} pt contre "
            f"{largeur:.3f} avant le correctif. Ce correctif ne devait "
            f"toucher que la part structurelle.")


def test_la_part_structurelle_n_a_pas_bouge_sur_l_ancrage_courant():
    """
    Le correctif ne devait changer AUCUN chiffre publie, et c'est
    verifiable : sur l'ancrage que le solveur retient, l'ancien plafond
    relache n'etait de toute facon pas contraignant. Valeurs relevees
    avant le correctif.

    Ce qui disparait est ailleurs : un ancrage qui atterrissait sur le
    bord annoncait 0,000 point de large pour les memes grandeurs.
    """
    from klastos.uncertainty import UncertaintyConfig, propagate
    v = vecteur(LOT)
    r = propagate({el: v[i] * 100 for i, el in enumerate(DOSES)},
                  elements=DOSES,
                  config=UncertaintyConfig(seed=1, n_draws=200))
    par = r.by_key()
    attendu = {"cathodes_totales": 3.029, "LFP": 3.021, "C_total": 1.380,
               "PVDF": 3.679, "LiPF6": 2.909, "Fe_metal": 1.070}
    for cle, largeur in attendu.items():
        obtenu = par[cle].struct_width * 100
        assert obtenu == pytest.approx(largeur, abs=0.01), (
            f"{cle} : part structurelle {obtenu:.3f} pt contre "
            f"{largeur:.3f} avant le correctif")
