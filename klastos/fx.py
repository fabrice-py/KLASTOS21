"""
KLASTOS21 - Conversion de devises.

Pourquoi un module dedie
------------------------
`market.py` ne porte que des structures et des chargeurs : sa docstring
l'interdit explicitement d'heberger de la logique. La conversion en est, donc
elle vit ici.

AUCUNE SOURCE DE TAUX N'EST INTEGREE, et c'est une decision
-----------------------------------------------------------
Le taux est FOURNI par l'utilisateur, exactement comme les prix le sont deja
par un fichier client : c'est le taux de sa banque qui vaut pour sa
transaction, et le logiciel n'a pas a en inventer un. Il n'y a donc ici ni
appel reseau, ni taux litteral, ni valeur de repli - pas plus que `market.py`
ne contient de prix.

Un taux en dur dans un module Python part dans le depot, se livre avec le
paquet, et se retrouve encore la trois ans plus tard. La parite euro-dollar
a varie de 0,95 a 1,17 sur vingt-quatre mois : le meme raisonnement que pour
les prix s'applique mot pour mot.

La conversion n'est jamais automatique
--------------------------------------
`PriceSet.check_currency()` continue de REFUSER un jeu multi-devises. C'est
voulu : convertir sans qu'on l'ait demande reviendrait a decider a la place
du negociant quel taux engage sa transaction. La conversion est un acte
explicite de l'appelant, qui fournit le taux et en porte la responsabilite.

Ou la bande de plausibilite s'applique
--------------------------------------
Les bandes de `units.py` sont libellees EN USD. Appliquer telle quelle une
bande USD a un prix converti en wons coreens rejetterait une conversion
parfaitement juste, d'un facteur 1 350.

La conversion passe donc par un PIVOT, et c'est sur la valeur en USD - celle
de depart, celle du pivot, ou celle d'arrivee - que la bande est verifiee.
C'est le seul endroit ou elle signifie quelque chose. Consequence mesurable :
un taux EUR/USD saisi a 108 au lieu de 1,08 porte un nickel de 14 000 EUR/t
a 1 512 000 USD/t au pivot, hors bande [5 000 ; 100 000], donc refuse. Alors
qu'un USD -> KRW correct a 1 350 ne declenche rien, puisque aucune valeur en
wons n'est confrontee a une bande en dollars.

Quand la chaine ne produit aucune valeur en USD - un GBP -> EUR par taux
direct - aucune verification n'est possible. Le module le DIT dans la
provenance, plutot que de laisser croire a un controle qui n'a pas eu lieu.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import pathlib
from dataclasses import dataclass, field

from .market import MetalPrice, PriceSet
from .units import check_plausible

#: Devise dans laquelle les bandes de plausibilite de `units.py` sont
#: libellees. Ce n'est pas un choix de ce module : c'est un fait sur
#: `PLAUSIBILITY_BANDS`, et le nommer evite de l'oublier.
DEVISE_DES_BANDES = "USD"

#: Age maximal d'un taux, en jours.
#:
#: NON ARBITRE. La valeur retenue couvre un week-end plus un jour ouvre, ce
#: qui est un raisonnement de calendrier et non une regle de marche. Un
#: negociant qui traite au comptant voudra 1 ; un contrat mensuel s'accommode
#: de 30. Le seuil est donc EXPOSE a l'appelant, comme les seuils de
#: bouclage, et pour la meme raison : personne ne l'a tranche.
MAX_RATE_AGE_DAYS = 3


class RateError(ValueError):
    """Taux inutilisable : absent, sans source, perime, ou incoherent."""


class StaleRateError(RateError):
    """Taux trop ancien pour la transaction."""


class MissingRateError(RateError):
    """Aucun taux ne permet la paire demandee."""


# ==========================================================================
# Le taux
# ==========================================================================

@dataclass(frozen=True)
class ExchangeRate:
    """
    Un taux de change, avec sa provenance et sa date.

    Calque sur `MetalPrice`, et soumis a la meme discipline : une valeur sans
    source ni date n'est pas exploitable. Le constructeur refuse donc ce que
    `load_price_set` refuse pour un prix.

    Convention de paire : « BASE/COTATION », et `rate` donne le nombre
    d'unites de COTATION pour UNE unite de BASE. « EUR/USD » a 1,0842
    signifie donc 1 EUR = 1,0842 USD. C'est la convention des tables
    bancaires ; l'inverser silencieusement est exactement l'erreur que la
    bande de plausibilite doit attraper.
    """

    pair: str
    rate: float
    as_of: _dt.date
    source: str
    reference_name: str
    note: str = ""

    def __post_init__(self) -> None:
        if "/" not in self.pair:
            raise RateError(
                f"Paire {self.pair!r} mal formee : « BASE/COTATION » attendu, "
                "par exemple « EUR/USD »."
            )
        base, _, cotation = self.pair.partition("/")
        if not base.strip() or not cotation.strip():
            raise RateError(f"Paire {self.pair!r} incomplete.")
        if base.strip().upper() == cotation.strip().upper():
            raise RateError(
                f"Paire {self.pair!r} : une devise ne se convertit pas en "
                "elle-meme."
            )
        if not self.rate > 0:
            raise RateError(
                f"{self.pair} : taux {self.rate!r}. Un taux nul ou negatif "
                "n'a pas de sens."
            )
        # UN TAUX SANS SOURCE DECLAREE EST REFUSE. Meme exigence que pour un
        # prix : un chiffre sans origine n'est opposable a personne.
        if not str(self.source).strip():
            raise RateError(
                f"{self.pair} : source absente. Un taux sans source declaree "
                "n'est pas exploitable - c'est la meme exigence que pour un "
                "prix."
            )
        if not str(self.reference_name).strip():
            raise RateError(
                f"{self.pair} : libelle de reference absent. Indiquez quelle "
                "cotation precise a ete relevee."
            )

    # ------------------------------------------------------------------
    @property
    def base(self) -> str:
        return self.pair.partition("/")[0].strip().upper()

    @property
    def quote(self) -> str:
        return self.pair.partition("/")[2].strip().upper()

    def age_days(self, today: _dt.date | None = None) -> int:
        today = today or _dt.date.today()
        return (today - self.as_of).days

    def is_stale(self, today: _dt.date | None = None,
                 max_age: int = MAX_RATE_AGE_DAYS) -> bool:
        return self.age_days(today) > max_age

    def inverse(self) -> "ExchangeRate":
        """
        Le taux inverse, provenance conservee.

        L'inversion est une operation ARITHMETIQUE sur un taux declare, pas
        un nouveau taux : la source et la date restent celles du relevé
        d'origine, et le libelle dit que la valeur a ete inversee. Sans quoi
        la provenance laisserait croire que la banque a cote USD/EUR alors
        qu'elle a cote EUR/USD.
        """
        return ExchangeRate(
            pair=f"{self.quote}/{self.base}",
            rate=1.0 / self.rate,
            as_of=self.as_of,
            source=self.source,
            reference_name=f"{self.reference_name} (inverse)",
            note=self.note,
        )

    def libelle(self) -> str:
        """Une ligne de provenance, telle qu'elle part au rapport."""
        return (f"{self.pair} = {self.rate:.6g} "
                f"({self.reference_name}, {self.as_of.isoformat()}, "
                f"{self.source})")


# ==========================================================================
# Provenance d'une conversion
# ==========================================================================

@dataclass(frozen=True)
class Conversion:
    """
    Ce qu'est devenu un prix, et par quel chemin.

    Un chiffre sans origine est interdit partout ailleurs dans ce logiciel.
    Ici aussi : la valeur d'origine, sa devise, les taux appliques et leur
    provenance sont conserves, et c'est cette structure que le rapport lit.
    """

    metal: str
    value_origine: float
    devise_origine: str
    value_convertie: float
    devise_cible: str
    #: Un taux pour une paire directe, DEUX pour une paire croisee. Jamais
    #: un taux croise fabrique a partir d'un seul.
    taux: tuple[ExchangeRate, ...]
    #: Valeur au pivot en USD, quand la chaine en produit une. C'est la
    #: seule valeur sur laquelle la bande de plausibilite signifie quelque
    #: chose, puisque les bandes sont libellees en USD.
    valeur_usd: float | None = None
    plausibilite_verifiee: bool = False

    @property
    def convertie(self) -> bool:
        return self.devise_origine.upper() != self.devise_cible.upper()

    def libelle(self) -> str:
        """Mention de provenance, telle qu'elle part au rapport."""
        if not self.convertie:
            return (f"{self.metal} : {self.value_origine:,.2f} "
                    f"{self.devise_origine}/t, aucune conversion")
        chemin = " puis ".join(t.libelle() for t in self.taux)
        mention = (
            f"{self.metal} : {self.value_origine:,.2f} "
            f"{self.devise_origine}/t converti en "
            f"{self.value_convertie:,.2f} {self.devise_cible}/t "
            f"par {chemin}"
        )
        if not self.plausibilite_verifiee:
            mention += (" — bande de plausibilite NON VERIFIEE : la chaine de "
                        "conversion ne produit aucune valeur en "
                        f"{DEVISE_DES_BANDES}")
        return mention


@dataclass(frozen=True)
class PriceSetConverti(PriceSet):
    """
    Un jeu de prix issu d'une conversion, qui porte le detail de celle-ci.

    Sous-classe plutot que champ ajoute a `PriceSet` : `market.py` est a la
    base de la chaine de dependances et ne doit rien savoir de la
    conversion. Un `PriceSetConverti` reste un `PriceSet` partout ailleurs.
    """

    conversions: dict[str, Conversion] = field(default_factory=dict)

    def provenance_fx(self) -> list[str]:
        """Les mentions de conversion, dans l'ordre des metaux."""
        return [c.libelle() for _, c in sorted(self.conversions.items())
                if c.convertie]

    def taux_appliques(self) -> list[ExchangeRate]:
        """Les taux distincts effectivement utilises."""
        vus: dict[tuple, ExchangeRate] = {}
        for c in self.conversions.values():
            for t in c.taux:
                vus.setdefault((t.pair, t.rate, t.as_of, t.source), t)
        return [vus[k] for k in sorted(vus, key=lambda k: str(k))]


# ==========================================================================
# Chargement d'un fichier de taux - le SEUL chemin d'entree
# ==========================================================================

_CHAMPS_JSON = ("rate", "as_of", "source", "reference_name")

#: Intitules acceptes dans un CSV, par champ. Un fichier de banque arrive
#: avec les en-tetes de la banque, pas avec les notres.
_ALIAS_CSV = {
    "pair": ("pair", "paire", "couple", "devises", "currency_pair"),
    "rate": ("rate", "taux", "cours", "value", "valeur"),
    "as_of": ("as_of", "date", "date_de_cotation", "quote_date"),
    "source": ("source", "fournisseur", "provider", "banque"),
    "reference_name": ("reference_name", "reference", "libelle", "label",
                       "nom_de_reference"),
}


def _normaliser(intitule: str) -> str:
    return intitule.strip().lower().replace(" ", "_").replace("-", "_")


def _champ_csv(ligne: dict[str, str], champ: str) -> str | None:
    for alias in _ALIAS_CSV[champ]:
        for brut, valeur in ligne.items():
            if brut is None:
                continue
            if _normaliser(brut) == alias:
                return (valeur or "").strip()
    return None


def charger_taux(chemin: str | pathlib.Path) -> list[ExchangeRate]:
    """
    Charge des taux depuis un fichier fourni par l'utilisateur.

    Deux formats, reconnus a l'extension : JSON et CSV. Dans les deux cas,
    chaque taux porte sa valeur, sa date, sa source et son libelle de
    reference. Un champ manquant est une erreur, jamais une valeur par
    defaut - c'est la discipline de `load_price_set`, appliquee aux taux.

    Le format est documente dans le README, avec un exemple dans `data/`.
    """
    chemin = pathlib.Path(chemin)
    if not chemin.exists():
        raise RateError(f"Fichier de taux introuvable : {chemin}")

    if chemin.suffix.lower() == ".json":
        taux = _charger_json(chemin)
    elif chemin.suffix.lower() in (".csv", ".txt"):
        taux = _charger_csv(chemin)
    else:
        raise RateError(
            f"{chemin.name} : extension {chemin.suffix!r} non reconnue. "
            "Attendu : .json ou .csv."
        )

    if not taux:
        raise RateError(f"{chemin.name} : aucun taux lisible.")
    return taux


def _date(brut: object, ou: str) -> _dt.date:
    try:
        return _dt.date.fromisoformat(str(brut).strip()[:10])
    except (TypeError, ValueError):
        raise RateError(
            f"{ou} : date {brut!r} illisible. Format attendu : AAAA-MM-JJ."
        ) from None


def _charger_json(chemin: pathlib.Path) -> list[ExchangeRate]:
    with chemin.open(encoding="utf-8-sig") as fh:
        brut = json.load(fh)

    entrees = brut.get("rates", brut if isinstance(brut, dict) else {})
    if not isinstance(entrees, dict):
        raise RateError(
            f"{chemin.name} : objet 'rates' attendu, "
            "{\"EUR/USD\": {...}}."
        )

    # Des valeurs communes peuvent etre declarees une fois pour le fichier.
    defauts = {c: brut.get(c) for c in ("as_of", "source") if brut.get(c)}

    taux: list[ExchangeRate] = []
    for paire, d in entrees.items():
        if not isinstance(d, dict):
            raise RateError(
                f"{chemin.name} : {paire!r} doit porter un objet "
                "{rate, as_of, source, reference_name}."
            )
        fusion = {**defauts, **d}
        for champ in _CHAMPS_JSON:
            if champ not in fusion or fusion[champ] in (None, ""):
                raise RateError(
                    f"{chemin.name} : champ {champ!r} absent pour {paire!r}. "
                    "Un taux sans source ni date n'est pas exploitable."
                )
        taux.append(ExchangeRate(
            pair=str(paire).strip().upper(),
            rate=float(fusion["rate"]),
            as_of=_date(fusion["as_of"], f"{chemin.name} / {paire}"),
            source=str(fusion["source"]),
            reference_name=str(fusion["reference_name"]),
            note=str(fusion.get("note", "")),
        ))
    return taux


def _charger_csv(chemin: pathlib.Path) -> list[ExchangeRate]:
    with chemin.open(encoding="utf-8-sig", newline="") as fh:
        echantillon = fh.read(4096)
        fh.seek(0)
        delimiteur = ";" if echantillon.count(";") > echantillon.count(",") \
            else ","
        lignes = list(csv.DictReader(fh, delimiter=delimiteur))

    taux: list[ExchangeRate] = []
    for i, ligne in enumerate(lignes, start=2):
        if not any((v or "").strip() for v in ligne.values()):
            continue
        valeurs = {c: _champ_csv(ligne, c) for c in _ALIAS_CSV}
        manquants = [c for c, v in valeurs.items() if not v]
        if manquants:
            raise RateError(
                f"{chemin.name} ligne {i} : champ(s) {manquants} absent(s). "
                "Un taux sans source ni date n'est pas exploitable. "
                f"Intitules lus : {sorted(ligne)}."
            )
        try:
            valeur = float(str(valeurs["rate"]).replace(",", "."))
        except ValueError:
            raise RateError(
                f"{chemin.name} ligne {i} : taux {valeurs['rate']!r} "
                "illisible."
            ) from None
        taux.append(ExchangeRate(
            pair=str(valeurs["pair"]).strip().upper(),
            rate=valeur,
            as_of=_date(valeurs["as_of"], f"{chemin.name} ligne {i}"),
            source=str(valeurs["source"]),
            reference_name=str(valeurs["reference_name"]),
        ))
    return taux


# ==========================================================================
# Resolution d'une paire
# ==========================================================================

def _index(taux: list[ExchangeRate]) -> dict[tuple[str, str], ExchangeRate]:
    """
    Les taux utilisables, par (depuis, vers).

    Chaque taux declare sert dans les deux sens : l'inverse est une
    operation arithmetique sur un taux fourni, pas un taux invente. Le
    libelle de provenance le dit.
    """
    index: dict[tuple[str, str], ExchangeRate] = {}
    for t in taux:
        index.setdefault((t.base, t.quote), t)
        index.setdefault((t.quote, t.base), t.inverse())
    return index


def _chemin(depuis: str, vers: str,
            index: dict[tuple[str, str], ExchangeRate],
            pivot: str = DEVISE_DES_BANDES) -> tuple[ExchangeRate, ...]:
    """
    La suite de taux qui mene de `depuis` a `vers`.

    Un taux direct s'il existe. Sinon un croisement par le pivot, qui exige
    DEUX taux declares. Jamais un taux croise fabrique a partir d'un seul :
    c'est precisement ainsi qu'on invente un chiffre que personne n'a cote.
    """
    depuis, vers, pivot = depuis.upper(), vers.upper(), pivot.upper()
    if depuis == vers:
        return ()
    if (depuis, vers) in index:
        return (index[(depuis, vers)],)

    premier = index.get((depuis, pivot))
    second = index.get((pivot, vers))
    if premier is not None and second is not None:
        return (premier, second)

    manque = []
    if premier is None:
        manque.append(f"{depuis}/{pivot}")
    if second is None:
        manque.append(f"{pivot}/{vers}")
    raise MissingRateError(
        f"Aucun taux ne permet {depuis} -> {vers}. Fournissez le taux direct "
        f"{depuis}/{vers}, ou les deux taux du croisement par {pivot} "
        f"(manquant(s) : {', '.join(manque)}). Un taux croise ne se deduit "
        "pas d'un seul taux."
    )


# ==========================================================================
# La conversion
# ==========================================================================

def convertir(
    prices: PriceSet,
    vers: str,
    taux: ExchangeRate | list[ExchangeRate] | tuple[ExchangeRate, ...],
    *,
    aujourdhui: _dt.date | None = None,
    max_age: int = MAX_RATE_AGE_DAYS,
    strict_plausibilite: bool = True,
    pivot: str = DEVISE_DES_BANDES,
) -> PriceSetConverti:
    """
    Convertit un jeu de prix vers une devise unique.

    ACTE EXPLICITE. Rien dans la chaine n'appelle cette fonction de son
    propre chef : `check_currency()` continue de refuser un jeu mixte, et
    c'est voulu. Le taux engage la transaction de celui qui le fournit.

    Parameters
    ----------
    vers : devise cible, par exemple « EUR ».
    taux : un taux, ou plusieurs. Un croisement en exige deux, et les deux
        figurent dans la provenance.
    max_age : age maximal d'un taux, en jours. EXPOSE parce qu'il n'est pas
        arbitre - voir MAX_RATE_AGE_DAYS.
    strict_plausibilite : transmis a `units.check_plausible`. True refuse un
        metal sans bande definie.
    pivot : devise de croisement, et devise dans laquelle les bandes de
        plausibilite sont libellees. La changer suppose d'avoir aussi
        rebase les bandes de `units.py`.

    Raises
    ------
    RateError, StaleRateError, MissingRateError
        Taux sans source, perime, ou insuffisant pour la paire.
    ImplausiblePriceError
        La valeur en USD issue de la conversion sort de la bande. C'est le
        filet anti-erreur de taux : voir la docstring du module.
    """
    vers = str(vers).strip().upper()
    if not vers:
        raise RateError("Devise cible absente.")

    if isinstance(taux, ExchangeRate):
        taux = [taux]
    taux = list(taux)
    for t in taux:
        if not isinstance(t, ExchangeRate):
            raise RateError(
                f"{t!r} n'est pas un ExchangeRate. Chargez les taux avec "
                "charger_taux() plutot que de passer des nombres nus : un "
                "taux sans source n'est pas exploitable."
            )

    index = _index(taux)
    convertis: dict[str, MetalPrice] = {}
    conversions: dict[str, Conversion] = {}

    for metal, p in prices.prices.items():
        depuis = p.currency.strip().upper()
        chemin = _chemin(depuis, vers, index, pivot=pivot)

        # Un taux perime est refuse. Meme logique que MetalPrice.is_stale,
        # et le seuil est celui que l'appelant a choisi.
        for t in chemin:
            if t.is_stale(aujourdhui, max_age):
                raise StaleRateError(
                    f"{t.pair} releve le {t.as_of.isoformat()}, soit "
                    f"{t.age_days(aujourdhui)} jour(s), au-dela des "
                    f"{max_age} jour(s) admis. Fournissez un taux plus "
                    "recent, ou relevez max_age en connaissance de cause."
                )

        valeur = p.value_per_tonne
        valeur_usd = valeur if depuis == pivot else None
        for t in chemin:
            valeur = valeur * t.rate
            if t.quote == pivot:
                valeur_usd = valeur

        # LA BANDE EST LIBELLEE EN USD : on la verifie sur la valeur en USD
        # que la chaine produit, et sur elle seule. Voir la docstring du
        # module pour le chiffre qui le justifie.
        if vers == pivot:
            valeur_usd = valeur
        verifiee = valeur_usd is not None
        if verifiee:
            check_plausible(metal, valeur_usd, strict=strict_plausibilite)

        convertis[metal] = MetalPrice(
            metal=p.metal,
            value_per_tonne=valeur,
            currency=vers,
            as_of=p.as_of,
            source=p.source,
            reference_name=p.reference_name,
            note=p.note,
            basis=p.basis,
        )
        conversions[metal] = Conversion(
            metal=metal,
            value_origine=p.value_per_tonne,
            devise_origine=depuis,
            value_convertie=valeur,
            devise_cible=vers,
            taux=chemin,
            valeur_usd=valeur_usd,
            plausibilite_verifiee=verifiee,
        )

    sortie = PriceSetConverti(
        prices=convertis,
        currency=vers,
        label=prices.label,
        is_production_source=prices.is_production_source,
        origin=prices.origin,
        redistribution_licensed=prices.redistribution_licensed,
        conversions=conversions,
    )
    # Le jeu produit doit etre homogene : c'etait le but de l'operation.
    sortie.check_currency()
    return sortie
