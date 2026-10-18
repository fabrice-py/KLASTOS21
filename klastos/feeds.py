"""
KLASTOS21 - Connecteurs vers les agences d'evaluation de prix.

Ce module branche KLASTOS21 sur les flux reels : Fastmarkets, Benchmark
Mineral Intelligence, SMM. Il produit des `RawQuote`, donc il se greffe sur
la chaine de `providers.py` sans rien y changer.

CE QUE CE MODULE PERMET ET CE QU'IL N'AUTORISE PAS
--------------------------------------------------
Un abonnement d'agence couvre, par defaut, l'USAGE INTERNE. Rediffuser les
prix a un tiers - par exemple les afficher dans un rapport facture a un
client - exige une autorisation ecrite distincte.

Ce module ne tranche pas cette question a votre place : il marque chaque jeu
de prix avec sa source et son niveau d'autorisation declare
(`redistribution_licensed`). Le rapport client porte ensuite la mention
correspondante. Declarer une autorisation que vous n'avez pas est votre
responsabilite contractuelle, pas celle du code.

IDENTIFIANTS
------------
Jamais dans le code, jamais en argument de ligne de commande - un argument
reste dans l'historique du shell. Ils sont lus dans l'environnement :

    KLASTOS_FM_SERVICE_KEY    KLASTOS_FM_SERVICE_NAME
    KLASTOS_BMI_API_KEY
    KLASTOS_SMM_USER          KLASTOS_SMM_PASSWORD_MD5

RESEAU
------
La fonction reseau est INJECTEE. Aucun appel HTTP n'est code en dur, ce qui
rend chaque connecteur testable hors ligne et independant de la bibliotheque
HTTP retenue. `urllib_fetcher()` fournit une implementation sur la
bibliotheque standard, sans dependance supplementaire.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from .providers import ProviderError, RawQuote
from .units import PriceUnit

CATALOGUE_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "symboles_pra.json"

# Delai reseau par defaut, en secondes. Un client attend son rapport : mieux
# vaut echouer vite et basculer sur le fournisseur suivant.
DEFAULT_TIMEOUT = 20.0


class CredentialsMissing(ProviderError):
    """Identifiants absents de l'environnement."""


class FeedError(ProviderError):
    """Le flux a repondu, mais la reponse est inexploitable."""


# ==========================================================================
# Catalogue de symboles : donnee, pas code
# ==========================================================================

def load_catalogue(path: str | pathlib.Path | None = None) -> dict:
    """Charge le catalogue de symboles depuis `data/symboles_pra.json`."""
    p = pathlib.Path(path or CATALOGUE_PATH)
    if not p.exists():
        raise FeedError(f"Catalogue de symboles introuvable : {p}")
    return json.loads(p.read_text(encoding="utf-8"))


# ==========================================================================
# Reseau
# ==========================================================================

@dataclass
class HttpResponse:
    status: int
    body: str

    def json(self) -> Any:
        try:
            return json.loads(self.body)
        except json.JSONDecodeError as e:
            raise FeedError(f"Reponse illisible (HTTP {self.status}) : {e}") from e


Fetcher = Callable[..., HttpResponse]


def urllib_fetcher(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | bytes | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> HttpResponse:
    """
    Implementation sur la bibliotheque standard, sans dependance ajoutee.

    Les erreurs HTTP sont rendues comme reponses, pas levees : chaque
    connecteur decide quoi faire d'un 401 ou d'un 403, et le message de
    l'agence est souvent plus instructif que l'exception.
    """
    donnees = body.encode("utf-8") if isinstance(body, str) else body
    req = urllib.request.Request(url, data=donnees, method=method,
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as rep:
            return HttpResponse(rep.status, rep.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return HttpResponse(e.code, e.read().decode("utf-8", "replace"))
    except urllib.error.URLError as e:
        raise ProviderError(f"{url} injoignable : {e.reason}") from e
    except TimeoutError as e:
        raise ProviderError(f"{url} : delai depasse ({timeout} s)") from e


def _env(nom: str, source: str) -> str:
    v = os.environ.get(nom, "").strip()
    if not v:
        raise CredentialsMissing(
            f"Variable d'environnement {nom} absente ou vide. "
            f"Elle est requise pour {source}. "
            "Ne la passez jamais en argument de ligne de commande : "
            "l'historique du shell la conserverait."
        )
    return v


# ==========================================================================
# Fastmarkets - Physical Prices API
# ==========================================================================

@dataclass
class FastmarketsFeed:
    """
    Connecteur Fastmarkets Physical Prices API, version 2.

    Authentification par cle de service, jeton porteur valable une heure.
    Les evaluations sont rendues sous forme de fourchette basse / mediane /
    haute ; le catalogue indique quelle borne retenir pour chaque symbole.
    """

    fetcher: Fetcher = urllib_fetcher
    catalogue: dict | None = None
    service_key: str | None = None
    service_name: str | None = None
    redistribution_licensed: bool = False
    name: str = "fastmarkets"
    _token: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.catalogue = (self.catalogue or load_catalogue())["fastmarkets"]

    # -- authentification -------------------------------------------------
    def _authentifier(self) -> str:
        cle = self.service_key or _env("KLASTOS_FM_SERVICE_KEY", "Fastmarkets")
        nom = self.service_name or _env("KLASTOS_FM_SERVICE_NAME", "Fastmarkets")
        corps = urllib.parse.urlencode({
            "grant_type": "servicekey",
            "client_id": "service_client",
            "scope": self.catalogue["scope"],
            "serviceKey": cle,
            "serviceName": nom,
        })
        rep = self.fetcher(
            self.catalogue["auth_url"], method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=corps,
        )
        if rep.status != 200:
            raise FeedError(
                f"Authentification Fastmarkets refusee (HTTP {rep.status}). "
                "Verifiez KLASTOS_FM_SERVICE_KEY et KLASTOS_FM_SERVICE_NAME."
            )
        jeton = rep.json().get("access_token")
        if not jeton:
            raise FeedError("Reponse d'authentification sans access_token.")
        self._token = jeton
        return jeton

    def _poster(self, chemin: str, champs: dict[str, str]) -> Any:
        """POST authentifie, avec une reprise unique sur jeton expire."""
        url = f"{self.catalogue['base_url']}/{chemin}"
        for tentative in (1, 2):
            jeton = self._token or self._authentifier()
            rep = self.fetcher(
                url, method="POST",
                headers={
                    "Authorization": f"Bearer {jeton}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                body=urllib.parse.urlencode(champs),
            )
            if rep.status == 401 and tentative == 1:
                self._token = None          # jeton expire : on renouvelle
                continue
            if rep.status == 403:
                raise FeedError(
                    f"Fastmarkets refuse l'acces a {champs.get('Symbols', chemin)} "
                    "(HTTP 403). Votre abonnement ne couvre probablement pas "
                    "ces symboles."
                )
            if rep.status != 200:
                raise FeedError(f"Fastmarkets {chemin} : HTTP {rep.status}.")
            return rep.json()
        raise FeedError("Fastmarkets : authentification impossible.")

    # -- lecture ----------------------------------------------------------
    def entitlements(self) -> list[str]:
        """Symboles que l'abonnement autorise reellement a voir."""
        payload = self._poster("Instruments", {})
        return sorted(
            i["symbol"] for i in payload.get("instruments", []) if i.get("symbol")
        )

    def quotes(self, symbols: list[str] | None = None) -> list[RawQuote]:
        """
        Cotations de prix metal. Les payables sont lus par `payables()`.

        Seuls les symboles portant un `metal` dans le catalogue sont des prix
        de reference ; les autres sont des pourcentages de payable.
        """
        connus = self.catalogue["symbols"]
        vises = symbols or [s for s, d in connus.items() if "metal" in d]
        vises = [s for s in vises if "metal" in connus.get(s, {})]
        if not vises:
            raise FeedError("Aucun symbole de prix metal a interroger.")

        payload = self._poster("Prices", {"Symbols": ",".join(vises)})
        out: list[RawQuote] = []
        for inst in payload.get("instruments", []):
            sym = inst.get("symbol")
            conf = connus.get(sym)
            if not conf or not inst.get("prices"):
                continue
            p = inst["prices"][0]
            valeur = p.get(conf.get("field", "mid"))
            if valeur is None:
                continue
            out.append(RawQuote(
                metal=conf["metal"],
                value=float(valeur),
                unit=_unite(conf["unit"]),
                currency="USD",
                as_of=_date(p.get("date") or p.get("assessmentDate")),
                source=f"Fastmarkets {sym}",
                reference_name=conf["reference_name"],
                basis=conf.get("basis", "metal"),
                note=conf.get("note", ""),
            ))
        if not out:
            raise FeedError(
                f"Fastmarkets n'a renvoye aucun prix exploitable pour {vises}."
            )
        return out

    def payables(self, market: str) -> dict[str, float]:
        """
        Payables du marche demande, en fraction du prix de reference.

        Fastmarkets les publie en pourcentage ; on rend des fractions, ce que
        `PayableTerms` attend.
        """
        connus = self.catalogue["symbols"]
        vises = {s: d for s, d in connus.items() if d.get("market") == market}
        if not vises:
            marches = sorted({d["market"] for d in connus.values() if "market" in d})
            raise FeedError(
                f"Marche {market!r} inconnu du catalogue. Marches : {marches}"
            )
        payload = self._poster("Prices", {"Symbols": ",".join(vises)})
        out: dict[str, float] = {}
        for inst in payload.get("instruments", []):
            conf = vises.get(inst.get("symbol"))
            if not conf or not inst.get("prices"):
                continue
            v = inst["prices"][0].get(conf.get("field", "mid"))
            if v is not None:
                out[conf["payable_for"]] = float(v) / 100.0
        if not out:
            raise FeedError(f"Aucun payable renvoye pour le marche {market!r}.")
        return out


# ==========================================================================
# Benchmark Mineral Intelligence - Prices API v3
# ==========================================================================

@dataclass
class BenchmarkFeed:
    """
    Connecteur Benchmark Prices API, version 3.

    Cle d'API dans l'en-tete `x-api-key`. Deux avantages pratiques sur
    Fastmarkets : l'API convertit elle-meme les unites et la devise, et le
    marche `recycling` porte les prix et payables de black mass.
    """

    fetcher: Fetcher = urllib_fetcher
    catalogue: dict | None = None
    api_key: str | None = None
    currency: str = "USD"
    unit: str = "t"
    redistribution_licensed: bool = False
    name: str = "benchmark"

    def __post_init__(self) -> None:
        self.catalogue = (self.catalogue or load_catalogue())["benchmark"]

    def _poster(self, endpoint: str, corps: dict) -> Any:
        cle = self.api_key or _env("KLASTOS_BMI_API_KEY", "Benchmark")
        rep = self.fetcher(
            f"{self.catalogue['base_url']}/{endpoint}", method="POST",
            headers={"x-api-key": cle, "Content-Type": "application/json"},
            body=json.dumps(corps),
        )
        if rep.status == 401:
            raise FeedError(
                "Benchmark refuse la cle d'API (HTTP 401). Verifiez "
                "KLASTOS_BMI_API_KEY dans votre espace abonnement."
            )
        if rep.status == 403:
            raise FeedError(
                f"Benchmark : droits insuffisants sur {endpoint} (HTTP 403). "
                "La portee requise n'est pas couverte par votre abonnement."
            )
        if rep.status != 200:
            raise FeedError(f"Benchmark {endpoint} : HTTP {rep.status}.")
        return rep.json()

    def _options(self) -> dict:
        return {
            "includeSummary": True,
            "includeSeries": False,
            "currency": self.currency.upper(),
            "unitOfMeasure": self.unit,
        }

    def quotes(self, metals: list[str] | None = None) -> list[RawQuote]:
        """Prix de reference des metaux demandes."""
        marches = self.catalogue["markets"]
        vises = metals or sorted(marches)
        out: list[RawQuote] = []
        for metal in vises:
            conf = marches.get(metal)
            if conf is None:
                raise FeedError(
                    f"Metal {metal!r} absent du catalogue Benchmark. "
                    f"Disponibles : {sorted(marches)}"
                )
            payload = self._poster(conf["endpoint"], {
                "filters": {}, "options": self._options(),
            })
            out.extend(self._extraire(payload, metal, conf))
        if not out:
            raise FeedError("Benchmark n'a renvoye aucun prix exploitable.")
        return out

    def _extraire(self, payload: Any, metal: str, conf: dict) -> list[RawQuote]:
        out: list[RawQuote] = []
        for d in payload.get("data", []):
            resume = (d.get("summary") or {}).get("latestPublication") or {}
            valeur = resume.get("valueMid")
            if valeur is None:
                valeur = resume.get("valueLow")
            if valeur is None or not resume.get("date"):
                continue

            symbole = ((d.get("unitOfMeasure") or {}).get("symbol")
                       or self.unit)
            devise = ((d.get("currency") or {}).get("iso")
                      or self.currency).upper()
            qualite = " [assure IOSCO]" if d.get("isIoscoAssured") else ""

            out.append(RawQuote(
                metal=metal,
                value=float(valeur),
                unit=_unite(f"{devise}/{symbole}"),
                currency=devise,
                as_of=_date(resume["date"]),
                source=f"Benchmark {d.get('code', '')}".strip(),
                reference_name=f"{d.get('name') or conf['reference_name']}{qualite}",
                basis=conf.get("basis", "metal"),
            ))
            break          # une seule cotation de reference par marche
        return out

    def black_mass(self, price_types: list[str] | None = None) -> Any:
        """
        Prix et payables de black mass, marche `recycling`.

        Rendu brut : la structure des payables de black mass depend des
        droits de l'abonnement, et l'inventer serait une faute. Lancez
        d'abord une requete de decouverte, puis renseignez le catalogue.
        """
        conf = self.catalogue["recycling"]
        filtres: dict = {}
        if price_types:
            filtres["priceTypes"] = price_types
        return self._poster(conf["endpoint"], {
            "filters": filtres,
            "options": {**self._options(), "includeSummary": True},
        })


# ==========================================================================
# SMM - Shanghai Metals Market
# ==========================================================================

@dataclass
class SMMFeed:
    """
    Connecteur SMM.

    Les identifiants de series pour les metaux de batterie ne sont pas
    documentes publiquement : le catalogue les attend, et ce connecteur
    refuse de deviner. Renseignez `smm.series` dans
    `data/symboles_pra.json` depuis votre espace client.
    """

    fetcher: Fetcher = urllib_fetcher
    catalogue: dict | None = None
    user: str | None = None
    password_md5: str | None = None
    redistribution_licensed: bool = False
    name: str = "smm"
    _token: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.catalogue = (self.catalogue or load_catalogue())["smm"]

    def _authentifier(self) -> str:
        rep = self.fetcher(
            self.catalogue["auth_url"], method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=urllib.parse.urlencode({
                "user_name": self.user or _env("KLASTOS_SMM_USER", "SMM"),
                "password": self.password_md5
                            or _env("KLASTOS_SMM_PASSWORD_MD5", "SMM"),
                "source": "dataapi",
            }),
        )
        if rep.status != 200:
            raise FeedError(f"Authentification SMM refusee (HTTP {rep.status}).")
        jeton = (rep.json().get("data") or {}).get("token") or rep.json().get("data")
        if not isinstance(jeton, str) or not jeton:
            raise FeedError("Reponse d'authentification SMM sans jeton.")
        self._token = jeton
        return jeton

    def quotes(self, metals: list[str] | None = None) -> list[RawQuote]:
        series = {k: v for k, v in (self.catalogue.get("series") or {}).items()
                  if not k.startswith("_")}
        if not series:
            raise FeedError(
                "Aucune serie SMM renseignee. Completez `smm.series` dans "
                "data/symboles_pra.json avec les identifiants de votre espace "
                "client : {metal: {serie, unit, field}}."
            )
        jeton = self._token or self._authentifier()
        vises = metals or sorted(series)
        out: list[RawQuote] = []
        for metal in vises:
            conf = series.get(metal)
            if conf is None:
                continue
            rep = self.fetcher(
                f"{self.catalogue['base_url']}/{conf['serie']}", method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                body=urllib.parse.urlencode({"token": jeton}),
            )
            if rep.status != 200:
                raise FeedError(f"SMM {conf['serie']} : HTTP {rep.status}.")
            donnees = rep.json().get("data") or {}
            if donnees.get("permission") == 0:
                raise FeedError(
                    f"SMM : aucun droit sur la serie {conf['serie']}."
                )
            contenu = donnees.get("content") or []
            if not contenu:
                continue
            ligne = contenu[-1]
            out.append(RawQuote(
                metal=metal,
                value=float(ligne[conf.get("value_index", 1)]),
                unit=_unite(conf["unit"]),
                currency=conf.get("currency", "CNY"),
                as_of=_date(str(ligne[0])),
                source=f"SMM {conf['serie']}",
                reference_name=conf.get("reference_name", f"SMM {metal}"),
                basis=conf.get("basis", "metal"),
            ))
        if not out:
            raise FeedError("SMM n'a renvoye aucune cotation exploitable.")
        return out


# ==========================================================================
# Utilitaires
# ==========================================================================

_UNITES = {u.label: u for u in PriceUnit}
_ALIAS_UNITES = {
    "USD/t": PriceUnit.PER_TONNE, "USD/mt": PriceUnit.PER_TONNE,
    "USD/tonne": PriceUnit.PER_TONNE, "USD/kg": PriceUnit.PER_KILOGRAM,
    "USD/lb": PriceUnit.PER_POUND, "USD/oz t": PriceUnit.PER_TROY_OUNCE,
    "CNY/t": PriceUnit.PER_TONNE, "CNY/kg": PriceUnit.PER_KILOGRAM,
    "EUR/t": PriceUnit.PER_TONNE, "EUR/kg": PriceUnit.PER_KILOGRAM,
    "GBP/t": PriceUnit.PER_TONNE, "KRW/t": PriceUnit.PER_TONNE,
    "JPY/t": PriceUnit.PER_TONNE, "AUD/t": PriceUnit.PER_TONNE,
}


def _unite(libelle: str) -> PriceUnit:
    """
    Traduit un libelle d'unite d'agence vers une unite du modele.

    Aucune deduction : un libelle inconnu provoque une erreur. Une unite
    devinee fausserait la valorisation d'un facteur 1 000 ou 32 150.
    """
    cle = (libelle or "").strip()
    if cle in _UNITES:
        return _UNITES[cle]
    if cle in _ALIAS_UNITES:
        return _ALIAS_UNITES[cle]
    raise FeedError(
        f"Unite {libelle!r} non reconnue. Ajoutez-la a klastos.feeds plutot "
        "que de la laisser deviner. Connues : "
        f"{sorted(set(_UNITES) | set(_ALIAS_UNITES))}"
    )


def _date(valeur: str | None) -> _dt.date:
    if not valeur:
        raise FeedError("Cotation sans date : inexploitable.")
    texte = str(valeur).strip()
    for coupe in ("T", " "):
        if coupe in texte:
            texte = texte.split(coupe)[0]
            break
    try:
        return _dt.date.fromisoformat(texte)
    except ValueError as e:
        raise FeedError(f"Date illisible : {valeur!r}") from e