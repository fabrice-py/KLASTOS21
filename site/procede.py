"""
KLASTOS21 - Le schema du procede, de la batterie a la valeur payable.

POURQUOI CE SCHEMA EXISTE, ET CE QU'IL DIT
------------------------------------------
Il ne decore pas la page : il repond a la question que pose tout
interlocuteur au bout de deux minutes - « vous faites quoi, exactement,
dans cette chaine ? »

La reponse est une frontiere, et c'est elle que le dessin met au centre.
KLASTOS21 NE VOIT JAMAIS LE LOT. Il ne broie pas, il ne dose pas, il ne
raffine pas. Il entre apres le laboratoire, sur un bulletin, et sa
matiere premiere est un tableau de chiffres.

Cette frontiere n'est pas un aveu de faiblesse, c'est l'explication de
tout le reste :

  - elle dit pourquoi la PROVENANCE doit etre declaree : l'outil ne peut
    pas regarder la poudre pour savoir d'ou elle vient ;
  - elle dit pourquoi le probleme est INDETERMINE : un bulletin donne des
    elements, un acheteur paie des phases, et plusieurs melanges de
    phases donnent le meme bulletin ;
  - elle dit pourquoi la sortie est un INTERVALLE et non un prix : c'est
    ce que la mesure porte.

Trois zones, donc : ce qui se passe avant, ce que fait le laboratoire,
ce que fait KLASTOS21.

COMMENT IL EST FAIT
-------------------
Un SVG ecrit a la main, comme le graphique des cotations : pas de
bibliotheque, pas de requete, pas de fichier image. Les couleurs
viennent des jetons de la charte. Le texte passe par le catalogue de
traduction - ce module n'en contient aucun.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Geometrie
# --------------------------------------------------------------------------
#: Unites du `viewBox`, pas des pixels : le schema s'etire a la largeur
#: de son conteneur.
CELLULE, ECART = 142, 26
MARGE_X, HAUT_BANDE, HAUT_CELLULE = 12, 30, 150
LARGEUR = MARGE_X * 2 + CELLULE * 6 + ECART * 5
HAUTEUR = HAUT_BANDE + HAUT_CELLULE + 26

#: Les six etapes : cle de texte, glyphe, zone.
#:
#: LA ZONE EST LA DONNEE QUI COMPTE. C'est elle qui porte la frontiere -
#: ce que KLASTOS21 fait, et ce qu'il ne fait pas.
ETAPES: tuple[tuple[str, str, str], ...] = (
    ("batterie", "batterie", "lot"),
    ("broyage", "broyage", "lot"),
    ("blackmass", "poudre", "lot"),
    ("bulletin", "bulletin", "labo"),
    ("deconvolution", "cube", "nous"),
    ("valeur", "intervalle", "nous"),
)

#: Les trois zones, dans l'ordre, avec le nombre d'etapes couvertes.
ZONES: tuple[tuple[str, int], ...] = (("lot", 3), ("labo", 1), ("nous", 2))


def _x(i: int) -> float:
    return MARGE_X + i * (CELLULE + ECART)


# --------------------------------------------------------------------------
# Glyphes
# --------------------------------------------------------------------------
# Ils sont volontairement GEOMETRIQUES et sans detail : le logo est un
# cube, la charte n'a ni degrade ni ombre, et un pictogramme realiste
# jurerait. Chacun tient dans une boite de 44 par 34, posee en haut de
# sa cellule.

def _glyphe(nom: str, cx: float, cy: float, zone: str) -> str:
    """Un pictogramme, centre sur (cx, cy). Peint par la classe de zone."""
    c = f"proc-glyphe proc-{zone}"
    if nom == "batterie":
        return (f'<rect class="{c}" x="{cx-20}" y="{cy-11}" width="36" '
                f'height="22" rx="3"></rect>'
                f'<rect class="{c} proc-plein" x="{cx+16}" y="{cy-5}" '
                f'width="5" height="10" rx="1.5"></rect>'
                f'<path class="{c} proc-plein" d="M{cx-4} {cy-6} '
                f'L{cx-10} {cy+1} L{cx-5} {cy+1} L{cx-7} {cy+7} '
                f'L{cx+1} {cy-1} L{cx-4} {cy-1} Z"></path>')
    if nom == "broyage":
        dents = "".join(
            f'<path class="{c}" d="M{cx-18+k*9} {cy-12} l4.5 7 l-4.5 7"></path>'
            for k in range(5))
        return (dents + f'<line class="{c}" x1="{cx-20}" y1="{cy+12}" '
                f'x2="{cx+20}" y2="{cy+12}"></line>')
    if nom == "poudre":
        pts = ((-14, -5), (-6, -9), (2, -4), (10, -8), (-11, 3), (-2, 5),
               (7, 2), (14, 6), (-7, 10), (3, 11))
        return "".join(
            f'<circle class="{c} proc-plein" cx="{cx+dx}" cy="{cy+dy}" '
            f'r="{2.6 if k % 3 else 3.4}"></circle>'
            for k, (dx, dy) in enumerate(pts))
    if nom == "bulletin":
        lignes = "".join(
            f'<line class="{c}" x1="{cx-9}" y1="{cy-7+k*6}" '
            f'x2="{cx+(9 if k != 2 else 2)}" y2="{cy-7+k*6}"></line>'
            for k in range(4))
        return (f'<path class="{c}" d="M{cx-16} {cy-15} h24 l8 8 v22 '
                f'h-32 Z"></path>'
                f'<path class="{c}" d="M{cx+8} {cy-15} v8 h8"></path>'
                + lignes)
    if nom == "cube":
        # Le cube du logo, repris a l'identique en fil de fer.
        return (f'<path class="{c}" d="M{cx} {cy-15} l16 9 v18 l-16 9 '
                f'l-16 -9 v-18 Z"></path>'
                f'<path class="{c}" d="M{cx-16} {cy-6} l16 9 l16 -9"></path>'
                f'<line class="{c}" x1="{cx}" y1="{cy+3}" x2="{cx}" '
                f'y2="{cy+21}"></line>')
    if nom == "intervalle":
        # LA SIGNATURE DU PRODUIT : une fourchette, pas un prix. Les deux
        # mors et la barre disent ce que la mesure porte vraiment.
        return (f'<line class="{c} proc-fort" x1="{cx-19}" y1="{cy}" '
                f'x2="{cx+19}" y2="{cy}"></line>'
                f'<line class="{c} proc-fort" x1="{cx-19}" y1="{cy-9}" '
                f'x2="{cx-19}" y2="{cy+9}"></line>'
                f'<line class="{c} proc-fort" x1="{cx+19}" y1="{cy-9}" '
                f'x2="{cx+19}" y2="{cy+9}"></line>'
                f'<circle class="{c} proc-plein" cx="{cx-4}" cy="{cy}" '
                f'r="3.4"></circle>')
    raise ValueError(f"Glyphe inconnu : {nom!r}")


# --------------------------------------------------------------------------
# Texte
# --------------------------------------------------------------------------

def _lignes(texte: str, par_ligne: int = 20, maxi: int = 3) -> list[str]:
    """
    Coupe un libelle en lignes courtes.

    LE SVG NE SAIT PAS REVENIR A LA LIGNE. Sans ce decoupage, un libelle
    un peu long sort de sa cellule et chevauche la suivante - et il le
    ferait differemment en francais et en anglais, donc sans qu'on le
    voie forcement.
    """
    mots, out, courante = texte.split(), [], ""
    for mot in mots:
        essai = f"{courante} {mot}".strip()
        if len(essai) <= par_ligne or not courante:
            courante = essai
        else:
            out.append(courante)
            courante = mot
    if courante:
        out.append(courante)
    if len(out) > maxi:
        out = out[:maxi - 1] + [" ".join(out[maxi - 1:])]
    return out


def _texte(contenu_: str, x: float, y: float, classe: str,
           par_ligne: int = 20) -> str:
    lignes = _lignes(contenu_, par_ligne)
    tspans = "".join(
        f'<tspan x="{x:.1f}" dy="{0 if k == 0 else 13}">{l}</tspan>'
        for k, l in enumerate(lignes))
    return (f'<text class="{classe}" x="{x:.1f}" y="{y:.1f}" '
            f'text-anchor="middle">{tspans}</text>')


# --------------------------------------------------------------------------
# Assemblage
# --------------------------------------------------------------------------

def schema(langue: str, textes) -> str:
    """Le SVG complet. `textes` est la fonction de traduction."""
    bandes, i = [], 0
    for zone, n in ZONES:
        gauche = _x(i)
        droite = _x(i + n - 1) + CELLULE
        milieu = (gauche + droite) / 2
        bandes.append(
            f'<rect class="proc-bande proc-{zone}" x="{gauche:.1f}" y="6" '
            f'width="{droite - gauche:.1f}" height="2"></rect>'
            f'<text class="proc-zone proc-{zone}" x="{milieu:.1f}" y="24" '
            f'text-anchor="middle">'
            f'{textes(f"proc.zone.{zone}", langue)}</text>')
        i += n

    cellules, fleches = [], []
    for k, (cle, glyphe, zone) in enumerate(ETAPES):
        gauche = _x(k)
        milieu = gauche + CELLULE / 2
        haut = HAUT_BANDE + 10
        cellules.append(
            f'<rect class="proc-cadre proc-{zone}" x="{gauche:.1f}" '
            f'y="{haut}" width="{CELLULE}" height="{HAUT_CELLULE}" '
            f'rx="4"></rect>'
            + _glyphe(glyphe, milieu, haut + 34, zone)
            + _texte(textes(f"proc.{cle}.nom", langue), milieu, haut + 76,
                     f"proc-nom proc-{zone}", 16)
            + _texte(textes(f"proc.{cle}.detail", langue), milieu,
                     haut + 104, "proc-detail", 21))
        if k < len(ETAPES) - 1:
            dx = gauche + CELLULE
            y = haut + HAUT_CELLULE / 2
            fleches.append(
                f'<path class="proc-fleche" d="M{dx + 5:.1f} {y:.1f} '
                f'h{ECART - 14:.1f} m-5 -4 l5 4 l-5 4"></path>')

    return (
        f'<svg class="procede" viewBox="0 0 {LARGEUR} {HAUTEUR}" '
        f'role="img" aria-label="{textes("proc.alt", langue)}">'
        f'{"".join(bandes)}{"".join(fleches)}{"".join(cellules)}'
        f'</svg>'
    )
