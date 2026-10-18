"""Tests de klastos/feeds.py.

Tout est teste HORS LIGNE : la fonction reseau est injectee et rejoue les
formats de reponse documentes par chaque agence. Aucun identifiant, aucun
appel sortant.

Quatre exigences :
  1. Les unites ne sont jamais devinees, et la bonne borne est retenue.
  2. Les identifiants viennent de l'environnement, jamais d'un argument.
  3. Un refus d'abonnement sort en message explicite.
  4. Le niveau d'autorisation de rediffusion est porte, pas suppose.
"""

import datetime as dt
import json

import pytest

from klastos.feeds import (CATALOGUE_PATH, BenchmarkFeed, CredentialsMissing,
                           FastmarketsFeed, FeedError, HttpResponse, SMMFeed,
                           load_catalogue, urllib_fetcher, _date, _unite)
from klastos.providers import build_price_set
from klastos.units import PriceUnit

# --------------------------------------------------------------------------
# Reponses rejouees, au format documente par chaque agence
# --------------------------------------------------------------------------

JETON_FM = {"access_token": "jeton-de-test", "expires_in": 3600,
            "token_type": "Bearer"}

PRIX_FM = {"instruments": [{
    "symbol": "MB-CO-0005",
    "firstDate": "2008-01-31T12:00:00+00:00",
    "lastDate": "2026-10-09T12:00:00+00:00",
    "prices": [{"date": "2026-10-09",
                "assessmentDate": "2026-10-09T12:00:00+00:00",
                "revision": 0, "low": 23.75, "mid": 25.45, "high": 27.15}],
}]}

PAYABLES_FM = {"instruments": [
    {"symbol": "MB-BMS-0004", "prices": [{"date": "2026-10-09", "mid": 61.25}]},
    {"symbol": "MB-BMS-0005", "prices": [{"date": "2026-10-09", "mid": 58.40}]},
]}

INSTRUMENTS_FM = {"instruments": [
    {"symbol": "MB-CO-0005", "description": "Cobalt standard grade"},
    {"symbol": "MB-BMS-0004", "description": "Black mass Ni payable"},
]}


def _bmi_marche(code, nom, valeur, unite="t", iosco=True):
    return {"$metadata": {"market": nom}, "data": [{
        "code": code, "name": nom, "isIoscoAssured": iosco,
        "unitOfMeasure": {"symbol": unite}, "currency": {"iso": "USD"},
        "summary": {"latestPublication": {
            "date": "2026-10-09", "valueLow": valeur * 0.98,
            "valueMid": valeur, "valueHigh": valeur * 1.02}},
    }]}


BMI = {
    "cobalt": _bmi_marche("BMICO001", "Cobalt Standard Grade", 52360.0),
    "lithium": _bmi_marche("BMILC004", "Lithium Carbonate Battery Grade", 19750.0),
    "nickel": _bmi_marche("BMINI001", "Nickel Class 1", 16811.0),
}


class Reseau:
    """Faux reseau, qui enregistre ce qui lui est demande."""

    def __init__(self, routes: dict, statut: int = 200):
        self.routes, self.statut = routes, statut
        self.appels: list[tuple[str, str, dict, str]] = []

    def __call__(self, url, method="GET", headers=None, body=None, timeout=20.0):
        self.appels.append((method, url, dict(headers or {}), body or ""))
        for motif, charge in self.routes.items():
            if motif in url:
                if isinstance(charge, HttpResponse):
                    return charge
                return HttpResponse(self.statut, json.dumps(charge))
        raise AssertionError(f"route non prevue : {url}")


def _fm(routes, **kw):
    return FastmarketsFeed(fetcher=Reseau(routes), service_key="k",
                           service_name="n", **kw)


# ==========================================================================
# 1. Catalogue : donnee, pas code
# ==========================================================================

def test_le_catalogue_est_un_fichier_de_donnees():
    assert CATALOGUE_PATH.exists()
    assert CATALOGUE_PATH.suffix == ".json"


def test_le_catalogue_couvre_les_trois_agences():
    c = load_catalogue()
    assert {"fastmarkets", "benchmark", "smm"} <= set(c)


def test_le_cobalt_retient_le_point_bas():
    """
    Les payables de black mass se referent au point bas du cobalt standard
    grade. Retenir le median surestimerait la valeur du lot.
    """
    c = load_catalogue()["fastmarkets"]["symbols"]["MB-CO-0005"]
    assert c["field"] == "low"
    assert c["unit"] == "USD/lb"
    assert c["metal"] == "Co"


def test_les_symboles_retires_sont_documentes():
    """Les payables EXW USA ont ete suspendus par Fastmarkets."""
    r = load_catalogue()["fastmarkets"]["retires"]
    assert "MB-BMS-0014" in r and "MB-BMS-0015" in r
    for motif in r.values():
        assert "suspendu" in motif.lower()


def test_catalogue_introuvable_rejete(tmp_path):
    with pytest.raises(FeedError, match="introuvable"):
        load_catalogue(tmp_path / "absent.json")


# ==========================================================================
# 2. Unites : jamais devinees
# ==========================================================================

@pytest.mark.parametrize("libelle,attendu", [
    ("USD/t", PriceUnit.PER_TONNE), ("USD/mt", PriceUnit.PER_TONNE),
    ("USD/lb", PriceUnit.PER_POUND), ("USD/kg", PriceUnit.PER_KILOGRAM),
    ("USD/oz t", PriceUnit.PER_TROY_OUNCE), ("CNY/t", PriceUnit.PER_TONNE),
])
def test_unites_reconnues(libelle, attendu):
    assert _unite(libelle) is attendu


def test_unite_inconnue_rejetee():
    with pytest.raises(FeedError, match="non reconnue"):
        _unite("USD/baril")


def test_date_illisible_rejetee():
    with pytest.raises(FeedError, match="illisible"):
        _date("le 9 octobre")
    with pytest.raises(FeedError, match="sans date"):
        _date(None)


def test_date_avec_horodatage_tronquee():
    assert _date("2026-10-09T12:00:00+00:00") == dt.date(2026, 10, 9)


# ==========================================================================
# 3. Fastmarkets
# ==========================================================================

def test_fastmarkets_authentifie_puis_interroge():
    f = _fm({"connect/token": JETON_FM, "/Prices": PRIX_FM})
    f.quotes()
    chemins = [u for _, u, _, _ in f.fetcher.appels]
    assert "connect/token" in chemins[0]
    assert chemins[1].endswith("/Prices")


def test_fastmarkets_envoie_la_cle_de_service_dans_le_corps():
    f = _fm({"connect/token": JETON_FM, "/Prices": PRIX_FM})
    f.quotes()
    _, _, _, corps = f.fetcher.appels[0]
    assert "grant_type=servicekey" in corps
    assert "client_id=service_client" in corps
    assert "fastmarkets.physicalprices.api" in corps


def test_fastmarkets_porte_le_jeton_en_bearer():
    f = _fm({"connect/token": JETON_FM, "/Prices": PRIX_FM})
    f.quotes()
    _, _, entetes, _ = f.fetcher.appels[1]
    assert entetes["Authorization"] == "Bearer jeton-de-test"


def test_fastmarkets_convertit_la_livre_en_tonne():
    """23,75 USD/lb au point bas donnent 52 360 USD/t."""
    f = _fm({"connect/token": JETON_FM, "/Prices": PRIX_FM})
    ps = build_price_set(f.quotes(), label="t", is_production_source=True)
    p = ps.get("Co")
    assert p.value_per_tonne == pytest.approx(52359.8, abs=1)
    assert p.as_of == dt.date(2026, 10, 9)
    assert "MB-CO-0005" in p.source
    assert "Converti depuis" in p.note


def test_fastmarkets_ne_retient_pas_le_median_sur_le_cobalt():
    """Le median donnerait 56 108 USD/t, soit 7 % de trop."""
    f = _fm({"connect/token": JETON_FM, "/Prices": PRIX_FM})
    p = build_price_set(f.quotes(), label="t").get("Co")
    median = 25.45 * 2204.622621848776
    assert abs(p.value_per_tonne - median) > 3000


def test_fastmarkets_payables_rendus_en_fractions():
    f = _fm({"connect/token": JETON_FM, "/Prices": PAYABLES_FM})
    pay = f.payables("exw_europe")
    assert pay["Ni"] == pytest.approx(0.6125)
    assert pay["Co"] == pytest.approx(0.5840)
    assert all(0.0 < v < 1.0 for v in pay.values())


def test_fastmarkets_marche_inconnu_liste_les_marches():
    f = _fm({"connect/token": JETON_FM, "/Prices": PAYABLES_FM})
    with pytest.raises(FeedError, match="exw_europe"):
        f.payables("mars")


def test_fastmarkets_catalogue_des_droits():
    f = _fm({"connect/token": JETON_FM, "/Instruments": INSTRUMENTS_FM})
    assert f.entitlements() == ["MB-BMS-0004", "MB-CO-0005"]


def test_fastmarkets_renouvelle_le_jeton_sur_401():
    """Un jeton expire doit declencher une reprise, pas un echec."""
    etat = {"n": 0}

    def reseau(url, method="GET", headers=None, body=None, timeout=20.0):
        if "connect/token" in url:
            return HttpResponse(200, json.dumps(JETON_FM))
        etat["n"] += 1
        if etat["n"] == 1:
            return HttpResponse(401, "{}")
        return HttpResponse(200, json.dumps(PRIX_FM))

    f = FastmarketsFeed(fetcher=reseau, service_key="k", service_name="n")
    assert len(f.quotes()) == 1
    assert etat["n"] == 2


def test_fastmarkets_403_explique_l_abonnement():
    f = FastmarketsFeed(
        fetcher=Reseau({"connect/token": JETON_FM}, statut=200),
        service_key="k", service_name="n",
    )
    f.fetcher.routes["/Prices"] = HttpResponse(403, "{}")
    with pytest.raises(FeedError, match="abonnement"):
        f.quotes()


def test_fastmarkets_authentification_refusee_est_explicite():
    f = FastmarketsFeed(
        fetcher=Reseau({"connect/token": HttpResponse(400, "{}")}),
        service_key="mauvaise", service_name="n",
    )
    with pytest.raises(FeedError, match="KLASTOS_FM_SERVICE_KEY"):
        f.quotes()


def test_fastmarkets_reponse_vide_rejetee():
    f = _fm({"connect/token": JETON_FM, "/Prices": {"instruments": []}})
    with pytest.raises(FeedError, match="aucun prix exploitable"):
        f.quotes()


# ==========================================================================
# 4. Benchmark
# ==========================================================================

def _bmi(**kw):
    routes = {f"/{m}": c for m, c in BMI.items()}
    return BenchmarkFeed(fetcher=Reseau(routes), api_key="cle-test", **kw)


def test_benchmark_envoie_la_cle_en_entete():
    b = _bmi()
    b.quotes(["Co"])
    _, _, entetes, _ = b.fetcher.appels[0]
    assert entetes["x-api-key"] == "cle-test"
    assert entetes["Content-Type"] == "application/json"


def test_benchmark_demande_la_conversion_en_tonnes():
    """L'API convertit elle-meme : autant le lui demander explicitement."""
    b = _bmi()
    b.quotes(["Co"])
    corps = json.loads(b.fetcher.appels[0][3])
    assert corps["options"]["unitOfMeasure"] == "t"
    assert corps["options"]["currency"] == "USD"
    assert corps["options"]["includeSummary"] is True


def test_benchmark_lit_les_trois_metaux():
    ps = build_price_set(_bmi().quotes(), label="t", is_production_source=True)
    assert ps.get("Co").value_per_tonne == pytest.approx(52360.0)
    assert ps.get("Li").value_per_tonne == pytest.approx(19750.0)
    assert ps.get("Ni").value_per_tonne == pytest.approx(16811.0)


def test_benchmark_declare_la_base_carbonate_du_lithium():
    """Le prix publie porte sur Li2CO3, pas sur le lithium contenu."""
    ps = build_price_set(_bmi().quotes(["Li"]), label="t")
    assert ps.get("Li").basis == "Li2CO3"


def test_benchmark_reporte_l_assurance_iosco():
    ps = build_price_set(_bmi().quotes(["Co"]), label="t")
    assert "IOSCO" in ps.get("Co").reference_name


def test_benchmark_metal_hors_catalogue_rejete():
    with pytest.raises(FeedError, match="absent du catalogue"):
        _bmi().quotes(["Pt"])


def test_benchmark_401_renvoie_a_la_cle():
    b = BenchmarkFeed(fetcher=Reseau({"/cobalt": HttpResponse(401, "{}")}),
                      api_key="mauvaise")
    with pytest.raises(FeedError, match="KLASTOS_BMI_API_KEY"):
        b.quotes(["Co"])


def test_benchmark_403_renvoie_a_la_portee():
    b = BenchmarkFeed(fetcher=Reseau({"/cobalt": HttpResponse(403, "{}")}),
                      api_key="cle")
    with pytest.raises(FeedError, match="droits insuffisants"):
        b.quotes(["Co"])


def test_benchmark_black_mass_rend_le_brut():
    """
    La structure des payables de black mass depend des droits : le connecteur
    rend le brut plutot que d'inventer une forme.
    """
    charge = {"data": [{"code": "BMIBM001", "name": "Black Mass NCM Payable"}]}
    b = BenchmarkFeed(fetcher=Reseau({"/recycling": charge}), api_key="cle")
    assert b.black_mass(price_types=["Payable"])["data"][0]["code"] == "BMIBM001"
    corps = json.loads(b.fetcher.appels[0][3])
    assert corps["filters"]["priceTypes"] == ["Payable"]


# ==========================================================================
# 5. SMM
# ==========================================================================

def test_smm_refuse_de_deviner_les_series():
    """Les identifiants de series ne sont pas publics : on ne les invente pas."""
    s = SMMFeed(fetcher=Reseau({}), user="u", password_md5="x")
    with pytest.raises(FeedError, match="Completez"):
        s.quotes()


def test_smm_lit_une_serie_renseignee():
    cat = load_catalogue()
    cat["smm"]["series"] = {"Co": {
        "serie": "co_spot_price", "unit": "CNY/t", "value_index": 1,
        "currency": "CNY", "reference_name": "SMM cobalt spot",
    }}
    routes = {
        "usercenter/auth": {"data": {"token": "jeton-smm"}},
        "co_spot_price": {"data": {
            "permission": 1,
            "field": [{"name": "report_date"}, {"name": "price"}],
            "content": [["2026-10-08", 300000.0], ["2026-10-09", 310000.0]],
        }},
    }
    s = SMMFeed(fetcher=Reseau(routes), catalogue=cat, user="u",
                password_md5="x")
    q = s.quotes()
    assert len(q) == 1
    assert q[0].value == pytest.approx(310000.0)   # derniere ligne
    assert q[0].currency == "CNY"
    assert q[0].as_of == dt.date(2026, 10, 9)


def test_smm_absence_de_droit_est_explicite():
    cat = load_catalogue()
    cat["smm"]["series"] = {"Co": {"serie": "s", "unit": "CNY/t"}}
    routes = {"usercenter/auth": {"data": {"token": "t"}},
              "/s": {"data": {"permission": 0, "content": []}}}
    s = SMMFeed(fetcher=Reseau(routes), catalogue=cat, user="u",
                password_md5="x")
    with pytest.raises(FeedError, match="aucun droit"):
        s.quotes()


# ==========================================================================
# 6. Identifiants : jamais en argument
# ==========================================================================

def test_identifiants_absents_message_explicite(monkeypatch):
    for v in ("KLASTOS_FM_SERVICE_KEY", "KLASTOS_FM_SERVICE_NAME"):
        monkeypatch.delenv(v, raising=False)
    f = FastmarketsFeed(fetcher=Reseau({}))
    with pytest.raises(CredentialsMissing, match="KLASTOS_FM_SERVICE_KEY"):
        f.quotes()


def test_le_message_dissuade_de_passer_la_cle_en_argument(monkeypatch):
    monkeypatch.delenv("KLASTOS_BMI_API_KEY", raising=False)
    b = BenchmarkFeed(fetcher=Reseau({}))
    with pytest.raises(CredentialsMissing, match="historique du shell"):
        b.quotes(["Co"])


def test_les_identifiants_sont_lus_dans_l_environnement(monkeypatch):
    monkeypatch.setenv("KLASTOS_BMI_API_KEY", "cle-env")
    b = BenchmarkFeed(fetcher=Reseau({"/cobalt": BMI["cobalt"]}))
    b.quotes(["Co"])
    assert b.fetcher.appels[0][2]["x-api-key"] == "cle-env"


def test_la_cle_n_apparait_pas_dans_la_representation():
    """Un objet imprime dans un journal ne doit pas fuir le jeton."""
    f = FastmarketsFeed(fetcher=Reseau({}), service_key="SECRET")
    assert "_token" not in repr(f)


# ==========================================================================
# 7. Autorisation de rediffusion : portee, pas supposee
# ==========================================================================

def test_la_rediffusion_est_refusee_par_defaut():
    """Un abonnement d'agence couvre l'usage interne, rien de plus."""
    for flux in (FastmarketsFeed(fetcher=Reseau({})),
                 BenchmarkFeed(fetcher=Reseau({})),
                 SMMFeed(fetcher=Reseau({}))):
        assert flux.redistribution_licensed is False


def test_la_rediffusion_doit_etre_declaree_explicitement():
    f = FastmarketsFeed(fetcher=Reseau({}), redistribution_licensed=True)
    assert f.redistribution_licensed is True


def test_le_module_documente_la_contrainte_de_licence():
    import klastos.feeds as m

    doc = m.__doc__ or ""
    assert "USAGE INTERNE" in doc
    assert "autorisation ecrite" in doc


# ==========================================================================
# 8. Reseau par defaut
# ==========================================================================

def test_le_fetcher_par_defaut_est_la_bibliotheque_standard():
    assert FastmarketsFeed(fetcher=urllib_fetcher).fetcher is urllib_fetcher


def test_reponse_non_json_rejetee():
    r = HttpResponse(200, "<html>maintenance</html>")
    with pytest.raises(FeedError, match="illisible"):
        r.json()