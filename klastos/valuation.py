"""
KLASTOS21 - Valorisation d'un lot et prix maximal a payer.

Ce module consomme des prix, il n'en produit aucun. Les prix arrivent par
`klastos.providers`, sous la forme d'un `PriceSet` de `klastos.market`.

REGLE FONDATRICE
----------------
La valorisation ne s'appuie QUE sur des grandeurs fermes (cf. PROTOCOLE.md
section 2.1). Les teneurs elementaires sont identifiables ; la ventilation
par grade ne l'est pas. Un prix ne doit donc jamais dependre d'une
repartition NMC 622 / NMC 811.

CONVENTION DE MARCHE
--------------------
Un payable de black mass ne s'exprime pas en euros mais en POURCENTAGE d'un
prix de reference publie :

  nickel   -> LME Nickel cash official price
  cobalt   -> Fastmarkets cobalt standard grade, in-whs Rotterdam (point bas)
  lithium  -> carbonate de lithium qualite batterie, prix spot

Le manganese, le cuivre et l'aluminium ne sont generalement PAS payables :
ce sont des impuretes soumises a des teneurs maximales et a des penalites.

`value_lot()` n'a AUCUN jeu de prix par defaut. L'appelant doit declarer
explicitement d'ou viennent ses chiffres.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

from .market import (LI_FRACTION_IN_LI2CO3, MAX_PRICE_AGE_DAYS,
                     NotAProductionSourceError, PayableTerms, PriceSet,
                     Specification, StalePriceError)


# ==========================================================================
# Valorisation
# ==========================================================================

@dataclass
class MetalContribution:
    """Apport d'un element a la valeur du lot, par tonne de matiere."""

    element: str
    grade_low: float
    grade_high: float
    price_per_tonne: float
    payable: float
    reference_name: str
    value_low: float
    value_high: float

    @property
    def value_mid(self) -> float:
        return 0.5 * (self.value_low + self.value_high)


@dataclass
class Valuation:
    """
    Valeur d'un lot et prix maximal a payer, exprimes en fourchette.

    La fourchette provient de l'incertitude sur les teneurs FERMES. Elle
    n'incorpore aucune grandeur non identifiable, par construction.
    """

    contributions: list[MetalContribution]
    currency: str
    gross_low: float
    gross_high: float
    processing_cost: float
    margin_rate: float
    max_price_low: float
    max_price_high: float
    spec_deviations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    @property
    def gross_mid(self) -> float:
        return 0.5 * (self.gross_low + self.gross_high)

    @property
    def max_price_mid(self) -> float:
        return 0.5 * (self.max_price_low + self.max_price_high)

    @property
    def spread(self) -> float:
        """Largeur de la fourchette de prix maximal, en unites monetaires."""
        return self.max_price_high - self.max_price_low

    @property
    def is_conforme(self) -> bool:
        return not self.spec_deviations

    def format_max_price(self) -> str:
        return (
            f"{self.max_price_low:,.0f} \u2013 {self.max_price_high:,.0f} "
            f"{self.currency}/t"
        )


def value_lot(
    uncertainty_report,
    prices: PriceSet,
    terms: PayableTerms,
    spec: Specification | None = None,
    processing_cost: float = 0.0,
    margin_rate: float = 0.0,
    today: _dt.date | None = None,
    allow_stale: bool = False,
) -> Valuation:
    """
    Valorise un lot a partir d'un rapport d'incertitude.

    Parameters
    ----------
    uncertainty_report : sortie de klastos.uncertainty.propagate().
    prices : jeu de prix, OBLIGATOIRE et sans valeur par defaut. L'appelant
        doit declarer explicitement d'ou viennent ses chiffres.
    terms : conditions commerciales, egalement obligatoires.
    processing_cost : cout de traitement par tonne, meme devise que `prices`.
    margin_rate : marge visee, en fraction de la valeur brute.
    allow_stale : leve les verrous de fraicheur et de source. Reserve a la
        demonstration et aux tests. Jamais en production.

    Raises
    ------
    StalePriceError si un prix ou des conditions sont perimes.
    NotAProductionSourceError si le jeu de prix n'est pas declare comme
        source de production.
    """
    today = today or _dt.date.today()
    prices.check_currency()

    if not prices.is_production_source and not allow_stale:
        raise NotAProductionSourceError(
            f"Le jeu de prix {prices.label!r} (origine : {prices.origin or 'inconnue'}) "
            "n'est pas declare comme source de production. Brancher un flux via "
            "PriceProvider, ou passer allow_stale=True pour une demonstration."
        )

    avertissements: list[str] = []
    provenance: list[str] = []

    if not prices.is_production_source:
        avertissements.append(
            f"Jeu de prix de demonstration : {prices.label}. "
            "Resultat non opposable."
        )

    perimes = prices.stale(today)
    if perimes and not allow_stale:
        raise StalePriceError(
            f"Prix perimes pour {perimes} (plus de {MAX_PRICE_AGE_DAYS} jours). "
            "Actualiser le flux avant toute valorisation opposable."
        )
    if perimes:
        avertissements.append(
            f"Prix perimes utilises en mode demonstration : {', '.join(perimes)}."
        )

    if terms.is_stale(today):
        msg = (
            f"Conditions commerciales perimees : {terms.market}, "
            f"datees du {terms.as_of.isoformat()} "
            f"({terms.age_days(today)} jours). Valeur indicative uniquement."
        )
        if not allow_stale:
            raise StalePriceError(msg)
        avertissements.append(msg)
    if not terms.validated:
        avertissements.append(
            f"Conditions commerciales non validees : {terms.market}. {terms.note}"
        )

    # --- teneurs fermes uniquement ----------------------------------------
    par_cle = uncertainty_report.by_key()
    teneurs_basses: dict[str, float] = {}
    teneurs_hautes: dict[str, float] = {}
    teneurs_med: dict[str, float] = {}
    for cle, r in par_cle.items():
        if not cle.startswith("el_"):
            continue
        el = cle[3:]
        if not r.identifiable:
            avertissements.append(
                f"Teneur en {el} non identifiable : exclue de la valorisation."
            )
            continue
        teneurs_basses[el] = max(0.0, r.total_lower)
        teneurs_hautes[el] = max(0.0, r.total_upper)
        teneurs_med[el] = max(0.0, r.median or 0.0)

    # --- contributions -----------------------------------------------------
    contributions: list[MetalContribution] = []
    brut_bas = brut_haut = 0.0

    for el, payable in terms.payables.items():
        if el not in teneurs_basses:
            avertissements.append(
                f"Element payable {el} absent du rapport : ignore."
            )
            continue
        p = prices.get(el)

        # Un prix cote en carbonate est ramene au lithium contenu.
        # La base est declaree dans le fichier de prix, pas devinee du nom.
        prix_effectif = p.value_per_tonne
        if p.basis == "Li2CO3":
            prix_effectif = p.value_per_tonne / LI_FRACTION_IN_LI2CO3

        v_bas = teneurs_basses[el] * prix_effectif * payable
        v_haut = teneurs_hautes[el] * prix_effectif * payable
        brut_bas += v_bas
        brut_haut += v_haut

        contributions.append(
            MetalContribution(
                element=el,
                grade_low=teneurs_basses[el],
                grade_high=teneurs_hautes[el],
                price_per_tonne=prix_effectif,
                payable=payable,
                reference_name=p.reference_name,
                value_low=v_bas,
                value_high=v_haut,
            )
        )
        provenance.append(
            f"{el} : {payable*100:.2f} % de {p.reference_name} "
            f"({p.value_per_tonne:,.0f} {p.currency}/t, {p.as_of.isoformat()}, "
            f"{p.source})"
        )

    if terms.lithium_included_in_ni_co and "Li" not in terms.payables:
        avertissements.append(
            "La valeur du lithium est reputee incluse dans les payables nickel "
            "et cobalt : elle n'est pas valorisee separement."
        )

    # --- conformite --------------------------------------------------------
    ecarts: list[str] = []
    if spec is not None:
        ecarts = spec.check(teneurs_med)
        if ecarts:
            avertissements.append(
                f"Lot non conforme a la specification {spec.name} : "
                "decote ou refus a prevoir, non chiffres en v0."
            )

    # --- prix maximal a payer ---------------------------------------------
    facteur = 1.0 - margin_rate
    pmax_bas = brut_bas * facteur - processing_cost
    pmax_haut = brut_haut * facteur - processing_cost

    # --- diagnostics amont -------------------------------------------------
    bouclage = getattr(uncertainty_report, "meta", {}).get("closure")
    if bouclage is not None and bouclage.status != "ok":
        avertissements.append(f"Bouclage massique : {bouclage.message}")

    if uncertainty_report.degeneracy > 0:
        avertissements.append(
            f"Systeme degenere ({uncertainty_report.degeneracy} degre(s) de "
            "liberte). La valorisation ne repose que sur les teneurs "
            "elementaires, qui restent fermes."
        )

    return Valuation(
        contributions=contributions,
        currency=prices.currency,
        gross_low=brut_bas,
        gross_high=brut_haut,
        processing_cost=processing_cost,
        margin_rate=margin_rate,
        max_price_low=pmax_bas,
        max_price_high=pmax_haut,
        spec_deviations=ecarts,
        warnings=avertissements,
        provenance=provenance,
        meta={
            "terms": terms,
            "prices_label": prices.label,
            "prices_origin": prices.origin,
            # Droit d'afficher ces prix a un tiers. Transporte jusqu'au
            # rapport, qui est le seul endroit ou la question se pose.
            "redistribution_licensed": prices.redistribution_licensed,
            "as_of": today,
            "grades_median": teneurs_med,
        },
    )
