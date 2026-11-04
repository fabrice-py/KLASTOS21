"""
KLASTOS21 - Illustrations techniques, dessinees plutot que photographiees.

POURQUOI CE MODULE EXISTE
-------------------------
Le site demandait des images de black mass et de batteries avant broyage.
Cinq banques libres ont ete fouillees - Unsplash, Pexels, Pixabay,
Wikimedia Commons, Openverse - et chaque candidat verifie un par un. Le
resultat est sans appel :

  - les seules bonnes images sont payantes : metal broye en benne et
    cellules Li-ion sont sous licence Unsplash+ ou Getty ;
  - les images libres montrent le MAUVAIS MATERIAU - piles alcalines
    Varta et Philips, batteries de demarrage au plomb, figurines
    miniatures, rendus 3D.

La raison est structurelle. La black mass est photographiee dans des
usines privees, par les entreprises qui la manipulent et par la presse
specialisee. Personne ne place ces photos sous licence libre.

Or une pile alcaline sur un site de black mass, c'est une photo de
charbon sur un site de minerai de fer : l'interlocuteur le voit
immediatement. Sur un produit dont tout l'argument est « ce que le
bulletin prouve », c'est le pire endroit ou mentir.

On dessine donc, et on assume le dessin : ces illustrations ne se font
pas passer pour des photographies.

CE QU'ELLES ONT EN COMMUN AVEC LE RESTE
---------------------------------------
SVG ecrit a la main, aucune bibliotheque, aucune requete, aucun fichier
image. Les couleurs viennent des jetons de la charte. La texture
granulaire est tiree au sort, mais avec une GRAINE FIXE : deux
constructions du site donnent le meme dessin, sinon le depot
changerait a chaque `git diff` sans raison.
"""

from __future__ import annotations

import math
import random

# --------------------------------------------------------------------------
# La texture de black mass
# --------------------------------------------------------------------------
#: Graine du tirage. FIXE, et c'est le point : une texture retiree a
#: chaque construction ferait apparaitre un diff dans le depot a chaque
#: `python site/construire.py`, et le site publie ne serait jamais deux
#: fois le meme.
GRAINE = 21

#: Nombre de grains. Une premiere version en posait 460, gros et clairs :
#: le rendu ressemblait a un CIEL ETOILE, pas a une poudre. Il en faut
#: beaucoup, petits, et surtout groupes.
#: Deuxieme correction : 1 300 grains fins et espaces lisaient encore
#: comme un ciel. Il faut qu'ils SE RECOUVRENT pour former une matiere -
#: une black mass est une masse dense et mate, pas des particules
#: eparses sur du noir.
GRAINS = 2300

#: Foyers d'agglomeration. C'est ce qui separe une poudre d'un bruit
#: uniforme : les grains se touchent et forment des amas. Sans eux, la
#: repartition au hasard donne une trame de television.
FOYERS = 54

#: Part des grains tires autour d'un foyer, le reste etant disperse.
PART_AMAS = 0.72

#: Trois tailles, et leur part. Une poudre reelle n'est pas monodisperse,
#: mais les fines dominent largement - d'ou des calibres resserres par
#: rapport a la premiere version.
CALIBRES: tuple[tuple[float, float, float], ...] = (
    (1.1, 2.4, 0.62),      # fines
    (2.4, 4.0, 0.31),      # intermediaires
    (4.0, 6.0, 0.07),      # agglomerats
)


def _grains(largeur: float, hauteur: float, graine: int = GRAINE) -> str:
    """
    Un champ de grains, tire au sort mais reproductible.

    L'opacite passe par TROIS CLASSES et non par un attribut : la charte
    interdit les couleurs en dur, et une opacite inline echapperait au
    theme sombre comme au changement de palette.
    """
    rng = random.Random(graine)
    foyers = [(rng.uniform(0, largeur), rng.uniform(0, hauteur))
              for _ in range(FOYERS)]
    out = []
    for _ in range(GRAINS):
        tirage = rng.random()
        cumul = 0.0
        for mini, maxi, part in CALIBRES:
            cumul += part
            if tirage <= cumul:
                r = rng.uniform(mini, maxi)
                break
        else:
            r = rng.uniform(*CALIBRES[0][:2])

        if rng.random() < PART_AMAS:
            fx, fy = rng.choice(foyers)
            x = fx + rng.gauss(0.0, 22.0)
            y = fy + rng.gauss(0.0, 15.0)
        else:
            x = rng.uniform(0, largeur)
            y = rng.uniform(0, hauteur)
        x = min(max(x, r), largeur - r)
        y = min(max(y, r), hauteur - r)

        tier = "a" if r < 2.4 else ("b" if r < 4.0 else "c")
        # Balise auto-fermante et classe unique : le champ compte plus
        # de mille grains, et chaque caractere economise y pese mille
        # fois. Le poids transfere reste de toute facon derisoire une
        # fois compresse - 11 Ko pour 99 Ko bruts - mais un depot se
        # lit aussi.
        out.append(f'<circle class="ill-grain-{tier}" '
                   f'cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}"/>')
    return "".join(out)


ECH_L, ECH_H = 320, 262
ECH_CHAMP = 170
#: Le titre se posait a `ECH_CHAMP + 2`, donc a cheval sur le
#: champ sombre. Il lui faut sa propre ligne de base.
ECH_TITRE = ECH_CHAMP + 24


def echantillon(langue: str, textes) -> str:
    """
    Une fiche d'echantillon : le champ de poudre, et son etiquette.

    ELLE RESSEMBLE A CE QU'ELLE EST. Un sachet de pulpe pose sur une
    paillasse, avec son numero de lot - pas une photographie truquee.
    L'etiquette porte les grandeurs qu'un bulletin porte vraiment.
    """
    lignes = [
        ("ech.lot", "ech.lot.valeur"),
        ("ech.granulo", "ech.granulo.valeur"),
        ("ech.humidite", "ech.humidite.valeur"),
    ]
    etiquette = "".join(
        f'<text class="ill-cle" x="16" y="{ECH_TITRE + 22 + k * 17}">'
        f'{textes(cle, langue)}</text>'
        f'<text class="ill-val" x="{ECH_L - 16}" '
        f'y="{ECH_TITRE + 22 + k * 17}" text-anchor="end">'
        f'{textes(val, langue)}</text>'
        for k, (cle, val) in enumerate(lignes))

    return (
        f'<svg class="illustration ill-echantillon" '
        f'viewBox="0 0 {ECH_L} {ECH_H}" role="img" '
        f'aria-label="{textes("ech.alt", langue)}">'
        f'<rect class="ill-cadre" x="0.5" y="0.5" width="{ECH_L - 1}" '
        f'height="{ECH_H - 1}" rx="5"></rect>'
        f'<clipPath id="ill-champ"><rect x="1" y="1" '
        f'width="{ECH_L - 2}" height="{ECH_CHAMP}" rx="4"></rect></clipPath>'
        f'<g clip-path="url(#ill-champ)">'
        f'<rect class="ill-fond" x="0" y="0" width="{ECH_L}" '
        f'height="{ECH_CHAMP}"></rect>'
        f'{_grains(ECH_L, ECH_CHAMP)}'
        f'</g>'
        f'<line class="ill-filet" x1="0" y1="{ECH_CHAMP}" x2="{ECH_L}" '
        f'y2="{ECH_CHAMP}"></line>'
        f'<text class="ill-titre" x="16" y="{ECH_TITRE}">'
        f'{textes("ech.titre", langue)}</text>'
        f'{etiquette}'
        f'</svg>'
    )


# --------------------------------------------------------------------------
# Le module batterie, en vue eclatee
# --------------------------------------------------------------------------
MOD_L, MOD_H = 320, 250

#: Marge gauche, qui loge les etiquettes. ELLE EST UNE CONSTANTE
#: pour que le test la LISE au lieu de la supposer : une premiere
#: version du test ecrivait 98 en dur, et ne voyait donc pas qu'on
#: etait redescendu a 74 - la valeur qui coupait « Collecteur Al ».
MOD_MARGE = 98.0

#: Les couches d'un module a cellules souples, de haut en bas. Nom de
#: cle, hauteur, et s'il s'agit d'un empilement.
COUCHES: tuple[tuple[str, float, int], ...] = (
    ("mod.boitier", 14, 1),
    ("mod.collecteur", 8, 1),
    ("mod.cellules", 11, 4),
    ("mod.collecteur2", 8, 1),
    ("mod.boitier2", 14, 1),
)


def module(langue: str, textes) -> str:
    """
    Un module a cellules souples, separe en couches.

    POURQUOI CETTE FORME. C'est la ou part la black mass : les
    collecteurs de cuivre et d'aluminium partent avec elle en fines,
    et c'est pourquoi le modele les porte comme phases. La vue eclatee
    montre d'ou viennent les quatorze colonnes de la matrice.
    """
    y = 26.0
    pieces, reperes = [], []
    marge = MOD_MARGE
    largeur = MOD_L - marge - 20
    for cle, hauteur, n in COUCHES:
        if n == 1:
            pieces.append(
                f'<rect class="ill-piece" x="{marge}" y="{y:.1f}" '
                f'width="{largeur}" height="{hauteur}" rx="2.5"></rect>')
        else:
            ep = (hauteur - (n - 1) * 2.0) / n
            for k in range(n):
                pieces.append(
                    f'<rect class="ill-piece ill-cellule" x="{marge + 6}" '
                    f'y="{y + k * (ep + 2.0):.1f}" width="{largeur - 12}" '
                    f'height="{ep:.1f}" rx="1.5"></rect>')
        milieu = y + hauteur / 2
        reperes.append(
            f'<line class="ill-amorce" x1="{marge - 8}" y1="{milieu:.1f}" '
            f'x2="{marge - 2}" y2="{milieu:.1f}"></line>'
            f'<text class="ill-repere" x="{marge - 13}" '
            f'y="{milieu + 3.5:.1f}" text-anchor="end">'
            f'{textes(cle, langue)}</text>')
        y += hauteur + 22.0

    return (
        f'<svg class="illustration ill-module" viewBox="0 0 {MOD_L} {MOD_H}" '
        f'role="img" aria-label="{textes("mod.alt", langue)}">'
        f'<text class="ill-titre ill-titre-haut" x="0" y="12">'
        f'{textes("mod.titre", langue)}</text>'
        f'{"".join(pieces)}{"".join(reperes)}'
        f'</svg>'
    )
