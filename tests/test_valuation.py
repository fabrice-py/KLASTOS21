"""Tests de klastos/valuation.py.

Deux invariants commerciaux :
  1. La valorisation ne repose QUE sur des grandeurs fermes.
  2. Aucun prix perime ni aucune source de demonstration ne peut fonder une
     valorisation opposable.
"""

import datetime as dt

import pytest

from klastos.generator import NoiseModel, make_lot
from klastos.market import (MetalPrice, PayableTerms, PriceSet,
                            REFERENCE_SPECS, Specification,
                            demo_payable_terms, demo_price_set)
from klastos.uncertainty import UncertaintyConfig, propagate
from klastos.valuation import value_lot

AUJOURDHUI = dt.date(2026, 9, 7)
BRUIT = NoiseModel(rel_sigma=0.03, abs_sigma=2e-4, lod=0.0)

REFERENCE_TERMS = demo_payable_terms()

# Jeu de prix propre aux tests : frais et declare source de production, pour
# que les tests d'arithmetique ne soient pas parasites par les verrous de
# fraicheur. Les verrous eux-memes sont testes dans test_market.py.
REFERENCE_PRICES = PriceSet(
    currency="USD",
    label="jeu de test",
    is_production_source=True,
    prices={
        "Ni": MetalPrice("Ni", 16811.13, "USD", dt.date(2026, 9, 4),
                         "test", "LME Ni cash official"),
        "Co": MetalPrice("Co", 52359.78, "USD", dt.date(2026, 9, 4),
                         "test", "Co standard grade Rotterdam"),
        "Li": MetalPrice("Li", 19750.0, "USD", dt.date(2026, 9, 4),
                         "test", "Carbonate de lithium", basis="Li2CO3"),
        "Cu": MetalPrice("Cu", 12841.84, "USD", dt.date(2026, 9, 4),
                         "test", "Cu cathode grade A"),
    },
)


@pytest.fixture(scope="module")
def rapport():
    lot = make_lot(rng=1, profile="mixed_ev", noise=BRUIT)
    return propagate(
        lot.b_measured, phase_keys=lot.phase_keys,
        config=UncertaintyConfig(noise=BRUIT, seed=0, n_draws=80,
                                 n_bound_draws=20),
    )


def _termes_frais(**kw):
    base = dict(
        market="test", payables={"Ni": 0.72, "Co": 0.72},
        as_of=AUJOURDHUI, source="test", validated=True,
    )
    base.update(kw)
    return PayableTerms(**base)


# ==========================================================================
# 3. La valorisation n'utilise que des grandeurs fermes
# ==========================================================================

def test_seules_les_teneurs_elementaires_sont_valorisees(rapport):
    v = value_lot(rapport, prices=REFERENCE_PRICES, terms=_termes_frais(), today=AUJOURDHUI)
    assert {c.element for c in v.contributions} <= {"Ni", "Co", "Li", "Cu"}
    for c in v.contributions:
        assert rapport.by_key()[f"el_{c.element}"].identifiable


def test_aucune_phase_non_identifiable_n_entre_dans_le_prix(rapport):
    """La ventilation NMC ne doit avoir aucun effet sur la valeur."""
    v = value_lot(rapport, prices=REFERENCE_PRICES, terms=_termes_frais(), today=AUJOURDHUI)
    for c in v.contributions:
        assert not c.element.startswith("NMC")
    assert v.max_price_low > 0


def test_la_degenerescence_est_signalee_sans_bloquer(rapport):
    v = value_lot(rapport, prices=REFERENCE_PRICES, terms=_termes_frais(), today=AUJOURDHUI)
    assert rapport.degeneracy > 0
    assert any("degenere" in w for w in v.warnings)


# ==========================================================================
# 4. Arithmetique de la valorisation
# ==========================================================================

def test_le_prix_maximal_suit_la_formule(rapport):
    cout, marge = 350.0, 0.15
    v = value_lot(rapport, prices=REFERENCE_PRICES, terms=_termes_frais(), today=AUJOURDHUI,
                  processing_cost=cout, margin_rate=marge)
    assert v.max_price_low == pytest.approx(v.gross_low * (1 - marge) - cout)
    assert v.max_price_high == pytest.approx(v.gross_high * (1 - marge) - cout)


def test_la_contribution_suit_teneur_prix_payable(rapport):
    v = value_lot(rapport, prices=REFERENCE_PRICES, terms=_termes_frais(), today=AUJOURDHUI)
    for c in v.contributions:
        assert c.value_low == pytest.approx(
            c.grade_low * c.price_per_tonne * c.payable
        )
        assert c.value_high >= c.value_low


def test_la_valeur_est_une_fourchette_pas_un_point(rapport):
    v = value_lot(rapport, prices=REFERENCE_PRICES, terms=_termes_frais(), today=AUJOURDHUI)
    assert v.gross_high > v.gross_low
    assert v.spread > 0
    assert "\u2013" in v.format_max_price()


def test_un_payable_plus_eleve_augmente_la_valeur(rapport):
    bas = value_lot(rapport, prices=REFERENCE_PRICES, terms=_termes_frais(payables={"Ni": 0.50}),
                    today=AUJOURDHUI)
    haut = value_lot(rapport, prices=REFERENCE_PRICES, terms=_termes_frais(payables={"Ni": 0.80}),
                     today=AUJOURDHUI)
    assert haut.gross_low > bas.gross_low


def test_un_element_payable_absent_du_rapport_est_signale(rapport):
    v = value_lot(rapport, prices=REFERENCE_PRICES, terms=_termes_frais(payables={"Ni": 0.7, "Pt": 0.5}),
                  today=AUJOURDHUI)
    assert any("Pt" in w for w in v.warnings)


# ==========================================================================
# 5. Conformite a la specification
# ==========================================================================

def test_specification_detecte_les_depassements():
    spec = REFERENCE_SPECS["ncm_cif_coree"]
    ecarts = spec.check({"Ni": 0.20, "Co": 0.08, "Li": 0.04,
                         "Cu": 0.027, "Al": 0.034})
    assert len(ecarts) == 2
    assert any("Cu" in e for e in ecarts)
    assert any("Al" in e for e in ecarts)


def test_specification_detecte_un_minimum_non_atteint():
    spec = REFERENCE_SPECS["ncm_cif_coree"]
    assert any("sous le minimum" in e for e in spec.check({"Ni": 0.05}))


def test_lot_conforme_sans_ecart():
    spec = REFERENCE_SPECS["ncm_cif_coree"]
    assert spec.check({"Ni": 0.20, "Co": 0.08, "Li": 0.04,
                       "Cu": 0.01, "Al": 0.01}) == []


def test_element_absent_du_bulletin_n_est_pas_penalise():
    spec = Specification("t", {"Zz": (0.1, 0.2)}, source="test")
    assert spec.check({"Ni": 0.2}) == []


def test_la_non_conformite_est_remontee_dans_la_valorisation(rapport):
    v = value_lot(rapport, prices=REFERENCE_PRICES, terms=_termes_frais(),
                  spec=REFERENCE_SPECS["ncm_cif_coree"], today=AUJOURDHUI)
    if v.spec_deviations:
        assert not v.is_conforme
        assert any("non conforme" in w for w in v.warnings)


# ==========================================================================
# 6. Tracabilite
# ==========================================================================

def test_chaque_contribution_est_tracee(rapport):
    v = value_lot(rapport, prices=REFERENCE_PRICES, terms=_termes_frais(), today=AUJOURDHUI)
    assert len(v.provenance) == len(v.contributions)
    for ligne in v.provenance:
        assert "%" in ligne and "/t" in ligne


def test_le_bouclage_amont_est_remonte():
    lot = make_lot(rng=6, profile="mixed_ev", noise=BRUIT, closure=0.90)
    rep = propagate(lot.b_measured, phase_keys=lot.phase_keys,
                    config=UncertaintyConfig(noise=BRUIT, seed=0, n_draws=40,
                                             n_bound_draws=10))
    v = value_lot(rep, prices=REFERENCE_PRICES, terms=_termes_frais(), today=AUJOURDHUI)
    # LE DIAGNOSTIC REMONTE, MAIS SANS SA PROSE.
    #
    # `value_lot` recopiait le message francais du solveur dans ses
    # avertissements. Depuis que le rapport rend ce message depuis le
    # STATUT, dans la langue du document, cette copie produisait un
    # avertissement EN DOUBLE - et en francais dans un rapport anglais,
    # begayant : « Bouclage massique : Bouclage massique degrade : ... ».
    #
    # L'intention du test reste : le bouclage amont doit etre PORTE jusqu'au
    # consommateur de la valorisation. Il l'est, par le statut, qui est la
    # donnee - la prose appartient au rendu.
    assert v.meta["closure_status"] in ("alerte", "rejet")
    assert not any("Bouclage massique :" in w for w in v.warnings), (
        "le message de bouclage est de nouveau recopie en double")


def test_le_lithium_inclus_dans_ni_co_est_signale(rapport):
    v = value_lot(rapport, prices=REFERENCE_PRICES, terms=_termes_frais(lithium_included_in_ni_co=True),
                  today=AUJOURDHUI)
    assert any("lithium" in w.lower() for w in v.warnings)


