"""
LES ILLUSTRATIONS TECHNIQUES.

POURQUOI CE FICHIER EXISTE
--------------------------
Le site demandait des images de black mass et de batteries avant
broyage. Cinq banques libres ont ete fouillees - Unsplash, Pexels,
Pixabay, Wikimedia Commons, Openverse - et chaque candidat verifie un
par un :

  - les seules bonnes images sont PAYANTES, sous licence Unsplash+ ou
    Getty ;
  - les images libres montrent le MAUVAIS MATERIAU : piles alcalines
    Varta et Philips, batteries de demarrage au plomb, figurines.

La raison est structurelle : la black mass est photographiee dans des
usines privees, et personne ne place ces photos sous licence libre. On
dessine donc, et le chapeau de la section l'assume en toutes lettres.

CE QUE CES TESTS GARDENT
------------------------
  1. la REPRODUCTIBILITE du tirage : une texture retiree a chaque
     construction ferait changer le site publie sans raison, et le
     depot porterait un diff a chaque `python site/construire.py` ;
  2. la geometrie, parce que deux defauts y sont passes - le titre
     « BLACK MASS » a cheval sur le champ sombre, et les etiquettes du
     module coupees a gauche ;
  3. l'absence de dependance et de couleur en dur, comme partout
     ailleurs dans ce site.
"""

from __future__ import annotations

import gzip
import pathlib
import re
import sys

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "site"))

import contenu                                            # noqa: E402
import illustrations                                      # noqa: E402

LANGUES = ("fr", "en")


# ==========================================================================
# 1. Le tirage est reproductible
# ==========================================================================

def test_deux_constructions_donnent_le_meme_dessin():
    """
    LA PROPRIETE QUI JUSTIFIE LA GRAINE FIXE.

    Sans elle, chaque `python site/construire.py` produirait une texture
    differente : le depot porterait un diff a chaque construction, et le
    site publie ne serait jamais deux fois le meme. Impossible de
    distinguer un vrai changement d'un simple nouveau tirage.
    """
    a = illustrations.echantillon("fr", contenu.t)
    b = illustrations.echantillon("fr", contenu.t)
    assert a == b


def test_une_autre_graine_donne_un_autre_dessin():
    """
    Le pendant du test precedent. Si le tirage ne dependait pas de la
    graine, le premier test passerait pour une mauvaise raison - par
    exemple parce que la texture serait figee en dur.
    """
    champ_a = illustrations._grains(300, 160, graine=1)
    champ_b = illustrations._grains(300, 160, graine=2)
    assert champ_a != champ_b


def test_le_nombre_de_grains_est_celui_annonce():
    champ = illustrations._grains(300, 160)
    assert champ.count("<circle") == illustrations.GRAINS


def test_les_calibres_couvrent_toute_la_distribution():
    """
    Les parts doivent sommer a 1. Si elles sommaient a moins, le tirage
    tomberait dans la branche de repli et toute la queue de
    distribution serait ecrasee sur les fines, sans que rien ne le
    signale.
    """
    total = sum(part for _, _, part in illustrations.CALIBRES)
    assert total == pytest.approx(1.0, abs=1e-9)


def test_aucun_grain_ne_sort_du_champ():
    """Un grain qui deborde serait coupe par le masque, donc invisible -
    mais il alourdirait le fichier pour rien."""
    champ = illustrations._grains(300, 160)
    for cx, cy, r in re.findall(
            r'cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"', champ):
        cx, cy, r = float(cx), float(cy), float(r)
        assert -0.01 <= cx - r and cx + r <= 300.01, cx
        assert -0.01 <= cy - r and cy + r <= 160.01, cy


# ==========================================================================
# 2. La geometrie, ou deux defauts sont passes
# ==========================================================================

def test_le_titre_ne_chevauche_pas_le_champ_de_poudre():
    """
    DEFAUT VU A L'ECRAN. Le titre se posait a `ECH_CHAMP + 2`, donc a
    cheval sur le champ sombre : « BLACK MASS » etait illisible, moitie
    sur la poudre, moitie sur le blanc.
    """
    assert illustrations.ECH_TITRE > illustrations.ECH_CHAMP + 10, (
        "la ligne de base du titre est revenue dans le champ sombre")
    assert illustrations.ECH_TITRE < illustrations.ECH_H - 50, (
        "le titre est descendu sur les lignes d'etiquette")


@pytest.mark.parametrize("langue", LANGUES)
def test_les_etiquettes_du_module_tiennent_a_gauche(langue):
    """
    DEFAUT VU A L'ECRAN. Avec une marge de 74, « Collecteur Al » sortait
    du cadre par la gauche et s'affichait « ollecteur Al ». Le test
    estime la largeur du texte plutot que de la supposer.
    """
    marge = illustrations.MOD_MARGE
    for cle, _, _ in illustrations.COUCHES:
        libelle = contenu.t(cle, langue)
        largeur = len(libelle) * 6.4      # ~11,5 px en f-body
        assert largeur <= marge - 13.0, (
            f"{cle} [{langue}] : « {libelle} » mesure environ "
            f"{largeur:.0f} unites, la marge n'en offre que "
            f"{marge - 13.0:.0f}")


def test_le_module_compte_bien_cinq_couches():
    """Boitier, collecteur, cellules, collecteur, boitier. Une couche
    perdue et la vue eclatee ne raconte plus le bon objet."""
    assert len(illustrations.COUCHES) == 5
    noms = [cle for cle, _, _ in illustrations.COUCHES]
    assert noms[0].startswith("mod.boitier")
    assert noms[-1].startswith("mod.boitier")
    assert "mod.cellules" in noms


def test_les_cellules_sont_le_seul_empilement():
    """Ce sont elles qui portent la couleur de la marque, et elles
    seules : c'est de la matiere active que vient la black mass."""
    empiles = [cle for cle, _, n in illustrations.COUCHES if n > 1]
    assert empiles == ["mod.cellules"]


# ==========================================================================
# 3. Aucune dependance, aucune couleur en dur
# ==========================================================================

@pytest.fixture(params=LANGUES)
def dessins(request):
    langue = request.param
    return (illustrations.echantillon(langue, contenu.t),
            illustrations.module(langue, contenu.t),
            illustrations.apercu(langue, contenu.t))


def test_les_illustrations_ne_sortent_chercher_aucune_ressource(dessins):
    for svg in dessins:
        for interdit in ("http://", "https://", "<script", "<image"):
            if interdit in svg:
                pytest.fail(f"contient {interdit!r}")


def test_aucune_couleur_ni_opacite_en_dur(dessins):
    """
    L'opacite compte autant que la couleur : posee en attribut,
    elle echapperait au theme sombre comme a tout changement de
    palette.

    `pytest.fail` PLUTOT QU'UN `assert`, et ce n'est pas du
    style. Un assert qui echoue fait representer a pytest une
    chaine de 166 000 caracteres : le rapport se fige pendant
    des minutes. Un test qui attrape le defaut mais met dix
    minutes a le dire ne vaut guere mieux qu'un test absent -
    constate en verifiant cette mutation-la.
    """
    for svg in dessins:
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", svg)
        for attribut in ('fill="', 'stroke="', 'opacity="'):
            if attribut in svg:
                pytest.fail(
                    f"peint via l'attribut {attribut} au lieu "
                    f"des classes")


@pytest.mark.parametrize("langue", LANGUES)
def test_chaque_illustration_porte_une_description(langue):
    for fabrique in (illustrations.echantillon, illustrations.module,
                     illustrations.apercu):
        svg = fabrique(langue, contenu.t)
        assert 'role="img"' in svg
        label = re.search(r'aria-label="([^"]+)"', svg)
        assert label and len(label.group(1)) > 50, (
            f"{fabrique.__name__} : description absente ou trop courte")
        assert not label.group(1).startswith(("ech.", "mod.", "apercu."))


def test_le_poids_transfere_reste_raisonnable():
    """
    Le champ compte plus de deux mille grains, donc le SVG brut est
    lourd. Ce qui compte est le poids COMPRESSE, puisque l'hebergeur
    sert en gzip. Mesure : environ 17 Ko pour 131 bruts.
    """
    brut = illustrations.echantillon("fr", contenu.t).encode()
    compresse = len(gzip.compress(brut, 9))
    assert compresse < 40_000, (
        f"{compresse / 1024:.0f} Ko compresses : la texture a grossi, "
        f"baisser GRAINS avant d'elargir cette borne")


def test_le_masque_porte_un_identifiant_unique():
    """
    Un `clipPath` partage son identifiant avec toute la page. Deux
    illustrations posees cote a cote avec le meme id, et le masque de
    la seconde ecraserait celui de la premiere.
    """
    svg = illustrations.echantillon("fr", contenu.t)
    ids = re.findall(r'<clipPath id="([^"]+)"', svg)
    assert len(ids) == len(set(ids))
    for identifiant in ids:
        assert f'url(#{identifiant})' in svg, (
            f"le masque {identifiant} est defini mais jamais utilise")


def test_l_apercu_partage_l_echelle_de_la_figure_d_accueil():
    """
    L'apercu resume la figure d'accueil, sur la meme page. Les valeurs
    sont communes par construction (`APE_GRANDEURS`) ; l'echelle aussi
    doit l'etre, sinon le meme 12,4 % tomberait a deux endroits.
    """
    import construire
    assert illustrations.APE_AXE == construire.AXE_MAX


@pytest.mark.parametrize("langue", LANGUES)
def test_les_bandes_de_l_apercu_tiennent_dans_la_page(langue):
    svg = illustrations.apercu(langue, contenu.t)
    reperes = re.findall(
        r'class="ape-(?:bande|trait)[^"]*" x="([\d.]+)" y="[\d.]+" '
        r'width="([\d.]+)"', svg)
    assert len(reperes) == len(illustrations.APE_GRANDEURS)
    for x, largeur in reperes:
        assert illustrations.APE_MARGE - 1 <= float(x)
        assert float(x) + float(largeur) <= (
            illustrations.APE_L - illustrations.APE_MARGE + 1)
