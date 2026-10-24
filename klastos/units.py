"""
KLASTOS21 - Unites de cotation et bandes de plausibilite.

Pourquoi un module dedie
------------------------
Les fournisseurs de prix ne cotent pas dans la meme unite. Certaines API
renvoient les prix LME par once troy : la conversion en tonne exige un
facteur 32 150. Une omission silencieuse produit une valorisation fausse
d'un facteur trente mille, sans aucun signe exterieur d'erreur.

Deux protections, cumulatives.

1. L'unite est OBLIGATOIRE a l'entree. Aucune valeur par defaut, aucune
   deduction a partir du nom du metal ou de l'ordre de grandeur.
2. Une BANDE DE PLAUSIBILITE par metal. Un prix converti qui en sort est
   rejete. Une erreur d'unite depasse toujours la bande de plusieurs ordres
   de grandeur : elle ne peut pas passer inapercue.

La bande est un filet de securite, pas une prevision de marche. Elle est
volontairement tres large.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Conversions exactes ou normalisees.
KG_PER_TONNE = 1000.0
LB_PER_TONNE = 2204.622621848776          # 1 lb = 0,453 592 37 kg exactement
TROY_OZ_PER_TONNE = 1_000_000.0 / 31.1034768   # 1 oz t = 31,103 476 8 g


class PriceUnit(Enum):
    """Unite de cotation. `units_per_tonne` convertit vers le prix a la tonne."""

    PER_TONNE = ("USD/t", 1.0)
    PER_KILOGRAM = ("USD/kg", KG_PER_TONNE)
    PER_POUND = ("USD/lb", LB_PER_TONNE)
    PER_TROY_OUNCE = ("USD/oz t", TROY_OZ_PER_TONNE)
    #: Cents par livre. L'USGS cote le cuivre et l'aluminium dans cette
    #: unite, et la confondre avec le dollar par livre fausse la
    #: valorisation d'un facteur CENT. Elle existe donc comme unite a part
    #: entiere, declaree et lue, plutot que par une division cachee dans un
    #: fournisseur.
    PER_POUND_CENT = ("USD cent/lb", LB_PER_TONNE / 100.0)

    def __init__(self, label: str, units_per_tonne: float) -> None:
        self.label = label
        self.units_per_tonne = units_per_tonne

    def to_per_tonne(self, value: float) -> float:
        """Convertit un prix exprime dans cette unite vers un prix a la tonne."""
        return value * self.units_per_tonne


class ImplausiblePriceError(ValueError):
    """Prix hors bande de plausibilite. Presume erreur d'unite ou de source."""


@dataclass(frozen=True)
class PlausibilityBand:
    """Fourchette large au-dela de laquelle un prix est refuse."""

    metal: str
    low_per_tonne: float
    high_per_tonne: float
    rationale: str = ""

    def check(self, value_per_tonne: float) -> None:
        if not (self.low_per_tonne <= value_per_tonne <= self.high_per_tonne):
            raise ImplausiblePriceError(
                f"{self.metal} a {value_per_tonne:,.0f} USD/t, hors bande "
                f"[{self.low_per_tonne:,.0f} ; {self.high_per_tonne:,.0f}]. "
                "Cause la plus probable : unite de cotation erronee. "
                "Verifier que le fournisseur cote bien dans l'unite declaree."
            )


# --------------------------------------------------------------------------
# Bandes de plausibilite.
#
# A VALIDER : bornes deliberement tres larges, destinees a n'attraper que les
# erreurs grossieres (facteur 1000 ou 32 150). Elles ne constituent PAS une
# opinion sur le marche et ne doivent jamais servir a borner une valorisation.
# --------------------------------------------------------------------------
PLAUSIBILITY_BANDS: dict[str, PlausibilityBand] = {
    "Ni": PlausibilityBand("Ni", 5_000.0, 100_000.0,
                           "A VALIDER. Bande large anti-erreur d'unite."),
    "Co": PlausibilityBand("Co", 15_000.0, 250_000.0,
                           "A VALIDER. Bande large anti-erreur d'unite."),
    "Cu": PlausibilityBand("Cu", 3_000.0, 40_000.0,
                           "A VALIDER. Bande large anti-erreur d'unite."),
    "Li": PlausibilityBand("Li", 3_000.0, 200_000.0,
                           "A VALIDER. Couvre carbonate et lithium contenu."),
    "Mn": PlausibilityBand("Mn", 500.0, 20_000.0,
                           "A VALIDER. Bande large anti-erreur d'unite."),
    "Al": PlausibilityBand("Al", 800.0, 15_000.0,
                           "A VALIDER. Bande large anti-erreur d'unite."),
}


def check_plausible(metal: str, value_per_tonne: float, strict: bool = True) -> None:
    """
    Verifie qu'un prix converti est plausible.

    `strict=True` refuse un metal sans bande definie : mieux vaut declarer la
    bande que laisser passer une valeur non controlee.
    """
    band = PLAUSIBILITY_BANDS.get(metal)
    if band is None:
        if strict:
            raise ImplausiblePriceError(
                f"Aucune bande de plausibilite definie pour {metal!r}. "
                "Ajouter la bande dans klastos.units avant d'utiliser ce metal."
            )
        return
    band.check(value_per_tonne)
