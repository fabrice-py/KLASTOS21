"""Tests de klastos/phases.py et klastos/elements.py."""

import numpy as np
import pytest

from klastos.elements import ATOMIC_MASS, ELEMENTS, formula_mass
from klastos.phases import (CATHODE_GROUPS, MOLAR_MASS, PHASE_KEYS, PHASES,
                            cathode_indicator, group_indicator, indicator,
                            nmc_lco_indicator, stoichiometry_matrix)


def test_formula_mass_connu():
    # LiCoO2 : 6.94 + 58.933194 + 2*15.999
    assert formula_mass({"Li": 1, "Co": 1, "O": 2}) == pytest.approx(97.871194, abs=1e-6)


def test_formula_mass_element_inconnu():
    with pytest.raises(KeyError):
        formula_mass({"Xx": 1.0})


def test_toutes_les_phases_ont_des_elements_connus():
    for key, ph in PHASES.items():
        assert set(ph["composition"]) <= set(ATOMIC_MASS), key
        assert set(ph["composition"]) <= set(ELEMENTS), key


def test_conservation_de_la_masse():
    """Chaque colonne de A doit sommer a 1 : c'est le test de non-regression
    le plus important du projet. S'il casse, la stoechiometrie est fausse."""
    A, _, keys = stoichiometry_matrix()
    sommes = A.sum(axis=0)
    for k, s in zip(keys, sommes):
        assert s == pytest.approx(1.0, abs=1e-12), f"{k} somme a {s}"


def test_matrice_positive():
    A, _, _ = stoichiometry_matrix()
    assert np.all(A >= 0.0)


def test_nmc_stoechiometrie_ni_mn_co():
    """Pour tout NMC, Ni + Mn + Co = 1 mole par mole de Li."""
    for key in ["NMC111", "NMC532", "NMC622", "NMC811"]:
        c = PHASES[key]["composition"]
        assert c["Ni"] + c["Mn"] + c["Co"] == pytest.approx(1.0)
        assert c["Li"] == pytest.approx(1.0)


def test_masses_molaires_ordre_de_grandeur():
    assert MOLAR_MASS["LFP"] == pytest.approx(157.755, abs=0.01)
    assert MOLAR_MASS["LiPF6"] == pytest.approx(151.904, abs=0.01)
    for k in ["NMC111", "NMC532", "NMC622", "NMC811"]:
        assert 96.0 < MOLAR_MASS[k] < 98.0


def test_restriction_de_phases():
    keys = [k for k in PHASE_KEYS if k not in ("LCO", "LMO")]
    A, _, kept = stoichiometry_matrix(phase_keys=keys)
    assert A.shape[1] == len(PHASE_KEYS) - 2
    assert "LCO" not in kept


def test_phase_inconnue_leve_une_erreur():
    with pytest.raises(KeyError):
        stoichiometry_matrix(phase_keys=["NMC622", "PHASE_BIDON"])


def test_indicateurs():
    ind = indicator(["NMC622", "LFP"])
    assert ind.sum() == 2.0
    assert group_indicator("NMC").sum() == 4.0
    assert cathode_indicator().sum() == 8.0          # 4 NMC + NCA + LCO + LFP + LMO
    assert nmc_lco_indicator().sum() == 5.0          # 4 NMC + LCO


def test_indicateurs_suivent_la_restriction():
    keys = [k for k in PHASE_KEYS if k not in ("LCO", "LMO")]
    assert nmc_lco_indicator(phase_keys=keys).sum() == 4.0
    assert cathode_indicator(phase_keys=keys).sum() == 6.0
    assert len(cathode_indicator(phase_keys=keys)) == len(keys)