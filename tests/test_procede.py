"""
LE SCHEMA DU PROCEDE.

POURQUOI CE FICHIER EXISTE
--------------------------
Le schema ne decore pas : il repond a la question que pose tout
interlocuteur au bout de deux minutes - « vous faites quoi, exactement,
dans cette chaine ? »

La reponse est une FRONTIERE. KLASTOS21 ne broie pas, ne dose pas, ne
raffine pas ; il entre apres le laboratoire, sur un bulletin. Cette
frontiere explique le reste du site : l'attestation de provenance, parce
que l'outil ne peut pas regarder la poudre ; l'indetermination, parce
qu'un bulletin donne des elements quand un acheteur paie des phases ; la
fourchette, parce que c'est ce que la mesure porte.

CE QUE CES TESTS GARDENT
------------------------
  1. la frontiere elle-meme, qui est le sens du dessin : trois etapes au
     lot, une au laboratoire, deux a nous - et pas l'inverse ;
  2. que le schema reste SANS DEPENDANCE, comme le graphique des
     cotations : ni requete, ni bibliotheque, ni couleur en dur ;
  3. que les libelles tiennent dans leur cellule, en francais comme en
     anglais - le SVG ne sait pas revenir a la ligne tout seul.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "site"))

import contenu                                            # noqa: E402
import procede                                            # noqa: E402

LANGUES = ("fr", "en")


@pytest.fixture(scope="module", params=LANGUES)
def svg(request):
    return procede.schema(request.param, contenu.t)


# ==========================================================================
# 1. La frontiere, qui est le sens du dessin
# ==========================================================================

def test_les_trois_zones_couvrent_exactement_les_six_etapes():
    """
    Si les comptes divergent, une bande de zone chevauche une cellule
    qui ne lui appartient pas, et le schema raconte une autre histoire
    que celle qu'on croit.
    """
    assert sum(n for _, n in procede.ZONES) == len(procede.ETAPES)
    noms_zones = [z for z, _ in procede.ZONES]
    attendu = []
    for zone, n in procede.ZONES:
        attendu += [zone] * n
    assert [z for _, _, z in procede.ETAPES] == attendu, (
        "l'ordre des etapes ne suit plus l'ordre des zones")
    assert noms_zones == ["lot", "labo", "nous"]


def test_klastos_n_occupe_que_les_deux_dernieres_etapes():
    """
    LE POINT DU SCHEMA. L'outil n'entre qu'apres le laboratoire. Si une
    etape amont basculait dans la zone « nous », le dessin promettrait
    un service que le produit ne rend pas - broyage, dosage ou
    raffinage.
    """
    notres = [cle for cle, _, zone in procede.ETAPES if zone == "nous"]
    assert notres == ["deconvolution", "valeur"], (
        f"KLASTOS21 revendique desormais {notres}")


def test_le_laboratoire_tient_le_bulletin_et_rien_d_autre():
    labo = [cle for cle, _, zone in procede.ETAPES if zone == "labo"]
    assert labo == ["bulletin"]


def test_la_derniere_etape_montre_une_fourchette_et_non_un_prix():
    """
    La signature du produit. Un glyphe de prix - un billet, une piece -
    contredirait tout le reste du site.
    """
    cle, glyphe, _ = procede.ETAPES[-1]
    assert cle == "valeur" and glyphe == "intervalle"


@pytest.mark.parametrize("langue", LANGUES)
def test_chaque_zone_porte_un_libelle_traduit(langue):
    for zone, _ in procede.ZONES:
        texte = contenu.t(f"proc.zone.{zone}", langue)
        assert texte and not texte.startswith("proc."), zone


# ==========================================================================
# 2. Le trace reste sans dependance
# ==========================================================================

def test_six_cellules_cinq_fleches_trois_bandes(svg):
    assert svg.count('class="proc-cadre') == 6
    assert svg.count('class="proc-fleche') == 5
    assert svg.count('class="proc-bande') == 3


def test_le_schema_ne_sort_pas_chercher_de_ressource(svg):
    for interdit in ("http://", "https://", "<script", "<image", "url("):
        assert interdit not in svg, f"le schema contient {interdit!r}"


def test_aucune_couleur_n_est_ecrite_en_dur(svg):
    """
    La discipline du projet : la palette passe par les jetons. Un
    `stroke="#B4632B"` survivrait a un changement de charte et jurerait.
    """
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", svg)
    for attribut in ('stroke="', 'fill="'):
        assert attribut not in svg, (
            f"le schema peint via {attribut} au lieu des classes")


def test_le_schema_est_fluide(svg):
    assert "viewBox=" in svg
    assert not re.search(r'<svg[^>]*\swidth="\d', svg)


@pytest.mark.parametrize("langue", LANGUES)
def test_le_schema_porte_une_description_pour_les_lecteurs_d_ecran(langue):
    s = procede.schema(langue, contenu.t)
    assert 'role="img"' in s
    label = re.search(r'aria-label="([^"]+)"', s)
    assert label and len(label.group(1)) > 60, (
        "la description du schema est absente ou trop courte : un lecteur "
        "d'ecran ne saurait pas ce qu'il manque")
    assert not label.group(1).startswith("proc.")


def test_un_glyphe_inconnu_echoue_fort():
    """Un glyphe manquant doit faire echouer la construction, pas
    produire une cellule vide que personne ne remarque."""
    with pytest.raises(ValueError, match="Glyphe inconnu"):
        procede._glyphe("licorne", 0, 0, "nous")


# ==========================================================================
# 3. Les libelles tiennent dans leur cellule
# ==========================================================================

@pytest.mark.parametrize("langue", LANGUES)
@pytest.mark.parametrize("cle", [c for c, _, _ in procede.ETAPES])
def test_aucun_libelle_ne_deborde_de_sa_cellule(cle, langue):
    """
    LE SVG NE REVIENT PAS A LA LIGNE TOUT SEUL. Un libelle trop long
    sort de sa cellule et chevauche la suivante - et il le ferait
    differemment en francais et en anglais, donc sans qu'on le voie
    forcement en relisant une seule langue.
    """
    nom = contenu.t(f"proc.{cle}.nom", langue)
    detail = contenu.t(f"proc.{cle}.detail", langue)
    for texte, par_ligne, maxi in ((nom, 16, 2), (detail, 21, 3)):
        lignes = procede._lignes(texte, par_ligne, maxi)
        assert len(lignes) <= maxi, (
            f"{cle} [{langue}] : {len(lignes)} lignes pour {texte!r}")
        for ligne in lignes:
            assert len(ligne) <= par_ligne + 6, (
                f"{cle} [{langue}] : la ligne {ligne!r} depasse la "
                f"largeur de cellule")


def test_la_coupure_ne_perd_aucun_mot():
    """Une coupure qui tronque serait pire qu'une coupure laide : le
    libelle mentirait par omission."""
    texte = "Decharge, demantelement, separation et criblage fin"
    assert " ".join(procede._lignes(texte, 18, 3)).split() == texte.split()


def test_un_mot_plus_long_que_la_ligne_ne_boucle_pas():
    """Garde-fou de terminaison : un mot indivisible ne doit pas
    provoquer une ligne vide a l'infini."""
    lignes = procede._lignes("anticonstitutionnellement", 8, 3)
    assert lignes == ["anticonstitutionnellement"]


@pytest.mark.parametrize("langue", LANGUES)
def test_les_libelles_sont_bien_dans_le_svg(langue):
    """
    LA LANGUE EST PASSEE, PAS DEVINEE. Une premiere version la
    reconnaissait a la presence du mot « Batteries » - qui s'ecrit de la
    meme facon dans les deux langues. Le test comparait donc le schema
    anglais au catalogue francais.
    """
    s = procede.schema(langue, contenu.t)
    for cle, _, _ in procede.ETAPES:
        mot = contenu.t(f"proc.{cle}.nom", langue).split()[0]
        assert mot in s, (
            f"{cle} [{langue}] : le nom {mot!r} manque au schema")
