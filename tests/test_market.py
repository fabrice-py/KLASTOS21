"""Tests de klastos/market.py.

Invariant d'architecture : aucun prix ne vit dans le code. Les instantanes
sont charges depuis `data/`, avec source, date et base de cotation.
"""

import datetime as dt
import pathlib

import pytest

from klastos.market import (DATA_DIR, LB_PER_TONNE, LI_FRACTION_IN_LI2CO3,
                            MAX_PAYABLE_AGE_DAYS, MAX_PRICE_AGE_DAYS,
                            REFERENCE_SPECS, CallablePriceProvider,
                            MetalPrice, MissingPriceError,
                            NotAProductionSourceError, PayableTerms, PriceSet,
                            Specification, StalePriceError, demo_payable_terms,
                            demo_price_set, load_payable_terms, load_price_set)
from klastos.generator import NoiseModel, make_lot
from klastos.uncertainty import UncertaintyConfig, propagate
from klastos.valuation import value_lot

AUJOURDHUI = dt.date(2026, 9, 7)
REFERENCE_TERMS = demo_payable_terms()

# Jeu frais et declare source de production, pour isoler le verrou teste.
REFERENCE_PRICES = PriceSet(
    currency="USD",
    label="jeu de test",
    is_production_source=True,
    prices={
        "Ni": MetalPrice("Ni", 16811.13, "USD", dt.date(2026, 9, 4),
                         "test", "LME Ni cash official"),
        "Co": MetalPrice("Co", 52359.78, "USD", dt.date(2026, 9, 4),
                         "test", "Co standard grade Rotterdam"),
    },
)
BRUIT = NoiseModel(rel_sigma=0.03, abs_sigma=2e-4, lod=0.0)


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
# 1. Les prix sont des donnees sourcees et datees
# ==========================================================================

def test_chaque_prix_porte_source_et_date():
    for metal, p in demo_price_set().prices.items():
        assert p.source.strip(), metal
        assert p.reference_name.strip(), metal
        assert isinstance(p.as_of, dt.date), metal
        assert p.value_per_tonne > 0, metal


def test_les_prix_de_reference_sont_frais_a_la_date_de_capture():
    assert demo_price_set().stale(AUJOURDHUI) == []


def test_le_jeu_de_prix_est_declare_comme_demonstration():
    ps = demo_price_set()
    assert "demonstration" in ps.label.lower()
    assert ps.is_production_source is False


def test_devises_heterogenes_rejetees():
    mauvais = PriceSet(
        currency="USD",
        prices={"Ni": MetalPrice("Ni", 1.0, "EUR", AUJOURDHUI, "s", "r")},
    )
    with pytest.raises(ValueError):
        mauvais.check_currency()


def test_prix_manquant_leve_une_erreur():
    with pytest.raises(MissingPriceError):
        demo_price_set().get("Pt")


# ==========================================================================
# 2. Peremption : verrou commercial
# ==========================================================================

def test_un_prix_perime_bloque_la_valorisation(rapport):
    vieux = PriceSet(
        currency="USD",
        is_production_source=True,      # on isole le verrou de FRAICHEUR
        prices={
            "Ni": MetalPrice("Ni", 16000.0, "USD",
                             AUJOURDHUI - dt.timedelta(days=90), "s", "r"),
            "Co": MetalPrice("Co", 52000.0, "USD",
                             AUJOURDHUI - dt.timedelta(days=90), "s", "r"),
        },
    )
    with pytest.raises(StalePriceError):
        value_lot(rapport, prices=vieux, terms=_termes_frais(),
                  today=AUJOURDHUI, allow_stale=False)


def test_des_conditions_perimees_bloquent_la_valorisation(rapport):
    with pytest.raises(StalePriceError):
        value_lot(rapport, prices=REFERENCE_PRICES,
                  terms=REFERENCE_TERMS["exw_europe"], today=AUJOURDHUI)


def test_le_mode_demonstration_avertit_au_lieu_de_bloquer(rapport):
    v = value_lot(rapport, prices=REFERENCE_PRICES,
                  terms=REFERENCE_TERMS["exw_europe"],
                  today=AUJOURDHUI, allow_stale=True)
    assert any("perimees" in w for w in v.warnings)


def test_toutes_les_conditions_livrees_sont_signalees_non_validees():
    for cle, t in REFERENCE_TERMS.items():
        assert t.validated is False, cle
        assert "PERIME" in t.note, cle


def test_les_seuils_d_anciennete_sont_coherents():
    assert 0 < MAX_PRICE_AGE_DAYS < MAX_PAYABLE_AGE_DAYS



# ==========================================================================
# 7. Aucun prix ne vit dans le code
# ==========================================================================

def test_aucun_jeu_de_prix_n_est_defini_dans_le_module():
    """
    Verrou d'architecture. Le marche varie trop pour qu'un prix vive dans du
    code : un litteral partirait dans le depot et se livrerait avec le paquet.
    Les prix ne peuvent entrer que par `load_price_set` ou un PriceProvider.
    """
    import klastos.market as m

    for nom in dir(m):
        obj = getattr(m, nom)
        assert not isinstance(obj, (PriceSet, MetalPrice, PayableTerms)), (
            f"{nom} est un objet de prix defini au niveau du module. "
            "Les prix doivent vivre dans data/, pas dans le code."
        )


def test_le_module_ne_contient_aucun_dictionnaire_de_prix():
    """Aucune structure nommee ne doit porter de valeurs monetaires."""
    import klastos.market as m

    for nom in dir(m):
        if not isinstance(getattr(m, nom), dict):
            continue
        for v in getattr(m, nom).values():
            assert not isinstance(v, (MetalPrice, PayableTerms)), nom


def test_value_lot_exige_des_prix_explicites():
    """Aucun jeu de prix par defaut : l'appelant declare sa source."""
    import inspect

    sig = inspect.signature(value_lot)
    assert sig.parameters["prices"].default is inspect.Parameter.empty
    assert sig.parameters["terms"].default is inspect.Parameter.empty


def test_une_source_de_demonstration_est_refusee_en_production(rapport):
    ps = demo_price_set()
    assert ps.is_production_source is False
    with pytest.raises(NotAProductionSourceError):
        value_lot(rapport, prices=ps, terms=_termes_frais(),
                  today=AUJOURDHUI, allow_stale=False)


def test_le_mode_demonstration_avertit_sur_la_source(rapport):
    v = value_lot(rapport, prices=demo_price_set(), terms=_termes_frais(),
                  today=AUJOURDHUI, allow_stale=True)
    assert any("non opposable" in w for w in v.warnings)


def test_chargement_depuis_fichier():
    ps = load_price_set(DATA_DIR / "prices_snapshot_2026-09-04.json")
    assert ps.currency == "USD"
    assert set(ps.prices) == {"Ni", "Co", "Li", "Cu"}
    assert ps.origin.endswith(".json")


def test_un_prix_sans_source_est_rejete(tmp_path):
    import json

    f = tmp_path / "p.json"
    f.write_text(json.dumps({
        "currency": "USD",
        "prices": {"Ni": {"value_per_tonne": 16000, "as_of": "2026-09-04"}},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="source"):
        load_price_set(f)


def test_un_fichier_sans_devise_est_rejete(tmp_path):
    import json

    f = tmp_path / "p.json"
    f.write_text(json.dumps({"prices": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="currency"):
        load_price_set(f)


def test_la_base_carbonate_est_declaree_dans_le_fichier():
    """La conversion Li2CO3 -> Li suit le champ `basis`, pas le nom de l'element."""
    ps = demo_price_set()
    assert ps.get("Li").basis == "Li2CO3"
    assert ps.get("Ni").basis == "metal"


def test_un_flux_de_production_se_branche(rapport):
    """Chemin d'integration reel : une fonction quelconque rendant un PriceSet."""
    def mon_flux() -> PriceSet:
        return PriceSet(
            currency="USD",
            label="flux de test",
            is_production_source=True,
            prices={
                "Ni": MetalPrice("Ni", 17000.0, "USD", AUJOURDHUI,
                                 "flux interne", "LME Ni cash"),
                "Co": MetalPrice("Co", 53000.0, "USD", AUJOURDHUI,
                                 "flux interne", "Co std grade"),
            },
        )

    fournisseur = CallablePriceProvider(mon_flux)
    v = value_lot(rapport, prices=fournisseur.fetch(), terms=_termes_frais(),
                  today=AUJOURDHUI)
    assert v.max_price_low > 0
    assert not any("non opposable" in w for w in v.warnings)


def test_un_fournisseur_qui_ne_rend_pas_un_priceset_est_rejete():
    with pytest.raises(TypeError):
        CallablePriceProvider(lambda: {"Ni": 17000}).fetch()


# ==========================================================================
# 8. Conversions d'unites et de base de cotation
# ==========================================================================

def test_conversion_carbonate_vers_lithium_contenu():
    """Li2CO3 contient environ 18,8 % de lithium."""
    assert LI_FRACTION_IN_LI2CO3 == pytest.approx(0.1879, abs=1e-3)


def test_conversion_livre_tonne():
    assert LB_PER_TONNE == pytest.approx(2204.62, abs=0.01)
    assert demo_price_set().get("Co").value_per_tonne == pytest.approx(
        23.75 * 2204.62, rel=1e-4
    )


