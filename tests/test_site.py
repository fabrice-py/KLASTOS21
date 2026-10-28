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

def test_la_generation_ecrit_les_quatorze_pages(site):
    """
    Les pages et la feuille de style. Les declinaisons de la marque sont
    comptees a part, par le test suivant : melanger les deux rendrait ce
    test illisible a chaque ajout de favicon.
    """
    attendus = {"klastos.css", "index.html"}
    attendus |= {f"{lg}/{p}.html"
                 for lg in contenu.LANGUES for p in contenu.PAGES}
    presents = {
        str(c.relative_to(site)).replace("\\", "/")
        for c in site.rglob("*")
        if c.is_file() and c.parent.name != "marque"
    }
    assert presents == attendus, (
        f"manquants : {sorted(attendus - presents)} / "
        f"en trop : {sorted(presents - attendus)}")


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
    nom = contenu.t("marque.nom")
    for langue, page, html in _pages(site):
        debut = html.index('<a class="marque"')
        fin = html.index("</a>", debut)
        marque = re.sub(r"<[^>]+>", "", html[debut:fin])
        assert marque.strip() == nom, (
            f"{langue}/{page} : logotype « {marque.strip()} » "
            f"au lieu de « {nom} »")


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
