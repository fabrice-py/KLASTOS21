"""
LE CHOIX DU REPRESENTANT, ET LA FIN DE `lambda_null`.

POURQUOI CE FICHIER EXISTE
--------------------------
Le solveur exprimait le prior comme une penalite ajoutee au moindre
carre, ponderee par `lambda_null`, dont le commentaire annoncait « une
valeur trop faible rend le representant instable, une valeur trop forte
le tire vers le prior ». Cet arbitrage n'existe pas.

Le bloc de penalite est EXACTEMENT orthogonal au bloc de donnees -
mesure : ||A . P_N|| = 5e-16. Sans contrainte de positivite le probleme
se separe, et n'importe quelle valeur positive donnerait le meme
resultat. Avec x >= 0, le poids des donnees vaut 1/sigma, soit 47 a
1764, contre sqrt(lambda) = 0,01 : cinq ordres de grandeur d'ecart.

Consequence mesuree sur le prior, que la penalite etait censee servir :

    lot de test, douze elements doses   prior deplace de 12,99 points
    bulletin reel, dix elements doses   prior deplace de  0,00 point

Le parametre n'etait donc pas inerte : il etait SILENCIEUSEMENT
INOPERANT sur les lots reels et operant sur ceux des tests. C'est pire
qu'une panne franche - les tests le declaraient vivant.

CE QUE CES TESTS GARDENT
------------------------
  1. que le prior soit HONORE, sur un lot reel et pas seulement sur le
     lot degenere des tests d'origine ;
  2. que l'honorer ne touche NI l'ajustement NI aucune grandeur
     identifiable ;
  3. que le chemin par defaut n'ait pas bouge d'un bit ;
  4. que `DEPARTAGE_NUMERIQUE` reste en place, parce que son retrait
     fait s'effondrer le domaine compatible - c'est son vrai role, et il
     n'a jamais eu l'autre.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest
from scipy.optimize import nnls

from klastos.elements import ATOMIC_MASS, ELEMENTS, formula_mass
from klastos.identifiability import (compatible_bounds, null_space,
                                     representant_proche)
from klastos.generator import DEFAULT_NOISE
from klastos.phases import (PHASES, PHASE_KEYS, cathode_indicator, indicator,
                            stoichiometry_matrix)
from klastos.solver import (DEPARTAGE_NUMERIQUE, SolverConfig, element_weights,
                           solve)

DOSES = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F"]

#: Six chimies realistes. Elles servent d'empreinte : le chemin par
#: defaut doit rendre exactement les memes solutions qu'avant le
#: remplacement de la penalite.
CHIMIES = {
    "NMC811": {"NMC811": .40, "C_total": .33, "Cu_metal": .10,
               "Al_metal": .07, "PVDF": .05, "LiPF6": .03, "Fe_metal": .02},
    "NMC111": {"NMC111": .36, "C_total": .36, "Cu_metal": .11,
               "Al_metal": .08, "PVDF": .05, "LiPF6": .02, "Fe_metal": .02},
    "LFP": {"LFP": .42, "C_total": .34, "Cu_metal": .11, "Al_metal": .07,
            "PVDF": .04, "LiPF6": .02},
    "LCO": {"LCO": .45, "C_total": .30, "Cu_metal": .12, "Al_metal": .06,
            "PVDF": .04, "LiPF6": .02, "Fe_metal": .01},
    "NMC+LFP": {"NMC622": .22, "LFP": .20, "C_total": .33, "Cu_metal": .10,
                "Al_metal": .07, "PVDF": .05, "LiPF6": .02, "Fe_metal": .01},
    "carbone riche": {"NMC532": .22, "C_total": .48, "Cu_metal": .13,
                      "Al_metal": .08, "PVDF": .06, "LiPF6": .02,
                      "Fe_metal": .01},
}


def bulletin(melange):
    b = {el: 0.0 for el in ELEMENTS}
    for ph, fr in melange.items():
        comp = PHASES[ph]["composition"]
        M = formula_mass(comp)
        for el, n in comp.items():
            b[el] += fr * ATOMIC_MASS[el] * n / M
    return {el: b[el] * 100.0 for el in DOSES}


def resoudre(melange, prior=None):
    return solve(bulletin(melange), elements=DOSES,
                 config=SolverConfig(), prior=prior)


def prior_sur(phase, part=0.40):
    p = np.zeros(len(PHASE_KEYS))
    p[PHASE_KEYS.index(phase)] = part
    return p


# ==========================================================================
# 1. Le prior est honore, sur un lot reel
# ==========================================================================

@pytest.mark.parametrize("phase", ["NMC111", "LCO", "NCA"])
def test_le_prior_deplace_le_representant_sur_un_bulletin_reel(phase):
    """
    LE DEFAUT QUI A MOTIVE TOUT CE FICHIER.

    Le test d'origine, `test_le_prior_deplace_la_ventilation`, portait
    sur un lot `degenerate_probe` a douze elements doses - une
    configuration ou la penalite fonctionnait. Sur un bulletin reel, a
    dix elements, elle deplacait le representant de 0,00 point : le
    prior etait sans effet, et rien ne le signalait.
    """
    sans = resoudre(CHIMIES["NMC811"])
    avec = resoudre(CHIMIES["NMC811"], prior=prior_sur(phase))
    deplacement = float(np.max(np.abs(avec.x - sans.x)))
    assert deplacement > 1e-3, (
        f"prior sur {phase} : le representant n'a bouge que de "
        f"{deplacement * 100:.4f} point. Le prior est de nouveau sans "
        f"effet sur un bulletin reel.")
    assert avec.meta["prior_used"] is True


def test_honorer_le_prior_n_abime_pas_l_ajustement():
    """
    C'est ce qui distingue une projection d'une penalite. La penalite
    n'achetait du deplacement qu'en degradant le residu - a lambda 1e2 il
    passait de 0,00 a 1,40, a 1e4 il atteignait 9,35. La projection se
    deplace LE LONG de l'espace nul, donc l'ajustement est intact par
    construction.
    """
    sans = resoudre(CHIMIES["NMC811"])
    avec = resoudre(CHIMIES["NMC811"], prior=prior_sur("NMC111"))
    assert avec.residual_weighted == pytest.approx(
        sans.residual_weighted, abs=1e-4), (
        f"l'ajustement s'est degrade : {sans.residual_weighted:.6f} -> "
        f"{avec.residual_weighted:.6f}")


def test_le_prior_ne_touche_aucune_grandeur_identifiable():
    """
    `A @ (N t) = 0` par construction : un deplacement dans l'espace nul
    laisse le bulletin reconstruit inchange. Si cette egalite cesse, la
    projection ne se fait plus dans le bon sous-espace.
    """
    A, _, _ = stoichiometry_matrix(elements=DOSES)
    sans = resoudre(CHIMIES["NMC811"])
    avec = resoudre(CHIMIES["NMC811"], prior=prior_sur("NMC111"))
    assert np.allclose(A @ sans.x, A @ avec.x, atol=1e-9), (
        "le bulletin reconstruit a bouge : la projection sort de "
        "l'espace nul")


def test_aucune_fraction_negative_ne_sort_de_la_projection():
    """La tolerance du programme lineaire laisse passer des negatifs de
    l'ordre de 1e-8. Ils doivent etre rabotes : une phase ne peut pas
    peser moins que rien."""
    avec = resoudre(CHIMIES["NMC811"], prior=prior_sur("NMC111"))
    assert avec.x.min() >= 0.0


# ==========================================================================
# 2. La projection elle-meme
# ==========================================================================

def test_la_projection_est_sans_effet_sur_un_systeme_bien_pose():
    """Sans direction nulle, il n'y a qu'un representant et le prior n'a
    rien a dire. Ce n'est pas une erreur, et il ne faut pas la lever."""
    x0 = np.array([0.5, 0.5])
    vide = np.zeros((2, 0))
    assert np.allclose(representant_proche(x0, vide, np.array([1.0, 0.0])), x0)


def test_un_prior_de_mauvaise_dimension_echoue_fort():
    A, _, cles = stoichiometry_matrix(elements=DOSES)
    N = null_space(A)
    x0 = resoudre(CHIMIES["NMC811"]).x
    with pytest.raises(ValueError, match="dimension"):
        representant_proche(x0, N, np.zeros(3))


def test_la_projection_reste_dans_le_domaine_compatible():
    """
    Le representant projete doit rester une solution admissible : toutes
    les phases positives, et le meme bulletin reconstruit.
    """
    A, _, cles = stoichiometry_matrix(elements=DOSES)
    N = null_space(A)
    x0 = resoudre(CHIMIES["NMC811"]).x
    x1 = np.maximum(representant_proche(x0, N, prior_sur("LCO")), 0.0)
    assert (x1 >= -1e-9).all()
    assert np.allclose(A @ x0, A @ x1, atol=1e-9)


# ==========================================================================
# 3. Ce qui ne doit PAS avoir bouge
# ==========================================================================

#: Empreinte des six solutions par defaut, relevee avant le remplacement
#: de la penalite par la projection. Elle garde l'equivalence du chemin
#: par defaut : aucun lot sans prior ne doit changer de reponse.
EMPREINTE = "626ef473caa5126196b6eeca"


def test_le_chemin_par_defaut_n_a_pas_bouge_d_un_bit():
    """
    CE TEST GARDE UNE PROMESSE FAITE AU MOMENT DU CORRECTIF.

    Remplacer la penalite par une projection ne devait rien changer aux
    lots sans prior - et c'est verifiable autrement que par confiance.
    L'empreinte a ete relevee sur le code d'avant.

    S'il echoue, ce n'est pas forcement une regression : c'est que le
    representant par defaut a change, ce qui deplace le detail des
    phases affiche par le rapport et la somme qui porte le bouclage. Le
    constater exige de remesurer, pas de mettre l'empreinte a jour.
    """
    h = hashlib.sha256()
    for nom in CHIMIES:
        h.update(np.round(resoudre(CHIMIES[nom]).x, 9).tobytes())
    assert h.hexdigest()[:24] == EMPREINTE, (
        "le representant par defaut a change. Remesurer avant de mettre "
        "l'empreinte a jour.")


def test_lambda_null_ne_revient_pas():
    """
    Il ne faisait pas ce que son nom disait, et son nom invitait a le
    regler. Le reintroduire ferait croire a un arbitrage qui n'existe
    pas.
    """
    assert not hasattr(SolverConfig(), "lambda_null"), (
        "`lambda_null` est de retour dans SolverConfig. Son commentaire "
        "decrivait un arbitrage mesurement inexistant : voir "
        "DEPARTAGE_NUMERIQUE.")


def test_le_departage_numerique_garde_le_domaine_ouvert():
    """
    SON VRAI ROLE, ET LA RAISON POUR LAQUELLE IL EST CONSERVE.

    Sans ce bloc, NNLS atterrit volontiers sur un sommet de masse
    minimale. Or `_domain_constraints` plafonne la masse a
    max(1, somme(x0)) : depuis un tel point, le domaine compatible
    devient de largeur nulle et toute la trichotomie du rapport
    s'effondre.

    Le test MONTRE le mecanisme au lieu de l'affirmer : il resout une
    seconde fois sans le bloc, et compare. Mesure :

        avec departage    somme 101,38 %   cathodes 3,116 pt de large
        sans departage    somme 100,00 %   cathodes 0,000 pt - effondre

    Une grandeur AGREGEE est choisie a dessein. Les grades NMC
    individuels sont pinces par d'autres contraintes et restent de
    largeur nulle dans les deux cas : ils ne montreraient rien.
    """
    assert DEPARTAGE_NUMERIQUE > 0
    A, _, cles = stoichiometry_matrix(elements=DOSES)
    N = null_space(A)
    cath = cathode_indicator(cles)

    avec = resoudre(CHIMIES["NMC811"])
    lo, hi = compatible_bounds(avec.x, N, cath)
    assert hi - lo > 1e-3, (
        f"le domaine des cathodes fait {(hi - lo) * 100:.4f} point depuis "
        f"le representant par defaut (somme {avec.x.sum() * 100:.3f} %). "
        f"Le departage numerique ne l'ecarte plus du bord.")

    # Le meme calcul SANS le bloc, pour montrer ce qu'il evite.
    b_vec = np.array([bulletin(CHIMIES["NMC811"])[el] / 100.0
                      for el in DOSES])
    w = element_weights(b_vec, DEFAULT_NOISE, 1e-5, elements=DOSES)
    nu, _ = nnls(np.diag(w) @ A, np.diag(w) @ b_vec)
    lo_nu, hi_nu = compatible_bounds(nu, N, cath)
    assert hi_nu - lo_nu < 1e-6, (
        "sans le departage, le domaine des cathodes n'est plus effondre. "
        "Le bloc a peut-etre cesse d'etre necessaire - le verifier avant "
        "de le retirer.")
    assert nu.sum() < avec.x.sum(), (
        "sans le departage, la somme n'est plus plus basse : le mecanisme "
        "decrit n'est plus celui qui opere.")


# ==========================================================================
# 4. Une limite, documentee plutot que masquee
# ==========================================================================

def test_la_projection_L1_ne_promet_pas_de_remplir_la_phase_visee():
    """
    CE TEST GARDE UNE LIMITE, PAS UNE REUSSITE.

    La projection retient le representant le plus proche du prior AU
    SENS L1. Cette norme n'est pas strictement convexe : ses optima sont
    plats, et elle prefere la parcimonie. Demander « mets 40 % de
    NMC 111 » deplace donc bien le representant - 3,79 points sur le lot
    d'essai - mais sans garantir que NMC 111 augmente.

    Le prior est un DEPARTAGE entre representants equivalents, pas une
    contrainte. Une contrainte se declare par une quantification DRX, qui
    passe par `projeter_dans_domaine` et resserre reellement le domaine.
    """
    sans = resoudre(CHIMIES["NMC811"])
    avec = resoudre(CHIMIES["NMC811"], prior=prior_sur("NMC111"))
    i = PHASE_KEYS.index("NMC111")
    assert float(np.max(np.abs(avec.x - sans.x))) > 1e-3, (
        "le representant n'a pas bouge du tout")
    assert avec.x[i] == pytest.approx(sans.x[i], abs=1e-6), (
        "NMC 111 a augmente : la projection tient desormais une promesse "
        "qu'elle ne faisait pas. Mettre a jour cette documentation.")
