"""
KLASTOS21 - Image de partage des reseaux sociaux, une par langue.

Usage
-----
    python site/partage.py

Ecrit `site/marque/partage-fr.png` et `site/marque/partage-en.png`, en
1200 x 630, la taille que LinkedIn recommande. La construction du site
les copie ensuite avec les autres PNG de `site/marque`, et chaque page
les cite dans ses balises Open Graph (`construire.partage`).

POURQUOI UN SCRIPT A PART
-------------------------
Il faut Pillow pour ecrire un PNG, et Pillow n'est PAS une dependance du
site : Netlify construit avec numpy et scipy seulement. Les images sont
donc produites ici, une fois, et versionnees comme le logo. On relance ce
script quand le titre de l'accueil ou la palette change ; un test verifie
que les deux fichiers existent et ont la bonne taille.

CE QUE L'IMAGE MONTRE
---------------------
Le titre de l'accueil, et sous lui les quatre grandeurs de la figure
d'accueil, sur la meme echelle et avec les memes valeurs : deux traits
fins, deux bandes. C'est la these du produit, et c'est ce qui distingue la
vignette d'un lien quelconque dans un fil LinkedIn. Aucune photo : la
raison est dans `site/illustrations.py`.
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
sys.path.insert(0, str(ICI))

from klastos import theme                                # noqa: E402

import contenu                                           # noqa: E402
import illustrations                                     # noqa: E402

LARGEUR, HAUTEUR = 1200, 630
MARGE = 72

#: Polices. Archivo et IBM Plex, celles du site, ne sont pas installees
#: d'office sous Windows ; Arial est le repli que la charte declare deja
#: derriere Archivo. On cherche dans l'ordre, et l'echec est BRUYANT :
#: une police par defaut de Pillow donnerait une image illisible.
POLICES_GRASSES = ("Archivo-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf",
                   "DejaVuSans-Bold.ttf")
POLICES_NORMALES = ("IBMPlexSans-Regular.ttf", "arial.ttf", "Arial.ttf",
                    "DejaVuSans.ttf")
DOSSIERS_POLICES = (pathlib.Path("C:/Windows/Fonts"),
                    pathlib.Path("/Library/Fonts"),
                    pathlib.Path("/usr/share/fonts/truetype/dejavu"))


def _police(noms: tuple[str, ...], taille: int) -> ImageFont.FreeTypeFont:
    for dossier in DOSSIERS_POLICES:
        for nom in noms:
            chemin = dossier / nom
            if chemin.is_file():
                return ImageFont.truetype(str(chemin), taille)
    raise SystemExit(f"aucune police trouvee parmi {noms}")


def _rgb(hexa: str) -> tuple[int, int, int]:
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))


def _lave(hexa: str, opacite: float) -> tuple[int, int, int]:
    """La couleur posee a `opacite` sur le blanc de la carte, comme la
    `.regle-bande` du site (opacite .32)."""
    fond = _rgb(theme.CARTE)
    return tuple(round(f + (c - f) * opacite)
                 for c, f in zip(_rgb(hexa), fond))


def _couper(texte: str, police, largeur: int, dessin) -> list[str]:
    """Coupe `texte` en lignes qui tiennent dans `largeur`."""
    lignes, courante = [], ""
    for mot in texte.split():
        essai = f"{courante} {mot}".strip()
        if dessin.textlength(essai, font=police) <= largeur:
            courante = essai
        else:
            lignes.append(courante)
            courante = mot
    lignes.append(courante)
    # Sur deux lignes, on EQUILIBRE : la coupe au plus tot laissait
    # « rien. » seul sur la seconde ligne. On retient la coupe dont la
    # ligne la plus longue est la plus courte.
    if len(lignes) == 2:
        mots = texte.split()
        coupes = [(" ".join(mots[:k]), " ".join(mots[k:]))
                  for k in range(1, len(mots))]
        lignes = list(min(coupes, key=lambda c: max(
            dessin.textlength(c[0], font=police),
            dessin.textlength(c[1], font=police))))
    return lignes


def image(langue: str) -> Image.Image:
    img = Image.new("RGB", (LARGEUR, HAUTEUR), _rgb(theme.CARTE))
    d = ImageDraw.Draw(img)
    encre, ardoise = _rgb(theme.ENCRE), _rgb(theme.ARDOISE)

    logo = Image.open(ICI / "marque" / "klastos21_logo.png").convert("RGBA")
    l_logo = 280
    logo = logo.resize((l_logo, round(logo.height * l_logo / logo.width)),
                       Image.LANCZOS)
    img.paste(logo, (MARGE - 6, 52), logo)

    titre = _police(POLICES_GRASSES, 50)
    y = 178
    for ligne in _couper(contenu.t("index.h1", langue), titre,
                         LARGEUR - 2 * MARGE, d):
        d.text((MARGE, y), ligne, font=titre, fill=encre)
        y += 60
    sous = _police(POLICES_NORMALES, 27)
    d.text((MARGE, y + 8), contenu.t("partage.sous_titre", langue),
           font=sous, fill=ardoise)

    # Les quatre grandeurs, sur l'echelle commune de la figure d'accueil.
    nom = _police(POLICES_NORMALES, 21)
    x0, x1 = 330, LARGEUR - MARGE
    y = 388
    for cle, bas, haut, statut in illustrations.APE_GRANDEURS:
        milieu = y + 13
        d.text((MARGE, y), contenu.t(cle, langue), font=nom, fill=ardoise)
        d.line([(x0, milieu), (x1, milieu)], fill=_rgb(theme.TRAIT), width=2)
        xb = x0 + (x1 - x0) * bas / illustrations.APE_AXE
        xh = x0 + (x1 - x0) * haut / illustrations.APE_AXE
        if statut == "determine":
            d.rectangle([xb - 2, milieu - 12, xb + 2, milieu + 12],
                        fill=_rgb(theme.COBALT))
        else:
            teinte = theme.AMBRE if statut == "mal" else theme.ROUILLE
            d.rectangle([xb, milieu - 10, xh, milieu + 10],
                        fill=_lave(teinte, .32))
        y += 46

    d.line([(MARGE, HAUTEUR - 52), (LARGEUR - MARGE, HAUTEUR - 52)],
           fill=_rgb(theme.TRAIT), width=1)
    pied = _police(POLICES_NORMALES, 20)
    domaine = "klastos21.fr"
    d.text((LARGEUR - MARGE - d.textlength(domaine, font=pied),
            HAUTEUR - 40), domaine, font=pied, fill=ardoise)
    return img


def main() -> int:
    for langue in contenu.LANGUES:
        chemin = ICI / "marque" / f"partage-{langue}.png"
        image(langue).save(chemin, optimize=True)
        print(f"ecrit {chemin.relative_to(ICI.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
