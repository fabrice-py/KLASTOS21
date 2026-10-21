"""Tests de klastos/provenance.py.

Le test critique est `test_sans_attestation_aucune_exclusion` : il verrouille
la decision 3. Il ne doit jamais etre assoupli.
"""

import pytest

from klastos.phases import PHASE_KEYS
from klastos import i18n
from klastos.provenance import PROVENANCE_PROFILES, ProvenanceDeclaration


def test_profil_inconnu_leve_une_erreur():
    with pytest.raises(KeyError):
        ProvenanceDeclaration("mars").resolve()


def test_defaut_est_non_declare():
    d = ProvenanceDeclaration()
    retained, excluded, journal = d.resolve()
    assert retained == PHASE_KEYS
    assert excluded == []
    assert any("Aucune exclusion" in l for l in journal)


@pytest.mark.parametrize("profil", ["vehicule_electrique", "stationnaire", "deee"])
def test_sans_attestation_aucune_exclusion(profil):
    """DECISION 3 : la declaration seule ne suffit jamais."""
    d = ProvenanceDeclaration(profil, attested=False)
    retained, excluded, journal = d.resolve()
    assert excluded == []
    assert retained == PHASE_KEYS
    assert any("ATTESTATION NON FOURNIE" in l for l in journal)


@pytest.mark.parametrize("profil", ["vehicule_electrique", "stationnaire"])
def test_ve_et_stationnaire_excluent_lco_et_lmo_si_atteste(profil):
    d = ProvenanceDeclaration(profil, attested=True)
    retained, excluded, journal = d.resolve()
    assert set(excluded) == {"LCO", "LMO"}
    assert "LCO" not in retained and "LMO" not in retained
    assert any("Attestation client fournie" in l for l in journal)


def test_profil_non_valide_leve_un_avertissement():
    d = ProvenanceDeclaration("deee", attested=True)
    _, excluded, journal = d.resolve()
    assert set(excluded) == {"NMC532", "NMC811"}
    # Par le CATALOGUE : le journal est traduit, et « A VALIDER » y est
    # desormais accentue - « A VALIDER » en francais, « TO BE VALIDATED »
    # en anglais. Un texte fige ici ne tiendrait ni l'accent ni la langue.
    attendu = i18n.t("journal.provenance.profil_non_valide", "fr")
    assert any(attendu == l for l in journal)
    assert PROVENANCE_PROFILES["deee"].validated is False


def test_gigafactory_exclut_les_grades_non_declares():
    d = ProvenanceDeclaration(
        "chutes_gigafactory", attested=True, declared_grades=("NMC622", "NMC811")
    )
    retained, excluded, _ = d.resolve()
    assert set(excluded) == {"NMC111", "NMC532"}
    assert "NMC622" in retained and "NMC811" in retained
    assert "LCO" in retained  # non concerne par ce profil


def test_gigafactory_sans_grades_declares_ne_restreint_rien():
    d = ProvenanceDeclaration("chutes_gigafactory", attested=True)
    retained, excluded, _ = d.resolve()
    assert excluded == []
    assert retained == PHASE_KEYS


def test_tous_les_profils_atteste_ont_un_texte_d_attestation():
    for key, prof in PROVENANCE_PROFILES.items():
        if prof.excluded_phases or key == "chutes_gigafactory":
            assert prof.attestation_text.strip(), key