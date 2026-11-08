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

from klastos import marque                              # noqa: E402

import charte                                           # noqa: E402
import mouvement                                        # noqa: E402
import contenu                                          # noqa: E402
import cotations                                        # noqa: E402
import illustrations                                    # noqa: E402
import procede                                          # noqa: E402
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

#: Adresse publiee sur le site. Elle est ECRITE EN CLAIR autant que posee
#: en lien : beaucoup de visiteurs lisent leur courrier dans un navigateur,
#: ou un `mailto:` n'ouvre rien du tout. Une adresse qu'on ne peut que
#: cliquer est une adresse perdue pour eux.
COURRIEL = f"contact@{DOMAINE}"


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
    """
    La barre de navigation, avec la page courante marquee.

    « Contact » n'y est PAS un lien de page : il ouvre directement la
    messagerie du visiteur, objet et corps pre-remplis. Un onglet qui
    menait a une page expliquant comment ecrire ajoutait une etape a qui
    voulait simplement ecrire.

    La page de contact reste publiee et reste atteignable par le pied :
    elle detaille ce qu'un bulletin doit contenir, et le plan du site la
    declare.
    """
    liens = []
    for p in PAGES:
        if p == "contact":
            liens.append(
                f'<a class="nav-contact"'
                f' href="{escape(lien_courriel(langue))}">'
                f'{escape(t(f"nav.{p}", langue))}</a>')
            continue
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
        {adresse(langue, "adresse adresse-pied")}
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
    for morceau in re.split(r"(<section\b[^>]*>)", corps):
        if (morceau.startswith("<section")
                and "data-reveler" not in morceau
                and not any(m in morceau for m in _SANS_REVELATION)):
            rang += 1
            morceau = morceau[:-1] + f' data-reveler="{rang % 3}">'
        sorties.append(morceau)
    return "".join(sorties)


def alternatives(page: str, langue: str) -> str:
    """
    Adresse canonique de la page, et ses versions dans l'autre langue.

    Le site publie chaque page DEUX FOIS, une par langue. Sans ces liens,
    un moteur les traite comme deux pages concurrentes sur le meme sujet,
    n'en retient qu'une au hasard, et le visiteur allemand tombe sur la
    version francaise.

    `x-default` designe la version servie a qui ne demande aucune des deux
    langues : l'anglais, comme dans `_redirects`.
    """
    liens = [f'<link rel="canonical"'
             f' href="https://{DOMAINE}/{langue}/{page}.html">']
    for autre in contenu.LANGUES:
        liens.append(f'<link rel="alternate" hreflang="{autre}"'
                     f' href="https://{DOMAINE}/{autre}/{page}.html">')
    liens.append(f'<link rel="alternate" hreflang="x-default"'
                 f' href="https://{DOMAINE}/en/{page}.html">')
    return "\n".join(liens)


#: Pages tenues HORS des moteurs. Elles ne repondent a aucune recherche :
#: on n'y arrive que par un envoi de formulaire, et une page de
#: remerciement dans les resultats n'aide personne - ni celui qui cherche
#: KLASTOS21, ni nous. Les tenir hors du plan du site ne suffit pas :
#: Google indexe ce qu'il trouve, pas seulement ce qu'on lui declare.
_HORS_MOTEURS = ("merci",)


#: Locale Open Graph de chaque langue.
_LOCALE_OG = {"fr": "fr_FR", "en": "en_GB"}

#: Taille de l'image de partage, celle que LinkedIn recommande.
PARTAGE_TAILLE = (1200, 630)


def partage(page: str, langue: str) -> str:
    """
    Les balises de partage : Open Graph, et la carte Twitter.

    ELLES MANQUAIENT, et la prospection en a besoin. Un lien vers le site
    poste sur LinkedIn s'affichait sans image ni description choisie :
    le reseau devinait. L'image est un PNG pose dans `site/marque`, donc
    copie par la construction comme les favicons ; elle est produite par
    `site/partage.py`. Les adresses sont ABSOLUES : un robot de reseau
    social ne resout pas un chemin relatif.
    """
    largeur, hauteur = PARTAGE_TAILLE
    titre = escape(t(f"{page}.titre_onglet", langue))
    description = escape(t(f"{page}.description", langue))
    return "\n".join([
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{escape(t("marque.nom", langue))}">',
        f'<meta property="og:title" content="{titre}">',
        f'<meta property="og:description" content="{description}">',
        f'<meta property="og:url" content="https://{DOMAINE}/{langue}/{page}.html">',
        f'<meta property="og:locale" content="{_LOCALE_OG[langue]}">',
        f'<meta property="og:image" content="https://{DOMAINE}/marque/partage-{langue}.png">',
        f'<meta property="og:image:width" content="{largeur}">',
        f'<meta property="og:image:height" content="{hauteur}">',
        f'<meta property="og:image:alt" content="{escape(t("partage.alt", langue))}">',
        '<meta name="twitter:card" content="summary_large_image">',
    ])


def page_complete(page: str, langue: str, corps: str) -> str:
    """Enveloppe une page : en-tete, navigation, corps, pied."""
    corps = rythmer(corps)
    robots = ('\n<meta name="robots" content="noindex, follow">'
              if page in _HORS_MOTEURS else "")
    return f"""<!doctype html>
<html lang="{langue}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>document.documentElement.className+=" js";</script>
<title>{escape(t(f"{page}.titre_onglet", langue))}</title>
<meta name="description" content="{escape(t(f"{page}.description", langue))}">{robots}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{charte.LIEN_POLICES}">
<link rel="stylesheet" href="../klastos.css">
<link rel="icon" type="image/png" sizes="32x32"
      href="../marque/favicon-32.png">
<link rel="apple-touch-icon" href="../marque/favicon-180.png">
{alternatives(page, langue)}
{partage(page, langue)}
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
    Trois chiffres sous le hero. Ils ne sont PAS decoratifs : les deux
    premiers viennent du lot XRF reel analyse pendant la mise au point, le
    troisieme est le delai de rendu, un engagement repris sur la page
    Contact. Un chiffre invente ici contredirait tout ce que la page
    affirme.
    """
    lignes = [
        ("1", 0, "", "index.preuve.phases.cle"),
        ("5", 0, "", "index.preuve.degen.cle"),
        ("48", 0, "", "index.preuve.delai.cle"),
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

    # Les valeurs vivent dans `illustrations.APE_GRANDEURS`, une fois :
    # l'apercu du rapport et l'image de partage les dessinent aussi, et
    # trois copies finiraient par dire trois choses.
    regle = "".join(
        ligne_regle(cle, langue, bas, haut, statut,
                    illustrations.pourcent(bas, haut, langue))
        for cle, bas, haut, statut in illustrations.APE_GRANDEURS)

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

{bloc_pour_qui(langue)}

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
</section>

{bloc_offre(langue)}"""


#: Les quatre profils de la section « Pour qui ». L'ordre suit la chaine :
#: celui qui vend le lot, celui qui l'achete, celui qui s'interpose, celui
#: qui le mesure.
PROFILS: tuple[str, ...] = ("vendeur", "acheteur", "negociant", "labo")


def bloc_pour_qui(langue: str) -> str:
    """
    Quatre cartes, une par profil de visiteur.

    EMPRUNT ASSUME a cylib (« Recycle with us ») et a tozero (« Become a
    partner ») : un visiteur doit savoir en dix secondes si la page le
    concerne. Chaque carte mene au formulaire, pas a une page de plus.
    """
    cartes = "".join(
        f"""<div class="carte carte-profil">
      <h3>{escape(t(f"index.pourqui.{p}.titre", langue))}</h3>
      <p>{escape(t(f"index.pourqui.{p}.texte", langue))}</p>
      <a class="lien-fleche" href="contact.html#formulaire">\
{escape(t("index.pourqui.lien", langue))}</a>
    </div>""" for p in PROFILS)
    return f"""<section class="bande section">
  <div class="enveloppe">
    <p class="surtitre">{escape(t("index.pourqui.surtitre", langue))}</p>
    <h2 class="mesure">{escape(t("index.pourqui.titre", langue))}</h2>
    <div class="grille grille-4" style="margin-top:34px">{cartes}</div>
  </div>
</section>"""


def bloc_offre(langue: str) -> str:
    """
    Le bandeau de fin d'accueil : l'offre, et l'apercu du document.

    La page se terminait sur les attestations, sans rien proposer de
    faire. Les sites de la filiere ferment tous sur un appel ; le notre
    ferme sur ce que le visiteur recoit, dessine, et sur les trois
    engagements que la page Contact repete mot pour mot.
    """
    return f"""<section class="bande bande-lavee section">
  <div class="enveloppe">
    <div class="offre">
      <div>
        <p class="surtitre">{escape(t("index.offre.surtitre", langue))}</p>
        <h2>{escape(t("index.offre.titre", langue))}</h2>
        <p class="chapeau" style="margin-bottom:26px">\
{escape(t("index.offre.texte", langue))}</p>
        {faits(["index.offre.f1", "index.offre.f2", "index.offre.f3"], langue)}
        <div class="boutons">
          <a class="bouton" href="contact.html#formulaire">\
{escape(t("index.offre.bouton", langue))}</a>
          <a class="bouton bouton-creux" href="rapport.html">\
{escape(t("index.bouton_rapport", langue))}</a>
        </div>
      </div>
      <figure class="offre-apercu">
        {illustrations.apercu(langue, t)}
        <figcaption>{escape(t("apercu.legende", langue))}</figcaption>
      </figure>
    </div>
  </div>
</section>"""


def page_methode(langue: str) -> str:
    etapes = "".join([
        carte("methode.un.titre", "methode.un.texte", langue),
        carte("methode.deux.titre", "methode.deux.texte", langue),
        carte("methode.trois.titre", "methode.trois.texte", langue),
    ])
    return f"""{entete("methode", langue)}

{bloc_procede(langue)}

<section class="bande section">
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

{bloc_illustrations(langue)}

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


def bloc_illustrations(langue: str) -> str:
    """
    Les deux illustrations techniques : l'echantillon et le module.

    ELLES SONT DESSINEES, ET LE DISENT. Cinq banques libres ont ete
    fouillees - Unsplash, Pexels, Pixabay, Wikimedia Commons, Openverse.
    Les seules bonnes images etaient payantes, et les images libres
    montraient le MAUVAIS MATERIAU : piles alcalines Varta et Philips,
    batteries de demarrage au plomb, figurines miniatures.

    Une pile alcaline sur un site de black mass, c'est une photo de
    charbon sur un site de minerai de fer. Sur un produit dont tout
    l'argument est « ce que le bulletin prouve », c'est le pire endroit
    ou mentir. Le chapeau de la section l'assume en toutes lettres.
    """
    return f"""<section class="bande section" id="illustrations">
  <div class="enveloppe">
    <h2>{escape(t("ill.titre", langue))}</h2>
    <p class="chapeau mesure">{escape(t("ill.chapeau", langue))}</p>
    <div class="ill-duo">
      <div>{illustrations.echantillon(langue, t)}</div>
      <div>{illustrations.module(langue, t)}</div>
    </div>
    <p class="ill-lecon">{escape(t("ill.lecon", langue))}</p>
  </div>
</section>"""


def bloc_procede(langue: str) -> str:
    """
    Le schema du procede : ou KLASTOS21 entre dans la chaine.

    IL REPOND A LA QUESTION QU'ON POSE TOUJOURS, au bout de deux minutes
    - « vous faites quoi, exactement ? » La reponse est une frontiere :
    l'outil ne broie pas, ne dose pas, ne raffine pas. Il entre apres le
    laboratoire, sur un bulletin.

    Et cette frontiere explique le reste du site : la provenance qu'il
    faut declarer, l'indetermination, la fourchette a la place d'un
    prix.
    """
    return f"""<section class="bande bande-lavee section" id="procede">
  <div class="enveloppe">
    <h2>{escape(t("proc.titre", langue))}</h2>
    <p class="chapeau mesure">{escape(t("proc.chapeau", langue))}</p>
    <div class="defilant" style="margin-top:28px">
      {procede.schema(langue, t)}
    </div>
    <p class="proc-lecon">{escape(t("proc.lecon", langue))}</p>
  </div>
</section>"""


def bloc_cotations(langue: str) -> str:
    """
    Le graphique des cotations, et ce qu'il demontre.

    IL N'ILLUSTRE PAS, IL ARGUMENTE. Le verrou de sept jours du moteur
    parait severe tant qu'on n'a pas vu le lithium faire 5,4 fois son
    prix en un an puis redescendre sous son point de depart. Une image
    de stock aurait decore ; ces quatre courbes viennent de l'extrait
    USGS que le projet embarque, et portent leur source.
    """
    series = cotations.lire_series()
    return f"""<section class="bande section" id="cotations">
  <div class="enveloppe">
    <h2>{escape(t("cot.titre", langue))}</h2>
    <p class="chapeau mesure">{escape(t("cot.chapeau", langue))}</p>
    <div class="cot-cadre defilant" style="margin-top:26px">
      {cotations.graphique(series, langue, t)}
    </div>
    <p class="cot-note">{escape(t("cot.echelle", langue))}</p>
    <p class="cot-note">{escape(t("cot.source", langue))}</p>
    <p class="cot-lecon">{escape(t("cot.lecon", langue))}</p>
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

{bloc_cotations(langue)}

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
    ])
    return f"""{entete("missions", langue)}

<section class="bande bande-lavee section">
  <div class="enveloppe">
    <div class="grille grille-3">{blocs}</div>
  </div>
</section>"""


def lien_courriel(langue: str) -> str:
    """
    Le lien `mailto:` complet : destinataire, objet et corps pre-remplis.

    L'encodage se fait par `urllib.parse.quote`, et non par un
    remplacement des espaces : un corps de message contient des retours a
    la ligne, des apostrophes et des accents, qui casseraient l'URL s'ils
    partaient tels quels.
    """
    from urllib.parse import quote

    objet = quote(t("contact.courriel.objet", langue))
    corps = quote(t("contact.courriel.corps", langue))
    return f"mailto:{COURRIEL}?subject={objet}&body={corps}"


def adresse(langue: str, classe: str = "adresse") -> str:
    """
    L'adresse de contact, ECRITE EN CLAIR et cliquable.

    Les deux, et pas seulement le lien. Beaucoup de visiteurs lisent leur
    courrier dans un navigateur : chez eux, un `mailto:` n'ouvre rien du
    tout. Une adresse qu'on ne peut que cliquer leur est inaccessible,
    alors qu'une adresse ecrite se copie toujours.

    L'objet est pre-rempli, parce qu'un courriel qui arrive avec son sujet
    se traite plus vite - et que le sujet rappelle au visiteur ce qu'il
    doit joindre.
    """
    return (f'<p class="{classe}">'
            f'<a href="{escape(lien_courriel(langue))}">'
            f'{escape(COURRIEL)}</a></p>')


def formulaire(langue: str) -> str:
    """
    Le formulaire, traite par Netlify.

    IL EXISTE POUR UNE RAISON MESUREE. Un lien `mailto:` ne mene nulle
    part chez une part notable des visiteurs : sur Windows 11, le
    gestionnaire pointe souvent sur l'application Courrier, retiree du
    systeme, et sa commande est vide. Le clic n'ouvre rien, et rien ne le
    signale. Le formulaire ne suppose aucun logiciel.

    Trois details qui le font fonctionner, et qu'on oublie facilement :

    - `data-netlify` declenche la detection a la construction. Netlify lit
      le HTML livre ; le formulaire doit donc etre dans la page, pas monte
      par script ;
    - `enctype` en `multipart/form-data`, sans quoi la piece jointe
      n'arrive pas ;
    - `form-name` en champ cache, qui nomme le formulaire dans le tableau
      de bord. Netlify l'ajoute lui-meme sur un formulaire statique, mais
      l'ecrire coute une ligne et evite d'en dependre ;
    - `action` en chemin ABSOLU. Mesure a l'appui : avec
      `action="merci.html"`, Netlify enregistre bien l'envoi mais sert
      SA page de remerciement generique au lieu de la notre. Il reecrit
      d'ailleurs l'attribut a la construction - `action='merci'`, sans
      extension - et ne sait pas resoudre un chemin relatif comme page
      de retour. Un visiteur voyait donc « Thank you! » en anglais, sans
      rappel de ce qu'il devait joindre.

    Le champ `bot-field` est un piege a robots : hors de l'ecran par la
    CSS, hors du parcours au clavier par `tabindex`, et hors de la lecture
    d'ecran par `aria-hidden`. Un visiteur ne peut donc ni le voir, ni
    l'atteindre, ni l'entendre ; un automate le remplit, et Netlify jette
    l'envoi.
    """
    oblig = escape(t("form.obligatoire", langue))

    def champ(nom, cle, type_="text", requis=False, indice=None):
        marque = f' <span class="champ-oblig">({oblig})</span>' if requis else ""
        aide = (f'<span class="champ-indice">{escape(t(indice, langue))}</span>'
                if indice else "")
        if type_ == "textarea":
            saisie = (f'<textarea id="{nom}" name="{nom}" rows="6"'
                      f'{" required" if requis else ""}></textarea>')
        else:
            saisie = (f'<input id="{nom}" name="{nom}" type="{type_}"'
                      f'{" required" if requis else ""}>')
        return (f'<p class="champ"><label for="{nom}">'
                f'{escape(t(cle, langue))}{marque}</label>{aide}{saisie}</p>')

    # Le profil du visiteur. Facultatif : la valeur vide est la premiere,
    # et un envoi sans profil vaut mieux qu'un envoi abandonne.
    options = "".join(
        f'<option value="{p}">{escape(t(f"form.profil.{p}", langue))}'
        f'</option>' for p in PROFILS + ("autre",))
    profil = (f'<p class="champ"><label for="profil">'
              f'{escape(t("form.profil", langue))}</label>'
              f'<select id="profil" name="profil">'
              f'<option value="">{escape(t("form.profil.choisir", langue))}'
              f'</option>{options}</select></p>')

    return f"""<section class="bande bande-lavee section" id="formulaire">
  <div class="enveloppe mesure">
    <h2>{escape(t("form.titre", langue))}</h2>
    <p class="chapeau" style="margin-bottom:30px">\
{escape(t("form.chapeau", langue))}</p>

    <form name="contact" method="POST" data-netlify="true"
          netlify-honeypot="bot-field" enctype="multipart/form-data"
          action="/{langue}/merci.html" class="formulaire">
      <input type="hidden" name="form-name" value="contact">
      <p class="piege" aria-hidden="true">
        <label>{escape(t("form.nom", langue))}
          <input name="bot-field" tabindex="-1" autocomplete="off"></label>
      </p>
      {champ("nom", "form.nom", requis=True)}
      {champ("organisation", "form.organisation")}
      {profil}
      {champ("courriel", "form.courriel", type_="email", requis=True)}
      {champ("message", "form.message", type_="textarea", requis=True,
             indice="form.message.indice")}
      {champ("bulletin", "form.fichier", type_="file",
             indice="form.fichier.indice")}
      <p style="margin-top:26px">
        <button type="submit" class="bouton">\
{escape(t("form.envoyer", langue))}</button>
      </p>
    </form>
  </div>
</section>"""


def page_introuvable() -> str:
    """
    La page servie pour toute adresse inexistante, dans les deux langues.

    POURQUOI ELLE EXISTE, ET POURQUOI ELLE EST BILINGUE.

    Netlify sert sa propre page d'erreur quand aucune `404.html` n'est
    publiee : un titre anglais, un paragraphe generique, et un lien vers
    sa documentation. Un visiteur francophone y lit qu'il a suivi « a
    broken link », et rien de ce qu'il doit faire.

    Le cas qui coute cher n'est d'ailleurs pas le lien mort : c'est un
    ENVOI DE FORMULAIRE QUI N'ABOUTIT PAS. Netlify repond alors 404, et
    le prospect repart en pensant que le site est casse. La page traite
    donc ce cas en premier, et donne l'adresse de courriel - la voie qui
    ne depend d'aucun reglage.

    TOUTES LES ADRESSES SONT ABSOLUES. Une page d'erreur est servie pour
    n'importe quel chemin, y compris `/a/b/c/inconnu` : un lien relatif
    y pointerait dans le vide, et la feuille de style ne se chargerait
    pas. C'est le piege propre a ce document, et il justifie qu'il ne
    passe pas par `page_complete`.

    Elle est bilingue sur un seul document parce qu'on ne peut pas
    deviner la langue du visiteur a partir d'une adresse qui n'existe
    pas.
    """
    def bloc_langue(langue: str) -> str:
        return f"""<section class="bande section">
  <div class="enveloppe mesure">
    <p class="surtitre">404</p>
    <h1>{escape(t("err.h1", langue))}</h1>
    <p class="chapeau">{escape(t("err.chapeau", langue))}</p>
    <div class="carte" style="margin-top:30px">
      <p class="carte-titre-mono">{escape(t("err.envoi.titre", langue))}</p>
      <p>{escape(t("err.envoi.texte", langue))}</p>
      <p class="adresse"><a href="{escape(lien_courriel(langue))}">{escape(COURRIEL)}</a></p>
    </div>
    <p class="boutons" style="margin-top:30px">
      <a class="bouton" href="/{langue}/index.html">{escape(t("err.retour", langue))}</a>
    </p>
  </div>
</section>"""

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(t("err.titre_onglet", "fr"))}</title>
<meta name="description" content="{escape(t("err.description", "fr"))}">
<meta name="robots" content="noindex, follow">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{charte.LIEN_POLICES}">
<link rel="stylesheet" href="/klastos.css">
<link rel="icon" type="image/png" sizes="32x32" href="/marque/favicon-32.png">
<link rel="apple-touch-icon" href="/marque/favicon-180.png">
</head>
<body>
<nav class="nav">
  <div class="enveloppe nav-interieur">
    <a class="marque" href="/">{logotype("fr")}</a>
  </div>
</nav>
<main>
{bloc_langue("fr")}
<div lang="en">{bloc_langue("en")}</div>
</main>
</body>
</html>
"""


def page_merci(langue: str) -> str:
    """L'accuse de reception, ou Netlify renvoie apres l'envoi."""
    return f"""<section class="bande section">
  <div class="enveloppe mesure">
    <p class="surtitre">{escape(t("merci.surtitre", langue))}</p>
    <h1>{escape(t("merci.h1", langue))}</h1>
    <p class="chapeau">{escape(t("merci.chapeau", langue))}</p>
  </div>
</section>

<section class="bande bande-lavee section">
  <div class="enveloppe mesure">
    <div class="carte">
      <p class="carte-titre-mono">{escape(t("merci.oubli.titre", langue))}</p>
      <p>{escape(t("merci.oubli.texte", langue))}</p>
      {adresse(langue)}
    </div>
    <p class="boutons" style="margin-top:34px">
      <a class="bouton" href="index.html">\
{escape(t("merci.retour", langue))}</a>
    </p>
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
        <p class="boutons" style="margin-top:22px">
          <a class="bouton" href="{escape(lien_courriel(langue))}">{escape(t("contact.courriel.bouton", langue))}</a>
          <button type="button" class="bouton bouton-creux bouton-copie" data-copier="{escape(COURRIEL)}" data-copie="{escape(t("contact.courriel.copie", langue))}">{escape(t("contact.courriel.copier", langue))}</button>
        </p>
        {adresse(langue)}
      </div>
      <div class="carte">
        <p class="carte-titre-mono">\
{escape(t("contact.modele.titre", langue))}</p>
        <p>{escape(t("contact.modele.texte", langue))}</p>
      </div>
    </div>
  </div>
</section>

<section class="bande section">
  <div class="enveloppe">
    <h2>{escape(t("contact.confiance.titre", langue))}</h2>
    <div style="margin-top:26px;max-width:72ch">
    {faits(["contact.confiance.f1", "contact.confiance.f2",
            "contact.confiance.f3", "contact.confiance.f4",
            "contact.confiance.f5"], langue)}
    </div>
  </div>
</section>

{formulaire(langue)}"""


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

    # Redirections de bord, lues par Netlify. La racine du site est
    # aujourd'hui une page de `meta refresh` : elle fonctionne partout,
    # y compris depuis un disque, mais elle coute un aller-retour complet
    # et ne choisit pas la langue.
    #
    # Ici, la redirection se fait AVANT d'envoyer la page, et sur
    # l'en-tete `Accept-Language` du visiteur. Un negociant allemand
    # arrive donc en anglais, un francais en francais. La page de
    # `meta refresh` reste en place pour tous les autres hebergements.
    # LE POINT D'EXCLAMATION N'EST PAS DECORATIF.
    #
    # Netlify sert un FICHIER STATIQUE avant d'appliquer une regle de
    # redirection. Or la racine en porte un : `index.html`, la page de
    # `meta refresh` gardee pour les autres hebergements. Sans le `!`, le
    # fichier gagnait et la regle ne s'appliquait jamais - mesure faite en
    # production, les trois langues rendaient 200 au lieu de 302.
    #
    # Le `!` force la regle malgre le fichier. Celui-ci reste en place et
    # sert partout ailleurs : sur un disque, sur un autre hebergeur.
    redirections = sortie / "_redirects"
    redirections.write_text(
        "# Racine : on sert la langue du visiteur, sinon l'anglais.\n"
        "# Le « ! » force la regle par-dessus index.html, que Netlify\n"
        "# servirait sinon en priorite.\n"
        "/    /fr/    302!    Language=fr\n"
        "/    /en/    302!\n", encoding="utf-8")
    ecrits.append(redirections)

    # ROBOTS ET PLAN DU SITE. Ils manquaient, et leur absence a eu une
    # consequence visible : Google affichait « nous voudrions effectuer
    # une description ici mais le site ne nous en laisse pas la
    # possibilite ».
    #
    # La cause n'etait pas chez nous - le domaine servait encore la page
    # d'attente du registrar, qui porte un `noindex` et un robots.txt
    # fermant. Mais un site sans robots.txt ni plan laisse le moteur
    # redecouvrir les douze pages a tatons, langue par langue. Les ecrire
    # abrege l'attente et dit explicitement ce qui est public.
    robots = sortie / "robots.txt"
    robots.write_text(
        "# KLASTOS21 - site vitrine. Tout est public.\n"
        "User-agent: *\n"
        "Allow: /\n"
        f"\nSitemap: https://{DOMAINE}/sitemap.xml\n", encoding="utf-8")
    ecrits.append(robots)

    # Le plan declare les DEUX langues de chaque page comme alternatives
    # l'une de l'autre. Sans cela, le moteur traite les versions
    # francaise et anglaise comme deux pages concurrentes sur le meme
    # sujet, et n'en montre qu'une au hasard.
    lignes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
              ' xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for langue in contenu.LANGUES:
        for page in PAGES:
            lignes.append("  <url>")
            lignes.append(f"    <loc>https://{DOMAINE}/{langue}/{page}.html</loc>")
            for autre in contenu.LANGUES:
                lignes.append(
                    f'    <xhtml:link rel="alternate" hreflang="{autre}"'
                    f' href="https://{DOMAINE}/{autre}/{page}.html"/>')
            lignes.append("  </url>")
    lignes.append("</urlset>")
    plan = sortie / "sitemap.xml"
    plan.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    ecrits.append(plan)

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

        # L'accuse de reception vit HORS de `PAGES` : il ne doit paraitre
        # ni dans la navigation, ni dans le pied, ni au plan du site. On
        # n'y arrive que par un envoi de formulaire, et une page de
        # remerciement trouvee par un moteur ne vaut rien a personne.
        merci = dossier / "merci.html"
        merci.write_text(
            page_complete("merci", langue, page_merci(langue)),
            encoding="utf-8")
        ecrits.append(merci)

    # LA PAGE D'ERREUR VIT A LA RACINE, et pas dans un dossier de
    # langue : Netlify la sert pour n'importe quelle adresse inconnue,
    # y compris celles qui n'ont pas de langue. C'est aussi elle que
    # voit un visiteur dont l'envoi de formulaire n'aboutit pas.
    introuvable = sortie / "404.html"
    introuvable.write_text(page_introuvable(), encoding="utf-8")
    ecrits.append(introuvable)
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
