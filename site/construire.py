"""
KLASTOS21 - Generateur du site vitrine.

Six pages, deux langues, douze fichiers. Les maintenir a la main avec la
navigation et le pied dupliques douze fois est exactement la facon dont on
fabrique une derive : ce depot en a deja attrape trois. Le site est donc
genere, comme le rapport l'est par `klastos/render_html.py`.

Usage
-----
    python site/construire.py            # ecrit dans site/public/
    python site/construire.py --sortie X # ecrit ailleurs

Sortie
------
    public/klastos.css
    public/index.html        redirection vers la langue par defaut
    public/fr/<page>.html
    public/en/<page>.html
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from html import escape

if __name__ == "__main__" and __package__ is None:      # execution directe
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import charte                                           # noqa: E402
import contenu                                          # noqa: E402
from contenu import PAGES, t                            # noqa: E402

#: Hauteur de l'axe des figures, en pourcentage de masse. Les quatre
#: grandeurs de la page d'accueil se lisent sur la meme echelle - c'est
#: toute la demonstration, donc l'echelle est une constante et non un
#: cadrage automatique par ligne.
AXE_MAX = 50.0


# ==========================================================================
# Briques
# ==========================================================================

def _lien_page(page: str, langue: str) -> str:
    """Chemin relatif d'une page, depuis une autre page de la meme langue."""
    del langue
    return f"{page}.html"


def logotype(langue: str) -> str:
    """
    Le logotype : le nom, dont les chiffres de fin passent en gris.

    La coupure est derivee du nom et non ecrite en dur. Un `<span>21</span>`
    en litteral dans le gabarit donnait « KLASTOS21 21 », parce que le nom
    complet venait deja de la cle.
    """
    nom = escape(t("marque.nom", langue))
    coupe = re.match(r"(.*?)(\d+)$", nom)
    if coupe is None:
        return nom
    return f"{coupe[1]}<span>{coupe[2]}</span>"


def nav(page: str, langue: str) -> str:
    """La barre de navigation, avec la page courante marquee."""
    liens = []
    for p in PAGES:
        courant = ' aria-current="page"' if p == page else ""
        liens.append(
            f'<a href="{_lien_page(p, langue)}"{courant}>'
            f'{escape(t(f"nav.{p}", langue))}</a>')

    bascules = []
    for lg in contenu.LANGUES:
        actif = ' aria-current="true"' if lg == langue else ""
        bascules.append(
            f'<a href="../{lg}/{page}.html" hreflang="{lg}"{actif}>'
            f'{lg}</a>')

    return f"""<nav class="nav">
  <div class="enveloppe nav-interieur">
    <a class="marque" href="index.html">{logotype(langue)}</a>
    <div class="nav-liens">{"".join(liens)}</div>
    <div class="langues">{"".join(bascules)}</div>
  </div>
</nav>"""


def pied(langue: str) -> str:
    """Le pied de page : navigation secondaire et mention de portee."""
    produit = "".join(
        f'<li><a href="{_lien_page(p, langue)}">'
        f'{escape(t(f"nav.{p}", langue))}</a></li>'
        for p in ("methode", "rapport", "prix"))
    maison = "".join(
        f'<li><a href="{_lien_page(p, langue)}">'
        f'{escape(t(f"nav.{p}", langue))}</a></li>'
        for p in ("missions", "contact"))
    return f"""<footer class="pied">
  <div class="enveloppe">
    <div class="pied-interieur">
      <div class="pied-bloc" style="min-width:200px">
        <h4>{escape(t("marque.nom", langue))}</h4>
        <p>{escape(t("marque.sous", langue))}</p>
      </div>
      <div class="pied-bloc">
        <h4>{escape(t("pied.produit", langue))}</h4>
        <ul>{produit}</ul>
      </div>
      <div class="pied-bloc">
        <h4>{escape(t("pied.maison", langue))}</h4>
        <ul>{maison}</ul>
      </div>
    </div>
    <p class="pied-mention">{escape(t("pied.mention", langue))}</p>
  </div>
</footer>"""


def page_complete(page: str, langue: str, corps: str) -> str:
    """Enveloppe une page : en-tete, navigation, corps, pied."""
    return f"""<!doctype html>
<html lang="{langue}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(t(f"{page}.titre_onglet", langue))}</title>
<meta name="description" content="{escape(t(f"{page}.description", langue))}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{charte.LIEN_POLICES}">
<link rel="stylesheet" href="../klastos.css">
</head>
<body>
{nav(page, langue)}
<main>
{corps}
</main>
{pied(langue)}
</body>
</html>
"""


def entete(page: str, langue: str, boutons: str = "") -> str:
    """Le bloc de titre d'une page interieure."""
    return f"""<section class="bande section">
  <div class="enveloppe mesure">
    <p class="surtitre">{escape(t(f"{page}.surtitre", langue))}</p>
    <h1>{escape(t(f"{page}.h1", langue))}</h1>
    <p class="chapeau">{escape(t(f"{page}.chapeau", langue))}</p>
    {boutons}
  </div>
</section>"""


def faits(cles: list[str], langue: str) -> str:
    """
    Une liste de faits. Ces textes contiennent volontairement des `<b>` :
    ils ne sont donc pas echappes. C'est admis parce que le catalogue est
    ecrit par nous et jamais alimente par une saisie.
    """
    lignes = "".join(f"<li>{t(c, langue)}</li>" for c in cles)
    return f'<ul class="faits">{lignes}</ul>'


def carte(titre_cle: str, texte_cle: str, langue: str,
          statut: str = "") -> str:
    """Une carte simple. `statut` colore le filet de gauche, si fourni."""
    classe = f"carte statut statut-{statut}" if statut else "carte"
    return f"""<div class="{classe}">
      <h3>{escape(t(titre_cle, langue))}</h3>
      <p>{escape(t(texte_cle, langue))}</p>
    </div>"""


def ligne_regle(nom_cle: str, langue: str, bas: float, haut: float,
                teinte: str, valeur: str) -> str:
    """
    Une ligne de la figure : un trait fin si bas == haut, une bande sinon.

    La position est calculee et sort en style en ligne, parce que c'est une
    donnee et non une decision de style. Aucune couleur n'est posee ici :
    `teinte` nomme une classe, et la classe seule connait le hex.
    """
    gauche = 100.0 * bas / AXE_MAX
    if bas == haut:
        marque = (f'<span class="regle-trait {teinte}" '
                  f'style="left:{gauche:.2f}%"></span>')
    else:
        largeur = 100.0 * (haut - bas) / AXE_MAX
        marque = (f'<span class="regle-bande {teinte}" '
                  f'style="left:{gauche:.2f}%;width:{largeur:.2f}%"></span>')
    return f"""<div class="regle-ligne">
      <div class="regle-nom">{escape(t(nom_cle, langue))}</div>
      <div class="regle-piste">{marque}</div>
      <div class="regle-valeur">{escape(valeur)}</div>
    </div>"""


# ==========================================================================
# Les six pages
# ==========================================================================

def page_index(langue: str) -> str:
    boutons = f"""<div class="boutons">
      <a class="bouton" href="methode.html">\
{escape(t("index.bouton_methode", langue))}</a>
      <a class="bouton bouton-creux" href="rapport.html">\
{escape(t("index.bouton_rapport", langue))}</a>
    </div>"""

    regle = "".join([
        ligne_regle("index.figure.ni", langue, 12.4, 12.4,
                    "determine", "12,4 %" if langue == "fr" else "12.4%"),
        ligne_regle("index.figure.co", langue, 8.1, 8.1,
                    "determine", "8,1 %" if langue == "fr" else "8.1%"),
        ligne_regle("index.figure.nmc", langue, 18.0, 46.0,
                    "mal", "18 – 46 %" if langue == "fr" else "18 – 46%"),
        ligne_regle("index.figure.lfp", langue, 0.0, 31.0,
                    "domaine", "0 – 31 %" if langue == "fr" else "0 – 31%"),
    ])

    tri = "".join([
        f"""<div class="carte statut statut-determine">
      <span class="pastille pastille-determine">\
{escape(t("index.tri.determine.nom", langue))}</span>
      <p style="margin-top:14px">\
{escape(t("index.tri.determine.texte", langue))}</p>
    </div>""",
        f"""<div class="carte statut statut-mal">
      <span class="pastille pastille-mal">\
{escape(t("index.tri.mal.nom", langue))}</span>
      <p style="margin-top:14px">\
{escape(t("index.tri.mal.texte", langue))}</p>
    </div>""",
        f"""<div class="carte statut statut-domaine">
      <span class="pastille pastille-domaine">\
{escape(t("index.tri.domaine.nom", langue))}</span>
      <p style="margin-top:14px">\
{escape(t("index.tri.domaine.texte", langue))}</p>
    </div>""",
    ])

    return f"""<section class="bande section">
  <div class="enveloppe">
    <p class="surtitre">{escape(t("index.surtitre", langue))}</p>
    <h1 style="max-width:19ch">{escape(t("index.h1", langue))}</h1>
    <p class="chapeau">{escape(t("index.chapeau", langue))}</p>
    {boutons}
  </div>
</section>

<section class="bande bande-lavee section">
  <div class="enveloppe">
    <h2>{escape(t("index.figure.titre", langue))}</h2>
    <p class="chapeau" style="margin-bottom:34px">\
{escape(t("index.figure.chapeau", langue))}</p>
    <div class="regle">{regle}</div>
    <p class="regle-legende">{escape(t("index.figure.legende", langue))}</p>
  </div>
</section>

<section class="bande section">
  <div class="enveloppe">
    <p class="surtitre">{escape(t("index.tri.surtitre", langue))}</p>
    <h2 class="mesure">{escape(t("index.tri.titre", langue))}</h2>
    <div class="grille grille-3" style="margin-top:34px">{tri}</div>
  </div>
</section>

<section class="bande section">
  <div class="enveloppe">
    <p class="surtitre">{escape(t("index.refus.surtitre", langue))}</p>
    <h2 class="mesure">{escape(t("index.refus.titre", langue))}</h2>
    <div class="grille grille-2" style="margin-top:30px;gap:40px">
      <p class="mesure">{escape(t("index.refus.texte", langue))}</p>
      <blockquote class="citation">
        {escape(t("index.refus.citation", langue))}
        <footer>{escape(t("index.refus.source", langue))}</footer>
      </blockquote>
    </div>
  </div>
</section>

<section class="bande bande-lavee section">
  <div class="enveloppe">
    <p class="surtitre">{escape(t("index.ferme.surtitre", langue))}</p>
    <h2 class="mesure">{escape(t("index.ferme.titre", langue))}</h2>
    <p class="chapeau" style="margin-bottom:30px">\
{escape(t("index.ferme.texte", langue))}</p>
    {faits(["index.ferme.f1", "index.ferme.f2", "index.ferme.f3"], langue)}
    <div class="boutons">
      <a class="bouton" href="rapport.html">\
{escape(t("index.bouton_rapport", langue))}</a>
    </div>
  </div>
</section>

<section class="bande section">
  <div class="enveloppe mesure">
    <p class="surtitre">{escape(t("index.attest.surtitre", langue))}</p>
    <h2>{escape(t("index.attest.titre", langue))}</h2>
    <p class="chapeau">{escape(t("index.attest.texte", langue))}</p>
  </div>
</section>"""


def page_methode(langue: str) -> str:
    etapes = "".join([
        carte("methode.un.titre", "methode.un.texte", langue),
        carte("methode.deux.titre", "methode.deux.texte", langue),
        carte("methode.trois.titre", "methode.trois.texte", langue),
    ])
    return f"""{entete("methode", langue)}

<section class="bande bande-lavee section">
  <div class="enveloppe">
    <div class="grille grille-3">{etapes}</div>
  </div>
</section>

<section class="bande section">
  <div class="enveloppe mesure">
    <h2>{escape(t("methode.quatre.titre", langue))}</h2>
    <div style="margin-top:26px">
    {faits(["methode.quatre.f1", "methode.quatre.f2",
            "methode.quatre.f3", "methode.quatre.f4"], langue)}
    </div>
  </div>
</section>"""


def page_rapport(langue: str) -> str:
    #: Les cinq lignes du verdict. Les valeurs viennent du lot reel ; elles
    #: sont ici en litteral parce que ce site est une vitrine et non une
    #: analyse - il ne recalcule rien.
    pct = "10,35 %" if langue == "fr" else "10.35%"
    verdict = [
        ("rapport.verdict.l1", "pastille-ok", "7 / 7"),
        ("rapport.verdict.l2", "pastille-mal", "1 / 12"),
        ("rapport.verdict.l3", "pastille-domaine", "5"),
        ("rapport.verdict.l4", "pastille-ok", pct),
    ]
    lignes = "".join(
        f"""<tr>
      <td>{escape(t(cle, langue))}</td>
      <td><span class="pastille {teinte}">{escape(val)}</span></td>
    </tr>""" for cle, teinte, val in verdict)
    lignes += f"""<tr>
      <td>{escape(t("rapport.verdict.l5", langue))}</td>
      <td><span class="pastille pastille-determine">\
{escape(t("rapport.verdict.v5", langue))}</span></td>
    </tr>"""

    return f"""{entete("rapport", langue)}

<section class="bande bande-lavee section">
  <div class="enveloppe">
    <h2>{escape(t("rapport.verdict.titre", langue))}</h2>
    <div class="defilant" style="margin-top:26px;max-width:620px">
      <table class="tableau">
        <thead><tr>
          <th>{escape(t("rapport.verdict.col_grandeur", langue))}</th>
          <th>{escape(t("rapport.verdict.col_etat", langue))}</th>
        </tr></thead>
        <tbody>{lignes}</tbody>
      </table>
    </div>
  </div>
</section>

<section class="bande section">
  <div class="enveloppe">
    <div class="grille grille-2" style="gap:40px">
      <div>
        <h2>{escape(t("rapport.manque.titre", langue))}</h2>
        <p class="chapeau">{escape(t("rapport.manque.texte", langue))}</p>
      </div>
      <div class="encart">
        <p class="carte-titre-mono">\
{escape(t("rapport.piege.titre", langue))}</p>
        <p>{escape(t("rapport.piege.texte", langue))}</p>
      </div>
    </div>
  </div>
</section>"""


def page_prix(langue: str) -> str:
    sources = f"""<tr>
      <td>World Bank Pink Sheet</td>
      <td>{escape(t("prix.licence.pink_couv", langue))}</td>
      <td><span class="pastille pastille-ok">\
{escape(t("prix.licence.pink_lic", langue))}</span></td>
    </tr>
    <tr>
      <td>{escape(t("prix.licence.releve_nom", langue))}</td>
      <td>{escape(t("prix.licence.releve_couv", langue))}</td>
      <td><span class="pastille pastille-mal">\
{escape(t("prix.licence.releve_lic", langue))}</span></td>
    </tr>"""

    return f"""{entete("prix", langue)}

<section class="bande bande-lavee section">
  <div class="enveloppe">
    <div class="grille grille-2" style="gap:40px">
      <div>
        <h2>{escape(t("prix.devise.titre", langue))}</h2>
        <p class="chapeau">{escape(t("prix.devise.texte", langue))}</p>
      </div>
      <div>
        <h2>{escape(t("prix.histo.titre", langue))}</h2>
        <p class="chapeau">{escape(t("prix.histo.texte", langue))}</p>
      </div>
    </div>
  </div>
</section>

<section class="bande section">
  <div class="enveloppe">
    <h2>{escape(t("prix.licence.titre", langue))}</h2>
    <p class="chapeau">{escape(t("prix.licence.texte", langue))}</p>
    <div class="defilant" style="margin-top:30px">
      <table class="tableau">
        <thead><tr>
          <th>{escape(t("prix.licence.col_source", langue))}</th>
          <th>{escape(t("prix.licence.col_couv", langue))}</th>
          <th>{escape(t("prix.licence.col_lic", langue))}</th>
        </tr></thead>
        <tbody>{sources}</tbody>
      </table>
    </div>
  </div>
</section>"""


def page_missions(langue: str) -> str:
    blocs = "".join([
        carte("missions.un.titre", "missions.un.texte", langue,
              "determine"),
        carte("missions.deux.titre", "missions.deux.texte", langue,
              "mal"),
        carte("missions.trois.titre", "missions.trois.texte", langue,
              "domaine"),
        carte("missions.quatre.titre", "missions.quatre.texte", langue,
              "ok"),
    ])
    return f"""{entete("missions", langue)}

<section class="bande bande-lavee section">
  <div class="enveloppe">
    <div class="grille grille-2">{blocs}</div>
  </div>
</section>"""


def page_contact(langue: str) -> str:
    return f"""{entete("contact", langue)}

<section class="bande bande-lavee section">
  <div class="enveloppe">
    <h2>{escape(t("contact.quoi.titre", langue))}</h2>
    <div style="margin-top:26px;max-width:72ch">
    {faits(["contact.quoi.f1", "contact.quoi.f2",
            "contact.quoi.f3", "contact.quoi.f4"], langue)}
    </div>
  </div>
</section>

<section class="bande section">
  <div class="enveloppe">
    <div class="grille grille-2" style="gap:40px">
      <div class="carte">
        <p class="carte-titre-mono">\
{escape(t("contact.courriel.titre", langue))}</p>
        <p>{escape(t("contact.courriel.texte", langue))}</p>
      </div>
      <div class="carte">
        <p class="carte-titre-mono">\
{escape(t("contact.modele.titre", langue))}</p>
        <p>{escape(t("contact.modele.texte", langue))}</p>
      </div>
    </div>
  </div>
</section>"""


#: Une fonction par page. La table sert aussi de garde : si `PAGES` gagne
#: une entree sans gagner sa fonction, la generation s'arrete.
CORPS_DE_PAGE = {
    "index": page_index,
    "methode": page_methode,
    "rapport": page_rapport,
    "prix": page_prix,
    "missions": page_missions,
    "contact": page_contact,
}


# ==========================================================================
# Generation
# ==========================================================================

def redirection() -> str:
    """La racine renvoie vers la langue par defaut, sans JavaScript."""
    cible = f"{contenu.DEFAUT}/index.html"
    return f"""<!doctype html>
<html lang="{contenu.DEFAUT}">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={cible}">
<link rel="canonical" href="{cible}">
<title>KLASTOS21</title>
</head>
<body><p><a href="{cible}">KLASTOS21</a></p></body>
</html>
"""


def construire(sortie: pathlib.Path) -> list[pathlib.Path]:
    """Ecrit le site complet dans `sortie`. Rend la liste des fichiers."""
    manquantes = set(PAGES) - set(CORPS_DE_PAGE)
    if manquantes:
        raise SystemExit(
            f"pages declarees sans fonction de corps : {sorted(manquantes)}")

    ecrits: list[pathlib.Path] = []
    sortie.mkdir(parents=True, exist_ok=True)

    css = sortie / "klastos.css"
    css.write_text(charte.feuille(), encoding="utf-8")
    ecrits.append(css)

    racine = sortie / "index.html"
    racine.write_text(redirection(), encoding="utf-8")
    ecrits.append(racine)

    for langue in contenu.LANGUES:
        dossier = sortie / langue
        dossier.mkdir(exist_ok=True)
        for page in PAGES:
            corps = CORPS_DE_PAGE[page](langue)
            chemin = dossier / f"{page}.html"
            chemin.write_text(page_complete(page, langue, corps),
                              encoding="utf-8")
            ecrits.append(chemin)
    return ecrits


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="construire",
        description="Genere le site vitrine KLASTOS21.")
    p.add_argument("--sortie", default=None,
                   help="dossier de sortie (defaut : site/public)")
    args = p.parse_args(argv)

    defaut = pathlib.Path(__file__).resolve().parent / "public"
    sortie = pathlib.Path(args.sortie) if args.sortie else defaut
    ecrits = construire(sortie)
    print(f"{len(ecrits)} fichiers ecrits dans {sortie}")
    for f in ecrits:
        print(f"  {f.relative_to(sortie)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
