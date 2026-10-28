"""Tests de l'identite visuelle.

LE RISQUE QUE CE FICHIER SURVEILLE
-----------------------------------
Le logo fourni porte un accent ORANGE. La palette du produit, elle, est
SEMANTIQUE : le cobalt signifie « grandeur determinee », la rouille « non
identifiable », l'ambre « a elucider », le vert « bouclage conforme ». Un
client les decode comme des etats.

Si l'orange de la marque se met a colorer une donnee, il devient un
cinquieme statut que personne n'a defini, voisin de l'ambre et de la
rouille. La faute a deja ete commise une fois dans ce projet, dans l'autre
sens : la tuile « bouclage conforme » sortait en cobalt, c'est-a-dire dans
la couleur qui veut dire « determine ». Elle portait deux sens sur le meme
document.

D'ou la regle tenue ici : l'orange de la marque habille le logotype, et
rien d'autre.
"""

import pathlib
import re
import xml.etree.ElementTree as ET

import pytest

from klastos import marque, theme

RACINE = pathlib.Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# La separation marque / semantique
# --------------------------------------------------------------------------

def test_l_orange_de_la_marque_n_est_pas_une_couleur_de_la_palette():
    """
    `theme.py` porte le SENS, `marque.py` porte l'identite. Les deux ne
    doivent pas se recouper : une couleur presente dans les deux serait
    lue comme un statut sur la moitie des ecrans.
    """
    semantiques = {v.upper() for n, v in vars(theme).items()
                   if isinstance(v, str) and v.startswith("#")}
    assert marque.ORANGE_MARQUE.upper() not in semantiques, (
        "l'orange de la marque est entre dans la palette semantique : il "
        "va se mettre a signifier un etat")


def test_la_palette_semantique_ignore_le_module_de_marque():
    """
    La dependance va dans UN SEUL SENS. `marque` peut ignorer `theme` ;
    l'inverse ferait du logo une source de verite sur les statuts.
    """
    src = (RACINE / "klastos" / "theme.py").read_text(encoding="utf-8")
    assert "marque" not in src.replace("marque-", "").replace("marque ", ""), (
        "theme.py importe desormais la marque")


def test_dans_le_rapport_l_orange_n_habille_que_le_logotype():
    """
    LE TEST QUI COMPTE. On releve toutes les regles CSS qui emploient le
    jeton de marque : il ne doit y en avoir qu'une, celle du logotype.
    """
    from klastos.render_html import CSS

    regles = [bloc for bloc in CSS.split("}")
              if "var(--marque)" in bloc or marque.ORANGE_MARQUE in bloc]
    # La declaration du jeton lui-meme, plus la regle du logotype.
    selecteurs = []
    for bloc in regles:
        if "{" not in bloc:
            continue
        selecteurs.append(bloc.rsplit("\n", 1)[-1].split("{")[0].strip()
                          or bloc.split("{")[0].strip().splitlines()[-1])
    assert all(s in (":root", ".marque-21") for s in selecteurs), (
        f"l'orange de la marque colore autre chose que le logotype : "
        f"{selecteurs}")


def test_le_rapport_ne_peint_aucun_statut_en_orange():
    """Le pendant mesure, sur un document reel."""
    from klastos.render_html import CSS

    for classe in (".st-ferme", ".st-large", ".st-ouvert", ".tuile.ok",
                   ".tuile.alerte", ".tuile.rejet", ".b-ferme", ".b-ouvert"):
        if classe + " " not in CSS and classe + "{" not in CSS:
            continue
        bloc = CSS[CSS.index(classe):]
        bloc = bloc[:bloc.index("}")]
        assert "--marque" not in bloc and marque.ORANGE_MARQUE not in bloc


# --------------------------------------------------------------------------
# Le cube
# --------------------------------------------------------------------------

def test_le_cube_est_un_svg_bien_forme():
    racine = ET.fromstring(marque.cube_svg())
    assert racine.tag.endswith("svg")
    assert racine.get("role") == "img"
    assert racine.get("aria-label") == "KLASTOS21"


def test_le_cube_ne_depend_d_aucune_ressource_externe():
    """
    Le rapport est un document AUTONOME destine a l'impression. Une image
    liee s'y afficherait en cadre vide chez le client.
    """
    # `xmlns` est un IDENTIFIANT d'espace de noms, pas une adresse que le
    # rendu va chercher. Il est donc retire avant le controle, sinon le
    # test se declenche sur le SVG le plus inoffensif qui soit.
    svg = re.sub(r'xmlns="[^"]*"', "", marque.cube_svg())
    for interdit in ("http://", "https://", "<image", "url(", "xlink:href"):
        assert interdit not in svg, interdit


def test_le_cube_pese_moins_qu_un_png():
    """
    Il est redessine plutot qu'embarque : 4,8 Ko de PNG en base64 pour une
    seule taille, contre un demi-kilo-octet net a toute resolution.
    """
    assert len(marque.cube_svg()) < 1024


def test_les_trois_faces_du_cube_sont_colorables():
    """
    Sur la barre laterale sombre de l'interface, le cube doit se renverser
    : dessine avec son encre d'origine, il disparait dans le fond.
    """
    svg = marque.cube_svg(encre="#FFFFFF", accent="#123456", face="#0E1526")
    assert "#FFFFFF" in svg and "#123456" in svg and "#0E1526" in svg
    assert marque.ENCRE_MARQUE not in svg


def test_le_cube_reprend_les_couleurs_du_logo_par_defaut():
    svg = marque.cube_svg()
    assert marque.ENCRE_MARQUE in svg
    assert marque.ORANGE_MARQUE in svg


# --------------------------------------------------------------------------
# Les trois supports portent la marque
# --------------------------------------------------------------------------

def _rapport_html() -> str:
    from klastos.render_html import to_html
    from klastos.service import Demande, analyser

    a = analyser(Demande(bulletin="data/exemples/bulletin_coherent.csv",
                         provenance="vehicule_electrique", attestee=True,
                         tirages=20))
    return to_html(a.rapport)


def test_le_rapport_porte_le_cube_et_le_logotype():
    html = _rapport_html()
    assert '<svg' in html and 'aria-label="KLASTOS21"' in html
    assert 'class="marque-21"' in html


@pytest.mark.parametrize("langue", ["fr", "en"])
def test_le_site_porte_le_cube_et_son_favicon(langue):
    page = RACINE / "site" / "public" / langue / "index.html"
    if not page.exists():
        pytest.skip("site non construit")
    html = page.read_text(encoding="utf-8")
    assert 'aria-label="KLASTOS21"' in html
    assert 'rel="icon"' in html and "favicon-32.png" in html


def test_l_interface_renverse_le_cube_sur_son_fond_sombre():
    """
    La barre laterale est en `theme.NUIT`. Un cube a l'encre d'origine y
    serait invisible : son encre passe au blanc et sa face droite prend la
    couleur du fond.
    """
    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    bloc = src[src.index("def _marque("):]
    bloc = bloc[:bloc.index("def _fil(")]
    assert "verrouillage_html(" in bloc
    assert 'encre="#FFFFFF"' in bloc
    assert "face=theme.NUIT" in bloc


def test_l_interface_colore_les_chiffres_a_l_orange_de_la_marque():
    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    assert "marque.ORANGE_MARQUE" in src


# --------------------------------------------------------------------------
# La signature
# --------------------------------------------------------------------------

def test_la_signature_est_celle_du_logo():
    assert marque.SIGNATURE == "WHAT THE ASSAY PROVES"


def test_la_signature_n_est_pas_traduite():
    """
    C'est une MARQUE, pas une phrase. La traduire en ferait un texte,
    c'est-a-dire autre chose - et le logo, lui, n'a qu'une version.
    """
    from klastos import i18n

    for entree in i18n.CATALOGUE.values():
        assert marque.SIGNATURE not in entree.values(), (
            "la signature est entree au catalogue : elle va se faire "
            "traduire")


def test_le_verrouillage_place_la_signature_sous_le_mot():
    """
    Sur le logo, la signature est alignee SUR LE MOT et non sous le cube.
    Les deux vivent donc dans une colonne commune, a cote du cube.
    """
    html = marque.verrouillage_html()
    bloc = html[html.index('class="marque-texte"'):]
    assert bloc.index("marque-nom") < bloc.index("marque-signature")
    # Le cube precede la colonne, il n'est pas dedans.
    assert html.index("<svg") < html.index('class="marque-texte"')


def test_la_signature_peut_etre_omise():
    """
    Un verrouillage reduit reste possible la ou la hauteur manque, sans
    qu'on ait a reconstruire le balisage a la main.
    """
    assert marque.SIGNATURE not in marque.verrouillage_html(signature=False)


@pytest.mark.parametrize("support", ["rapport", "site", "interface"])
def test_les_trois_supports_portent_la_signature(support):
    if support == "rapport":
        assert marque.SIGNATURE in _rapport_html()
    elif support == "site":
        page = RACINE / "site" / "public" / "fr" / "index.html"
        if not page.exists():
            pytest.skip("site non construit")
        html = page.read_text(encoding="utf-8")
        # En navigation ET au pied : deux occurrences au moins.
        assert html.count(marque.SIGNATURE) >= 2
    else:
        src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
        assert "verrouillage_html(" in src


def test_la_signature_ne_remplace_pas_le_descriptif_d_activite():
    """
    Les deux coexistent et ne disent pas la meme chose : la signature est
    une devise, le descriptif dit le metier - et lui est traduit. Les
    confondre priverait le lecteur francais de la seule des deux qui soit
    dans sa langue.
    """
    from klastos import i18n

    html = _rapport_html()
    assert marque.SIGNATURE in html
    assert i18n.t("rapport.doc.soustitre", "fr") in html


# --------------------------------------------------------------------------
# Les declinaisons matricielles
# --------------------------------------------------------------------------

def test_les_declinaisons_du_logo_sont_versionnees():
    """
    Tout support ne sait pas lire un SVG : un favicon de navigateur
    ancien, une signature de courriel, une plaquette.
    """
    dossier = RACINE / "site" / "marque"
    attendus = ("klastos21_logo.png", "klastos21_logo@2x.png",
                "klastos21_marque.png", "favicon-32.png", "favicon-180.png")
    manquants = [n for n in attendus if not (dossier / n).exists()]
    assert not manquants, f"declinaisons absentes : {manquants}"


def test_aucun_fichier_d_essai_ne_traine_dans_les_declinaisons():
    dossier = RACINE / "site" / "marque"
    assert not list(dossier.glob("_essai_*"))
