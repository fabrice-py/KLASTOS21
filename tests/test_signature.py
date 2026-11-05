"""
LA SIGNATURE DE COURRIEL.

POURQUOI CE FICHIER EXISTE
--------------------------
Une signature n'est pas un livrable comme un autre : une fois collee
dans une messagerie, elle n'est plus mise a jour. Elle part dans chaque
courriel pendant des annees, et personne ne la relit.

Son point faible est le LOGO, servi depuis klastos21.fr. Si ce fichier
est renomme, deplace ou retire du site, toutes les signatures deja
posees affichent un carre vide - chez tous les destinataires, sans que
rien ne le signale a l'expediteur.

CE QUE CES TESTS GARDENT
------------------------
  1. que le logo cite par la signature soit bien un fichier que la
     construction du site publie ;
  2. que le style reste EN LIGNE et la mise en page en TABLEAU, faute
     de quoi la signature arrive en texte nu chez une partie des
     destinataires ;
  3. que les coordonnees soient les memes dans les deux langues : un
     numero corrige d'un cote et pas de l'autre est le genre d'erreur
     qui dure.
"""

from __future__ import annotations

import html as html_mod
import pathlib
import re
import struct
import sys

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "site"))

import construire                                         # noqa: E402

DOSSIER = RACINE / "docs" / "signature"
LANGUES = ("fr", "en")

#: Les coordonnees, declarees UNE FOIS ici. Les deux signatures doivent
#: les porter a l'identique.
TELEPHONE = "+33 6 05 74 03 74"
TELEPHONE_LIEN = "tel:+33605740374"
COURRIEL = "fabricetsamo@klastos21.fr"
NOM = "Fabrice Tsamo"


def _sans_commentaires(html: str) -> str:
    """
    Le balisage prive de ses commentaires.

    SANS CE FILTRAGE, LES TESTS SE MORDENT LA QUEUE. Le commentaire en
    tete de chaque signature explique pourquoi elle ne contient pas de
    bloc `<style>` - et contient donc le mot. Un test qui cherche
    `<style` y trouvait sa propre documentation.
    """
    return re.sub(r"<!--.*?-->", "", html, flags=re.S)


@pytest.fixture(params=LANGUES)
def signature(request):
    chemin = DOSSIER / f"signature-{request.param}.html"
    assert chemin.exists(), f"signature manquante : {chemin}"
    return request.param, _sans_commentaires(
        chemin.read_text(encoding="utf-8"))


# ==========================================================================
# 1. Le logo doit exister la ou la signature le cherche
# ==========================================================================

@pytest.fixture(scope="module")
def site_construit(tmp_path_factory):
    """Le site construit une fois, pour verifier ce qu'il PUBLIE."""
    sortie = tmp_path_factory.mktemp("site")
    construire.construire(sortie)
    return sortie


def test_le_logo_cite_est_bien_publie_par_le_site(site_construit):
    """
    LE POINT FAIBLE DE TOUTE SIGNATURE HEBERGEE.

    Une signature collee dans une messagerie ne se met plus a jour. Si
    le logo change d'adresse, elle affiche un carre vide chez tous les
    destinataires, pour toujours, et l'expediteur ne voit rien - son
    propre client garde l'image en cache.

    LE TEST INTERROGE LA CONSTRUCTION, PAS LE DEPOT. Trouver le fichier
    dans `site/marque/` ne prouve rien : la construction ne copie que
    les `*.png` de ce dossier. Un logo en SVG, ou deplace ailleurs,
    existerait dans le depot sans jamais etre publie - et toutes les
    signatures deja posees afficheraient un carre vide.
    """
    for langue in LANGUES:
        html = _sans_commentaires(
            (DOSSIER / f"signature-{langue}.html").read_text(
                encoding="utf-8"))
        adresses = re.findall(r'<img[^>]*src="([^"]+)"', html)
        assert adresses, f"signature-{langue} : aucune image"
        for adresse in adresses:
            assert adresse.startswith("https://klastos21.fr/"), (
                f"signature-{langue} : le logo n'est pas servi par le "
                f"site ({adresse})")
            relatif = adresse.removeprefix("https://klastos21.fr/")
            publie = site_construit / relatif
            assert publie.exists(), (
                f"signature-{langue} : {adresse} n'est PAS publie par la "
                f"construction du site. Les signatures deja collees "
                f"afficheront un carre vide.")
            assert publie.stat().st_size > 0, (
                f"signature-{langue} : {adresse} est publie vide")


def test_toutes_les_adresses_de_la_signature_sont_absolues(signature):
    """Une signature voyage hors du site : un chemin relatif n'y
    pointe nulle part."""
    langue, html = signature
    liens = re.findall(r'(?:href|src)="([^"]+)"', html)
    for lien in liens:
        assert lien.startswith(("https://", "mailto:", "tel:")), (
            f"signature-{langue} : adresse non absolue ({lien})")


# ==========================================================================
# 2. Ce qui la fait survivre aux clients de messagerie
# ==========================================================================

def test_le_style_est_entierement_en_ligne(signature):
    """
    Gmail supprime les blocs `<style>` a l'affichage. Une signature qui
    compte dessus arrive en texte nu, sans logo ni mise en page.
    """
    langue, html = signature
    assert "<style" not in html.lower(), (
        f"signature-{langue} : un bloc <style> sera supprime par Gmail")
    assert "<link" not in html.lower(), (
        f"signature-{langue} : une feuille externe ne sera jamais chargee")
    assert 'class="' not in html, (
        f"signature-{langue} : une classe sans feuille de style ne "
        f"peint rien")


def test_la_mise_en_page_est_un_tableau(signature):
    """
    Outlook rend le HTML avec le moteur de Word, qui ignore flexbox et
    grid. Un tableau est la seule disposition qui tienne partout.
    """
    langue, html = signature
    assert "<table" in html, f"signature-{langue} : pas de tableau"
    for interdit in ("display:flex", "display: flex",
                     "display:grid", "display: grid"):
        assert interdit not in html, (
            f"signature-{langue} : {interdit} ne sera pas rendu par "
            f"Outlook")


def test_l_image_porte_ses_dimensions_et_un_texte_de_remplacement(signature):
    """
    Beaucoup de clients bloquent les images par defaut. Sans `alt`, le
    destinataire voit un carre vide ; sans `width`/`height`, la mise en
    page saute pendant le chargement.
    """
    langue, html = signature
    img = re.search(r"<img[^>]*>", html)
    assert img, f"signature-{langue} : aucune image"
    balise = img.group(0)
    for attribut in ('alt="', 'width="', 'height="'):
        assert attribut in balise, (
            f"signature-{langue} : l'image n'a pas d'attribut {attribut}")
    alt = re.search(r'alt="([^"]*)"', balise).group(1)
    assert len(alt) > 10 and "logo" != alt.lower(), (
        f"signature-{langue} : le texte de remplacement « {alt} » ne dit "
        f"rien a qui bloque les images")


#: Ecart de rapport largeur/hauteur tolere entre le fichier logo et son
#: affichage dans la signature. A 2 pour cent, une deformation reste
#: invisible a l'oeil ; au-dela, le logo s'ecrase ou s'etire.
ECART_RAPPORT = 0.02


def test_le_logo_n_est_pas_deforme(signature):
    """
    LES DIMENSIONS ECRITES DANS LA SIGNATURE DOIVENT RESPECTER LE
    RAPPORT DU FICHIER.

    `width` et `height` sont obligatoires - sans eux la mise en page
    saute pendant le chargement - mais ils forcent aussi la forme de
    l'image. Si le logo est un jour re-exporte a un autre rapport, la
    signature l'etirera sans que rien ne le signale : elle part dans
    chaque courriel, et personne ne la relit.
    """
    langue, html = signature
    balise = re.search(r"<img[^>]*>", html).group(0)
    largeur = int(re.search(r'width="(\d+)"', balise).group(1))
    hauteur = int(re.search(r'height="(\d+)"', balise).group(1))
    adresse = re.search(r'src="([^"]+)"', balise).group(1)
    fichier = RACINE / "site" / adresse.removeprefix("https://klastos21.fr/")

    octets = fichier.read_bytes()
    assert octets[:8] == bytes((137, 80, 78, 71, 13, 10, 26, 10)), (
        f"{fichier.name} n'est pas un PNG ; cette lecture d'en-tete ne "
        f"vaut plus")
    source_l, source_h = struct.unpack(">II", octets[16:24])

    rapport_source = source_l / source_h
    rapport_affiche = largeur / hauteur
    ecart = abs(rapport_affiche - rapport_source) / rapport_source
    assert ecart <= ECART_RAPPORT, (
        f"signature-{langue} : le logo fait {source_l}x{source_h} "
        f"(rapport {rapport_source:.3f}) et s'affiche en "
        f"{largeur}x{hauteur} (rapport {rapport_affiche:.3f}), soit "
        f"{ecart:.1%} de deformation")

    assert source_l >= 2 * largeur, (
        f"signature-{langue} : le logo est servi en {source_l} px pour "
        f"un affichage a {largeur} px ; il sera flou sur ecran retina, "
        f"ou chaque pixel affiche en vaut deux")


def test_les_liens_portent_leur_couleur(signature):
    """Sans couleur en ligne, chaque client impose la sienne - en
    general un bleu qui jure avec la marque."""
    langue, html = signature
    for lien in re.findall(r"<a [^>]*>", html):
        if "<img" in html[html.index(lien):html.index(lien) + 200]:
            continue          # le lien du logo n'affiche pas de texte
        assert "color:" in lien, (
            f"signature-{langue} : un lien sans couleur ({lien[:60]})")


# ==========================================================================
# 3. Les deux langues disent la meme chose
# ==========================================================================

@pytest.mark.parametrize("valeur", [NOM, TELEPHONE, TELEPHONE_LIEN, COURRIEL])
def test_les_coordonnees_sont_identiques_dans_les_deux_langues(valeur):
    """
    Un numero corrige d'un cote et pas de l'autre est le genre d'erreur
    qui dure des annees : on ne relit jamais la signature qu'on
    n'utilise pas.
    """
    for langue in LANGUES:
        html = (DOSSIER / f"signature-{langue}.html").read_text(
            encoding="utf-8")
        assert valeur in html, (
            f"signature-{langue} : « {valeur} » absent")


def test_le_courriel_est_celui_du_domaine():
    """Une signature qui donne une adresse personnelle sur un site
    professionnel se remarque."""
    assert COURRIEL.endswith("@klastos21.fr")
    for langue in LANGUES:
        html = (DOSSIER / f"signature-{langue}.html").read_text(
            encoding="utf-8")
        assert "gmail.com" not in html, (
            f"signature-{langue} : une adresse personnelle y figure")


#: Ou doivent pointer TOUS les liens vers le site, par langue.
ACCUEIL = {
    "fr": ("https://klastos21.fr", "https://klastos21.fr/"),
    "en": ("https://klastos21.fr/en/",),
}


@pytest.mark.parametrize("langue", LANGUES)
def test_chaque_lien_renvoie_vers_le_site_de_la_bonne_langue(langue):
    """
    Un interlocuteur etranger doit atterrir sur la version qu'il peut
    lire, pas sur l'accueil francais.

    LE TEST PORTE SUR TOUS LES LIENS, PAS SUR UN SEUL. La signature
    anglaise en compte deux vers le site - celui du logo et celui de
    l'adresse. Une premiere version de ce test se contentait de
    trouver `/en/` quelque part dans le fichier : en de-localiser un
    seul des deux passait inapercu, et le destinataire qui cliquait
    sur le logo tombait sur le francais.
    """
    html = _sans_commentaires(
        (DOSSIER / f"signature-{langue}.html").read_text(encoding="utf-8"))
    liens = [lien for lien in re.findall(r'href="([^"]+)"', html)
             if lien.startswith("https://klastos21.fr")]
    assert liens, f"signature-{langue} : aucun lien vers le site"
    for lien in liens:
        assert lien in ACCUEIL[langue], (
            f"signature-{langue} : {lien} ne mene pas a l'accueil "
            f"{langue} ({' ou '.join(ACCUEIL[langue])})")


@pytest.mark.parametrize("langue", LANGUES)
def test_un_repli_en_texte_brut_accompagne_chaque_signature(langue):
    """
    Certains clients, et certains destinataires, ne lisent que du texte.
    Le repli porte les memes coordonnees, sans mise en forme.
    """
    chemin = DOSSIER / f"signature-{langue}.txt"
    assert chemin.exists(), f"repli texte manquant : {chemin}"
    texte = chemin.read_text(encoding="utf-8")
    for valeur in (NOM, TELEPHONE, COURRIEL):
        assert valeur in texte, (
            f"repli {langue} : « {valeur} » absent")
    assert "<" not in texte, "le repli texte contient du balisage"


@pytest.mark.parametrize("langue", LANGUES)
def test_la_signature_html_est_en_ascii_pur(langue):
    """
    LES ACCENTS SONT ECRITS EN ENTITES, PAS EN UTF-8. C'est une
    PRECAUTION, non la correction d'un defaut mesure : Edge decode
    correctement le fichier sans declaration d'encodage. Mais le
    LISEZMOI demande d'ouvrir la signature par double-clic, et un
    fragment HTML sans `<head>` ne peut pas porter de `<meta charset>`
    utile - le commentaire d'en-tete fait a lui seul plus de 1200
    octets, soit au-dela de la fenetre de 1024 dans laquelle les
    navigateurs cherchent cette declaration. Un navigateur qui se
    rabat sur la locale de la machine afficherait « Ingénieur », et
    c'est ce texte-la qui serait copie dans la messagerie.

    En ASCII pur, la question ne se pose plus.
    """
    octets = (DOSSIER / f"signature-{langue}.html").read_bytes()
    fautifs = [(i, o) for i, o in enumerate(octets) if o > 127]
    assert not fautifs, (
        f"signature-{langue} : {len(fautifs)} octets non ASCII, le "
        f"premier a la position {fautifs[0][0]}. Les accents doivent "
        f"etre ecrits en entites (&eacute;, &egrave;, ...).")


@pytest.mark.parametrize("langue", LANGUES)
def test_les_entites_de_la_signature_rendent_le_bon_texte(langue):
    """
    Le pendant du test precedent : l'ASCII pur ne doit pas avoir mange
    les accents. On decode les entites et on verifie le texte attendu.
    """
    attendu = {
        "fr": "Ing" + chr(233) + "nieur en minéralurgie et valorisation "
              "de mati" + chr(232) + "res premi" + chr(232) + "res",
        "en": "Mineral processing and raw materials valorisation engineer",
    }[langue]
    html = _sans_commentaires(
        (DOSSIER / f"signature-{langue}.html").read_text(encoding="utf-8"))
    texte = html_mod.unescape(re.sub(r"<[^>]+>", "", html))
    texte = " ".join(texte.split())
    assert " ".join(attendu.split()) in texte, (
        f"signature-{langue} : la qualification ne se lit pas "
        f"correctement apres decodage des entites")


def test_aucun_cadratin_dans_la_signature():
    """
    La meme regle que partout ailleurs dans ce projet : le cadratin est
    banni des textes affiches.
    """
    for fichier in DOSSIER.glob("signature-*"):
        texte = fichier.read_text(encoding="utf-8")
        assert chr(8212) not in texte, f"{fichier.name} porte un cadratin"
