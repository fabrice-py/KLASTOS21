"""Tests de klastos/generator.py.

L'invariant fondateur est `test_bulletin_exact_sans_bruit` : sans bruit, le
bulletin doit valoir exactement A @ x_true. Si ce test casse, toute la
validation du solveur repose sur du sable.
"""

import numpy as np
import pytest
import pytest

from klastos.generator import (COMPOSITION_PROFILES, DEFAULT_NOISE, NOISE_FREE,
                               CompositionProfile, NoiseModel, make_batch,
                               make_lot, sample_mixture, unvalidated_profiles)
from klastos.phases import PHASE_KEYS, stoichiometry_matrix
from klastos.provenance import ProvenanceDeclaration

PROFILS = sorted(COMPOSITION_PROFILES)


# ==========================================================================
# 1. Coherence du tirage
# ==========================================================================

@pytest.mark.parametrize("profil", PROFILS)
def test_tirage_ferme_a_un(profil):
    x = sample_mixture(rng=0, profile=profil)
    assert x.sum() == pytest.approx(1.0, abs=1e-12)
    assert np.all(x >= 0.0)


@pytest.mark.parametrize("profil", PROFILS)
def test_closure_partielle_respectee(profil):
    x = sample_mixture(rng=1, profile=profil, closure=0.85)
    assert x.sum() == pytest.approx(0.85, abs=1e-12)


def test_closure_invalide_rejetee():
    for mauvaise in (0.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            sample_mixture(rng=0, closure=mauvaise)


def test_profil_inconnu_rejete():
    with pytest.raises(KeyError):
        sample_mixture(rng=0, profile="profil_bidon")


def test_profil_reference_une_phase_inconnue():
    faux = CompositionProfile("x", "x", {"PHASE_BIDON": (0.1, 0.2)})
    with pytest.raises(KeyError):
        sample_mixture(rng=0, profile=faux)


def test_liste_de_phases_incompatible_rejetee():
    """Un profil 100 % LCO tire sur une liste sans LCO n'a aucune phase."""
    prof = CompositionProfile("lco_pur", "LCO pur", {"LCO": (0.5, 0.6)})
    keys = [k for k in PHASE_KEYS if k != "LCO"]
    with pytest.raises(ValueError):
        sample_mixture(rng=0, profile=prof, phase_keys=keys)


# ==========================================================================
# 2. Exactitude stoechiometrique
# ==========================================================================

@pytest.mark.parametrize("profil", PROFILS)
def test_bulletin_exact_sans_bruit(profil):
    """INVARIANT FONDATEUR : b_true == A @ x_true a la precision machine."""
    A, _, keys = stoichiometry_matrix()
    lot = make_lot(rng=7, profile=profil, noise=NOISE_FREE)
    assert np.allclose(lot.b_true, A @ lot.x_true, atol=1e-14)
    assert np.allclose(lot.b_measured, lot.b_true, atol=1e-14)
    assert not lot.below_lod.any()


@pytest.mark.parametrize("profil", PROFILS)
def test_bilan_elementaire_ferme(profil):
    """La somme des elements egale la somme des phases (conservation)."""
    lot = make_lot(rng=3, profile=profil, noise=NOISE_FREE, closure=0.9)
    assert lot.b_true.sum() == pytest.approx(lot.x_true.sum(), abs=1e-12)
    assert lot.b_true.sum() == pytest.approx(0.9, abs=1e-12)


# ==========================================================================
# 3. Modele de bruit
# ==========================================================================

def test_bruit_reste_dans_un_ordre_de_grandeur_raisonnable():
    lot = make_lot(rng=11, profile="mixed_ev", noise=DEFAULT_NOISE)
    majeurs = lot.b_true > 0.01
    ecart = np.abs(lot.b_measured - lot.b_true)[majeurs] / lot.b_true[majeurs]
    assert np.all(ecart < 6 * DEFAULT_NOISE.rel_sigma)   # 6 sigma


def test_bulletin_jamais_negatif():
    for graine in range(30):
        lot = make_lot(rng=graine, profile="mixed_ev")
        assert np.all(lot.b_measured >= 0.0)


def test_censure_lod():
    fort = NoiseModel(rel_sigma=0.0, abs_sigma=0.0, lod=0.02)
    lot = make_lot(rng=5, profile="mixed_ev", noise=fort)
    assert lot.below_lod.any()
    assert np.all(lot.b_measured[lot.below_lod] == 0.0)
    bulletin = lot.as_bulletin()
    for i, el in enumerate(lot.elements):
        if lot.below_lod[i]:
            assert bulletin[el] == 0.0


def test_reproductibilite():
    a = make_lot(rng=123, profile="mixed_ev")
    b = make_lot(rng=123, profile="mixed_ev")
    assert np.allclose(a.x_true, b.x_true)
    assert np.allclose(a.b_measured, b.b_measured)


def test_graines_differentes_donnent_des_lots_differents():
    a = make_lot(rng=1, profile="mixed_ev")
    b = make_lot(rng=2, profile="mixed_ev")
    assert not np.allclose(a.x_true, b.x_true)


# ==========================================================================
# 4. Provenance : le generateur suit la liste restreinte
# ==========================================================================

def test_lot_ve_atteste_ne_contient_ni_lco_ni_lmo():
    keys, _, _ = ProvenanceDeclaration("vehicule_electrique", attested=True).resolve()
    lot = make_lot(rng=9, profile="mixed_ev", phase_keys=keys)
    assert "LCO" not in lot.phase_keys
    assert "LMO" not in lot.phase_keys
    assert lot.x_true.shape[0] == len(keys)


def test_lot_sans_attestation_garde_la_liste_large():
    keys, _, _ = ProvenanceDeclaration("vehicule_electrique", attested=False).resolve()
    lot = make_lot(rng=9, profile="mixed_ev", phase_keys=keys)
    assert lot.x_true.shape[0] == len(PHASE_KEYS)


# ==========================================================================
# 5. Attestation mensongere
# ==========================================================================

def test_contamination_simule_une_fausse_attestation():
    """Un lot declare VE qui contient en realite du LCO."""
    lot = make_lot(
        rng=13, profile="mixed_ev", noise=NOISE_FREE,
        contaminants={"LCO": 0.08},
    )
    assert lot.contains("LCO")
    assert lot.meta["contaminants"] == {"LCO": 0.08}
    A, _, _ = stoichiometry_matrix()
    assert np.allclose(lot.b_true, A @ lot.x_true, atol=1e-14)


def test_contamination_absente_de_la_liste_rejetee():
    keys, _, _ = ProvenanceDeclaration("vehicule_electrique", attested=True).resolve()
    with pytest.raises(KeyError):
        make_lot(rng=0, phase_keys=keys, contaminants={"LCO": 0.05})


def test_contamination_negative_rejetee():
    with pytest.raises(ValueError):
        make_lot(rng=0, contaminants={"LCO": -0.05})


def test_contamination_renormalise_si_depassement():
    lot = make_lot(rng=0, profile="mixed_ev", contaminants={"LCO": 0.30})
    assert lot.x_true.sum() <= 1.0 + 1e-9


# ==========================================================================
# 6. Lots imposes, series et dette technique
# ==========================================================================

def test_x_true_impose():
    A, _, keys = stoichiometry_matrix()
    x = np.zeros(len(keys))
    x[keys.index("NMC622")] = 0.4
    x[keys.index("C_total")] = 0.6
    lot = make_lot(x_true=x, noise=NOISE_FREE)
    assert lot.true_mixture() == {"NMC622": 40.0, "C_total": 60.0}


def test_x_true_de_mauvaise_dimension_rejete():
    with pytest.raises(ValueError):
        make_lot(x_true=np.zeros(3))


def test_make_batch_produit_des_lots_distincts():
    lots = make_batch(5, rng=17, profile="mixed_ev")
    assert len(lots) == 5
    assert not np.allclose(lots[0].x_true, lots[1].x_true)


def test_profils_non_valides_sont_traces():
    """Dette technique explicite : ces fourchettes ne sont pas arbitrees."""
    non_valides = unvalidated_profiles()
    assert "mixed_ev" in non_valides
    assert "degenerate_probe" not in non_valides
    lot = make_lot(rng=0, profile="mixed_ev")
    assert lot.meta["profile_validated"] is False


def test_l_erreur_relative_est_calibree_sur_une_reference_certifiee():
    """
    Dette soldee. L'incertitude elargie du LNE-LiB01 va de 10 a 15 % (k=2),
    soit 5 a 7,5 % d'incertitude type. On retient 6 %, milieu de fourchette.
    """
    assert DEFAULT_NOISE.validated is True
    assert DEFAULT_NOISE.rel_sigma == pytest.approx(0.06)
    assert 0.05 <= DEFAULT_NOISE.rel_sigma <= 0.075
    assert NOISE_FREE.validated is True


def test_la_source_de_calibration_est_citee_dans_le_module():
    """Aucun parametre numerique sans reference verifiable."""
    from klastos.generator import NoiseModel

    doc = NoiseModel.__doc__ or ""
    assert "LNE-LiB01" in doc
    assert "ISO 33405" in doc
    assert "lne.fr" in doc


def test_les_parametres_non_sources_restent_marques():
    """Le bruit de fond et la limite de detection ne sont pas arbitres."""
    from klastos.generator import NoiseModel

    doc = NoiseModel.__doc__ or ""
    assert "A VALIDER" in doc


def test_with_ranges_ne_mute_pas_l_original():
    base = COMPOSITION_PROFILES["mixed_ev"]
    variante = base.with_ranges(NMC811=(0.30, 0.40))
    assert variante.ranges["NMC811"] == (0.30, 0.40)
    assert base.ranges["NMC811"] == (0.00, 0.20)


# ==========================================================================
# 7. Qualification des donnees : le generateur n'est pas un oracle du reel
# ==========================================================================

def test_tout_lot_est_marque_synthetique():
    from klastos.generator import DATA_CLASS
    for profil in PROFILS:
        lot = make_lot(rng=0, profile=profil)
        assert lot.meta["data_class"] == DATA_CLASS
        assert lot.is_client_grade is False


def test_le_lot_porte_l_avertissement_et_l_engagement():
    from klastos.generator import REVISION_COMMITMENT, SYNTHETIC_WARNING
    lot = make_lot(rng=0)
    assert lot.meta["warning"] == SYNTHETIC_WARNING
    assert lot.meta["revision_commitment"] == REVISION_COMMITMENT
    assert "v1.1" in REVISION_COMMITMENT
    assert "livrable client" in SYNTHETIC_WARNING


def test_garde_fou_refuse_une_donnee_synthetique_en_contexte_client():
    """Verrou : aucune sortie du generateur ne peut atteindre un client."""
    from klastos.generator import (SyntheticDataInClientContext,
                                   assert_client_grade)
    lot = make_lot(rng=0)
    with pytest.raises(SyntheticDataInClientContext):
        assert_client_grade(lot)


def test_le_module_se_declare_outil_de_test_interne():
    """Le statut doit rester ecrit noir sur blanc dans l'en-tete du module."""
    import klastos.generator as g
    doc = g.__doc__ or ""
    assert "OUTIL DE TEST INTERNE" in doc
    assert "N'EST PAS UN ORACLE DU REEL" in doc
    assert "v1.1" in doc