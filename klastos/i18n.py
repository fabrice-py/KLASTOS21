"""
KLASTOS21 - Catalogue de messages, francais et anglais.

Pourquoi un catalogue explicite
-------------------------------
Pas de gettext, pas de fichiers .po, aucune dependance. Le projet se relit
en entier dans la source : un `.mo` compile romprait cette propriete, et une
chaine traduite qui se lirait seulement dans un outil externe ne serait plus
verifiable par un test.

Le catalogue est donc un dictionnaire `{cle: {"fr": ..., "en": ...}}`. Il se
lit, il se teste, il se diffe.

Principe directeur
------------------
UNE CLE N'EST JAMAIS UN TEXTE AFFICHE. C'est la faute que ce module existe
pour empecher. `report.py` indexait ses libelles de statut par le TITRE
francais de la section - « Comment reduire l'incertitude » servait a la fois
d'en-tete imprime et de cle de dictionnaire. Traduire le titre cassait
silencieusement la recherche, et la colonne « statut » du rapport anglais se
serait videe sans qu'aucune exception ne soit levee.

Les cles sont donc des identifiants ASCII stables, hierarchises par couche :

    rapport.section.*     titres des sections du livrable
    rapport.intro.*       prose d'introduction de section
    rapport.statut.*      libelles de statut, par section
    ui.*                  interface Streamlit
    journal.*             journal de lecture et avertissements
    cli.*                 ligne de commande

Le protocole reste en francais
------------------------------
Arbitrage assume : `protocole.md` porte les engagements methodologiques et
n'est pas traduit. Un rapport anglais le cite donc en signalant sa langue,
plutot que de laisser croire a une version anglaise opposable qui n'existe
pas. Voir `rapport.protocole.renvoi`.
"""

from __future__ import annotations

#: Langues servies. L'ordre fixe celui des tests de completude.
LANGUES: tuple[str, ...] = ("fr", "en")

#: Langue de repli. Le francais, parce que c'est la langue de redaction du
#: protocole et celle dans laquelle les arbitrages ont ete pris.
DEFAUT = "fr"


class CleInconnue(KeyError):
    """Cle absente du catalogue. C'est un bug, pas un resultat."""


# ==========================================================================
# Catalogue
# ==========================================================================
# Regle de redaction : le francais porte ses accents. Une chaine affichee
# sans accent est un defaut, pas un choix - les commentaires et docstrings du
# projet sont en ASCII, les textes VISIBLES ne le sont pas.

CATALOGUE: dict[str, dict[str, str]] = {

    # ---------------------------------------------------------------- titres
    "rapport.section.diagnostic": {
        "fr": "Diagnostic du bulletin",
        "en": "Assay diagnostics",
    },
    "rapport.section.grandeurs_fermes": {
        "fr": "Grandeurs fermes",
        "en": "Determined quantities",
    },
    "rapport.section.ventilation": {
        "fr": "Ventilation par grade",
        "en": "Breakdown by grade",
    },
    "rapport.section.reduire": {
        "fr": "Comment réduire l'incertitude",
        "en": "How to reduce the uncertainty",
    },
    "rapport.section.sensibles": {
        "fr": "Grandeurs sensibles à la qualité du bulletin",
        "en": "Quantities sensitive to assay quality",
    },
    "rapport.section.scenario": {
        "fr": "Scénario : et si l'oxygène était dosé",
        "en": "Scenario: what if oxygen were assayed",
    },
    "rapport.section.drx": {
        "fr": "Quantification structurale (diffraction)",
        "en": "Structural quantification (diffraction)",
    },
    "rapport.section.conseil": {
        "fr": "Quelle quantification commander",
        "en": "Which quantification to order",
    },
    "rapport.section.valorisation": {
        "fr": "Valorisation",
        "en": "Valuation",
    },
    "rapport.section.specification": {
        "fr": "Écarts à la spécification",
        "en": "Deviations from specification",
    },
    "rapport.section.avertissements": {
        "fr": "Avertissements",
        "en": "Warnings",
    },
    "rapport.section.limites": {
        "fr": "Limites méthodologiques déclarées",
        "en": "Declared methodological limits",
    },
    "rapport.section.tracabilite": {
        "fr": "Traçabilité",
        "en": "Traceability",
    },

    # ----------------------------------------------------------- introductions
    "rapport.intro.grandeurs_fermes": {
        "fr": "Ces valeurs sont déterminées par l'analyse élémentaire, quelle "
              "que soit la ventilation retenue par le solveur. Ce sont les "
              "seules opposables.",
        "en": "These values are determined by the elemental assay, whatever "
              "breakdown the solver settles on. They are the only ones that "
              "can be relied upon.",
    },
    "rapport.intro.ventilation": {
        "fr": "Les valeurs ci-dessous sont des DOMAINES COMPATIBLES, pas des "
              "estimations. Toute valeur du domaine explique le bulletin "
              "aussi bien qu'une autre.",
        "en": "The values below are COMPATIBLE RANGES, not estimates. Any "
              "value within a range explains the assay just as well as any "
              "other.",
    },
    "rapport.intro.reduire": {
        "fr": "Toute incertitude n'a pas le même remède. Le tableau distingue "
              "ce qu'une meilleure analyse résoudrait de ce qu'elle ne "
              "résoudra pas.",
        "en": "Not every uncertainty has the same remedy. The table "
              "separates what a better assay would resolve from what it "
              "will not.",
    },
    "rapport.intro.sensibles": {
        "fr": "Ces largeurs se réduiraient avec une analyse de meilleure "
              "qualité ou des réplicats.",
        "en": "These widths would narrow with a higher-quality assay or with "
              "replicates.",
    },
    "rapport.intro.specification": {
        "fr": "Écarts constatés par rapport à la spécification retenue.",
        "en": "Deviations observed against the selected specification.",
    },

    # --------------------------------------------------- libelles de statut
    # Question posee : « cette grandeur est-elle determinee ? »
    "rapport.statut.ferme": {"fr": "ferme", "en": "determined"},
    "rapport.statut.ferme_large": {
        "fr": "ferme mais **mal déterminé**",
        "en": "determined but **poorly constrained**",
    },
    "rapport.statut.ouvert": {
        "fr": "**non identifiable**",
        "en": "**not identifiable**",
    },

    # Question posee : « cette largeur se reduirait-elle ? »
    "rapport.statut.reductible": {"fr": "réductible", "en": "reducible"},
    "rapport.statut.irreductible": {
        "fr": "**irréductible**",
        "en": "**irreducible**",
    },

    # Question posee : « que deviendrait cette grandeur ? »
    "rapport.statut.deviendrait_ferme": {
        "fr": "deviendrait ferme",
        "en": "would become determined",
    },
    "rapport.statut.resterait_ouverte": {
        "fr": "resterait ouverte",
        "en": "would remain open",
    },

    # Question posee : « la diffraction a-t-elle resserre ? »
    "rapport.statut.resserree": {"fr": "resserrée", "en": "narrowed"},
    "rapport.statut.inchangee": {"fr": "inchangée", "en": "unchanged"},

    # ------------------------------------------------------------- protocole
    "rapport.protocole.renvoi": {
        "fr": "Les engagements méthodologiques figurent au protocole joint.",
        "en": "The methodological commitments are set out in the "
              "accompanying protocol, which is available in French only "
              "(protocole.md). This report does not restate them in English, "
              "and no English version of the protocol is binding.",
    },
}


# ==========================================================================
# Acces
# ==========================================================================

def t(cle: str, langue: str = DEFAUT, **champs: object) -> str:
    """
    Rend le message `cle` dans `langue`, champs de format appliques.

    Une cle absente leve. Le silence serait pire : un rapport client avec un
    trou a la place d'un titre part quand meme, et personne ne le voit avant
    le destinataire.

    Une langue inconnue retombe sur le francais sans lever : mieux vaut un
    rapport lisible dans la mauvaise langue qu'un rapport qui n'existe pas.
    """
    try:
        entree = CATALOGUE[cle]
    except KeyError:
        raise CleInconnue(
            f"{cle!r} n'est pas au catalogue i18n. Ajoutez-la dans "
            f"klastos/i18n.py plutot que d'ecrire le texte en clair."
        ) from None

    texte = entree.get(langue) or entree[DEFAUT]
    return texte.format(**champs) if champs else texte


def langue_valide(langue: str | None) -> str:
    """Normalise une langue d'entree vers une langue servie."""
    if not langue:
        return DEFAUT
    court = str(langue).strip().lower()[:2]
    return court if court in LANGUES else DEFAUT


def cles_par_prefixe(prefixe: str) -> list[str]:
    """Les cles d'une couche, triees. Sert aux tests de completude."""
    return sorted(c for c in CATALOGUE if c.startswith(prefixe))
