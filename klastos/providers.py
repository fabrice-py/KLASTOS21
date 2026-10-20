"""
KLASTOS21 - Fournisseurs de prix interchangeables.

Trois routes d'approvisionnement, une seule interface
-----------------------------------------------------
1. PRIX APPORTES PAR LE CLIENT (CSV, JSON, saisie datee). Route prioritaire :
   gratuite, sans licence a rediffuser, et plus juste puisqu'elle reflete les
   conditions contractuelles reelles du client plutot qu'un indice public.
2. SOURCES PUBLIQUES ET DERIVEES (flux differes, reglements de contrats a
   terme). Route de secours pour les metaux de bourse.
3. EVALUATION PROPRE, construite sur les transactions observees. Route de
   long terme : c'est un actif, pas une depense.

Toutes exposent la meme interface `fetch()`. Ajouter une route n'impose
aucune reecriture du reste du code.

Ce que ce module refuse de faire
--------------------------------
- Deviner une unite de cotation. Elle est declaree, ou la lecture echoue.
- Accepter un prix sans date ni source.
- Laisser passer un prix hors bande de plausibilite.
- Extraire des donnees de sites soumis a licence : le droit sui generis des
  bases de donnees protege les recueils d'evaluations, et une valorisation
  fondee sur une source illicite n'est pas defendable devant un client.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import pathlib
from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol

from .market import MetalPrice, MissingPriceError, PriceSet
from .units import PriceUnit, check_plausible

# ==========================================================================
# Cotation brute, avant normalisation
# ==========================================================================

@dataclass(frozen=True)
class RawQuote:
    """
    Une cotation telle que la rend une source, AVANT conversion.

    Aucun champ n'a de valeur par defaut a l'exception de `basis` et `note` :
    une cotation sans unite, sans date ou sans source n'est pas exploitable.
    """

    metal: str
    value: float
    unit: PriceUnit
    currency: str
    as_of: _dt.date
    source: str
    reference_name: str
    basis: str = "metal"      # "metal", "Li2CO3", "LiOH"...
    note: str = ""

    def to_metal_price(self, strict_band: bool = True) -> MetalPrice:
        """Convertit vers un prix a la tonne, apres controle de plausibilite."""
        par_tonne = self.unit.to_per_tonne(self.value)
        check_plausible(self.metal, par_tonne, strict=strict_band)
        note = self.note
        if self.unit is not PriceUnit.PER_TONNE:
            conv = f"Converti depuis {self.value:,.4f} {self.unit.label}."
            note = f"{note} {conv}".strip()
        return MetalPrice(
            metal=self.metal,
            value_per_tonne=par_tonne,
            currency=self.currency,
            as_of=self.as_of,
            source=self.source,
            reference_name=self.reference_name,
            note=note,
            basis=self.basis,
        )


class ProviderError(RuntimeError):
    """Echec d'un fournisseur de prix."""


class PriceProvider(Protocol):
    """Toute source capable de rendre des cotations brutes."""

    name: str

    def quotes(self) -> list[RawQuote]: ...


def build_price_set(
    quotes: Iterable[RawQuote],
    label: str,
    currency: str = "USD",
    is_production_source: bool = True,
    origin: str = "",
    strict_band: bool = True,
    redistribution_licensed: bool = True,
) -> PriceSet:
    """
    Assemble des cotations brutes en jeu de prix normalise et controle.

    `redistribution_licensed` vaut True par defaut parce que la route la
    plus courante est le fichier fourni par le client : ses propres prix,
    qu'aucune licence d'agence ne restreint. Les flux d'agence passent
    explicitement le drapeau de leur abonnement.
    """
    prix: dict[str, MetalPrice] = {}
    for q in quotes:
        if q.currency != currency:
            raise ProviderError(
                f"{q.metal} cote en {q.currency}, jeu declare en {currency}. "
                "La conversion de devise doit etre explicite, jamais implicite."
            )
        prix[q.metal] = q.to_metal_price(strict_band=strict_band)
    if not prix:
        raise ProviderError("Aucune cotation exploitable.")
    ps = PriceSet(
        prices=prix, currency=currency, label=label,
        is_production_source=is_production_source, origin=origin,
        redistribution_licensed=redistribution_licensed,
    )
    ps.check_currency()
    return ps


# ==========================================================================
# Route 1 : prix apportes par le client
# ==========================================================================

@dataclass
class CSVProvider:
    """
    Export quotidien du client. Route la plus frequente en pratique.

    Colonnes attendues : metal, value, unit, currency, as_of, source,
    reference_name. Colonnes optionnelles : basis, note.

    `unit` prend les valeurs "USD/t", "USD/kg", "USD/lb", "USD/oz t".
    Une unite absente ou inconnue provoque une erreur : elle n'est jamais
    devinee.
    """

    path: str | pathlib.Path
    name: str = "csv"
    delimiter: str = ","

    _UNITES = {u.label: u for u in PriceUnit}
    REQUIS = ("metal", "value", "unit", "currency", "as_of", "source",
              "reference_name")

    def quotes(self) -> list[RawQuote]:
        p = pathlib.Path(self.path)
        if not p.exists():
            raise ProviderError(f"Fichier de prix absent : {p}")
        out: list[RawQuote] = []
        with p.open(encoding="utf-8-sig", newline="") as fh:
            lecteur = csv.DictReader(fh, delimiter=self.delimiter)
            for i, ligne in enumerate(lecteur, start=2):
                manquants = [c for c in self.REQUIS if not ligne.get(c)]
                if manquants:
                    raise ProviderError(
                        f"{p.name} ligne {i} : colonnes absentes {manquants}."
                    )
                libelle = ligne["unit"].strip()
                if libelle not in self._UNITES:
                    raise ProviderError(
                        f"{p.name} ligne {i} : unite {libelle!r} inconnue. "
                        f"Valeurs admises : {sorted(self._UNITES)}. "
                        "L'unite n'est jamais deduite."
                    )
                out.append(RawQuote(
                    metal=ligne["metal"].strip(),
                    value=float(ligne["value"]),
                    unit=self._UNITES[libelle],
                    currency=ligne["currency"].strip(),
                    as_of=_dt.date.fromisoformat(ligne["as_of"].strip()),
                    source=ligne["source"].strip(),
                    reference_name=ligne["reference_name"].strip(),
                    basis=(ligne.get("basis") or "metal").strip(),
                    note=(ligne.get("note") or "").strip(),
                ))
        return out


@dataclass
class ManualEntryProvider:
    """
    Saisie manuelle datee et signee, pour les references sans flux.

    L'operateur est enregistre : une valorisation reposant sur une saisie
    manuelle doit pouvoir etre rattachee a une personne.
    """

    entries: list[RawQuote]
    operator: str
    name: str = "saisie_manuelle"

    def quotes(self) -> list[RawQuote]:
        if not self.operator.strip():
            raise ProviderError(
                "Une saisie manuelle exige l'identite de l'operateur."
            )
        return [
            RawQuote(
                metal=q.metal, value=q.value, unit=q.unit, currency=q.currency,
                as_of=q.as_of, source=f"{q.source} (saisi par {self.operator})",
                reference_name=q.reference_name, basis=q.basis, note=q.note,
            )
            for q in self.entries
        ]


# ==========================================================================
# Route 2 : sources publiques et derivees
# ==========================================================================

@dataclass
class HTTPProvider:
    """
    Fournisseur REST generique.

    La fonction reseau est INJECTEE (`fetcher`), ce qui rend le fournisseur
    testable hors ligne et independant de la bibliotheque HTTP retenue.

    `mapping` associe chaque metal a la maniere de le lire dans la reponse :
        {"Ni": {"path": ["rates", "LME-NI"], "unit": PriceUnit.PER_TROY_OUNCE,
                "reference_name": "LME Nickel"}}

    L'unite est declaree dans le mapping, une fois pour toutes, au moment de
    la configuration. Elle ne depend jamais de la reponse.
    """

    url: str
    mapping: dict[str, dict]
    fetcher: Callable[[str], dict]
    source_label: str
    currency: str = "USD"
    date_path: tuple[str, ...] = ("date",)
    name: str = "http"

    def _lire(self, payload: dict, chemin: Iterable[str]):
        courant = payload
        for cle in chemin:
            if not isinstance(courant, dict) or cle not in courant:
                raise ProviderError(
                    f"{self.source_label} : chemin {list(chemin)} absent de la reponse."
                )
            courant = courant[cle]
        return courant

    def quotes(self) -> list[RawQuote]:
        try:
            payload = self.fetcher(self.url)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"{self.source_label} injoignable : {exc}") from exc

        brut_date = self._lire(payload, self.date_path)
        as_of = (
            brut_date if isinstance(brut_date, _dt.date)
            else _dt.date.fromisoformat(str(brut_date))
        )

        out: list[RawQuote] = []
        for metal, conf in self.mapping.items():
            if "unit" not in conf:
                raise ProviderError(
                    f"Mapping de {metal!r} sans unite declaree. "
                    "L'unite est obligatoire a la configuration."
                )
            valeur = float(self._lire(payload, conf["path"]))
            out.append(RawQuote(
                metal=metal,
                value=valeur,
                unit=conf["unit"],
                currency=conf.get("currency", self.currency),
                as_of=as_of,
                source=self.source_label,
                reference_name=conf.get("reference_name", metal),
                basis=conf.get("basis", "metal"),
                note=conf.get("note", ""),
            ))
        return out


@dataclass
class JSONFileProvider:
    """Instantane JSON deja normalise, au format de `data/`."""

    path: str | pathlib.Path
    name: str = "json"

    def quotes(self) -> list[RawQuote]:
        p = pathlib.Path(self.path)
        if not p.exists():
            raise ProviderError(f"Fichier absent : {p}")
        brut = json.loads(p.read_text(encoding="utf-8"))
        devise = brut.get("currency")
        if not devise:
            raise ProviderError(f"{p.name} : champ 'currency' absent.")
        return [
            RawQuote(
                metal=metal,
                value=float(d["value_per_tonne"]),
                unit=PriceUnit.PER_TONNE,
                currency=devise,
                as_of=_dt.date.fromisoformat(d["as_of"]),
                source=d["source"],
                reference_name=d["reference_name"],
                basis=d.get("basis", "metal"),
                note=d.get("note", ""),
            )
            for metal, d in brut.get("prices", {}).items()
        ]


# ==========================================================================
# Agregation, repli et cache
# ==========================================================================

@dataclass
class SourceLedger:
    """Journal de provenance : quel fournisseur a servi quel metal."""

    served: dict[str, str] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = [f"{m} : fourni par {s}" for m, s in sorted(self.served.items())]
        out += [f"echec : {e}" for e in self.failures]
        return out


@dataclass
class AggregatingProvider:
    """
    Empile des fournisseurs par ordre de preference.

    Le premier fournisseur qui rend un metal l'emporte. Les suivants ne
    servent que les metaux encore manquants. Une panne n'interrompt pas la
    chaine : elle est journalisee et le fournisseur suivant prend le relais.

    Ordre recommande :
        1. prix deposes par le client
        2. flux public ou derive
        3. instantane en cache

    `required` liste les metaux sans lesquels le jeu est inutilisable.
    """

    providers: list[PriceProvider]
    required: tuple[str, ...] = ()
    name: str = "agregat"
    ledger: SourceLedger = field(default_factory=SourceLedger)

    def quotes(self) -> list[RawQuote]:
        retenues: dict[str, RawQuote] = {}
        self.ledger = SourceLedger()
        for fournisseur in self.providers:
            try:
                lot = fournisseur.quotes()
            except Exception as exc:
                self.ledger.failures.append(f"{fournisseur.name} : {exc}")
                continue
            for q in lot:
                if q.metal not in retenues:
                    retenues[q.metal] = q
                    self.ledger.served[q.metal] = fournisseur.name

        manquants = [m for m in self.required if m not in retenues]
        if manquants:
            raise ProviderError(
                f"Metaux requis non fournis : {manquants}. "
                f"Journal : {self.ledger.lines()}"
            )
        if not retenues:
            raise ProviderError(
                f"Aucun fournisseur n'a repondu. Journal : {self.ledger.lines()}"
            )
        return list(retenues.values())


@dataclass
class CachingProvider:
    """
    Cache disque autour d'un fournisseur.

    Un client attend son rapport : une panne reseau ne doit pas interrompre
    le service. Le cache sert de repli, avec sa date d'origine conservee -
    les verrous d'anciennete de `pricing` s'appliquent donc normalement au
    contenu servi depuis le cache.
    """

    provider: PriceProvider
    cache_path: str | pathlib.Path
    name: str = "cache"
    served_from_cache: bool = False

    def _ecrire(self, quotes: list[RawQuote]) -> None:
        p = pathlib.Path(self.cache_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "cached_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "quotes": [{
                "metal": q.metal, "value": q.value, "unit": q.unit.label,
                "currency": q.currency, "as_of": q.as_of.isoformat(),
                "source": q.source, "reference_name": q.reference_name,
                "basis": q.basis, "note": q.note,
            } for q in quotes],
        }, indent=2), encoding="utf-8")

    def _lire(self) -> list[RawQuote]:
        p = pathlib.Path(self.cache_path)
        if not p.exists():
            raise ProviderError(f"Aucun cache disponible en {p}.")
        brut = json.loads(p.read_text(encoding="utf-8"))
        unites = {u.label: u for u in PriceUnit}
        return [
            RawQuote(
                metal=d["metal"], value=float(d["value"]),
                unit=unites[d["unit"]], currency=d["currency"],
                as_of=_dt.date.fromisoformat(d["as_of"]),
                source=f"{d['source']} [servi depuis le cache]",
                reference_name=d["reference_name"],
                basis=d.get("basis", "metal"), note=d.get("note", ""),
            )
            for d in brut["quotes"]
        ]

    def quotes(self) -> list[RawQuote]:
        try:
            q = self.provider.quotes()
        except Exception:
            self.served_from_cache = True
            return self._lire()
        self.served_from_cache = False
        self._ecrire(q)
        return q


# ==========================================================================
# Pink Sheet de la Banque mondiale - la seule source gratuite et rediffusable
# ==========================================================================

#: Adresse du classeur mensuel. CONFIGURABLE, et pour une raison mesuree :
#: l'URL porte un identifiant de document qui a DEJA change entre les
#: editions 2025 et 2026. Un lien code en dur dans le module casserait une
#: analyse le jour ou la Banque mondiale republie.
PINK_SHEET_URL = (
    "https://thedocs.worldbank.org/en/doc/"
    "18675f1d1639c7a34d463f59263ba0a2-0050012025/related/"
    "CMO-Historical-Data-Monthly.xlsx"
)

#: Emplacement local par defaut du classeur telecharge.
PINK_SHEET_FICHIER = pathlib.Path("data") / "CMO-Historical-Data-Monthly.xlsx"

#: Attribution exigee par la licence de reutilisation. Elle part dans la
#: provenance ET dans le rapport : c'est la contrepartie de la gratuite.
PINK_SHEET_ATTRIBUTION = "Banque mondiale, Commodity Price Data (Pink Sheet)"

#: Les TROIS metaux que le Pink Sheet cote, et eux seuls. Verifie sur
#: l'edition d'octobre 2026. La table associe le symbole au libelle de
#: colonne du classeur.
PINK_SHEET_METAUX = {
    "Al": "Aluminum",
    "Cu": "Copper",
    "Ni": "Nickel",
}

#: Ce que le Pink Sheet NE cote PAS, et ou le chercher. Un operateur qui
#: demande le cobalt doit lire une adresse, pas un zero.
PINK_SHEET_ABSENTS = {
    "Co": "cobalt",
    "Li": "lithium",
    "Mn": "manganese",
    "C": "graphite",
}

_OU_TROUVER = (
    "Le Pink Sheet de la Banque mondiale ne cote ni le cobalt, ni le "
    "lithium, ni le manganese, ni le graphite : ce sont des marches de gre "
    "a gre, sans cotation de bourse. Il faut une evaluation d'agence "
    "(Fastmarkets, Benchmark Mineral Intelligence, SMM - voir "
    "klastos/feeds.py) ou les prix contractuels du client."
)


class PinkSheetProvider:
    """
    Moyennes mensuelles de la Banque mondiale, lues dans un fichier LOCAL.

    Pourquoi un fichier local, et pas un telechargement
    ---------------------------------------------------
    DECISION. L'URL du classeur porte un identifiant de document qui a deja
    change entre les editions 2025 et 2026. Telecharger a chaque analyse
    ferait dependre une valorisation d'un lien susceptible de mourir sans
    preavis. Le fichier est donc telecharge SEPAREMENT - `klastos pink-sheet
    --rafraichir` - et le fournisseur lit ce qui est sur le disque.

    L'echec est BRUYANT : fichier absent, feuille introuvable, metal absent
    du classeur produisent une erreur nommee, jamais un zero ni un silence.

    Ce que cette source est, et n'est pas
    -------------------------------------
    Ce sont des MOYENNES MENSUELLES officielles, pas des evaluations spot.
    `is_production_source` vaut donc False : un negociant qui traite au
    comptant ne peut pas opposer une moyenne d'octobre a une cargaison du
    21 octobre. Le mois retenu figure dans le libelle de reference et dans
    la note, pour qu'aucune moyenne ne passe pour une cotation du jour.

    En revanche la donnee est PUBLIQUE et reutilisable avec attribution :
    c'est le seul flux de KLASTOS21 ou `redistribution_licensed` vaut True.
    """

    name = "pink_sheet"

    #: Donnee publique, reutilisable avec attribution. UNIQUE parmi les
    #: flux : une evaluation d'agence ne peut jamais figurer dans un
    #: document remis a un tiers sans licence ecrite.
    redistribution_licensed = True

    #: Moyennes mensuelles, donc PAS une source de cotation de production.
    is_production_source = False

    def __init__(
        self,
        chemin: str | pathlib.Path | None = None,
        *,
        feuille: str = "Monthly Prices",
        url: str = PINK_SHEET_URL,
        mois: str | None = None,
    ) -> None:
        self.chemin = pathlib.Path(chemin or PINK_SHEET_FICHIER)
        self.feuille = feuille
        self.url = url
        #: Mois voulu, au format du classeur (« 2026M10 »). None prend le
        #: dernier mois renseigne.
        self.mois = mois

    # ------------------------------------------------------------------
    def quotes(self, metaux: Iterable[str] | None = None) -> list[RawQuote]:
        """
        Les cotations des metaux demandes, par defaut les trois disponibles.

        Demander un metal absent du Pink Sheet leve `MissingPriceError` avec
        l'adresse ou le trouver. Jamais un zero : une valorisation fondee
        sur un cobalt a zero serait fausse sans qu'aucun controle la refuse.
        """
        voulus = list(metaux) if metaux is not None else list(PINK_SHEET_METAUX)

        inconnus = [m for m in voulus if m not in PINK_SHEET_METAUX]
        if inconnus:
            absents = [m for m in inconnus if m in PINK_SHEET_ABSENTS]
            if absents:
                noms = ", ".join(PINK_SHEET_ABSENTS[m] for m in absents)
                raise MissingPriceError(
                    f"{noms} ({', '.join(absents)}) absent(s) du Pink "
                    f"Sheet. {_OU_TROUVER}"
                )
            raise MissingPriceError(
                f"{inconnus} hors du Pink Sheet. Metaux disponibles : "
                f"{sorted(PINK_SHEET_METAUX)}. {_OU_TROUVER}"
            )

        table, mois = self._lire(voulus)
        annee, _, numero = mois.partition("M")
        try:
            date = _dt.date(int(annee), int(numero), 1)
        except ValueError:
            raise ProviderError(
                f"{self.chemin.name} : periode {mois!r} illisible. Format "
                "attendu : « 2026M10 »."
            ) from None

        out: list[RawQuote] = []
        for metal in voulus:
            valeur = table[metal]
            out.append(RawQuote(
                metal=metal,
                value=valeur,
                # Le classeur cote en dollars la tonne metrique. L'unite est
                # LUE dans le classeur par `_lire`, jamais devinee.
                unit=PriceUnit.PER_TONNE,
                currency="USD",
                # Premier jour du mois : une moyenne mensuelle n'a pas de
                # jour, et lui en inventer un la ferait passer pour un spot.
                as_of=date,
                source=PINK_SHEET_ATTRIBUTION,
                reference_name=(
                    f"{PINK_SHEET_METAUX[metal]}, moyenne mensuelle "
                    f"{annee}-{int(numero):02d}"
                ),
                note=(
                    f"MOYENNE MENSUELLE {annee}-{int(numero):02d}, pas une "
                    f"evaluation spot. {PINK_SHEET_ATTRIBUTION}."
                ),
            ))
        return out

    def fetch(self) -> PriceSet:
        """Jeu de prix complet, avec son attribution et sa licence."""
        cotations = self.quotes()
        mois = cotations[0].as_of
        return build_price_set(
            cotations,
            label=(f"Pink Sheet {mois:%Y-%m} (moyennes mensuelles) - "
                   f"{PINK_SHEET_ATTRIBUTION}"),
            is_production_source=self.is_production_source,
            origin=self.name,
            redistribution_licensed=self.redistribution_licensed,
        )

    # ------------------------------------------------------------------
    def _lire(self, voulus: list[str]) -> tuple[dict[str, float], str]:
        """
        Lit le classeur et rend {symbole: valeur} plus le mois retenu.

        Toute anomalie leve : le silence serait pire qu'une erreur, puisque
        la valeur manquante partirait en valorisation.
        """
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise ProviderError(
                "openpyxl est requis pour lire le classeur Pink Sheet. "
                "Installez-le : pip install openpyxl"
            ) from None

        if not self.chemin.exists():
            raise ProviderError(
                f"Classeur Pink Sheet absent : {self.chemin}. "
                f"Telechargez-le avec « klastos pink-sheet --rafraichir », "
                f"ou depuis {self.url}"
            )

        classeur = load_workbook(self.chemin, data_only=True, read_only=True)
        try:
            if self.feuille not in classeur.sheetnames:
                raise ProviderError(
                    f"{self.chemin.name} : feuille {self.feuille!r} "
                    f"introuvable. Feuilles presentes : "
                    f"{classeur.sheetnames}. La Banque mondiale a pu "
                    "renommer l'onglet : passez `feuille=`."
                )
            lignes = [list(r) for r in classeur[self.feuille].iter_rows(
                values_only=True)]
        finally:
            classeur.close()

        colonnes, ligne_entete = self._colonnes(lignes, voulus)
        unites = self._unites(lignes, ligne_entete, colonnes)
        mois, valeurs = self._valeurs(lignes, ligne_entete, colonnes)

        # L'unite est LUE, jamais devinee : c'est l'engagement de units.py.
        for metal, libelle in unites.items():
            if libelle and "mt" not in libelle.lower():
                raise ProviderError(
                    f"{self.chemin.name} : {PINK_SHEET_METAUX[metal]} cote "
                    f"en {libelle!r}, alors que la tonne metrique est "
                    "attendue. L'unite n'est jamais deduite : verifiez "
                    "l'edition du classeur."
                )
        return valeurs, mois

    def _colonnes(self, lignes: list[list], voulus: list[str]
                  ) -> tuple[dict[str, int], int]:
        """Repere la ligne d'en-tete et l'indice de colonne de chaque metal."""
        attendus = {PINK_SHEET_METAUX[m].lower(): m for m in voulus}
        for i, ligne in enumerate(lignes):
            trouve: dict[str, int] = {}
            for j, cel in enumerate(ligne):
                nom = str(cel).strip().lower() if cel is not None else ""
                if nom in attendus:
                    trouve[attendus[nom]] = j
            if len(trouve) == len(voulus):
                return trouve, i
        raise ProviderError(
            f"{self.chemin.name} : colonnes "
            f"{[PINK_SHEET_METAUX[m] for m in voulus]} introuvables dans la "
            f"feuille {self.feuille!r}. La Banque mondiale a pu renommer une "
            "serie : l'echec est volontairement bruyant plutot que silencieux."
        )

    def _unites(self, lignes: list[list], ligne_entete: int,
                colonnes: dict[str, int]) -> dict[str, str]:
        """L'unite declaree sous chaque en-tete, si le classeur la porte."""
        for ligne in lignes[ligne_entete + 1:ligne_entete + 4]:
            cellules = {m: ligne[j] if j < len(ligne) else None
                        for m, j in colonnes.items()}
            textes = {m: str(v).strip() for m, v in cellules.items()
                      if isinstance(v, str) and v.strip()}
            if len(textes) == len(colonnes):
                return textes
        return {}

    def _valeurs(self, lignes: list[list], ligne_entete: int,
                 colonnes: dict[str, int]) -> tuple[str, dict[str, float]]:
        """Le mois retenu et ses valeurs. Dernier mois complet par defaut."""
        import re

        periode = re.compile(r"^\s*(\d{4})M(\d{1,2})\s*$")
        candidats: list[tuple[str, dict[str, float]]] = []
        for ligne in lignes[ligne_entete + 1:]:
            if not ligne:
                continue
            m = periode.match(str(ligne[0] or ""))
            if not m:
                continue
            mois = f"{m.group(1)}M{m.group(2)}"
            valeurs: dict[str, float] = {}
            for metal, j in colonnes.items():
                brut = ligne[j] if j < len(ligne) else None
                try:
                    valeurs[metal] = float(str(brut).replace(",", "."))
                except (TypeError, ValueError):
                    valeurs = {}
                    break
            if valeurs:
                candidats.append((mois, valeurs))

        if not candidats:
            raise ProviderError(
                f"{self.chemin.name} : aucune ligne mensuelle exploitable "
                f"pour {sorted(colonnes)}. Les periodes sont attendues au "
                "format « 2026M10 » en premiere colonne."
            )

        if self.mois is None:
            return candidats[-1]

        voulu = self.mois.strip().upper()
        for mois, valeurs in candidats:
            if mois == voulu:
                return mois, valeurs
        raise ProviderError(
            f"{self.chemin.name} : mois {voulu!r} absent du classeur. "
            f"Derniere periode disponible : {candidats[-1][0]}."
        )
