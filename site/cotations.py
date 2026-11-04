"""
KLASTOS21 - Le graphique des cotations, construit a partir de donnees reelles.

POURQUOI CE MODULE EXISTE
-------------------------
Le site demandait une illustration de la volatilite des metaux critiques.
Une image de stock aurait decore ; celle-ci DEMONTRE, parce qu'elle est
tiree de l'extrait USGS que le projet embarque deja et qu'elle porte sa
source et sa date.

Elle argumente surtout le produit. KLASTOS21 refuse de valoriser sur un
prix de plus de sept jours, et ce refus parait severe tant qu'on n'a pas
vu ceci : le carbonate de lithium de qualite batterie est passe de
11 700 a 63 700 dollars la tonne en un an, puis est redescendu a 9 000
quatre ans plus tard. Un prix d'il y a un mois n'est pas un prix.

CE QUI EST DESSINE, ET COMMENT
------------------------------
Quatre metaux, ceux que le modele declare payables : lithium, cobalt,
nickel, cuivre. Leurs cotations ne partagent ni unite ni ordre de
grandeur - dollars la tonne pour les uns, cents la livre pour les
autres - donc on les ramene a une BASE 100 en 2021. C'est la seule
facon de les comparer sans mentir.

L'echelle verticale est LOGARITHMIQUE, et c'est dit sur le graphique. En
lineaire, le pic du lithium a 544 ecraserait le cuivre entre 91 et 104 :
on ne verrait qu'une ligne et un trait plat. En logarithmique, une
multiplication par deux occupe la meme hauteur qu'une division par deux,
ce qui est exactement ce qu'on veut comparer.

AUCUNE DEPENDANCE, AUCUNE REQUETE
---------------------------------
Le graphique est un SVG ecrit a la main, pose dans la page. Pas de
bibliotheque, pas d'appel reseau, pas de fichier image : le site reste
un dossier de fichiers statiques que l'on peut lire hors ligne. Les
couleurs viennent des jetons de la charte, jamais d'un hexadecimal.
"""

from __future__ import annotations

import csv
import math
import pathlib

RACINE = pathlib.Path(__file__).resolve().parents[1]
SOURCE = RACINE / "data" / "exemples" / "usgs_mcs2026_extrait.csv"

#: Le fichier de l'USGS est encode par Windows, pas en UTF-8 : il porte
#: des tirets cadratins en cp1252. Le lire en UTF-8 echoue des la
#: premiere ligne.
ENCODAGE_SOURCE = "cp1252"

#: Les quatre metaux retenus, et la cotation retenue pour chacun.
#:
#: LE CHOIX DE LA SERIE EST EXPLICITE. L'USGS publie parfois deux
#: cotations pour un meme metal - cobalt LME et cobalt spot americain,
#: cuivre COMEX, LME et producteur. Prendre « la premiere trouvee »
#: donnerait un graphique qui change au gre de l'ordre des lignes.
#:
#: Pour chaque metal : la cle USGS, le fragment qui identifie la serie,
#: le jeton de couleur, et l'ordre de dessin.
#: Le fragment porte sur `Statistics_detail`. Il ne suffit PAS pour le
#: nickel, dont les deux cotations partagent le meme intitule et ne
#: different que par l'unite - une tonne ou une livre. Le filtre porte
#: donc aussi sur l'unite, faute de quoi la serie retenue dependrait de
#: l'ordre des lignes du fichier.
SERIES: tuple[tuple[str, str, str, str], ...] = (
    ("Lithium", "battery-grade lithium", "dollars per metric ton", "marque"),
    ("Cobalt", "London Metal Exchange", "dollars per pound", "cobalt"),
    ("Nickel", "London Metal Exchange", "dollars per metric ton", "green"),
    # Le cuivre est la ligne de REFERENCE : c'est celle qui ne bouge
    # pas. Une teinte neutre le dit, et l'ambre etait de toute facon
    # indistinguable de l'orange de la marque a deux pixels de trait.
    ("Copper", "London Metal Exchange", "cents per pound", "muted"),
)

#: Annee de reference de la base 100.
BASE = "2021"


class SourceCotationsIntrouvable(FileNotFoundError):
    """L'extrait USGS manque. Le graphique ne s'invente pas."""


def _nombre(valeur: str) -> float | None:
    """
    Un nombre de l'USGS, qui porte des separateurs de milliers.

    `float("1,330")` echoue, et silencieusement si on l'entoure d'un
    `try` trop large : la serie perdrait une annee sans que rien ne le
    dise. On convertit donc explicitement, et on rend None pour une
    case vide - que l'appelant doit traiter.
    """
    texte = str(valeur).replace(",", "").replace(" ", "").strip()
    if not texte:
        return None
    try:
        return float(texte)
    except ValueError:
        return None


def lire_series(chemin: pathlib.Path | None = None) -> dict:
    """
    Les quatre series, en base 100, avec leur unite d'origine.

    Rend un dictionnaire par metal : annees, valeurs brutes, valeurs
    indexees, unite, intitule de la cotation. L'unite d'origine est
    CONSERVEE meme si le graphique affiche un indice - c'est elle qui
    rend le chiffre verifiable chez la source.
    """
    chemin = chemin or SOURCE
    if not chemin.exists():
        raise SourceCotationsIntrouvable(
            f"Extrait USGS absent : {chemin}. Le graphique des cotations "
            f"ne peut pas etre construit sans lui."
        )

    with chemin.open(encoding=ENCODAGE_SOURCE, newline="") as fh:
        lignes = [l for l in csv.DictReader(fh) if l["Statistics"] == "Price"]

    out: dict[str, dict] = {}
    for metal, fragment, unite, jeton in SERIES:
        choisies = [l for l in lignes
                    if l["Commodity"] == metal
                    and fragment in l["Statistics_detail"]
                    and l["Unit"] == unite]
        retenues = {l["Year"]: _nombre(l["Value"]) for l in choisies}
        annees = sorted(a for a, v in retenues.items() if v is not None)
        if BASE not in annees or len(annees) < 3:
            raise SourceCotationsIntrouvable(
                f"Serie {metal!r} incomplete dans {chemin.name} : "
                f"annees {annees}. Verifier le couple "
                f"({fragment!r}, {unite!r})."
            )
        # UNE SEULE COTATION PAR METAL. Si le filtre en laisse passer
        # deux, le graphique melangerait deux series sans le dire.
        intitules = {l["Statistics_detail"] for l in choisies}
        if len(intitules) != 1:
            raise SourceCotationsIntrouvable(
                f"Serie {metal!r} ambigue : {len(intitules)} cotations "
                f"repondent au filtre ({fragment!r}, {unite!r}). "
                f"Preciser le fragment."
            )
        base = retenues[BASE]
        out[metal] = {
            "annees": annees,
            "valeurs": [retenues[a] for a in annees],
            "indice": [retenues[a] / base * 100.0 for a in annees],
            "unite": unite,
            "detail": intitules.pop(),
            "jeton": jeton,
        }
    return out


# --------------------------------------------------------------------------
# Dessin
# --------------------------------------------------------------------------

#: Geometrie du trace, en unites de `viewBox`. Le SVG est fluide : il
#: s'etire a la largeur de son conteneur, et ces nombres ne sont donc pas
#: des pixels mais des proportions.
LARGEUR, HAUTEUR = 760, 330
MARGE_G, MARGE_D, MARGE_H, MARGE_B = 46, 96, 24, 38

#: Graduations de l'axe logarithmique, en indice base 100.
PALIERS = (25, 50, 100, 200, 400)


def _y(indice: float) -> float:
    """Ordonnee d'un indice, sur une echelle logarithmique."""
    haut, bas = math.log10(PALIERS[-1] * 1.4), math.log10(PALIERS[0] / 1.4)
    part = (math.log10(indice) - bas) / (haut - bas)
    return MARGE_H + (1.0 - part) * (HAUTEUR - MARGE_H - MARGE_B)


def _x(i: int, n: int) -> float:
    if n < 2:
        return MARGE_G
    return MARGE_G + i / (n - 1) * (LARGEUR - MARGE_G - MARGE_D)


def graphique(series: dict, langue: str, textes) -> str:
    """
    Le SVG complet, pret a etre pose dans une page.

    `textes` est la fonction de traduction : ce module ne contient AUCUN
    texte affiche, comme tout le reste du projet.
    """
    annees = series["Lithium"]["annees"]
    n = len(annees)

    grille = "".join(
        f'<line class="cot-grille" x1="{MARGE_G}" y1="{_y(p):.1f}" '
        f'x2="{LARGEUR - MARGE_D}" y2="{_y(p):.1f}"></line>'
        f'<text class="cot-echelle" x="{MARGE_G - 8}" y="{_y(p) + 3.5:.1f}" '
        f'text-anchor="end">{p}</text>'
        for p in PALIERS
    )

    reperes = "".join(
        f'<text class="cot-annee" x="{_x(i, n):.1f}" y="{HAUTEUR - 14}" '
        f'text-anchor="middle">{a}</text>'
        for i, a in enumerate(annees)
    )

    # ETIQUETTES ECARTEES. Les quatre series finissent entre 65 et 104
    # en indice, soit quelques pixels d'ecart sur une echelle
    # logarithmique : posees a leur hauteur exacte, les quatre noms se
    # superposent et deviennent illisibles. On les ecarte du minimum
    # necessaire, en partant du haut.
    ECART = 15.0
    fins = sorted(((d["indice"][-1], metal) for metal, d in series.items()),
                  reverse=True)
    hauteurs: dict[str, float] = {}
    precedente = None
    for valeur, metal in fins:
        y = _y(valeur)
        if precedente is not None and y - precedente < ECART:
            y = precedente + ECART
        hauteurs[metal] = y
        precedente = y

    traces = []
    for metal, d in series.items():
        points = " ".join(f"{_x(i, n):.1f},{_y(v):.1f}"
                          for i, v in enumerate(d["indice"]))
        dernier = d["indice"][-1]
        traces.append(
            f'<polyline class="cot-trace cot-{d["jeton"]}" points="{points}">'
            f'</polyline>'
            + "".join(f'<circle class="cot-point cot-{d["jeton"]}" '
                      f'cx="{_x(i, n):.1f}" cy="{_y(v):.1f}" r="2.6"></circle>'
                      for i, v in enumerate(d["indice"]))
            + f'<line class="cot-amorce cot-{d["jeton"]}" '
              f'x1="{LARGEUR - MARGE_D:.1f}" y1="{_y(dernier):.1f}" '
              f'x2="{LARGEUR - MARGE_D + 7:.1f}" '
              f'y2="{hauteurs[metal] - 4:.1f}"></line>'
            + f'<text class="cot-nom cot-{d["jeton"]}" '
              f'x="{LARGEUR - MARGE_D + 11}" y="{hauteurs[metal]:.1f}">'
              f'{textes(f"cot.{metal.lower()}", langue)}</text>'
        )

    return (
        f'<svg class="cotations" viewBox="0 0 {LARGEUR} {HAUTEUR}" '
        f'role="img" aria-label="'
        f'{textes("cot.alt", langue)}">'
        f'{grille}{reperes}{"".join(traces)}'
        f'</svg>'
    )
