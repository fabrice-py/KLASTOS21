"""Tests de klastos/solver.py.

Deux invariants portent tout le module :

  1. Sur un systeme BIEN POSE, le solveur retrouve exactement le melange.
  2. Sur un systeme DEGENERE, il retrouve exactement les grandeurs FERMES,
     et son estimation des grandeurs non identifiables reste dans le domaine
     compatible - c'est un representant, pas une estimation.
"""

import numpy as np
import pytest

from klastos.generator import NOISE_FREE, NoiseModel, make_batch, make_lot
from klastos.identifiability import (compatible_bounds, null_space,
                                     standard_functionals)
from klastos.phases import PHASE_KEYS, stoichiometry_matrix
from klastos.provenance import ProvenanceDeclaration
from klastos.solver import (CLOSURE_ALERT, CLOSURE_REJECT,
                            CLOSURE_THRESHOLDS_VALIDATED, STATUT_ALERTE,
                            STATUT_OK, STATUT_REJET, SolverConfig,
                            check_closure, element_weights, solve, solve_lot)

# Liste de phases sans degenerescence (cf. tests d'identifiabilite).
LISTE_BIEN_POSEE = [
    k for k in PHASE_KEYS if k not in ("NMC111", "NMC532", "LCO", "LMO")
]

TOL_NUM = 1e-6      # tolerance numerique, soit 1e-4 point de %


# ==========================================================================
# 1. Systeme bien pose : reconstruction exacte
# ==========================================================================

def test_systeme_bien_pose_reconstruit_le_melange():
    lot = make_lot(
        rng=1, profile="gigafactory_nmc",
        phase_keys=LISTE_BIEN_POSEE, noise=NOISE_FREE,
    )
    res = solve_lot(lot)
    assert res.degeneracy == 0
    assert np.allclose(res.x, lot.x_true, atol=TOL_NUM)
    assert res.point_estimate_is_representative is False


def test_residu_negligeable_sans_bruit():
    lot = make_lot(rng=2, phase_keys=LISTE_BIEN_POSEE, noise=NOISE_FREE)
    res = solve_lot(lot)
    assert res.max_element_residual < TOL_NUM


def test_solution_toujours_non_negative():
    for graine in range(15):
        lot = make_lot(rng=graine, profile="mixed_ev")
        assert np.all(solve_lot(lot).x >= 0.0)


# ==========================================================================
# 2. Systeme degenere : les grandeurs fermes sont exactes
# ==========================================================================

def _ecarts_par_identifiabilite(lot, res):
    """Retourne (pire ecart sur les fermes, pire ecart sur les non fermes)."""
    A, _, keys = stoichiometry_matrix(phase_keys=lot.phase_keys)
    N = null_space(A)
    pire_ferme = pire_ouvert = 0.0
    for f in standard_functionals(keys):
        d = abs(float(f.c @ lot.x_true) - float(f.c @ res.x))
        lo, hi = compatible_bounds(lot.x_true, N, f.c)
        if hi - lo < 1e-12:
            pire_ferme = max(pire_ferme, d)
        else:
            pire_ouvert = max(pire_ouvert, d)
    return pire_ferme, pire_ouvert


def test_grandeurs_fermes_exactes_malgre_la_degenerescence():
    """INVARIANT : la regularisation ne deforme jamais ce que la donnee determine."""
    lot = make_lot(rng=1, profile="gigafactory_nmc", noise=NOISE_FREE)
    res = solve_lot(lot)
    assert res.degeneracy == 2
    ferme, _ = _ecarts_par_identifiabilite(lot, res)
    assert ferme < TOL_NUM


def test_la_ventilation_par_grade_diverge_bel_et_bien():
    """Contre-preuve : sans cette divergence, la degenerescence serait fictive."""
    lot = make_lot(rng=1, profile="gigafactory_nmc", noise=NOISE_FREE)
    res = solve_lot(lot)
    _, ouvert = _ecarts_par_identifiabilite(lot, res)
    assert ouvert > 0.01          # au moins un point de % d'ecart
    assert res.point_estimate_is_representative is True


def test_la_solution_reste_dans_le_domaine_compatible():
    lot = make_lot(rng=1, profile="degenerate_probe", noise=NOISE_FREE)
    res = solve_lot(lot)
    A, _, keys = stoichiometry_matrix(phase_keys=lot.phase_keys)
    N = null_space(A)
    for f in standard_functionals(keys):
        lo, hi = compatible_bounds(lot.x_true, N, f.c)
        v = float(f.c @ res.x)
        assert lo - TOL_NUM <= v <= hi + TOL_NUM, f.key


@pytest.mark.parametrize("graine", range(5))
def test_le_bulletin_est_toujours_reproduit(graine):
    """Quelle que soit la ventilation retenue, le bulletin est explique."""
    lot = make_lot(rng=graine, profile="mixed_ev", noise=NOISE_FREE)
    res = solve_lot(lot)
    assert np.allclose(res.b_fitted, lot.b_measured, atol=TOL_NUM)


# ==========================================================================
# 3. Provenance : la restriction ameliore la reconstruction
# ==========================================================================

def test_l_attestation_rend_la_ventilation_exacte():
    """Chaine complete : attestation -> liste restreinte -> grades determines."""
    keys, _, _ = ProvenanceDeclaration(
        "chutes_gigafactory", attested=True,
        declared_grades=("NMC622", "NMC811"),
    ).resolve()
    keys = [k for k in keys if k not in ("LCO", "LMO")]
    lot = make_lot(rng=4, profile="gigafactory_nmc",
                   phase_keys=keys, noise=NOISE_FREE)
    res = solve_lot(lot)
    assert res.degeneracy == 0
    assert np.allclose(res.x, lot.x_true, atol=TOL_NUM)


# ==========================================================================
# 4. Bouclage massique
# ==========================================================================

def test_bouclage_conforme():
    c = check_closure(np.array([0.5, 0.5]))
    assert c.status == STATUT_OK
    assert c.is_exploitable


def test_bouclage_alerte():
    milieu = 1.0 - (CLOSURE_ALERT + CLOSURE_REJECT) / 2
    c = check_closure(np.array([milieu]))
    assert c.status == STATUT_ALERTE
    assert c.is_exploitable
    assert "n'est pas expliquee" in c.message


def test_bouclage_rejet():
    c = check_closure(np.array([1.0 - CLOSURE_REJECT - 0.05]))
    assert c.status == STATUT_REJET
    assert not c.is_exploitable
    assert "inexploitable" in c.message


def test_bouclage_detecte_une_masse_manquante():
    manquant = CLOSURE_REJECT + 0.05
    lot = make_lot(rng=6, profile="mixed_ev", noise=NOISE_FREE,
                   closure=1.0 - manquant)
    res = solve_lot(lot)
    assert res.closure.total == pytest.approx(1.0 - manquant, abs=1e-9)
    assert res.closure.status == STATUT_REJET


def test_les_seuils_de_bouclage_sont_arbitres():
    """
    Dette soldee. Arbitrage du geometallurgiste : 6 % et 20 %, cales sur la
    realite metallurgique des black masses plutot que sur un echantillon
    idealement caracterise.
    """
    assert CLOSURE_THRESHOLDS_VALIDATED is True
    assert CLOSURE_ALERT == pytest.approx(0.06)
    assert CLOSURE_REJECT == pytest.approx(0.20)
    assert 0.0 < CLOSURE_ALERT < CLOSURE_REJECT


def test_les_seuils_sont_au_dessus_du_plancher_de_bruit():
    """
    Le seul bruit analytique produit jusqu'a 10,3 % de masse apparemment
    inexpliquee. Des seuils en dessous refuseraient des lots sains.
    """
    assert CLOSURE_ALERT >= 0.055, "l'alerte doit couvrir le 95e centile du bruit"
    assert CLOSURE_REJECT > 0.105, "le rejet doit depasser le pire cas du bruit"


def test_seuils_configurables():
    cfg = SolverConfig(closure_alert=0.001, closure_reject=0.20)
    lot = make_lot(rng=6, noise=NOISE_FREE, closure=0.95)
    res = solve_lot(lot, config=cfg)
    assert res.closure.status == STATUT_ALERTE


# ==========================================================================
# 5. Ponderation
# ==========================================================================

def test_les_poids_favorisent_les_elements_mineurs():
    b = np.array([0.35, 0.01])
    w = element_weights(b)
    assert w[1] > w[0]


def test_plancher_de_ponderation():
    w = element_weights(np.array([0.0]), floor=1e-3)
    assert np.isfinite(w).all()
    assert w[0] == pytest.approx(1e3)


def test_la_ponderation_ameliore_les_phases_mineures():
    """Sans poids, l'oxygene ecrase le fluor et le PVDF est mal estime."""
    bruit = NoiseModel(rel_sigma=0.02, abs_sigma=1e-4, lod=0.0)
    avec, sans = [], []
    for lot in make_batch(20, rng=99, profile="gigafactory_nmc",
                          phase_keys=LISTE_BIEN_POSEE, noise=bruit):
        i = lot.phase_keys.index("PVDF")
        vrai = lot.x_true[i]
        avec.append(abs(solve_lot(lot).x[i] - vrai))
        sans.append(
            abs(solve_lot(lot, config=SolverConfig(use_weights=False)).x[i] - vrai)
        )
    assert np.median(avec) < np.median(sans)


# ==========================================================================
# 6. Prior : effet confine a l'espace nul
# ==========================================================================

def test_le_prior_ne_touche_pas_les_grandeurs_fermes():
    lot = make_lot(rng=8, profile="degenerate_probe", noise=NOISE_FREE)
    A, _, keys = stoichiometry_matrix(phase_keys=lot.phase_keys)
    prior = np.zeros(len(keys))
    prior[keys.index("NMC811")] = 0.5

    sans = solve_lot(lot)
    avec = solve_lot(lot, prior=prior)

    for f in standard_functionals(keys):
        N = null_space(A)
        lo, hi = compatible_bounds(lot.x_true, N, f.c)
        if hi - lo < 1e-12:                       # grandeur ferme
            assert float(f.c @ sans.x) == pytest.approx(
                float(f.c @ avec.x), abs=1e-5
            ), f.key


def test_le_prior_deplace_la_ventilation():
    lot = make_lot(rng=8, profile="degenerate_probe", noise=NOISE_FREE)
    keys = lot.phase_keys
    prior = np.zeros(len(keys))
    prior[keys.index("NMC811")] = 0.5
    sans = solve_lot(lot)
    avec = solve_lot(lot, prior=prior)
    i = keys.index("NMC811")
    assert abs(avec.x[i] - sans.x[i]) > 1e-4
    assert avec.meta["prior_used"] is True


def test_prior_de_mauvaise_dimension_rejete():
    lot = make_lot(rng=0)
    with pytest.raises(ValueError):
        solve_lot(lot, prior=np.zeros(3))


# ==========================================================================
# 7. Entrees : bulletin sous forme de dictionnaire, validation
# ==========================================================================

def test_bulletin_en_dictionnaire():
    lot = make_lot(rng=3, profile="mixed_ev", noise=NOISE_FREE)
    par_vecteur = solve(lot.b_measured, phase_keys=lot.phase_keys)
    par_dict = solve(lot.as_bulletin(decimals=12), phase_keys=lot.phase_keys)
    assert np.allclose(par_vecteur.x, par_dict.x, atol=1e-6)


def test_element_inconnu_rejete():
    with pytest.raises(KeyError):
        solve({"Li": 5.0, "Xx": 1.0})


def test_bulletin_negatif_rejete():
    b = np.zeros(12)
    b[0] = -0.1
    with pytest.raises(ValueError):
        solve(b)


def test_bulletin_de_mauvaise_dimension_rejete():
    with pytest.raises(ValueError):
        solve(np.zeros(5))


# ==========================================================================
# 8. Robustesse au bruit analytique
# ==========================================================================

def test_les_teneurs_elementaires_restent_proches_sous_bruit():
    bruit = NoiseModel(rel_sigma=0.03, abs_sigma=2e-4, lod=0.0)
    ecarts = []
    for lot in make_batch(20, rng=55, profile="mixed_ev", noise=bruit):
        A, els, keys = stoichiometry_matrix(phase_keys=lot.phase_keys)
        res = solve_lot(lot)
        for el in ("Ni", "Co", "Li"):
            row = A[els.index(el)]
            vrai = float(row @ lot.x_true)
            if vrai > 0.01:
                ecarts.append(abs(float(row @ res.x) - vrai) / vrai)
    assert np.median(ecarts) < 0.06        # 2 x le bruit relatif injecte


def test_as_dict_ne_liste_que_les_phases_presentes():
    lot = make_lot(rng=1, phase_keys=LISTE_BIEN_POSEE, noise=NOISE_FREE,
                   profile="gigafactory_nmc")
    d = solve_lot(lot).as_dict()
    assert all(v > 0 for v in d.values())
    assert set(d) <= set(LISTE_BIEN_POSEE)


# ==========================================================================
# 9. Resolution sans oxygene : le cas de tout bulletin reel
# ==========================================================================

SANS_O = [e for e in __import__("klastos.elements", fromlist=["x"]).ELEMENTS
          if e != "O"]


def _bulletin_sans_oxygene(lot):
    """Projette un bulletin complet sur les onze elements doses."""
    return np.array([lot.b_measured[lot.elements.index(e)] for e in SANS_O])


def test_la_masse_expliquee_vaut_cent_pour_un_lot_entierement_decrit():
    lot = make_lot(rng=1, profile="gigafactory_nmc",
                   phase_keys=LISTE_BIEN_POSEE, noise=NOISE_FREE)
    res = solve(_bulletin_sans_oxygene(lot), phase_keys=LISTE_BIEN_POSEE,
                elements=SANS_O)
    assert res.explained_mass == pytest.approx(1.0, abs=1e-5)
    assert res.unexplained_mass == pytest.approx(0.0, abs=1e-5)
    assert res.closure.status == STATUT_OK


def test_la_masse_manquante_est_mesuree_exactement():
    """
    8 % de masse hors modele doivent ressortir a 8 %.

    On ne teste ICI que la MESURE, pas la classification : 8 % tombe
    exactement sur le seuil de rejet, et le dernier bit du calcul NNLS
    suffit a faire basculer d'un cote ou de l'autre selon la version de
    BLAS installee. La classification est testee juste en dessous, sur une
    valeur franche.
    """
    lot = make_lot(rng=1, profile="gigafactory_nmc",
                   phase_keys=LISTE_BIEN_POSEE, noise=NOISE_FREE,
                   closure=0.92)
    res = solve(_bulletin_sans_oxygene(lot), phase_keys=LISTE_BIEN_POSEE,
                elements=SANS_O)
    assert res.unexplained_mass == pytest.approx(0.08, abs=1e-5)
    assert res.closure.status != STATUT_OK


def test_une_masse_manquante_franche_est_rejetee():
    """Au-dela du seuil de rejet, et hors de tout doute numerique."""
    manquant = CLOSURE_REJECT + 0.05
    lot = make_lot(rng=1, profile="gigafactory_nmc",
                   phase_keys=LISTE_BIEN_POSEE, noise=NOISE_FREE,
                   closure=1.0 - manquant)
    res = solve(_bulletin_sans_oxygene(lot), phase_keys=LISTE_BIEN_POSEE,
                elements=SANS_O)
    assert res.unexplained_mass == pytest.approx(manquant, abs=1e-5)
    assert res.closure.status == STATUT_REJET
    assert not res.closure.is_exploitable
    assert not res.closure.is_exploitable


def test_une_masse_manquante_moderee_declenche_une_alerte():
    """Entre les deux seuils : signale, mais le lot reste exploitable."""
    milieu = (CLOSURE_ALERT + CLOSURE_REJECT) / 2
    lot = make_lot(rng=1, profile="gigafactory_nmc",
                   phase_keys=LISTE_BIEN_POSEE, noise=NOISE_FREE,
                   closure=1.0 - milieu)
    res = solve(_bulletin_sans_oxygene(lot), phase_keys=LISTE_BIEN_POSEE,
                elements=SANS_O)
    assert res.closure.status == STATUT_ALERTE
    assert res.closure.is_exploitable


def test_l_oxygene_est_predit_exactement():
    """INVARIANT : l'oxygene non dose est retrouve par la stoechiometrie."""
    lot = make_lot(rng=3, profile="gigafactory_nmc",
                   phase_keys=LISTE_BIEN_POSEE, noise=NOISE_FREE)
    res = solve(_bulletin_sans_oxygene(lot), phase_keys=LISTE_BIEN_POSEE,
                elements=SANS_O)
    o_reel = lot.b_measured[lot.elements.index("O")]
    assert res.predicted_unmeasured["O"] == pytest.approx(o_reel, abs=1e-6)


def test_le_bulletin_sans_oxygene_ne_boucle_pas_lui_meme():
    """Ce qui serait rejete a tort si le bouclage portait sur le bulletin."""
    lot = make_lot(rng=1, profile="gigafactory_nmc",
                   phase_keys=LISTE_BIEN_POSEE, noise=NOISE_FREE)
    b11 = _bulletin_sans_oxygene(lot)
    assert b11.sum() < 0.85           # pres de 20 % d'oxygene manquant
    res = solve(b11, phase_keys=LISTE_BIEN_POSEE, elements=SANS_O)
    assert res.closure.status == STATUT_OK    # le bouclage porte sur les phases


def test_retirer_l_oxygene_augmente_la_degenerescence():
    lot = make_lot(rng=1, profile="mixed_ev", noise=NOISE_FREE)
    avec = solve(lot.b_measured, phase_keys=lot.phase_keys)
    sans = solve(_bulletin_sans_oxygene(lot), phase_keys=lot.phase_keys,
                 elements=SANS_O)
    assert sans.degeneracy == avec.degeneracy + 1


def test_les_elements_doses_sont_traces():
    lot = make_lot(rng=1, noise=NOISE_FREE)
    res = solve(_bulletin_sans_oxygene(lot), elements=SANS_O)
    assert res.elements == SANS_O
    assert res.meta["unmeasured_elements"] == ["O"]
    assert set(res.predicted_unmeasured) == {"O"}


def test_sans_element_non_dose_aucune_prediction():
    lot = make_lot(rng=1, noise=NOISE_FREE)
    res = solve(lot.b_measured, phase_keys=lot.phase_keys)
    assert res.predicted_unmeasured == {}
    assert res.meta["unmeasured_elements"] == []


def test_bulletin_en_dictionnaire_avec_elements_restreints():
    lot = make_lot(rng=3, profile="mixed_ev", noise=NOISE_FREE)
    d = {e: float(lot.b_measured[lot.elements.index(e)] * 100.0) for e in SANS_O}
    par_vecteur = solve(_bulletin_sans_oxygene(lot),
                        phase_keys=lot.phase_keys, elements=SANS_O)
    par_dict = solve(d, phase_keys=lot.phase_keys, elements=SANS_O)
    assert np.allclose(par_vecteur.x, par_dict.x, atol=1e-6)


def test_element_hors_modele_rejete():
    with pytest.raises(KeyError, match="hors modele"):
        solve(np.zeros(2), elements=["Ni", "Xx"])


def test_liste_d_elements_vide_rejetee():
    with pytest.raises(ValueError, match="Aucun element dose"):
        solve(np.zeros(0), elements=[])


def test_dimension_incoherente_avec_les_elements_rejetee():
    with pytest.raises(ValueError, match="11 elements attendus"):
        solve(np.zeros(12), elements=SANS_O)