"""
KLASTOS21 - Types de marche partages.

Ce module ne contient que des STRUCTURES et des CHARGEURS. Aucune logique
de valorisation, aucune valeur de prix.

Il est volontairement place a la base de la chaine de dependances :

    units  ->  market  ->  providers
                       ->  valuation

Un fournisseur de prix n'a aucune raison de dependre du calcul de
valorisation, et reciproquement. Le service d'approvisionnement en prix peut
donc vivre - et se vendre - independamment du service de valorisation.

AUCUN PRIX N'EST ECRIT DANS CE FICHIER
--------------------------------------
Le marche varie trop pour qu'un prix vive dans du code. Le carbonate de
lithium a varie de plus de 100 % sur douze mois et le cobalt de plus de
300 % en 2025. Un prix litteral dans un module Python part dans le depot,
se livre avec le paquet, et se retrouve encore la trois ans plus tard.

Les instantanes vivent dans `data/`, au format JSON, avec leur source, leur
date et leur base de cotation. Un champ manquant est une erreur, jamais une
valeur par defaut.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from dataclasses import dataclass
from typing import Callable, Protocol

from .units import LB_PER_TONNE

MAX_PRICE_AGE_DAYS = 7
MAX_PAYABLE_AGE_DAYS = 60


class StalePriceError(RuntimeError):
    """Prix trop ancien pour fonder une valorisation opposable."""


class MissingPriceError(KeyError):
    """
    Aucun prix disponible pour un element payable.

    La classe de base reste `KeyError` : du code appelant l'attrape ainsi,
    et un prix manquant EST une cle absente. Mais `KeyError.__str__` rend
    `repr(args[0])`, donc des guillemets autour du message.

    Utile quand l'argument est une cle - `KeyError('Ni')` affiche 'Ni', et
    les guillemets montrent qu'on parle d'une chaine. Nuisible quand
    l'argument est une PHRASE destinee a l'utilisateur : la ligne de
    commande affichait

        prix manquant : "cobalt (Co) absent du Pink Sheet. ..."

    avec des guillemets parasites autour de tout le message, et un
    apostrophe francais dans le texte faisait basculer Python sur des
    guillemets doubles - donc une ponctuation qui change selon le contenu.
    """

    def __str__(self) -> str:
        if len(self.args) == 1 and isinstance(self.args[0], str):
            return self.args[0]
        return super().__str__()


# ==========================================================================
# Prix
# ==========================================================================

@dataclass(frozen=True)
class MetalPrice:
    """Un prix de reference, avec sa provenance et sa date."""

    metal: str
    value_per_tonne: float
    currency: str
    as_of: _dt.date
    source: str
    reference_name: str
    note: str = ""
    basis: str = "metal"          # "metal" ou "Li2CO3" pour le lithium

    def age_days(self, today: _dt.date | None = None) -> int:
        today = today or _dt.date.today()
        return (today - self.as_of).days

    def is_stale(self, today: _dt.date | None = None,
                 max_age: int = MAX_PRICE_AGE_DAYS) -> bool:
        return self.age_days(today) > max_age


@dataclass(frozen=True)
class PriceSet:
    """Un jeu de prix coherent, dans une devise unique."""

    prices: dict[str, MetalPrice]
    currency: str = "USD"
    label: str = ""
    is_production_source: bool = False
    origin: str = ""

    #: Droit d'AFFICHER ces prix dans un document remis a un tiers.
    #:
    #: Un abonnement d'agence couvre l'usage interne, pas la rediffusion.
    #: Le drapeau existait deja a la recuperation, mais il mourait avec le
    #: fichier : `load_price_set` ne le relisait pas, et plus rien dans le
    #: systeme ne savait si un instantane pouvait partir chez un client. Il
    #: ne restait que le libelle, du texte que personne ne verifie.
    #:
    #: La valeur par defaut est True parce que le cas le plus courant est le
    #: fichier de prix FOURNI PAR LE CLIENT : ce sont ses propres donnees,
    #: aucune licence d'agence ne s'y applique. Seuls les flux d'agence
    #: posent explicitement False.
    redistribution_licensed: bool = True

    def get(self, metal: str) -> MetalPrice:
        if metal not in self.prices:
            raise MissingPriceError(
                f"Aucun prix pour {metal!r}. Prix disponibles : "
                f"{sorted(self.prices)}."
            )
        return self.prices[metal]

    def stale(self, today: _dt.date | None = None,
              max_age: int = MAX_PRICE_AGE_DAYS) -> list[str]:
        return sorted(
            m for m, p in self.prices.items() if p.is_stale(today, max_age)
        )

    def check_currency(self) -> None:
        mauvaises = {p.currency for p in self.prices.values()} - {self.currency}
        if mauvaises:
            raise ValueError(
                f"Devises heterogenes dans le jeu de prix : {sorted(mauvaises)} "
                f"alors que le jeu est declare en {self.currency}."
            )



# ==========================================================================
# Chargement depuis fichier - le SEUL chemin d'entree des prix
# ==========================================================================

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"


class NotAProductionSourceError(RuntimeError):
    """Un instantane de demonstration a ete utilise en contexte opposable."""


def load_price_set(path: str | pathlib.Path) -> PriceSet:
    """
    Charge un jeu de prix depuis un fichier JSON.

    Le fichier porte, pour chaque metal : valeur, date, source et libelle de
    reference. Un champ manquant est une erreur, jamais une valeur par defaut.
    """
    path = pathlib.Path(path)
    with path.open(encoding="utf-8") as fh:
        brut = json.load(fh)

    devise = brut.get("currency")
    if not devise:
        raise ValueError(f"{path.name} : champ 'currency' absent.")

    prix: dict[str, MetalPrice] = {}
    for metal, d in brut.get("prices", {}).items():
        for champ in ("value_per_tonne", "as_of", "source", "reference_name"):
            if champ not in d:
                raise ValueError(
                    f"{path.name} : champ {champ!r} absent pour {metal!r}. "
                    "Un prix sans source ni date n'est pas exploitable."
                )
        prix[metal] = MetalPrice(
            metal=metal,
            value_per_tonne=float(d["value_per_tonne"]),
            currency=devise,
            as_of=_dt.date.fromisoformat(d["as_of"]),
            source=d["source"],
            reference_name=d["reference_name"],
            note=d.get("note", ""),
            basis=d.get("basis", "metal"),
        )
    if not prix:
        raise ValueError(f"{path.name} : aucun prix.")

    ps = PriceSet(
        prices=prix,
        currency=devise,
        label=brut.get("label", path.name),
        is_production_source=bool(brut.get("is_production_source", False)),
        origin=str(path),
        # Absent du fichier : c'est un fichier de prix du client, donc
        # aucune licence d'agence ne s'y applique. Present : c'est un
        # instantane d'agence, et il dit la verite sur le droit d'affichage.
        redistribution_licensed=bool(brut.get("redistribution_licensed", True)),
    )
    ps.check_currency()
    return ps


def load_payable_terms(path: str | pathlib.Path) -> dict[str, PayableTerms]:
    """Charge des conditions commerciales depuis un fichier JSON."""
    path = pathlib.Path(path)
    with path.open(encoding="utf-8") as fh:
        brut = json.load(fh)
    out: dict[str, PayableTerms] = {}
    for cle, d in brut.get("terms", {}).items():
        out[cle] = PayableTerms(
            market=d["market"],
            payables={k: float(v) for k, v in d["payables"].items()},
            as_of=_dt.date.fromisoformat(d["as_of"]),
            source=d["source"],
            lithium_included_in_ni_co=bool(d.get("lithium_included_in_ni_co")),
            validated=bool(d.get("validated", False)),
            note=d.get("note", ""),
        )
    return out


def demo_price_set() -> PriceSet:
    """
    Instantane de demonstration livre avec le code.

    NE PAS UTILISER EN PRODUCTION. Il porte `is_production_source=False`, ce
    que `value_lot()` refuse sans `allow_stale=True`.
    """
    return load_price_set(DATA_DIR / "prices_snapshot_2026-09-04.json")


def demo_payable_terms() -> dict[str, PayableTerms]:
    """Conditions de demonstration, toutes perimees et non validees."""
    return load_payable_terms(DATA_DIR / "payable_terms.json")


# ==========================================================================
# Branchement d'un flux de production
# ==========================================================================

class PriceProvider(Protocol):
    """N'importe quelle source capable de rendre un jeu de prix date."""

    def fetch(self) -> PriceSet: ...


@dataclass(frozen=True)
class CallablePriceProvider:
    """
    Enveloppe une fonction quelconque en fournisseur de prix.

    Exemple d'usage en production :

        def depuis_mon_api() -> PriceSet:
            ...                       # appel HTTP, lecture d'un export, etc.

        fournisseur = CallablePriceProvider(depuis_mon_api)
        valorisation = value_lot(rapport, prices=fournisseur.fetch(), ...)
    """

    func: Callable[[], PriceSet]

    def fetch(self) -> PriceSet:
        ps = self.func()
        if not isinstance(ps, PriceSet):
            raise TypeError("Le fournisseur doit rendre un PriceSet.")
        ps.check_currency()
        return ps


# Conversion carbonate -> lithium contenu.
# Li2CO3 : 2 x 6,94 + 12,011 + 3 x 15,999 = 73,888 g/mol ; Li = 13,888 g
LI_FRACTION_IN_LI2CO3 = (2 * 6.94) / (2 * 6.94 + 12.011 + 3 * 15.999)


# ==========================================================================
# Payables
# ==========================================================================

@dataclass(frozen=True)
class PayableTerms:
    """
    Conditions commerciales d'un marche donne.

    `payables` : element -> fraction du prix de reference effectivement payee.
    """

    market: str
    payables: dict[str, float]
    as_of: _dt.date
    source: str
    lithium_included_in_ni_co: bool = False
    validated: bool = False
    note: str = ""

    def age_days(self, today: _dt.date | None = None) -> int:
        return ((today or _dt.date.today()) - self.as_of).days

    def is_stale(self, today: _dt.date | None = None,
                 max_age: int = MAX_PAYABLE_AGE_DAYS) -> bool:
        return self.age_days(today) > max_age


# ==========================================================================
# Specification commerciale
# ==========================================================================

@dataclass(frozen=True)
class Specification:
    """
    Fourchettes de teneur exigees par un acheteur, en fraction massique.

    `limits` : element -> (minimum ou None, maximum ou None).
    """

    name: str
    limits: dict[str, tuple[float | None, float | None]]
    source: str
    note: str = ""

    def check(self, teneurs: dict[str, float]) -> list[str]:
        """Retourne la liste des non-conformites constatees."""
        ecarts: list[str] = []
        for el, (lo, hi) in self.limits.items():
            v = teneurs.get(el)
            if v is None:
                continue
            if lo is not None and v < lo:
                ecarts.append(
                    f"{el} a {v*100:.2f} % : sous le minimum de {lo*100:.2f} %"
                )
            if hi is not None and v > hi:
                ekk = f"{el} a {v*100:.2f} % : au-dessus du maximum de {hi*100:.2f} %"
                ecarts.append(ekk)
        return ecarts


REFERENCE_SPECS: dict[str, Specification] = {
    "ncm_cif_coree": Specification(
        name="NCM black mass, CIF Coree du Sud",
        limits={
            "Ni": (0.15, 0.25),
            "Co": (0.05, 0.15),
            "Li": (0.03, 0.05),
            "Cu": (None, 0.02),
            "Al": (None, 0.02),
        },
        source="Methodologie Fastmarkets, black mass NCM CIF Coree du Sud",
        note="Matiere seche et coulante exigee.",
    ),
    "chine_import": Specification(
        name="Norme d'import chinoise",
        limits={"Li": (0.035, None)},
        source="Standard chinois GB/T 45203-2024",
        note=(
            "Exige aussi Ni + Co >= 25 % cumule et fluorure hydrosoluble "
            "<= 0,4 % : controles hors portee de la v0."
        ),
    ),
}
