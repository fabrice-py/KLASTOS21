"""
Tests du site vitrine.

Le site est le troisieme consommateur de la charte, apres l'interface et le
rapport imprime. Les deux premiers avaient deja derive cinq fois sur douze
jetons avant qu'un test ne les tienne. Ces tests existent pour que le
troisieme n'ajoute pas sa propre derive.

Ils portent sur quatre promesses :
  1. le contenu est complet dans les deux langues, et ne fuit pas d'une
     langue vers l'autre ;
  2. la charte ne nomme aucune couleur hors de son bloc `:root`, et obeit
     aux interdits qu'elle s'est donnes ;
  3. la palette du site est celle de `theme`, qui est elle-meme celle du
     rapport imprime ;
  4. les douze pages generees se tiennent : liens valides, langue declaree,
     aucune cle affichee a la place de son texte.
"""

from __future__ import annotations

import pathlib
import re
import sys
from html import unescape

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "site"))

import charte            # noqa: E402
import construire        # noqa: E402
import contenu           # noqa: E402

from klastos import theme    # noqa: E402


#: Cles dont le francais et l'anglais coincident legitimement : noms propres
#: et mots identiques dans les deux langues. Toute autre coincidence est une
#: traduction oubliee, donc le test la refuse.
IDENTIQUES_ADMISES = {
    "nav.contact",
    "marque.nom",
    "prix.licence.col_source",
    "contact.titre_onglet",
    "contact.surtitre",
    # Deux etiquettes de formulaire qui s'ecrivent de la meme facon dans
    # les deux langues. Verifie mot a mot, pas suppose.
    "form.message",
    "form.organisation",
    # Trois noms de metaux qui s'ecrivent de la meme facon dans les
    # deux langues. Le cuivre, lui, est bien traduit.
    "cot.lithium",
    "cot.cobalt",
    "cot.nickel",
    # Le schema du procede. « Black mass » est un terme anglais passe
    # tel quel en francais ; les trois autres sont des coincidences
    # ou le nom de la marque.
    "proc.batterie.nom",
    "proc.blackmass.nom",
    "proc.bulletin.nom",
    "proc.zone.nous",
    # Les illustrations. « BLACK MASS » est le nom du materiau, « Lot »
    # s'ecrit pareil, et les deux dernieres sont des DONNEES - un
    # numero de lot et une mesure - qui n'ont pas de version anglaise.
    "ech.titre",
    "ech.lot",
    "ech.lot.valeur",
    "ech.granulo.valeur",
}


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """Genere le site une fois pour tout le module."""
    sortie = tmp_path_factory.mktemp("site")
    construire.construire(sortie)
    return sortie


def _pages(sortie: pathlib.Path):
    """Les douze pages, en (langue, page, html brut)."""
    for langue in contenu.LANGUES:
        for page in contenu.PAGES:
            chemin = sortie / langue / f"{page}.html"
            yield langue, page, chemin.read_text(encoding="utf-8")


def _lisible(html: str) -> str:
    """
    Le HTML avec ses entites resolues.

    Sans cette etape, toute comparaison de texte est muette des qu'une
    apostrophe est en jeu : `html.escape` transforme « qu'il » en
    « qu&#x27;il », et une recherche du texte francais ne trouve rien. Le
    test de fuite de langue ci-dessous passait donc pour la mauvaise
    raison - presque chaque phrase francaise du catalogue porte une
    apostrophe.
    """
    return unescape(html)


# ==========================================================================
# 1. Le contenu
# ==========================================================================

@pytest.mark.parametrize("langue", contenu.LANGUES)
def test_chaque_cle_existe_dans_chaque_langue(langue):
    """Une cle sans traduction n'echoue qu'a l'affichage, trop tard."""
    manquantes = [c for c, e in contenu.TEXTES.items() if langue not in e]
    assert not manquantes, f"{langue} : {manquantes}"


@pytest.mark.parametrize("langue", contenu.LANGUES)
def test_aucun_texte_vide(langue):
    vides = [c for c, e in contenu.TEXTES.items() if not e[langue].strip()]
    assert not vides, f"{langue} : {vides}"


def test_une_traduction_identique_est_declaree_ou_refusee():
    """
    Un texte anglais identique au francais est presque toujours une
    traduction oubliee. Les quelques coincidences reelles - « Contact »,
    « Source », le nom de marque - sont nommees dans IDENTIQUES_ADMISES.
    Le test mord donc dans les deux sens : une nouvelle coincidence non
    declaree echoue, et une entree d'IDENTIQUES_ADMISES qui cesse de
    coincider echoue aussi, ce qui evite une liste qui s'allonge sans
    jamais se relire.
    """
    coincident = {c for c, e in contenu.TEXTES.items() if e["fr"] == e["en"]}
    assert coincident - IDENTIQUES_ADMISES == set(), (
        f"traductions probablement oubliees : "
        f"{sorted(coincident - IDENTIQUES_ADMISES)}")
    assert IDENTIQUES_ADMISES - coincident == set(), (
        f"declarees identiques mais traduites depuis : "
        f"{sorted(IDENTIQUES_ADMISES - coincident)}")


#: Voir `tests/test_i18n.py` : le cadratin est banni des textes affiches de
#: tout le projet. Le site est le troisieme support, il porte donc le meme
#: garde.
CARACTERE_BANNI = "\u2014"      # le cadratin, en echappement


def test_aucun_texte_du_site_ne_porte_de_cadratin():
    """
    Garde typographique, et il porte aussi sur les PAGES generees, pas
    seulement sur le catalogue : un gabarit pourrait en introduire un sans
    passer par une cle.
    """
    fautifs = [
        f"{cle} [{lg}]"
        for cle, entree in contenu.TEXTES.items()
        for lg in contenu.LANGUES
        if CARACTERE_BANNI in entree[lg]
    ]
    assert not fautifs, f"cadratin dans le contenu : {fautifs[:6]}"


def test_aucune_page_generee_ne_porte_de_cadratin(site):
    for langue, page, html in _pages(site):
        assert CARACTERE_BANNI not in html, (
            f"{langue}/{page} : un gabarit introduit un cadratin")


def test_une_cle_absente_donne_un_message_lisible():
    """
    Meme defaut que `i18n.CleInconnue` corrigeait : un KeyError affiche son
    argument entre guillemets, ce qui donne un message dans un message.
    """
    with pytest.raises(contenu.CleInconnue) as capture:
        contenu.t("page.inexistante")
    message = str(capture.value)
    assert "page.inexistante" in message
    assert message == capture.value.args[0]
    assert message != repr(capture.value.args[0])


def test_toute_page_declaree_a_ses_cles_d_en_tete():
    """
    Ajouter une page a `PAGES` sans ses cles de titre produirait une page
    dont l'onglet est vide. On exige les quatre cles de base.
    """
    for page in contenu.PAGES:
        for suffixe in ("titre_onglet", "description", "surtitre", "h1"):
            cle = f"{page}.{suffixe}"
            assert cle in contenu.TEXTES, f"cle absente : {cle}"


def test_toute_page_declaree_a_une_fonction_de_corps():
    """Garde de la table du generateur."""
    assert set(contenu.PAGES) == set(construire.CORPS_DE_PAGE), (
        f"PAGES {sorted(contenu.PAGES)} contre "
        f"CORPS_DE_PAGE {sorted(construire.CORPS_DE_PAGE)}")


# ==========================================================================
# 2. La charte
# ==========================================================================

def test_le_corps_de_la_feuille_ne_nomme_aucune_couleur():
    """
    Tout hex doit passer par le bloc `:root`, donc par `theme`. Un hex
    ecrit dans le corps serait une source de verite de plus, invisible au
    test de concordance ci-dessous.
    """
    trouves = re.findall(r"#[0-9A-Fa-f]{3,8}\b", charte.CORPS)
    assert not trouves, f"couleurs en litteral dans le corps : {trouves}"


@pytest.mark.parametrize("interdit", [
    "gradient", "box-shadow", "text-align: center", "text-align:center",
])
def test_la_charte_obeit_a_ses_propres_interdits(interdit):
    """
    Les quatre interdits releves comme unanimes sur les systemes de design
    de produits techniques, et inscrits dans la docstring de `charte`. Un
    degrade ou une ombre portee sur ce site le ferait glisser vers le SaaS
    aimable, qui est exactement le registre que le produit contredit.
    """
    assert interdit not in charte.CORPS, (
        f"« {interdit} » est interdit par la docstring de charte.py")


@pytest.mark.parametrize("nom,jeton", [
    ("bg", "CARTE"), ("paper", "PAPIER"), ("ink", "ENCRE"),
    ("muted", "ARDOISE"), ("line", "TRAIT"), ("line-strong", "TRAIT_FORT"),
    ("cobalt", "COBALT"), ("cobalt-soft", "COBALT_PALE"),
    ("amber", "AMBRE"), ("amber-soft", "AMBRE_PALE"),
    ("rust", "ROUILLE"), ("rust-soft", "ROUILLE_PALE"),
    ("green", "VERT"), ("green-soft", "VERT_PALE"),
])
def test_la_palette_du_site_est_celle_de_theme(nom, jeton):
    """
    Le maillon qui ferme la chaine : site <- theme <- rapport imprime.
    `tests/test_theme.py` tient le second maillon, celui-ci tient le
    premier. Les deux ensemble garantissent qu'une couleur changee au
    rapport se propage, ou fait echouer un test.
    """
    assert charte.JETONS[nom] == getattr(theme, jeton), (
        f"--{nom} : site {charte.JETONS[nom]} "
        f"contre theme.{jeton} {getattr(theme, jeton)}")


def test_la_table_des_jetons_couvre_toute_la_palette_de_theme():
    """
    Garde de completude. Sans elle, retirer une ligne de `JETONS`
    desarmerait sa verification en silence. Les jetons de barre laterale
    sont exclus : le site n'a pas de barre laterale sombre.
    """
    PROPRES_A_L_APP = {"NUIT", "NUIT_CLAIRE", "BORD_NUIT"}
    de_theme = {
        n for n in dir(theme)
        if n.isupper() and isinstance(getattr(theme, n), str)
        and getattr(theme, n).startswith("#")
    }
    oublies = de_theme - PROPRES_A_L_APP - set(
        {"CARTE", "PAPIER", "ENCRE", "ARDOISE", "TRAIT", "TRAIT_FORT",
         "COBALT", "COBALT_PALE", "AMBRE", "AMBRE_PALE", "ROUILLE",
         "ROUILLE_PALE", "VERT", "VERT_PALE"})
    assert not oublies, (
        f"jetons de theme non classes : {sorted(oublies)} - les ajouter a "
        f"charte.JETONS ou a PROPRES_A_L_APP")


def test_toute_variable_citee_par_le_corps_est_definie():
    """
    Un `var(--machin)` sans `--machin` dans `:root` ne provoque aucune
    erreur : la propriete est simplement ignoree et l'element sort sans
    couleur. C'est le genre de panne qu'on ne voit qu'a l'oeil, sur une
    page qu'on ne regarde plus.
    """
    citees = set(re.findall(r"var\(--([a-z-]+)\)", charte.CORPS))
    definies = set(charte.JETONS) | {f"f-{n}" for n in charte.POLICES}
    assert citees <= definies, (
        f"variables citees mais non definies : {sorted(citees - definies)}")


def _luminance(hexa: str) -> float:
    """Luminance relative WCAG d'une couleur #RRGGBB."""
    h = hexa.lstrip("#")
    canaux = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    canaux = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in canaux]
    return 0.2126 * canaux[0] + 0.7152 * canaux[1] + 0.0722 * canaux[2]


def _contraste(a: str, b: str) -> float:
    """Rapport de contraste WCAG entre deux couleurs."""
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


@pytest.mark.parametrize("nom,texte,fond", [
    ("pastille determinee", "cobalt", "cobalt-soft"),
    ("pastille mal determinee", "amber", "amber-soft"),
    ("pastille domaine", "rust", "rust-soft"),
    ("pastille bouclage", "green", "green-soft"),
    ("corps de texte", "ink", "bg"),
    ("texte secondaire", "muted", "bg"),
    ("texte secondaire sur lave", "muted", "paper"),
    ("bouton principal", "bg", "ink"),
])
def test_chaque_couple_de_couleurs_est_lisible(nom, texte, fond):
    """
    Sur ce produit, la couleur porte l'information : une pastille de statut
    illisible n'est pas un defaut cosmetique, c'est une mesure perdue. Le
    seuil retenu est AA pour texte normal, soit 4,5:1.

    Le couple le plus juste est le vert de bouclage, a 4,68:1. La marge est
    mince, donc ce test est precisement la ou il faut : un vert assombri ou
    un fond pali d'un cran le ferait tomber, et personne ne le verrait en
    relecture de diff.
    """
    r = _contraste(charte.JETONS[texte], charte.JETONS[fond])
    assert r >= 4.5, (
        f"{nom} : {charte.JETONS[texte]} sur {charte.JETONS[fond]} "
        f"donne {r:.2f}:1, sous le seuil AA de 4,5:1")


# ==========================================================================
# 3. Les pages generees
# ==========================================================================

def test_la_generation_ecrit_exactement_les_fichiers_attendus(site):
    """
    Les pages et la feuille de style. Les declinaisons de la marque sont
    comptees a part, par le test suivant : melanger les deux rendrait ce
    test illisible a chaque ajout de favicon.
    """
    # `CNAME` et `.nojekyll` sont des fichiers de DEPLOIEMENT, pas des
    # pages : ils ont leur propre test, juste en dessous.
    attendus = {"klastos.css", "index.html"}
    attendus |= {f"{lg}/{p}.html"
                 for lg in contenu.LANGUES for p in contenu.PAGES}
    # L'accuse de reception du formulaire. Il vit HORS de `PAGES` : on n'y
    # arrive que par un envoi, et il n'a sa place ni dans la navigation,
    # ni au plan du site.
    attendus |= {f"{lg}/merci.html" for lg in contenu.LANGUES}
    # La page d'erreur vit a la RACINE : Netlify ne la sert que
    # de la. Elle n'appartient a aucune langue.
    attendus |= {"404.html"}
    presents = {
        str(c.relative_to(site)).replace("\\", "/")
        for c in site.rglob("*")
        if c.is_file() and c.parent.name != "marque"
        and c.name not in ("CNAME", ".nojekyll", "_redirects",
                           "robots.txt", "sitemap.xml")
    }
    assert presents == attendus, (
        f"manquants : {sorted(attendus - presents)} / "
        f"en trop : {sorted(presents - attendus)}")


def test_la_generation_ecrit_le_domaine_servi(site):
    """
    GitHub Pages lit le domaine dans un fichier `CNAME` a la racine du
    site publie, et il le RECLAME A CHAQUE DEPLOIEMENT. Pose a la main
    dans les reglages du depot, il saute au deploiement suivant et le site
    repart sur l'adresse en github.io - sans rien signaler.

    Il appartient donc a la construction, comme le reste.
    """
    from construire import DOMAINE

    cname = site / "CNAME"
    assert cname.exists(), "le domaine servi n'est plus ecrit"
    assert cname.read_text(encoding="utf-8").strip() == DOMAINE
    assert (site / ".nojekyll").exists(), (
        "sans ce fichier, Jekyll retraite le site et ignore tout dossier "
        "commencant par un tiret bas")


def test_l_adresse_de_contact_figure_sur_toutes_les_pages(site):
    """
    La page de contact disait « ecrivez-nous » sans donner la moindre
    adresse, et aucune autre page n'en portait. Le site invitait a ecrire
    sans dire ou.

    Elle est desormais au pied de chaque page : un visiteur qui vient de
    lire la methode ne doit pas avoir a chercher l'onglet contact.
    """
    from construire import COURRIEL

    for langue, page, html in _pages(site):
        assert COURRIEL in html, f"{langue}/{page} : aucune adresse"
        assert f"mailto:{COURRIEL}" in html, f"{langue}/{page} : non cliquable"


def test_l_adresse_est_lisible_autant_que_cliquable(site):
    """
    LE POINT QUI COMPTE. Beaucoup de visiteurs lisent leur courrier dans
    un navigateur : chez eux, un `mailto:` n'ouvre rien du tout. Une
    adresse posee UNIQUEMENT en lien leur est inaccessible, alors qu'une
    adresse ecrite se copie toujours.

    Le texte du lien doit donc etre l'adresse elle-meme, et non un
    libelle du genre « nous contacter ».
    """
    import re as _re

    from construire import COURRIEL

    html = _page_texte(site, "contact", "fr")
    liens = _re.findall(r'<a href="mailto:[^"]*">([^<]*)</a>', html)
    assert liens, "aucun lien de courriel"
    assert COURRIEL in liens, (
        f"l'adresse n'est pas ecrite en clair, seulement masquee derriere "
        f"un libelle : {liens}")


def test_le_lien_de_courriel_porte_un_objet(site):
    """Un courriel qui arrive avec son sujet se traite plus vite, et le
    sujet rappelle au visiteur ce qu'il doit joindre."""
    html = _page_texte(site, "contact", "fr")
    assert "?subject=" in html
    assert "%20" in html, "l'objet n'est pas encode pour une URL"


def test_l_onglet_contact_ouvre_la_messagerie(site):
    """
    « Contact » n'est plus un lien de page : il ouvre directement la
    messagerie du visiteur. Un onglet qui menait a une page expliquant
    comment ecrire ajoutait une etape a qui voulait simplement ecrire.
    """
    from construire import COURRIEL

    for langue, page, html in _pages(site):
        i = html.index('class="nav-liens"')
        barre = html[i:html.index("</div>", i)]
        assert f'href="mailto:{COURRIEL}' in barre, (
            f"{langue}/{page} : l'onglet Contact ne mene plus a la "
            f"messagerie")
        assert 'href="contact.html"' not in barre, (
            f"{langue}/{page} : l'onglet Contact est redevenu un lien de "
            f"page")


def test_le_lien_de_courriel_porte_un_corps_pre_rempli(site):
    """
    Le corps rappelle les trois choses que la page de contact enumere -
    unite, provenance, DRX - au moment ou le visiteur ecrit, et non trois
    ecrans plus tot. Un bulletin arrive ainsi deja qualifie.
    """
    html = _page_texte(site, "contact", "fr")
    assert "&amp;body=" in html or "&body=" in html, "aucun corps pre-rempli"
    assert "%0A" in html, "le corps ne contient aucun retour a la ligne"


def test_la_page_de_contact_reste_atteignable(site):
    """
    Elle detaille ce qu'un bulletin doit contenir. La sortir de la
    navigation ne doit pas la rendre introuvable : le pied y mene, et le
    plan du site la declare.
    """
    import xml.etree.ElementTree as ET

    for langue, page, html in _pages(site):
        i = html.index('<footer')
        assert 'href="contact.html"' in html[i:], (
            f"{langue}/{page} : le pied ne mene plus a la page de contact")

    plan = (site / "sitemap.xml").read_text(encoding="utf-8")
    assert "contact.html" in plan, "le plan du site a perdu la page"


def _page_texte(site, page, langue):
    return (site / langue / f"{page}.html").read_text(encoding="utf-8")


def test_le_site_autorise_explicitement_son_indexation(site):
    """
    Google affichait « nous voudrions effectuer une description ici mais
    le site ne nous en laisse pas la possibilite ». La cause etait en
    amont - le domaine servait encore la page d'attente du registrar, qui
    porte un `noindex` - mais le site n'avait ni robots.txt ni plan, et
    rien ne disait au moteur quoi lire.
    """
    from construire import DOMAINE

    robots = site / "robots.txt"
    assert robots.exists(), "aucun robots.txt : le moteur avance a tatons"
    texte = robots.read_text(encoding="utf-8")
    assert "Allow: /" in texte
    assert "Disallow: /" not in texte, (
        "le site s'interdit a lui-meme d'etre lu")
    assert f"https://{DOMAINE}/sitemap.xml" in texte

    # Et aucune page ne doit porter de `noindex`.
    for langue, page, html in _pages(site):
        assert "noindex" not in html, f"{langue}/{page}"


def test_le_plan_du_site_declare_les_douze_pages(site):
    import xml.etree.ElementTree as ET

    from construire import DOMAINE

    plan = site / "sitemap.xml"
    assert plan.exists(), "aucun plan du site"
    racine = ET.fromstring(plan.read_text(encoding="utf-8"))
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    adresses = [u.findtext("s:loc", namespaces=ns) for u in racine]
    assert len(adresses) == len(contenu.LANGUES) * len(contenu.PAGES)
    for a in adresses:
        assert a.startswith(f"https://{DOMAINE}/")


@pytest.mark.parametrize("langue", ["fr", "en"])
def test_chaque_page_declare_sa_version_dans_l_autre_langue(site, langue):
    """
    Le site publie chaque page DEUX FOIS, une par langue. Sans liens
    `hreflang`, un moteur les traite comme deux pages concurrentes sur le
    meme sujet, n'en retient qu'une au hasard, et le visiteur allemand
    tombe sur la version francaise.
    """
    from construire import DOMAINE

    for page in contenu.PAGES:
        html = (site / langue / f"{page}.html").read_text(encoding="utf-8")
        attendu = (f'<link rel="canonical"'
                   f' href="https://{DOMAINE}/{langue}/{page}.html">')
        assert attendu in html, f"{langue}/{page} : pas d'adresse canonique"
        for autre in contenu.LANGUES:
            assert (f'hreflang="{autre}"'
                    f' href="https://{DOMAINE}/{autre}/{page}.html"') in html
        assert 'hreflang="x-default"' in html, (
            f"{langue}/{page} : aucune langue par defaut declaree")


def test_la_racine_redirige_vers_la_langue_du_visiteur(site):
    """
    La racine du site est servie de deux facons, et les deux comptent.

    `_redirects` est lu par Netlify et redirige AVANT d'envoyer la page,
    sur l'en-tete Accept-Language : un negociant allemand arrive en
    anglais, un francais en francais.

    La page de `meta refresh` reste en place pour tous les autres
    hebergements, et pour une ouverture depuis un disque.
    """
    red = site / "_redirects"
    assert red.exists(), "les redirections de bord ont disparu"
    texte = red.read_text(encoding="utf-8")
    assert "Language=fr" in texte
    assert "/en/" in texte, "aucune langue de repli"
    # La regle de repli vient APRES la regle conditionnelle, sans quoi
    # elle capterait tout le monde.
    assert texte.index("Language=fr") < texte.index("/    /en/")

    # LE POINT D'EXCLAMATION. Netlify sert un fichier statique avant
    # d'appliquer une redirection, et la racine en porte un : index.html.
    # Sans le `!`, la regle ne s'appliquait jamais - mesure faite en
    # production, les trois langues rendaient 200 au lieu de 302.
    for ligne in texte.splitlines():
        if ligne.startswith("/ ") or ligne.startswith("/\t") or \
                (ligne.startswith("/") and not ligne.startswith("#")
                 and ligne.split()[0] == "/"):
            assert "!" in ligne, (
                f"regle sans « ! » : index.html la masquera. {ligne!r}")

    racine = (site / "index.html").read_text(encoding="utf-8")
    assert "http-equiv=\"refresh\"" in racine, (
        "la racine ne redirige plus hors de Netlify")


def test_la_generation_copie_les_declinaisons_de_la_marque(site):
    """
    Les favicons etaient deposes a la main dans `site/public`. Une
    construction neuve n'en portait donc aucun, et les pages pointaient sur
    des fichiers absents - ce que le test de liens morts a attrape. Les
    assets sont desormais COPIES depuis `site/marque` a la construction.
    """
    from construire import MARQUE_SOURCE

    copiees = {c.name for c in (site / "marque").glob("*.png")}
    sources = {c.name for c in MARQUE_SOURCE.glob("*.png")}
    assert copiees == sources, (
        f"declinaisons non copiees : {sorted(sources - copiees)}")
    assert {"favicon-32.png", "favicon-180.png"} <= copiees


def test_chaque_page_declare_sa_langue(site):
    for langue, page, html in _pages(site):
        assert f'<html lang="{langue}">' in html, f"{langue}/{page}"


def test_chaque_page_porte_un_titre_et_une_description(site):
    for langue, page, html in _pages(site):
        titre = contenu.t(f"{page}.titre_onglet", langue)
        assert "<title>" in html, f"{langue}/{page} : pas de titre"
        # Le titre joint la marque et le sujet par « | », separateur
        # que le depot emploie deja dans `Analyse.resume()`. On ne
        # verifie que le premier segment : il suffit a identifier la
        # page, et le second varie avec la langue.
        assert titre.split(" | ")[0] in _lisible(html), (
            f"{langue}/{page}")
        assert 'name="description"' in html, f"{langue}/{page}"


def test_chaque_page_a_ses_balises_equilibrees(site):
    """
    Un gabarit qui oublie un `</div>` ne leve rien : le navigateur recolle
    la page a sa facon, et la mise en page part de travers sans message. On
    verifie donc l'equilibre, y compris sur la page de redirection.
    """
    from html.parser import HTMLParser

    class Verif(HTMLParser):
        VIDES = {"meta", "link", "br", "img", "hr", "input", "source"}

        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.pile: list[str] = []
            self.fautes: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag not in self.VIDES:
                self.pile.append(tag)

        def handle_endtag(self, tag):
            if not self.pile:
                self.fautes.append(f"</{tag}> sans ouverture")
            elif self.pile[-1] != tag:
                self.fautes.append(f"</{tag}> ferme <{self.pile[-1]}>")
            else:
                self.pile.pop()

    for chemin in sorted(site.rglob("*.html")):
        v = Verif()
        v.feed(chemin.read_text(encoding="utf-8"))
        nom = chemin.relative_to(site)
        assert not v.fautes, f"{nom} : {v.fautes[:4]}"
        assert not v.pile, f"{nom} : balises non fermees {v.pile}"


def test_le_logotype_ne_repete_pas_les_chiffres(site):
    """
    Le gabarit ecrivait le nom venu de la cle, puis un `<span>21</span>` en
    litteral : le logotype sortait « KLASTOS21 21 ». La coupure est
    maintenant derivee du nom, et ce test la tient.
    """
    from klastos import marque as _marque

    nom = contenu.t("marque.nom")
    for langue, page, html in _pages(site):
        debut = html.index('<a class="marque"')
        fin = html.index("</a>", debut)
        bloc = html[debut:fin]
        # La signature fait partie du verrouillage depuis que le logo est
        # pose. On l'ote avant de verifier le MOT, qui est le sujet de ce
        # test : sans cela, il echouerait sur une addition legitime.
        mot = re.sub(r"<[^>]+>", "", bloc).replace(_marque.SIGNATURE, "")
        assert mot.strip() == nom, (
            f"{langue}/{page} : logotype « {mot.strip()} » "
            f"au lieu de « {nom} »")
        assert _marque.SIGNATURE in bloc, (
            f"{langue}/{page} : la signature du logo a disparu du "
            f"verrouillage")


def test_chaque_lien_interne_pointe_sur_un_fichier_existant(site):
    """
    Douze pages qui se citent mutuellement, plus la bascule de langue :
    cinquante-quatre liens par page. Un lien mort ne se voit qu'au clic.
    """
    morts = []
    for langue, page, html in _pages(site):
        dossier = site / langue
        for cible in re.findall(r'href="([^"#]+)"', html):
            if cible.startswith(("http://", "https://", "mailto:")):
                continue
            if not (dossier / cible).resolve().exists():
                morts.append(f"{langue}/{page} -> {cible}")
    assert not morts, f"liens morts : {morts}"


def test_la_page_courante_est_marquee_une_fois_et_une_seule(site):
    """
    `aria-current="page"` est ce qui souligne l'onglet actif. Deux marques
    ou zero marque, et le visiteur ne sait plus ou il est.
    """
    for langue, page, html in _pages(site):
        n = html.count('aria-current="page"')
        if page == "contact":
            # « Contact » n'est plus un onglet de page : il ouvre la
            # messagerie. La page de contact existe toujours - le pied y
            # mene et le plan du site la declare - mais aucun onglet ne
            # peut s'y marquer courant, puisqu'aucun onglet n'y mene.
            assert n == 0, (
                f"{langue}/{page} : un onglet se dit courant alors que la "
                f"navigation ne mene plus a cette page")
            continue
        assert n == 1, f"{langue}/{page} : {n} marques de page courante"


def test_la_bascule_de_langue_mene_a_la_meme_page(site):
    """
    Changer de langue doit garder le lecteur sur son sujet. Renvoyer a
    l'accueil est le defaut classique des sites bilingues, et il fait
    perdre la page qu'on etait en train de lire.
    """
    for langue, page, html in _pages(site):
        for autre in contenu.LANGUES:
            attendu = f'href="../{autre}/{page}.html"'
            assert attendu in html, f"{langue}/{page} : {attendu} absent"


def test_aucune_cle_ne_s_affiche_a_la_place_de_son_texte(site):
    """
    L'invariant du projet : UNE CLE N'EST JAMAIS UN TEXTE AFFICHE. Si une
    cle fuit dans la page, elle y apparait sous sa forme pointee.
    """
    suspects = {c for c in contenu.TEXTES if "." in c}
    for langue, page, html in _pages(site):
        # On retire les attributs techniques avant de chercher.
        visible = re.sub(r"<[^>]+>", " ", _lisible(html))
        fuites = [c for c in suspects if c in visible]
        assert not fuites, f"{langue}/{page} : cles affichees {fuites}"


def test_aucun_reste_de_gabarit(site):
    """
    Une f-string mal fermee laisse un `{quelque_chose}` dans la page, et un
    appel rate laisse un « None ». Les deux passent inapercus en relecture.
    """
    for langue, page, html in _pages(site):
        assert "None" not in html, f"{langue}/{page} : « None » dans la page"
        restes = re.findall(r"\{[a-z_]+\}", html)
        assert not restes, f"{langue}/{page} : gabarit non rendu {restes}"


# ==========================================================================
# 4. Le test qui mord le plus : la fuite d'une langue vers l'autre
# ==========================================================================

def test_aucun_texte_francais_ne_fuit_dans_les_pages_anglaises(site):
    """
    Le defaut que la conversion bilingue du produit a produit deux fois :
    un texte reste en francais dans une sortie anglaise. Un test qui ne
    cherche que les accents ne l'attrape pas - « Internal record » et
    « Relevé interne » diffe-rent, mais « Source » est identique dans les
    deux langues et passerait.

    Le test est donc exhaustif plutot qu'heuristique : pour chaque cle dont
    les deux langues diffe-rent, le texte francais ne doit pas apparaitre
    dans une page anglaise, ni l'inverse. C'est la forme la plus forte
    disponible, et elle ne depend d'aucune liste de mots.
    """
    pages = {(lg, p): h for lg, p, h in _pages(site)}
    fuites = []
    for cle, entree in contenu.TEXTES.items():
        if entree["fr"] == entree["en"]:
            continue
        for langue, autre in (("en", "fr"), ("fr", "en")):
            intrus = entree[autre]
            if len(intrus) < 12:        # trop court pour etre concluant
                continue
            for page in contenu.PAGES:
                if intrus in _lisible(pages[(langue, page)]):
                    fuites.append(f"{langue}/{page} : {cle} en {autre}")
    assert not fuites, f"fuites de langue : {fuites}"


def test_chaque_page_contient_bien_les_textes_de_sa_langue(site):
    """
    Le pendant positif du test ci-dessus. Sans lui, une page vide passerait
    le test de fuite sans rien dire : rien a fuir si rien ne s'affiche.
    """
    pages = {(lg, p): h for lg, p, h in _pages(site)}
    for langue in contenu.LANGUES:
        for page in contenu.PAGES:
            html = pages[(langue, page)]
            attendu = contenu.t(f"{page}.h1", langue)
            assert attendu in _lisible(html), (
                f"{langue}/{page} : le titre h1 de la page est absent")
            assert len(html) > 3000, (
                f"{langue}/{page} : page suspecte de {len(html)} octets")


# ======================================================================
# LE FORMULAIRE
# ----------------------------------------------------------------------
# Trois attributs le font fonctionner, et aucun ne se voit a l'oeil sur
# la page livree : si l'un disparait dans un remaniement, les messages
# cessent d'arriver SANS AUCUN SIGNAL. C'est exactement le genre de panne
# qu'un test doit porter a notre place.
# ======================================================================

def _formulaire(site, langue: str) -> str:
    """Le seul formulaire de la page contact, balises comprises."""
    html = (site / langue / "contact.html").read_text(encoding="utf-8")
    assert html.count("<form") == 1, (
        f"{langue}/contact : {html.count('<form')} formulaires, un attendu")
    return html[html.index("<form"):html.index("</form>") + 7]


@pytest.mark.parametrize("langue", sorted(contenu.LANGUES))
def test_le_formulaire_porte_les_attributs_que_netlify_exige(site, langue):
    """
    `data-netlify` declenche la detection a la construction, `method=POST`
    et `enctype` multipart acheminent la piece jointe. Sans le dernier,
    le message arrive et le bulletin se perd en route, ce qui est le pire
    des cas : un envoi mutile qu'on croit complet.
    """
    f = _formulaire(site, langue)
    for attendu in ('data-netlify="true"',
                    'method="POST"',
                    'enctype="multipart/form-data"',
                    'name="contact"'):
        assert attendu in f, f"{langue}/contact : {attendu} absent du formulaire"


def test_l_action_du_formulaire_est_un_chemin_absolu(site):
    """
    MESURE SUR LE SITE EN LIGNE, apres un envoi reel.

    Avec `action="merci.html"`, Netlify enregistrait bien l'envoi mais
    servait SA page de remerciement generique - « Thank you! », en
    anglais, sans rappel de ce que le visiteur devait joindre. Il
    reecrit d'ailleurs l'attribut a la construction, en
    `action='merci'`, et ne sait pas resoudre un chemin relatif comme
    page de retour.

    La page d'accuse que porte ce depot ne servait donc jamais.
    """
    for langue in contenu.LANGUES:
        html = (site / langue / "contact.html").read_text(encoding="utf-8")
        action = re.search(r'<form[^>]*action="([^"]+)"', html)
        assert action, f"{langue}/contact : le formulaire n'a pas d'action"
        chemin = action.group(1)
        assert chemin.startswith("/"), (
            f"{langue}/contact : action {chemin!r} relative. Netlify "
            f"servira sa page generique a la place de la notre.")
        assert chemin == f"/{langue}/merci.html", (
            f"{langue}/contact : action {chemin!r}, attendu "
            f"/{langue}/merci.html")
        cible = site / langue / "merci.html"
        assert cible.exists(), (
            f"l'action pointe vers {chemin}, qui n'est pas publie")


@pytest.mark.parametrize("langue", sorted(contenu.LANGUES))
def test_le_piege_a_robots_est_declare_et_inatteignable(site, langue):
    """
    Le piege ne vaut que si Netlify sait lequel il est, et s'il reste
    hors de portee d'un visiteur. `display:none` est exclu : plusieurs
    automates le reconnaissent et laissent le champ vide, ce qui rend le
    piege inoperant.
    """
    f = _formulaire(site, langue)
    assert 'netlify-honeypot="bot-field"' in f, (
        f"{langue}/contact : le piege n'est pas declare a Netlify")
    assert 'name="bot-field"' in f, f"{langue}/contact : le piege est absent"

    piege = f[f.index('class="piege"'):f.index('name="bot-field"') + 60]
    assert 'tabindex="-1"' in piege, (
        f"{langue}/contact : le piege est atteignable au clavier")
    assert 'aria-hidden="true"' in piege, (
        f"{langue}/contact : le piege est lu par les lecteurs d'ecran")

    css = (site / "klastos.css").read_text(encoding="utf-8")
    regle = css[css.index(".piege {"):css.index("}", css.index(".piege {"))]
    assert "display: none" not in regle and "display:none" not in regle, (
        "le piege est masque par display:none, que les robots reconnaissent")
    assert "-9999px" in regle, "le piege n'est pas sorti de l'ecran"


@pytest.mark.parametrize("langue", sorted(contenu.LANGUES))
def test_chaque_champ_visible_porte_une_etiquette_liee(site, langue):
    """
    Un champ sans `label for` n'est pas annonce par un lecteur d'ecran et
    ne se clique pas par son intitule. Le piege est exclu du compte : il
    est deliberement cache.
    """
    f = _formulaire(site, langue)
    visible = f[f.index("</p>", f.index('class="piege"')):]
    noms = re.findall(r'<(?:input|textarea) id="([a-z]+)"', visible)
    assert noms, f"{langue}/contact : aucun champ visible trouve"
    for nom in noms:
        assert f'<label for="{nom}">' in visible, (
            f"{langue}/contact : le champ « {nom} » n'a pas d'etiquette liee")


@pytest.mark.parametrize("langue", sorted(contenu.LANGUES))
def test_l_accuse_de_reception_est_atteignable_mais_hors_du_plan(site, langue):
    """
    La page de remerciement doit exister, sinon l'envoi finit sur une 404
    qui laisse croire a un echec. Elle ne doit pas pour autant figurer au
    plan du site : on n'y arrive que par un envoi, et une page de
    remerciement indexee est du bruit pour qui cherche KLASTOS21.
    """
    merci = site / langue / "merci.html"
    assert merci.exists(), f"{langue}/merci.html : absent, l'envoi finira en 404"

    f = _formulaire(site, langue)
    assert f'action="/{langue}/merci.html"' in f, (
        f"{langue}/contact : le formulaire ne renvoie pas vers l'accuse. "
        f"Le chemin doit etre ABSOLU : voir "
        f"test_l_action_du_formulaire_est_un_chemin_absolu.")

    plan = (site / "sitemap.xml").read_text(encoding="utf-8")
    assert "merci" not in plan, "l'accuse de reception figure au plan du site"

    # L'absence du plan ne suffit pas : un moteur indexe ce qu'il trouve,
    # pas seulement ce qu'on lui declare. Le `follow` est volontaire -
    # la page ne doit pas paraitre dans les resultats, mais les liens
    # qu'elle porte vers le site restent suivis.
    html_tete = merci.read_text(encoding="utf-8")[:1500]
    assert 'content="noindex, follow"' in html_tete, (
        f"{langue}/merci.html : rien n'empeche son indexation")

    html = merci.read_text(encoding="utf-8")
    assert contenu.t("merci.h1", langue) in _lisible(html), (
        f"{langue}/merci.html : son propre titre est absent")


# ======================================================================
# LES ACCENTS DU CATALOGUE FRANCAIS
# ----------------------------------------------------------------------
# Le code de ce projet est ecrit sans accents : commentaires, docstrings,
# noms de fonctions. C'est une convention utile, et c'est aussi un piege,
# parce que la main prend le pli et continue dans les TEXTES AFFICHES,
# ou l'accent n'est pas optionnel. La faute est passee une fois : les
# dix-neuf textes du formulaire sont arrives sans un seul accent, au
# milieu d'un catalogue entierement accentue, et rien ne l'a signale.
#
# Le test ne sait pas lire le francais. Il connait une LISTE DE FORMES
# QUI N'EXISTENT PAS : aucune de ces suites de lettres n'est un mot
# francais valide, donc leur presence est toujours un accent manquant.
# La liste est un echantillon, pas une grammaire - elle attrape la faute
# courante, pas toutes les fautes. Elle vaut mieux qu'un controle absent.
# ======================================================================

#: Formes sans accent qui ne sont jamais des mots francais. Les mots
#: ambigus sont volontairement exclus : « parait » et « cle » existent
#: (orthographe de 1990, lie/lier), « arrive » et « oublie » aussi.
JAMAIS_DES_MOTS = (
    "ete", "recu", "echeant", "indetermination", "deja", "apres", "tres",
    "etre", "meme", "numero", "unite", "qualite", "donnees", "methode",
    "resultat", "reference", "parametre", "operateur", "securite",
    "precision", "verite", "procede", "declare", "elements", "modele",
    "detail", "periode", "critere", "categorie", "echantillon",
)


def _prose(texte: str) -> str:
    """
    Le texte prive de ce qui n'est pas de la prose.

    Un nom de fichier n'a pas d'accent, et c'est normal :
    `bulletin_modele.csv` s'ecrit ainsi sur le disque. Sans ce filtrage,
    le test reclamerait un accent dans un chemin, et la seule facon de
    le faire taire serait de retirer le mot de la liste - ce qui le
    rendrait aveugle a la vraie faute, « modele » en pleine phrase.
    """
    texte = re.sub(r"[\w.\-/]*[/_][\w.\-/]*", " ", texte)
    return re.sub(r"\b\w+\.[a-z]{2,4}\b", " ", texte)


def test_aucun_texte_francais_ne_perd_ses_accents():
    """
    Un accent manquant ne casse rien : la page s'affiche, les tests
    passent, et seul un lecteur francophone le voit. C'est exactement le
    genre de defaut qui survit a une relecture et arrive en production.
    """
    fautes = []
    for cle, textes in contenu.TEXTES.items():
        mots = set(re.findall(r"[a-z]+", _prose(textes["fr"]).lower()))
        for suspect in JAMAIS_DES_MOTS:
            if suspect in mots:
                fautes.append(f"{cle} : « {suspect} » sans accent")
    assert not fautes, (
        "accents manquants dans des textes affiches :\n  "
        + "\n  ".join(fautes))


def test_la_liste_des_formes_fautives_est_bien_formee():
    """
    Le pendant du test ci-dessus. Une entree en double, accentuee, ou
    contenant autre chose que des minuscules rendrait la liste muette
    sans que personne ne s'en apercoive.
    """
    assert len(JAMAIS_DES_MOTS) == len(set(JAMAIS_DES_MOTS)), (
        "doublon dans JAMAIS_DES_MOTS")
    for forme in JAMAIS_DES_MOTS:
        assert re.fullmatch(r"[a-z]+", forme), (
            f"« {forme} » n'est pas une forme sans accent en minuscules")


# ==========================================================================
# 9. LA FEUILLE DE STYLE EST SYNTAXIQUEMENT SAINE
# --------------------------------------------------------------------------
# Un defaut reel est passe ici sans etre vu pendant plusieurs sessions :
# un commentaire se fermait AVANT son dernier paragraphe, qui se
# retrouvait en CSS invalide, suivi d'une fermeture orpheline. Et un
# selecteur `.js` trainait, orphelin, devant une banniere de
# commentaire.
#
# Le navigateur ne dit rien : il jette la regle fautive et continue. La
# page reste donc presentable, et le defaut survit - celui-ci a ete
# publie en production.
#
# Aucun test ne lisait la feuille comme un document a part entiere. Les
# deux ci-dessous le font.
# ==========================================================================

def test_les_commentaires_de_la_feuille_sont_tous_fermes():
    """
    UN COMMENTAIRE QUI SE FERME TROP TOT EST INVISIBLE A L'OEIL.

    Le texte qui suit devient du CSS, le navigateur le jette avec la
    regle qui l'entoure, et rien ne le signale. Mesure du defaut trouve :
    56 ouvertures pour 57 fermetures.
    """
    f = charte.feuille()
    i, dans, ouvert_a = 0, False, None
    while i < len(f) - 1:
        if not dans and f[i:i + 2] == "/*":
            dans, ouvert_a = True, i
            i += 2
            continue
        if dans and f[i:i + 2] == "*/":
            dans = False
            i += 2
            continue
        if not dans and f[i:i + 2] == "*/":
            extrait = f[max(0, i - 120):i + 2].replace("\n", " ")
            pytest.fail(
                f"fermeture de commentaire orpheline : ...{extrait}")
        i += 1
    assert not dans, (
        f"commentaire ouvert a la position {ouvert_a} et jamais ferme : "
        f"tout le reste de la feuille est avale")


def test_aucun_selecteur_ne_reste_orphelin():
    """
    UN SELECTEUR SANS BLOC avale ce qui le suit.

    `.js` trainait devant une banniere de commentaire ; le navigateur
    cherchait alors une accolade et consommait l'`@keyframes` suivant
    pour en faire le corps de la regle. L'animation du hero disparaissait
    sans un mot.

    On retire les commentaires, puis on verifie que chaque fragment
    entre blocs ressemble bien a un selecteur et non a de la prose.

    LE CRITERE A ETE CORRIGE. Une premiere version comptait les mots et
    declarait suspect tout fragment de plus de douze : une liste de cinq
    selecteurs sur cinq lignes la faisait echouer a tort. On cherche
    desormais ce qu'un selecteur ne contient JAMAIS - apostrophe,
    guillemet, contre-apostrophe, lettre accentuee - et qui abonde dans
    une phrase francaise.
    """
    import re
    sans = re.sub(r"/\*.*?\*/", "", charte.feuille(), flags=re.S)
    interdits = "`'" + chr(171) + chr(187)
    profondeur, courant, suspects = 0, [], []
    for c in sans:
        if c == "{":
            if profondeur == 0:
                fragment = "".join(courant).strip()
                marques = [k for k in fragment
                           if k in interdits or ord(k) > 127]
                if marques:
                    suspects.append(
                        f"{fragment[:70]!r} contient {marques[:4]}")
                # UNE AT-REGLE NE SE PRECEDE PAS D'UN SELECTEUR. Si un
                # `@media` ou un `@keyframes` traine derriere autre
                # chose, c'est qu'un selecteur orphelin l'a avale - le
                # cas exact du `.js` reste devant la banniere du hero.
                elif "@" in fragment and not fragment.startswith("@"):
                    avant = fragment[:fragment.index("@")].strip()
                    if avant:
                        suspects.append(
                            f"{avant[:50]!r} precede l'at-regle "
                            f"{fragment[fragment.index('@'):][:30]!r}")
                courant = []
            profondeur += 1
        elif c == "}":
            profondeur -= 1
            courant = []
        elif profondeur == 0:
            courant.append(c)
    assert not suspects, (
        f"du texte hors commentaire sert de selecteur : {suspects}")


# ==========================================================================
# 10. LA PAGE D'ERREUR
# --------------------------------------------------------------------------
# Elle a ete ecrite apres un vrai incident : un envoi de formulaire a
# echoue, et le visiteur - en l'occurrence le proprietaire du site - a
# recu la page generique de Netlify. Un titre anglais, un paragraphe
# vague, un lien vers la documentation de l'hebergeur. Rien de ce qu'il
# fallait faire.
#
# Le cas qui coute cher n'est pas le lien mort : c'est l'envoi qui
# n'aboutit pas. Le prospect repart en pensant que le site est casse.
# ==========================================================================

def test_la_page_d_erreur_est_a_la_racine(site):
    """
    Netlify sert `404.html` depuis la RACINE du dossier publie, pas
    depuis un dossier de langue. Posee ailleurs, elle ne serait jamais
    servie et personne ne s'en apercevrait.
    """
    assert (site / "404.html").exists(), (
        "aucune page d'erreur : Netlify servira la sienne, en anglais")


def test_toutes_les_adresses_de_la_page_d_erreur_sont_absolues(site):
    """
    LA PROPRIETE CRITIQUE DE CE DOCUMENT.

    Il est servi pour n'importe quel chemin, y compris
    `/a/b/c/inconnu`. Un `href="index.html"` y pointerait vers
    `/a/b/c/index.html`, et un `../klastos.css` chercherait la feuille
    de style dans un dossier qui n'existe pas : la page s'afficherait
    sans style et tous ses liens seraient morts.
    """
    html = (site / "404.html").read_text(encoding="utf-8")
    relatifs = re.findall(
        r'(?:href|src)="(?!https?:|/|mailto:|#|data:)([^"]+)"', html)
    assert not relatifs, (
        f"adresses relatives dans la page d'erreur : {relatifs}")


def test_la_page_d_erreur_parle_les_deux_langues(site):
    """
    On ne peut pas deviner la langue d'un visiteur a partir d'une
    adresse qui n'existe pas. Les deux versions coexistent donc sur le
    meme document.
    """
    html = _lisible((site / "404.html").read_text(encoding="utf-8"))
    for langue in contenu.LANGUES:
        attendu = contenu.t("err.h1", langue)
        assert attendu in html, (
            f"la page d'erreur ne dit rien en {langue}")


def test_la_page_d_erreur_nomme_le_remede(site):
    """
    La discipline du projet : un refus nomme ce qu'il faut faire. Ici le
    remede est l'adresse de courriel, qui ne depend d'aucun formulaire
    ni d'aucun reglage d'hebergeur.
    """
    html = _lisible((site / "404.html").read_text(encoding="utf-8"))
    assert construire.COURRIEL in html, (
        "la page d'erreur ne donne pas d'adresse ou ecrire")
    for langue in contenu.LANGUES:
        assert contenu.t("err.envoi.titre", langue) in html, (
            f"le cas de l'envoi echoue n'est pas traite en {langue}")


def test_la_page_d_erreur_n_est_pas_indexee(site):
    """Une page d'erreur dans les resultats de recherche est du bruit
    pour qui cherche KLASTOS21."""
    html = (site / "404.html").read_text(encoding="utf-8")
    assert 'content="noindex, follow"' in html


def test_la_page_d_erreur_ne_figure_pas_au_plan_du_site(site):
    plan = (site / "sitemap.xml").read_text(encoding="utf-8")
    assert "404" not in plan
