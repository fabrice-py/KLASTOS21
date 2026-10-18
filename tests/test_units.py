"""Tests de klastos/units.py.

Le piege des onces troy est l'erreur la plus couteuse possible dans ce
projet : elle produit un facteur 32 150 sans aucun signe exterieur.
"""

import pytest

from klastos.units import (KG_PER_TONNE, LB_PER_TONNE, PLAUSIBILITY_BANDS,
                           TROY_OZ_PER_TONNE, ImplausiblePriceError,
                           PlausibilityBand, PriceUnit, check_plausible)


def test_facteurs_de_conversion():
    assert KG_PER_TONNE == 1000.0
    assert LB_PER_TONNE == pytest.approx(2204.6226, abs=1e-3)
    assert TROY_OZ_PER_TONNE == pytest.approx(32150.7466, abs=1e-3)


def test_conversion_livre_vers_tonne():
    """23,75 $/lb de cobalt correspond a environ 52 360 $/t."""
    assert PriceUnit.PER_POUND.to_per_tonne(23.75) == pytest.approx(52359.8, abs=1)


def test_conversion_once_troy_vers_tonne():
    """Une cotation LME a 0,5191 $/oz t correspond a environ 16 700 $/t."""
    assert PriceUnit.PER_TROY_OUNCE.to_per_tonne(0.5191) == pytest.approx(
        16689.0, abs=5
    )


def test_la_tonne_est_neutre():
    assert PriceUnit.PER_TONNE.to_per_tonne(16811.13) == 16811.13


@pytest.mark.parametrize("unite", list(PriceUnit))
def test_chaque_unite_a_un_libelle_et_un_facteur(unite):
    assert unite.label
    assert unite.units_per_tonne > 0


# ==========================================================================
# Bandes de plausibilite : filet contre les erreurs d'unite
# ==========================================================================

def test_un_prix_correct_passe():
    check_plausible("Ni", 16811.13)
    check_plausible("Co", 52359.78)
    check_plausible("Cu", 12841.84)


def test_oubli_de_conversion_refuse():
    """0,5191 pris pour un prix a la tonne : erreur d'un facteur 32 150."""
    with pytest.raises(ImplausiblePriceError):
        check_plausible("Ni", 0.5191)


def test_confusion_livre_once_refusee():
    with pytest.raises(ImplausiblePriceError):
        check_plausible("Ni", PriceUnit.PER_POUND.to_per_tonne(0.5191))


def test_double_conversion_refusee():
    with pytest.raises(ImplausiblePriceError):
        check_plausible("Ni", PriceUnit.PER_TROY_OUNCE.to_per_tonne(16811.13))


def test_erreur_de_facteur_mille_refusee():
    with pytest.raises(ImplausiblePriceError):
        check_plausible("Co", 52.36)          # $/kg pris pour $/t


def test_le_message_oriente_vers_l_unite():
    with pytest.raises(ImplausiblePriceError, match="unite de cotation"):
        check_plausible("Ni", 0.5191)


def test_metal_sans_bande_refuse_en_mode_strict():
    with pytest.raises(ImplausiblePriceError, match="Aucune bande"):
        check_plausible("Pt", 30000.0)


def test_metal_sans_bande_tolere_en_mode_souple():
    check_plausible("Pt", 30000.0, strict=False)


def test_toutes_les_bandes_sont_coherentes():
    for metal, band in PLAUSIBILITY_BANDS.items():
        assert 0 < band.low_per_tonne < band.high_per_tonne, metal
        assert band.rationale.strip(), metal


def test_les_bandes_sont_declarees_non_validees():
    """Dette technique : bornes anti-erreur, pas opinion de marche."""
    for metal, band in PLAUSIBILITY_BANDS.items():
        assert "A VALIDER" in band.rationale, metal


def test_bande_personnalisee():
    b = PlausibilityBand("X", 10.0, 20.0)
    b.check(15.0)
    with pytest.raises(ImplausiblePriceError):
        b.check(25.0)
