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

from klastos import marque
import sys
from html import escape

if __name__ == "__main__" and __package__ is None:      # execution directe
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import charte                                           # noqa: E402
import mouvement                                        # noqa: E402
import contenu                                          # noqa: E402
from contenu import PAGES, t                            # noqa: E402

#: Hauteur de l'axe des figures, en pourcentage de masse. Les quatre
#: grandeurs de la page d'accueil se lisent sur la meme echelle - c'est
#: toute la demonstration, donc l'echelle est une constante et non un
#: cadrage automatique par ligne.
AXE_MAX = 50.0

#: Source des declinaisons matricielles de la marque. Elle vit HORS du
#: dossier de sortie : `site/public` est un produit de construction, pas
#: un endroit ou deposer des sources.
MARQUE_SOURCE = pathlib.Path(__file__).resolve().parent / "marque"

#: Domaine servi. GitHub Pages lit ce nom dans un fichier `CNAME` a la
#: racine du site publie, et le reclame a CHAQUE deploiement : pose a la
#: main dans les reglages, il saute au deploiement suivant et le site
#: repart sur l'adresse en github.io. Il est donc ECRIT PAR LA
#: CONSTRUCTION, comme le reste.
DOMAINE = "klastos21.fr"


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
    mot = nom if coupe is None else f"{coupe[1]}<span>{coupe[2]}</span>"
    # Le verrouillage du logo : le cube, puis le mot au-dessus de la
    # signature. Le cube est VECTORIEL - net a toute taille, et il ne
    # coute pas une requete de plus.
    return (f'{marque.cube_svg(hauteur="2.1em")}'
            f'<span class="marque-texte">'
            f'<span class="mot">{mot}</span>'
            f'<span class="marque-signature">{marque.SIGNATURE}</span>'
            f'</span>')



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
        <p class="pied-signature">{escape(marque.SIGNATURE)}</p>
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


#: Sections deja porteuses d'un rythme de revelation propre. On ne les
#: retouche pas : la console se revele d'un bloc, et le hero doit etre
#: lisible a l'instant ou la page s'ouvre.
_SANS_REVELATION = ('class="hero"', 'id="console"')


def rythmer(corps: str) -> str:
    """
    Donne a chaque section un rang de revelation.

    Pose a la main sur la seule page d'accueil, l'attribut aurait manque
    partout ailleurs et le site serait reste immobile sur cinq pages sur
    six. Il est donc ajoute ICI, une fois, pour toutes les sections qui
    n'en declarent pas deja un.
    """
    rang = 0
    sorties: list[str] = []
    for morceau in re.split(r"(<section[^>]*>)", corps):
        if (morceau.startswith("<section")
                and "data-reveler" not in morceau
                and not any(m in morceau for m in _SANS_REVELATION)):
            rang += 1
            morceau = morceau[:-1] + f' data-reveler="{rang % 3}">'
        sorties.append(morceau)
    return "".join(sorties)


def page_complete(page: str, langue: str, corps: str) -> str:
    """Enveloppe une page : en-tete, navigation, corps, pied."""
    corps = rythmer(corps)
    return f"""<!doctype html>
<html lang="{langue}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>document.documentElement.className+=" js";</script>
<title>{escape(t(f"{page}.titre_onglet", langue))}</title>
<meta name="description" content="{escape(t(f"{page}.description", langue))}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{charte.LIEN_POLICES}">
<link rel="stylesheet" href="../klastos.css">
<link rel="icon" type="image/png" sizes="32x32"
      href="../marque/favicon-32.png">
<link rel="apple-touch-icon" href="../marque/favicon-180.png">
</head>
<body>
{nav(page, langue)}
<main>
{corps}
</main>
{pied(langue)}
<script>{mouvement.script()}</script>
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
        trace = (f'<span class="regle-trait {teinte}" '
                 f'style="left:{gauche:.2f}%"></span>')
    else:
        largeur = 100.0 * (haut - bas) / AXE_MAX
        trace = (f'<span class="regle-bande {teinte}" '
                 f'style="left:{gauche:.2f}%;width:{largeur:.2f}%"></span>')
    return f"""<div class="regle-ligne">
      <div class="regle-nom">{escape(t(nom_cle, langue))}</div>
      <div class="regle-piste">{trace}</div>
      <div class="regle-valeur">{escape(valeur)}</div>
    </div>"""


# ==========================================================================
# Les six pages
# ==========================================================================

def preuves(langue: str) -> str:
    """
    Trois chiffres sous le hero. Ils ne sont PAS decoratifs : ils viennent
    du lot XRF reel analyse pendant la mise au point, et du depot. Un
    chiffre invente ici contredirait tout ce que la page affirme.
    """
    lignes = [
        ("1", 0, "", "index.preuve.phases.cle"),
        ("5", 0, "", "index.preuve.degen.cle"),
        ("1356", 0, "", "index.preuve.tests.cle"),
    ]
    cartes = []
    for valeur, dec, suffixe, cle in lignes:
        cartes.append(
            f'<div class="preuve">'
            # La valeur FINALE est le contenu initial. Mise a zero, elle
            # restait a zero sans JavaScript : trois chiffres faux en tete
            # de page, sur un site qui vend l'exactitude. Le script part
            # de zero de lui-meme pour animer.
            f'<div class="preuve-val" data-compteur="{valeur}"'
            f' data-decimales="{dec}" data-suffixe="{suffixe}">'
            f'{valeur}{suffixe}</div>'
            f'<div class="preuve-cle">{escape(t(cle, langue))}</div></div>')
    # PAS de `data-reveler` ici. Le bandeau est dans le hero, dont
    # l'entree est deja animee au chargement. Porter les deux mecanismes
    # les faisait se contredire : l'entree finissait a l'opacite 1, puis
    # la regle de revelation la ramenait a 0 faute de classe `.vu`, et le
    # bandeau disparaissait.
    return f'<div class="preuves">{"".join(cartes)}</div>'


def console(langue: str) -> str:
    """
    La console d'identifiabilite : le coeur de la page d'accueil.

    Le visiteur coche les elements que son bulletin dose et lit, en direct,
    ce que ce bulletin determinerait. Les reponses viennent de `demo.json`,
    produit a la construction par `klastos.identifiability` : voir
    site/demo.py. Rien n'est approxime en JavaScript.

    Le balisage est COMPLET sans le script. Sans JavaScript, le visiteur
    voit les douze phases et la selection de depart ; il perd
    l'interaction, pas l'information.
    """
    from demo import DEPART, ELEMENTS_DEMO, _phases_retenues
    from klastos.phases import PHASES

    boutons = "".join(
        f'<button type="button" class="el" data-element="{e}"'
        f' aria-pressed="{"true" if e in DEPART else "false"}">{e}</button>'
        for e in ELEMENTS_DEMO)

    cartes = []
    for cle in _phases_retenues():
        fiche = PHASES.get(cle, {})
        formule = escape(fiche.get("formula", ""))
        cartes.append(
            f'<div class="phase" data-phase="{escape(cle)}">'
            f'<div class="phase-nom">{escape(fiche.get("label", cle))}</div>'
            + (f'<div class="phase-formule">{formule}</div>' if formule else "")
            + f'<div class="phase-etat"'
              f' data-ferme="{escape(t("console.etat.ferme", langue))}"'
              f' data-ouvert="{escape(t("console.etat.ouvert", langue))}">'
              f'</div></div>')

    mesures = "".join(
        f'<div class="console-mesure"><div class="console-mesure-val"'
        f' data-sortie="{sortie}">0</div>'
        f'<div class="console-mesure-cle">{escape(t(cle, langue))}</div></div>'
        for sortie, cle in (("dosees", "console.mesure.dosees"),
                            ("rang", "console.mesure.rang"),
                            ("deg", "console.mesure.deg"),
                            ("fermes", "console.mesure.fermes")))

    import json

    from demo import balayage

    donnees = json.dumps(balayage(), ensure_ascii=False,
                         separators=(",", ":"))
    # Une chaine « </ » dans le JSON fermerait le <script> qui le
    # porte. On la neutralise, comme le veut la specification.
    donnees = donnees.replace("</", r"<\/")

    return f"""<section class="bande bande-nuit section" id="console">
  <script type="application/json" id="demo-donnees">{donnees}</script>
  <div class="enveloppe">
    <p class="surtitre" data-reveler="0">\
{escape(t("console.surtitre", langue))}</p>
    <h2 style="max-width:22ch" data-reveler="1">\
{escape(t("console.h2", langue))}</h2>
    <p class="chapeau" data-reveler="2">\
{escape(t("console.chapeau", langue))}</p>

    <div class="console" data-console data-reveler="3">
      <p class="console-secours">\
{escape(t("console.indisponible", langue))}</p>
      <div class="console-corps">
        <p class="el-note">{escape(t("console.elements", langue))}</p>
        <div class="console-elements">{boutons}</div>
        <div class="console-actions">
          <button type="button" data-raz>\
{escape(t("console.raz", langue))}</button>
          <button type="button" data-tout>\
{escape(t("console.tout", langue))}</button>
        </div>
        <div class="console-mesures">{mesures}</div>
        <div class="jauge-piste"><div class="jauge-part" data-jauge></div></div>
        <p class="el-note">{escape(t("console.phases", langue))}</p>
        <div class="phases">{"".join(cartes)}</div>
        <p class="verdict-console" data-verdict
           data-rien="{escape(t("console.verdict.rien", langue))}"
           data-partiel="{escape(t("console.verdict.partiel", langue))}"
           data-large="{escape(t("console.verdict.large", langue))}"></p>
      </div>
    </div>
  </div>
</section>

<section class="bande section">
  <div class="enveloppe mesure">
    <h2 data-reveler="0" style="max-width:20ch">\
{escape(t("console.lecon.titre", langue))}</h2>
    <p class="chapeau" data-reveler="1">\
{escape(t("console.lecon.texte", langue))}</p>
  </div>
</section>"""


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

    return f"""<section class="hero">
  <div class="enveloppe">
    <p class="surtitre">{escape(t("index.surtitre", langue))}</p>
    <h1>{escape(t("index.h1", langue))}</h1>
    <p class="chapeau">{escape(t("index.chapeau", langue))}</p>
    {boutons.replace('bouton-creux', 'bouton-creux bouton-nuit')}
    {preuves(langue)}
    <a class="vers-console" href="#console">{escape(t("index.vers_console", langue))}</a>
  </div>
</section>

{console(langue)}

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

    # Le domaine servi. Voir la constante DOMAINE : GitHub Pages le
    # reclame a chaque deploiement, donc il appartient a la construction.
    cname = sortie / "CNAME"
    cname.write_text(DOMAINE + "\n", encoding="utf-8")
    ecrits.append(cname)

    # Pas de traitement Jekyll : le site est deja construit, et Jekyll
    # ignorerait tout dossier commencant par un tiret bas.
    nojekyll = sortie / ".nojekyll"
    nojekyll.write_text("", encoding="utf-8")
    ecrits.append(nojekyll)

    # Declinaisons de la marque. Elles sont COPIEES depuis `site/marque`,
    # qui est leur source, et non deposees a la main dans la sortie : une
    # construction neuve doit porter ses favicons, sinon le site n'en a que
    # sur la machine ou quelqu'un les a poses un jour. Un test de liens
    # morts l'a attrape.
    # La table de la demonstration n'est PAS ecrite a cote des pages :
    # elle est inseree dans la page d'accueil elle-meme. Un fichier
    # separe serait une copie que personne ne lit et qui derive.
    # Voir `console()`.

    if MARQUE_SOURCE.is_dir():
        cible = sortie / "marque"
        cible.mkdir(exist_ok=True)
        for fichier in sorted(MARQUE_SOURCE.glob("*.png")):
            copie = cible / fichier.name
            copie.write_bytes(fichier.read_bytes())
            ecrits.append(copie)

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
