"""
KLASTOS21 - Bandes de plausibilite sur les COMPOSITIONS PREDITES.

Le trou que le generateur synthetique ne pouvait pas reveler
-------------------------------------------------------------
`units.py` porte des bandes de plausibilite sur les PRIX : un prix converti
hors bande est refuse, parce qu'une erreur d'unite depasse toujours la bande
de plusieurs ordres de grandeur. Il n'existait aucun equivalent sur les
compositions que le solveur PREDIT pour les elements non doses.

Defaut trouve le 22 octobre 2026, sur un lot reel : ni le phosphore ni le
fluor n'etant doses, le solveur a predit 17,79 % de FLUOR, en retenant
14,3 % de LiPF6 et 11,8 % de PVDF. Le materiau de reference certifie OREAS
donne un fluor a 2,44 % : la prediction valait SEPT FOIS la valeur d'un
materiau reel. Rien ne l'a signale - `is_exploitable` valait True, et le lot
serait parti en valorisation avec 110 % de masse, donc a un prix surestime.

Le generateur ne pouvait pas attraper ca : il produit des lots coherents par
construction, et `make_lot` refuse meme un bouclage superieur a 1.

Pourquoi un module separe de units.py
--------------------------------------
`units.py` se declare en docstring comme le module des unites de COTATION.
Les bandes de prix y restent. Une composition n'est pas un prix : elle n'a
ni devise, ni source de marche, ni licence de rediffusion, et son
depassement ne se traite pas de la meme facon - un prix hors bande est
REFUSE, une composition hors bande est SIGNALEE. Le precedent du depot est
le meme : la conversion de devises a eu son module plutot que d'elargir
`market.py`.

Ce que ces bandes valent, et ce qu'elles ne valent pas
------------------------------------------------------
UN POINT N'EST PAS UNE BANDE. Les deux ancrages disponibles viennent d'un
SEUL certificat, sur un SEUL materiau. Les bornes portent donc
`validated=False`, et le facteur qui les ecarte est expose en parametre -
comme les seuils de bouclage, parce qu'un reglage qui n'est pas arbitre doit
se discuter.

Aucune borne n'est inventee pour un element sans ancrage. Un element non
controle est declare non controle : c'est la regle du projet, ne jamais
afficher ce que la donnee ne porte pas.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .phases import stoichiometry_matrix

#: Teneurs certifiees, materiau de reference OREAS, black mass de batteries
#: lithium-ion. Fractions massiques.
#:
#: C'est la SEULE source d'ancrage disponible, et elle ne porte qu'un
#: materiau. Une valeur ne decrit pas une population : elle dit seulement
#: qu'un materiau reel existe a ce niveau-la.
ANCRAGES_CERTIFIES: dict[str, float] = {
    "F": 0.0244,      # 2,44 % - 1SD 0,139 pt
}

# POURQUOI LE PHOSPHORE N'EST PAS ANCRE, alors que le certificat le donne.
# ---------------------------------------------------------------------------
# Le certificat porte P = 0,350 %, et une premiere version de ce module en
# avait fait un ancrage. Mesure sur 1 200 lots que le projet lui-meme declare
# plausibles, phosphore non dose :
#
#     fluor      : 0,0 % de faux positifs
#     phosphore  : 45,8 % de faux positifs, et 100 % sur les lots riches
#                  en LFP
#
# La cause est chimique. LFP est LiFePO4 : le phosphore y est un element
# MAJEUR, pas une trace. Les profils du projet produisent jusqu'a 11,70 % de
# P, soit 33 fois la teneur du certificat - tandis que leur fluor plafonne a
# 5,17 %, soit 2,1 fois l'ancrage.
#
# Le materiau OREAS ne contient quasiment pas de LFP. Son phosphore n'est
# donc pas un ancrage : c'est un cas particulier, et s'en servir revient a
# supposer qu'aucun lot ne contient de LFP.
#
# Le phosphore ressort donc en `non_controles`, declare comme tel. C'est la
# regle du module : n'inventer aucune borne pour un element sans ancrage.
# L'ancrer exigerait une teneur certifiee sur une black mass de chimie LFP.
SANS_ANCRAGE_DOCUMENTE: dict[str, str] = {
    "P": "LFP est LiFePO4 : le phosphore y est majeur. Le certificat "
         "disponible porte un materiau quasi sans LFP, donc son P = 0,350 % "
         "ne borne pas le cas general.",
}

#: Facteur applique a l'ancrage pour obtenir la borne haute.
#:
#: NON ARBITRE. Il n'y a aucune mesure pour le choisir : un seul materiau
#: certifie ne donne pas de dispersion. 3 est retenu comme filet large,
#: dans l'esprit des bandes de prix de `units.py` qui sont « volontairement
#: tres larges » et ne servent qu'a attraper les erreurs grossieres.
#:
#: Ce qu'il attrape et ce qu'il laisse passer, sur les donnees connues :
#:
#:     fluor predit sur le lot reel   17,79 %   soit 7,3 x l'ancrage
#:     borne a facteur 3               7,32 %   -> SIGNALE
#:     fluor certifie OREAS             2,44 %   -> non signale
#:
#: Un facteur jusqu'a 7 signalerait encore ce lot. Au-dela de 7,3 il ne le
#: signalerait plus. A ARBITRER avec un geometallurgiste : la question est
#: quelle teneur en fluor une black mass peut atteindre quand le liant PVDF
#: et le sel d'electrolyte LiPF6 sont tous deux abondants.
#:
#: Mesure du taux de faux positifs, sur 1 200 lots que les profils du projet
#: declarent plausibles, fluor non dose : 0,0 %. Leur fluor plafonne a
#: 5,17 %, soit 2,1 fois l'ancrage, contre une borne a 3 fois. La marge
#: existe donc des deux cotes - 2,1 en dessous, 7,3 au-dessus.
FACTEUR_PLAUSIBILITE = 3.0

#: Le facteur est-il arbitre ? Non, et le rapport doit le dire.
FACTEUR_VALIDE = False


class ImplausiblePredictionError(ValueError):
    """Prediction hors bande. Non levee par defaut : le defaut est de SIGNALER."""


@dataclass(frozen=True)
class CompositionBand:
    """
    Fourchette admise pour un element que le bulletin ne dose pas.

    La borne basse est zero : un element non dose peut legitimement etre
    absent. Seul l'exces se signale.
    """

    element: str
    high: float
    """Borne haute, en fraction massique."""

    anchor: float
    """Teneur certifiee qui sert d'ancrage."""

    factor: float
    """Facteur applique a l'ancrage. Expose, parce que non arbitre."""

    validated: bool = False
    source: str = ""

    @property
    def low(self) -> float:
        """Toujours zero. Un element non dose peut etre absent."""
        return 0.0

    def depasse(self, fraction: float) -> bool:
        return fraction > self.high


def bandes(facteur: float = FACTEUR_PLAUSIBILITE) -> dict[str, CompositionBand]:
    """
    Les bandes, construites a partir des ancrages et du facteur.

    Calculees et non figees dans une constante : le facteur est un parametre,
    et une table figee en aurait ignore les changements en silence.
    """
    return {
        el: CompositionBand(
            element=el,
            high=ancre * facteur,
            anchor=ancre,
            factor=facteur,
            validated=False,
            source="OREAS, materiau de reference certifie, un seul materiau",
        )
        for el, ancre in ANCRAGES_CERTIFIES.items()
    }


@dataclass(frozen=True)
class Depassement:
    """Un element predit au-dela de sa bande, et la phase qui l'y a mis."""

    element: str
    fraction: float
    """Teneur predite, en fraction massique."""

    borne: float
    """Borne haute de la bande."""

    ancrage: float
    """Teneur certifiee de reference."""

    phase: str
    """Phase porteuse qui contribue le plus a cet element."""

    phase_fraction: float
    """Fraction massique attribuee a cette phase."""

    @property
    def facteur_observe(self) -> float:
        """Combien de fois l'ancrage la prediction vaut-elle."""
        return self.fraction / self.ancrage if self.ancrage else float("inf")


@dataclass(frozen=True)
class ControlePlausibilite:
    """
    Resultat du controle. Porte autant ce qui a ete verifie que ce qui n'a
    pas pu l'etre : un element sans ancrage n'est pas un element conforme.
    """

    depassements: tuple[Depassement, ...]
    non_controles: tuple[str, ...]
    """Elements non doses pour lesquels aucun ancrage n'existe. Declares,
    jamais presumes conformes."""

    facteur: float
    facteur_valide: bool = FACTEUR_VALIDE

    def __bool__(self) -> bool:
        """Vrai s'il y a quelque chose a signaler."""
        return bool(self.depassements)


def verifier_predictions(
    x: np.ndarray,
    phase_keys: list[str],
    elements_doses: list[str],
    *,
    facteur: float = FACTEUR_PLAUSIBILITE,
) -> ControlePlausibilite:
    """
    Controle les teneurs PREDITES des elements que le bulletin ne dose pas.

    Un element dose n'est jamais controle : sa valeur est une mesure, pas
    une prediction, et la refuser reviendrait a contester le laboratoire.
    C'est pourquoi le lot OREAS, dont le fluor EST dose, ne declenche rien.

    Parameters
    ----------
    x : fractions massiques de phases, issues de la resolution.
    phase_keys : les phases retenues, dans l'ordre de `x`.
    elements_doses : les elements que le bulletin porte reellement.
    facteur : ecart admis par rapport a l'ancrage certifie.
    """
    A, elements, _ = stoichiometry_matrix(phase_keys=phase_keys)
    table = bandes(facteur)

    non_doses = [e for e in elements if e not in set(elements_doses)]
    depassements: list[Depassement] = []
    non_controles: list[str] = []

    for el in non_doses:
        bande = table.get(el)
        if bande is None:
            # Aucun ancrage : on ne devine pas de borne. L'absence de
            # controle est declaree, elle n'est pas un satisfecit.
            non_controles.append(el)
            continue
        i = elements.index(el)
        contributions = A[i, :] * x
        fraction = float(contributions.sum())
        if not bande.depasse(fraction):
            continue
        j = int(np.argmax(contributions))
        depassements.append(Depassement(
            element=el,
            fraction=fraction,
            borne=bande.high,
            ancrage=bande.anchor,
            phase=phase_keys[j],
            phase_fraction=float(x[j]),
        ))

    return ControlePlausibilite(
        depassements=tuple(depassements),
        non_controles=tuple(non_controles),
        facteur=facteur,
    )
