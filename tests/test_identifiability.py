"""Tests de klastos/identifiability.py.

Deux invariants critiques :
  1. "Cathodes totales" et "NMC + LCO" sont fermes quelle que soit la liste
     de phases (decision 1). C'est CALCULE, jamais suppose.
  2. Tout domaine compatible contient la valeur vraie. Si cet invariant
     casse, le rapport ment au client.
"""

import numpy as np
import pytest

from klastos.identifiability import (NOTE_NON_IDENTIFIABLE, analyse,
                                     compatible_bounds, degeneracy_dimension,
                                     describe_null_directions, evaluate,
                                     is_identifiable, null_space,
                                     standard_functionals)
from klastos.phases import (MOLAR_MASS, PHASE_KEYS, cathode_indicator,
                            indicator, nmc_lco_indicator,
                            stoichiometry_matrix)
from klastos.provenance import ProvenanceDeclaration

# --- Jeux de phases correspondant aux scenarios de provenance -------------
LISTE_COMPLETE = list(PHASE_KEYS)
LISTE_VE = [k for k in PHASE_KEYS if k not in ("LCO", "LMO")]
LISTE_GIGA = [k for k in PHASE_KEYS if k not in ("NMC111", "NMC532", "LCO", "LMO")]


# ==========================================================================
# 1. Structure de la degenerescence
# ==========================================================================

def test_degenerescence_liste_complete_vaut_deux():
    A, _, _ = stoichiometry_matrix()
    assert degeneracy_dimension(A) == 2


def test_provenance_ve_ramene_la_degenerescence_a_un():
    A, _, _ = stoichiometry_matrix(phase_keys=LISTE_VE)
    assert degeneracy_dimension(A) == 1


def test_provenance_gigafactory_annule_la_degenerescence():
    A, _, _ = stoichiometry_matrix(phase_keys=LISTE_GIGA)
    assert degeneracy_dimension(A) == 0


def test_la_provenance_pilote_bien_la_degenerescence():
    """Chaine complete : declaration attestee -> liste restreinte -> nullite."""
    d = ProvenanceDeclaration("vehicule_electrique", attested=True)
    retenues, exclues, _ = d.resolve()
    assert set(exclues) == {"LCO", "LMO"}
    A, _, _ = stoichiometry_matrix(phase_keys=retenues)
    assert degeneracy_dimension(A) == 1


def test_sans_attestation_la_degenerescence_reste_a_deux():
    d = ProvenanceDeclaration("vehicule_electrique", attested=False)
    retenues, _, _ = d.resolve()
    A, _, _ = stoichiometry_matrix(phase_keys=retenues)
    assert degeneracy_dimension(A) == 2


def test_directions_nulles_somment_a_zero():
    """Propriete structurelle qui rend 'Cathodes totales' ferme."""
    A, _, keys = stoichiometry_matrix()
    for d in describe_null_directions(A, keys):
        assert d["somme"] == pytest.approx(0.0, abs=1e-9)


def test_directions_nulles_ne_touchent_que_nmc_et_lco():
    A, _, keys = stoichiometry_matrix()
    touchees = set()
    for d in describe_null_directions(A, keys):
        touchees |= set(d["coefficients"])
    assert touchees <= {"NMC111", "NMC532", "NMC622", "NMC811", "LCO"}


# ==========================================================================
# 2. Equivalence exacte entre melanges NMC
# ==========================================================================

def test_melanges_nmc_indiscernables():
    """0.75 NMC111 + 1.00 NMC811 est elementairement identique a 1.75 NMC622."""
    A, _, keys = stoichiometry_matrix()
    i = {k: n for n, k in enumerate(keys)}
    xa = np.zeros(len(keys))
    xb = np.zeros(len(keys))
    xa[i["NMC111"]] = 0.75 * MOLAR_MASS["NMC111"]
    xa[i["NMC811"]] = 1.00 * MOLAR_MASS["NMC811"]
    xb[i["NMC622"]] = 1.75 * MOLAR_MASS["NMC622"]
    xa /= xa.sum()
    xb /= xb.sum()
    assert np.allclose(A @ xa, A @ xb, atol=1e-12)


# ==========================================================================
# 3. Grandeurs fermes (decision 1) - calculees, pas supposees
# ==========================================================================

@pytest.mark.parametrize("keys", [LISTE_COMPLETE, LISTE_VE, LISTE_GIGA])
def test_cathodes_totales_toujours_ferme(keys):
    A, _, k = stoichiometry_matrix(phase_keys=keys)
    assert is_identifiable(cathode_indicator(phase_keys=k), null_space(A))


def test_bloc_nmc_lco_ferme_sur_liste_complete():
    A, _, k = stoichiometry_matrix()
    assert is_identifiable(nmc_lco_indicator(phase_keys=k), null_space(A))


@pytest.mark.parametrize("el", ["Li", "Ni", "Co", "Mn", "Fe", "Cu", "Al", "P", "F"])
def test_toutes_les_teneurs_elementaires_sont_fermes(el):
    """Invariant commercial : la valeur du lot reste un chiffre unique."""
    A, els, _ = stoichiometry_matrix()
    assert is_identifiable(A[els.index(el)], null_space(A))


@pytest.mark.parametrize("pk", ["LFP", "NCA", "LMO", "C_total", "Cu_metal",
                                "Al_metal", "PVDF", "LiPF6", "Fe_metal"])
def test_phases_hors_famille_degeneree_sont_fermes(pk):
    A, _, k = stoichiometry_matrix()
    assert is_identifiable(indicator([pk], phase_keys=k), null_space(A))


@pytest.mark.parametrize("pk", ["NMC111", "NMC532", "NMC622", "NMC811", "LCO"])
def test_grades_non_fermes_sur_liste_complete(pk):
    A, _, k = stoichiometry_matrix()
    assert not is_identifiable(indicator([pk], phase_keys=k), null_space(A))


@pytest.mark.parametrize("pk", ["NMC622", "NMC811"])
def test_grades_deviennent_fermes_en_gigafactory(pk):
    A, _, k = stoichiometry_matrix(phase_keys=LISTE_GIGA)
    assert is_identifiable(indicator([pk], phase_keys=k), null_space(A))


# ==========================================================================
# 4. Domaines compatibles
# ==========================================================================

def _lot_test(keys):
    """Melange de reference : trois grades NMC, du carbone, des collecteurs."""
    i = {k: n for n, k in enumerate(keys)}
    x = np.zeros(len(keys))
    for pk, v in [("NMC111", 0.12), ("NMC622", 0.18), ("NMC811", 0.10),
                  ("C_total", 0.30), ("Cu_metal", 0.03), ("Al_metal", 0.03),
                  ("PVDF", 0.02)]:
        if pk in i:
            x[i[pk]] = v
    return x


def test_le_domaine_contient_toujours_la_valeur_vraie():
    """Invariant le plus important : le rapport ne doit jamais exclure la verite."""
    A, _, keys = stoichiometry_matrix()
    x = _lot_test(keys)
    N = null_space(A)
    for f in standard_functionals(keys):
        lo, hi = compatible_bounds(x, N, f.c)
        vraie = float(f.c @ x)
        assert lo - 1e-9 <= vraie <= hi + 1e-9, f.key


def test_domaine_nul_pour_une_grandeur_ferme():
    A, _, keys = stoichiometry_matrix()
    x = _lot_test(keys)
    N = null_space(A)
    lo, hi = compatible_bounds(x, N, cathode_indicator(phase_keys=keys))
    assert hi - lo == pytest.approx(0.0, abs=1e-9)


def test_domaine_strictement_positif_pour_un_grade():
    A, _, keys = stoichiometry_matrix()
    x = _lot_test(keys)
    N = null_space(A)
    lo, hi = compatible_bounds(x, N, indicator(["NMC622"], phase_keys=keys))
    assert hi - lo > 1e-3


def test_bornes_restent_dans_zero_un():
    A, _, keys = stoichiometry_matrix()
    x = _lot_test(keys)
    N = null_space(A)
    for pk in ["NMC111", "NMC532", "NMC622", "NMC811", "LCO"]:
        lo, hi = compatible_bounds(x, N, indicator([pk], phase_keys=keys))
        assert lo >= -1e-9
        assert hi <= 1.0 + 1e-9


# ==========================================================================
# 5. Evaluation complete et rendu
# ==========================================================================

def test_evaluate_marque_les_blocs_correctement():
    A, _, keys = stoichiometry_matrix()
    x = _lot_test(keys)
    res = {r.key: r for r in evaluate(x, A, standard_functionals(keys))}

    assert res["cathodes_totales"].identifiable
    assert res["nmc_lco"].identifiable
    assert res["el_Ni"].identifiable
    assert res["C_total"].identifiable

    for pk in ["NMC111", "NMC532", "NMC622", "NMC811", "LCO"]:
        assert not res[pk].identifiable
        assert NOTE_NON_IDENTIFIABLE in res[pk].note
        assert res[pk].block == "ventilation"


def test_note_carbone_est_conservee():
    A, _, keys = stoichiometry_matrix()
    res = {r.key: r for r in evaluate(_lot_test(keys), A, standard_functionals(keys))}
    assert "texturales" in res["C_total"].note


def test_format_value_ferme_vs_domaine():
    A, _, keys = stoichiometry_matrix()
    res = {r.key: r for r in evaluate(_lot_test(keys), A, standard_functionals(keys))}
    assert "\u2013" not in res["cathodes_totales"].format_value()
    assert "\u2013" in res["NMC622"].format_value()


def test_evaluate_refuse_une_dimension_incoherente():
    A, _, keys = stoichiometry_matrix()
    with pytest.raises(ValueError):
        evaluate(np.zeros(3), A, standard_functionals(keys))


def test_gigafactory_tout_est_ferme():
    A, _, keys = stoichiometry_matrix(phase_keys=LISTE_GIGA)
    res = evaluate(_lot_test(keys), A, standard_functionals(keys))
    assert all(r.identifiable for r in res)
    assert analyse(A, keys).is_well_posed


# ==========================================================================
# 6. Non-regression : plafond de masse et solutions bruitees
# ==========================================================================

def test_bornes_calculables_quand_la_solution_depasse_le_plafond():
    """
    Regression. Sous bruit, le solveur peut sortir a 100,3 %. Les directions
    nulles sommant a ~1e-16, la contrainte de masse devenait 0 <= -0,003,
    donc infaisable, et la fonction renvoyait un intervalle infini.
    """
    A, _, keys = stoichiometry_matrix()
    x = _lot_test(keys)
    x = x / x.sum() * 1.005              # 100,5 % : depassement volontaire
    N = null_space(A)
    for f in standard_functionals(keys):
        lo, hi = compatible_bounds(x, N, f.c)
        assert np.isfinite(lo) and np.isfinite(hi), f.key
        # tolerance des DEUX cotes, sinon elle s'annule dans la comparaison
        assert lo - 1e-9 <= float(f.c @ x) <= hi + 1e-9, f.key


def test_x0_appartient_toujours_a_son_propre_domaine():
    """Le domaine est defini relativement a x0 : x0 ne peut en etre exclu."""
    A, _, keys = stoichiometry_matrix()
    N = null_space(A)
    for facteur in (0.80, 1.00, 1.02):
        x = _lot_test(keys)
        x = x / x.sum() * facteur
        for f in standard_functionals(keys):
            lo, hi = compatible_bounds(x, N, f.c)
            assert lo - 1e-9 <= float(f.c @ x) <= hi + 1e-9


def test_une_infaisabilite_est_levee_et_non_masquee():
    """Une anomalie doit echouer bruyamment, pas produire un intervalle faux."""
    from klastos.identifiability import UnboundedCompatibleSet
    assert issubclass(UnboundedCompatibleSet, RuntimeError)