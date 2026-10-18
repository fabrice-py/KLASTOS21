"""Tests de klastos/providers.py.

Trois exigences structurantes :
  1. Une unite n'est jamais devinee : elle est declaree ou la lecture echoue.
  2. Une panne de source ne doit pas interrompre le service.
  3. La provenance de chaque prix est tracee, y compris apres repli.
"""

import datetime as dt
import json

import pytest

from klastos.market import DATA_DIR
from klastos.valuation import value_lot
from klastos.providers import (AggregatingProvider, CachingProvider,
                               CSVProvider, HTTPProvider, JSONFileProvider,
                               ManualEntryProvider, ProviderError, RawQuote,
                               build_price_set)
from klastos.units import ImplausiblePriceError, PriceUnit

AUJ = dt.date(2026, 9, 4)


def _quote(metal="Ni", value=16811.13, unit=PriceUnit.PER_TONNE, **kw):
    base = dict(currency="USD", as_of=AUJ, source="test",
                reference_name=f"{metal} ref")
    base.update(kw)
    return RawQuote(metal=metal, value=value, unit=unit, **base)


# ==========================================================================
# 1. Cotation brute et normalisation
# ==========================================================================

def test_conversion_vers_prix_a_la_tonne():
    p = _quote("Co", 23.75, PriceUnit.PER_POUND).to_metal_price()
    assert p.value_per_tonne == pytest.approx(52359.8, abs=1)
    assert "Converti depuis" in p.note


def test_pas_de_mention_de_conversion_si_deja_en_tonnes():
    assert "Converti" not in _quote().to_metal_price().note


def test_un_prix_implausible_est_refuse():
    with pytest.raises(ImplausiblePriceError):
        _quote("Ni", 0.5191, PriceUnit.PER_TONNE).to_metal_price()


def test_la_base_de_cotation_est_transmise():
    p = _quote("Li", 19750.0, basis="Li2CO3").to_metal_price()
    assert p.basis == "Li2CO3"


def test_devise_heterogene_refusee():
    with pytest.raises(ProviderError, match="explicite"):
        build_price_set([_quote(currency="EUR")], label="x", currency="USD")


def test_jeu_vide_refuse():
    with pytest.raises(ProviderError):
        build_price_set([], label="x")


# ==========================================================================
# 2. CSV : le format que deposera le client
# ==========================================================================

def _ecrire_csv(tmp_path, lignes, entete=None):
    entete = entete or ("metal,value,unit,currency,as_of,source,"
                        "reference_name,basis")
    f = tmp_path / "prix.csv"
    f.write_text(entete + "\n" + "\n".join(lignes), encoding="utf-8")
    return f


def test_lecture_csv(tmp_path):
    f = _ecrire_csv(tmp_path, [
        "Ni,16811.13,USD/t,USD,2026-09-04,Client,LME Ni cash,metal",
        "Co,23.75,USD/lb,USD,2026-09-04,Client,Co std Rotterdam,metal",
        "Li,19750,USD/t,USD,2026-09-04,Client,Carbonate,Li2CO3",
    ])
    ps = build_price_set(CSVProvider(f).quotes(), label="client", currency="USD")
    assert ps.get("Co").value_per_tonne == pytest.approx(52359.8, abs=1)
    assert ps.get("Li").basis == "Li2CO3"


def test_csv_unite_inconnue_refusee(tmp_path):
    f = _ecrire_csv(tmp_path, [
        "Ni,16811,dollars la tonne,USD,2026-09-04,Client,LME,metal",
    ])
    with pytest.raises(ProviderError, match="jamais deduite"):
        CSVProvider(f).quotes()


def test_csv_colonne_manquante_refusee(tmp_path):
    f = _ecrire_csv(tmp_path, ["Ni,16811,,USD,2026-09-04,Client,LME,metal"])
    with pytest.raises(ProviderError, match="colonnes absentes"):
        CSVProvider(f).quotes()


def test_csv_absent_refuse(tmp_path):
    with pytest.raises(ProviderError, match="absent"):
        CSVProvider(tmp_path / "inexistant.csv").quotes()


def test_csv_le_numero_de_ligne_est_indique(tmp_path):
    f = _ecrire_csv(tmp_path, [
        "Ni,16811.13,USD/t,USD,2026-09-04,Client,LME,metal",
        "Co,23.75,USD/oncetroy,USD,2026-09-04,Client,Co,metal",
    ])
    with pytest.raises(ProviderError, match="ligne 3"):
        CSVProvider(f).quotes()


# ==========================================================================
# 3. Saisie manuelle : tracabilite de l'operateur
# ==========================================================================

def test_la_saisie_manuelle_enregistre_l_operateur():
    q = ManualEntryProvider([_quote()], operator="F. Ndongo").quotes()
    assert "saisi par F. Ndongo" in q[0].source


def test_saisie_manuelle_sans_operateur_refusee():
    with pytest.raises(ProviderError, match="identite de l'operateur"):
        ManualEntryProvider([_quote()], operator="  ").quotes()


# ==========================================================================
# 4. HTTP : unite declaree a la configuration, reseau injecte
# ==========================================================================

def _faux_reseau(payload):
    return lambda url: payload


def test_lecture_http_avec_conversion_once_troy():
    """Cas reel : une API cotant le nickel LME par once troy."""
    payload = {"date": "2026-09-04", "rates": {"LME-NI": 0.5191}}
    p = HTTPProvider(
        url="https://exemple.test/latest",
        mapping={"Ni": {"path": ["rates", "LME-NI"],
                        "unit": PriceUnit.PER_TROY_OUNCE,
                        "reference_name": "LME Nickel"}},
        fetcher=_faux_reseau(payload),
        source_label="agregateur",
    )
    ps = build_price_set(p.quotes(), label="http")
    assert ps.get("Ni").value_per_tonne == pytest.approx(16689.0, abs=5)


def test_http_sans_unite_declaree_refuse():
    p = HTTPProvider(
        url="u", mapping={"Ni": {"path": ["rates", "NI"]}},
        fetcher=_faux_reseau({"date": "2026-09-04", "rates": {"NI": 1.0}}),
        source_label="s",
    )
    with pytest.raises(ProviderError, match="sans unite declaree"):
        p.quotes()


def test_http_chemin_absent_refuse():
    p = HTTPProvider(
        url="u",
        mapping={"Ni": {"path": ["rates", "ABSENT"],
                        "unit": PriceUnit.PER_TONNE}},
        fetcher=_faux_reseau({"date": "2026-09-04", "rates": {}}),
        source_label="s",
    )
    with pytest.raises(ProviderError, match="absent de la reponse"):
        p.quotes()


def test_http_panne_reseau_convertie_en_erreur_lisible():
    def tombe(url):
        raise ConnectionError("timeout")

    p = HTTPProvider(url="u", mapping={}, fetcher=tombe, source_label="flux X")
    with pytest.raises(ProviderError, match="injoignable"):
        p.quotes()


# ==========================================================================
# 5. Agregation : ordre de preference et journal
# ==========================================================================

class _Fournisseur:
    def __init__(self, name, quotes=None, exc=None):
        self.name, self._q, self._exc = name, quotes or [], exc

    def quotes(self):
        if self._exc:
            raise self._exc
        return self._q


def test_le_premier_fournisseur_l_emporte():
    ag = AggregatingProvider([
        _Fournisseur("client", [_quote("Ni", 17000.0)]),
        _Fournisseur("public", [_quote("Ni", 16000.0), _quote("Co", 52000.0)]),
    ])
    ps = build_price_set(ag.quotes(), label="x")
    assert ps.get("Ni").value_per_tonne == 17000.0
    assert ag.ledger.served == {"Ni": "client", "Co": "public"}


def test_une_panne_n_interrompt_pas_la_chaine():
    ag = AggregatingProvider([
        _Fournisseur("flux", exc=ProviderError("503")),
        _Fournisseur("cache", [_quote("Ni")]),
    ])
    assert len(ag.quotes()) == 1
    assert ag.ledger.served == {"Ni": "cache"}
    assert any("flux" in e for e in ag.ledger.failures)


def test_un_metal_requis_manquant_interrompt():
    ag = AggregatingProvider([_Fournisseur("f", [_quote("Ni")])],
                             required=("Ni", "Co"))
    with pytest.raises(ProviderError, match="Co"):
        ag.quotes()


def test_aucun_fournisseur_disponible():
    ag = AggregatingProvider([_Fournisseur("f", exc=ProviderError("ko"))])
    with pytest.raises(ProviderError, match="Aucun fournisseur"):
        ag.quotes()


def test_le_journal_est_lisible():
    ag = AggregatingProvider([
        _Fournisseur("a", exc=ProviderError("ko")),
        _Fournisseur("b", [_quote("Ni")]),
    ])
    ag.quotes()
    lignes = ag.ledger.lines()
    assert any("Ni : fourni par b" in l for l in lignes)
    assert any("echec" in l for l in lignes)


# ==========================================================================
# 6. Cache : le client attend son rapport
# ==========================================================================

def test_le_cache_est_ecrit_puis_relu(tmp_path):
    c = CachingProvider(_Fournisseur("flux", [_quote("Co", 23.75,
                                                     PriceUnit.PER_POUND)]),
                        cache_path=tmp_path / "c.json")
    c.quotes()
    assert c.served_from_cache is False
    assert (tmp_path / "c.json").exists()

    c.provider = _Fournisseur("flux", exc=ProviderError("panne"))
    q = c.quotes()
    assert c.served_from_cache is True
    assert q[0].unit is PriceUnit.PER_POUND        # l'unite survit au cache
    assert q[0].value == pytest.approx(23.75)


def test_le_cache_signale_son_origine(tmp_path):
    c = CachingProvider(_Fournisseur("flux", [_quote()]),
                        cache_path=tmp_path / "c.json")
    c.quotes()
    c.provider = _Fournisseur("flux", exc=ProviderError("panne"))
    assert "servi depuis le cache" in c.quotes()[0].source


def test_le_cache_conserve_la_date_d_origine(tmp_path):
    """Les verrous d'anciennete doivent s'appliquer au contenu du cache."""
    vieux = _quote(as_of=dt.date(2026, 1, 1))
    c = CachingProvider(_Fournisseur("flux", [vieux]),
                        cache_path=tmp_path / "c.json")
    c.quotes()
    c.provider = _Fournisseur("flux", exc=ProviderError("panne"))
    assert c.quotes()[0].as_of == dt.date(2026, 1, 1)


def test_cache_absent_et_source_en_panne(tmp_path):
    c = CachingProvider(_Fournisseur("f", exc=ProviderError("ko")),
                        cache_path=tmp_path / "vide.json")
    with pytest.raises(ProviderError, match="Aucun cache"):
        c.quotes()


# ==========================================================================
# 7. Chaine complete jusqu'a la valorisation
# ==========================================================================

def test_chaine_complete_client_puis_public(tmp_path):
    from klastos.generator import NoiseModel, make_lot
    from klastos.market import PayableTerms
    from klastos.uncertainty import UncertaintyConfig, propagate

    f = _ecrire_csv(tmp_path, [
        "Co,23.75,USD/lb,USD,2026-09-04,Fastmarkets (client),Co std,metal",
    ])
    public = HTTPProvider(
        url="u",
        mapping={"Ni": {"path": ["rates", "LME-NI"],
                        "unit": PriceUnit.PER_TROY_OUNCE,
                        "reference_name": "LME Nickel"}},
        fetcher=_faux_reseau({"date": "2026-09-04", "rates": {"LME-NI": 0.5191}}),
        source_label="agregateur public",
    )
    ag = AggregatingProvider([CSVProvider(f), public], required=("Ni", "Co"))
    ps = build_price_set(ag.quotes(), label="chaine", is_production_source=True)

    bruit = NoiseModel(rel_sigma=0.03, abs_sigma=2e-4, lod=0.0)
    lot = make_lot(rng=1, profile="mixed_ev", noise=bruit)
    rep = propagate(lot.b_measured, phase_keys=lot.phase_keys,
                    config=UncertaintyConfig(noise=bruit, seed=0, n_draws=40,
                                             n_bound_draws=10))
    v = value_lot(
        rep, prices=ps,
        terms=PayableTerms(market="t", payables={"Ni": 0.72, "Co": 0.72},
                           as_of=AUJ, source="t", validated=True),
        today=dt.date(2026, 9, 7),
    )
    assert v.max_price_low > 0
    assert ag.ledger.served == {"Co": "csv", "Ni": "http"}


def test_instantane_json_livre_lisible_par_le_fournisseur():
    q = JSONFileProvider(DATA_DIR / "prices_snapshot_2026-09-04.json").quotes()
    assert {x.metal for x in q} == {"Ni", "Co", "Li", "Cu"}
    assert all(x.unit is PriceUnit.PER_TONNE for x in q)
