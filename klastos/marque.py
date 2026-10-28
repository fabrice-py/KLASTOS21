"""
KLASTOS21 - Identite visuelle de la marque.

POURQUOI CE MODULE EXISTE, ET POURQUOI IL N'EST PAS `theme.py`
---------------------------------------------------------------
`theme.py` porte la palette SEMANTIQUE : le cobalt signifie « grandeur
determinee », la rouille « non identifiable », l'ambre « a elucider », le
vert « bouclage conforme ». Ces couleurs sont des DONNEES rendues ; un
lecteur les decode.

La marque, elle, ne signifie rien d'autre qu'elle-meme. Son orange est une
identite, pas un statut.

Les confondre serait une faute deja commise une fois dans ce projet : la
tuile « bouclage conforme » sortait en `var(--accent)`, c'est-a-dire en
cobalt, soit la couleur qui veut dire « determine ». Elle portait deux sens
sur le meme document. Le commentaire de `render_html.CSS` en garde la
trace.

D'ou la separation, tenue par un test : ORANGE_MARQUE n'apparait JAMAIS
dans le rendu d'une donnee. Il habille le logotype, et rien d'autre.

CE QUE LE LOGO FOURNI CONTIENT
-------------------------------
Un cube isometrique - face superieure orange, face droite claire, le reste
encre - puis le mot KLASTOS en encre et 21 en orange, et une signature
« WHAT THE ASSAY PROVES ».

Deux de ses trois couleurs etaient DEJA celles de la charte, au point de
vue pres : l'encre #12161C contre #13171E, l'ardoise #5B6573 contre
#5A6472. Seul l'accent differe, et c'est tout le sujet ci-dessus.

LE CUBE EST VECTORIEL
---------------------
Redessine en SVG plutot qu'embarque en PNG. Le rapport est un document
AUTONOME destine a l'impression : un PNG y partirait en base64 et pesait
4,8 Ko pour une seule taille, contre 452 octets ici, nets a toute
resolution. Les declinaisons matricielles restent dans `site/public/marque`
pour les usages qui ne savent pas lire un SVG.
"""

from __future__ import annotations

#: Encre du logo. Un point plus froid que `theme.ENCRE`, imperceptible a
#: l'oeil ; la valeur du logo fait foi pour la marque.
ENCRE_MARQUE = "#12161C"

#: Orange de la marque. IL N'EST PAS UN STATUT. Voir l'avertissement en
#: tete de module : il ne doit jamais colorer une donnee.
ORANGE_MARQUE = "#B4632B"

#: Ardoise de la signature.
ARDOISE_MARQUE = "#5B6573"

#: Signature telle qu'elle figure sur le logo fourni. Elle n'est pas
#: traduite : c'est une marque, pas une phrase.
SIGNATURE = "WHAT THE ASSAY PROVES"

#: Hexagone isometrique inscrit dans 100 x 115,47. Un cube vu en isometrie
#: a six sommets ; le centre est le point commun aux trois faces visibles.
_W, _H = 100.0, 115.47
_SOMMETS = {
    "haut": (_W / 2, 0.0),
    "hd": (_W, _H / 4),
    "bd": (_W, 3 * _H / 4),
    "bas": (_W / 2, _H),
    "bg": (0.0, 3 * _H / 4),
    "hg": (0.0, _H / 4),
    "centre": (_W / 2, _H / 2),
}

#: Epaisseur du trait. A joints ronds, il reproduit les angles arrondis du
#: logo et dessine en meme temps les aretes sombres entre les faces.
_TRAIT = 7.0


def _polygone(*noms: str) -> str:
    return " ".join(f"{_SOMMETS[n][0]:.2f},{_SOMMETS[n][1]:.2f}"
                    for n in noms)


def cube_svg(encre: str = ENCRE_MARQUE,
             accent: str = ORANGE_MARQUE,
             face: str = "#FFFFFF",
             hauteur: str = "1em",
             classe: str = "") -> str:
    """
    Le cube de la marque, en SVG inline.

    Parameters
    ----------
    encre : silhouette et aretes. A inverser sur fond sombre, sans quoi le
        cube disparait dans le fond.
    accent : face superieure.
    face : face droite. Elle est CLAIRE sur le logo ; sur fond sombre, lui
        donner la couleur du fond conserve la lecture en volume.
    hauteur : passee telle quelle a l'attribut `height`.
    classe : classe CSS optionnelle.
    """
    cl = f' class="{classe}"' if classe else ""
    return (
        f'<svg{cl} xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="-6 -6 112 127.47" height="{hauteur}" '
        f'role="img" aria-label="KLASTOS21" focusable="false">'
        f'<g stroke="{encre}" stroke-width="{_TRAIT}" stroke-linejoin="round">'
        f'<polygon points="{_polygone("haut", "hd", "bd", "bas", "bg", "hg")}"'
        f' fill="{encre}"/>'
        f'<polygon points="{_polygone("haut", "hd", "centre", "hg")}"'
        f' fill="{accent}"/>'
        f'<polygon points="{_polygone("hd", "bd", "bas", "centre")}"'
        f' fill="{face}"/>'
        "</g></svg>"
    )


def logotype_html(nom: str = "KLASTOS", chiffres: str = "21",
                  classe_chiffres: str = "marque-21") -> str:
    """
    Le mot de la marque, avec ses deux chiffres distingues.

    Le texte reste du TEXTE : il se selectionne, se cherche, se lit par un
    lecteur d'ecran, et suit la typographie du support. Seul le cube est
    dessine.
    """
    return f'{nom}<span class="{classe_chiffres}">{chiffres}</span>'
