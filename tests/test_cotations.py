"""
LE GRAPHIQUE DES COTATIONS.

POURQUOI CE FICHIER EXISTE
--------------------------
Le site demandait une illustration de la volatilite des metaux critiques.
Une image de stock aurait decore ; ce graphique DEMONTRE, parce qu'il est
tire de l'extrait USGS embarque dans le depot et qu'il porte sa source.

Il argumente surtout le produit. Le verrou de sept jours du moteur parait
severe tant qu'on n'a pas vu le carbonate de lithium passer de 11 700 a
63 700 dollars la tonne en un an, puis redescendre a 9 000 quatre ans
plus tard.

CE QUE CES TESTS GARDENT
------------------------
  1. que les chiffres dessines soient CEUX DE LA SOURCE - un graphique
     faux est pire qu'un graphique absent, parce qu'il se cite ;
  2. qu'une seule cotation soit retenue par metal : l'USGS en publie
     plusieurs, et « la premiere trouvee » donnerait un trace qui change
     au gre de l'ordre des lignes du fichier ;
  3. que le trace reste SANS DEPENDANCE : ni requete, ni bibliotheque,
     ni hexadecimal en dur ;
  4. que les quatre etiquettes restent lisibles, c'est-a-dire ecartees.
"""

from __future__ import annotations

import pathlib
import re

import pytest

import sys

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "site"))

import contenu                                            # noqa: E402
import cotations                                          # noqa: E402

#: Les chiffres de l'USGS, recopies a la main depuis l'extrait. Ils sont
#: la pour etre COMPARES a ce que le module lit : si les deux divergent,
#: soit la source a change, soit le filtre s'est trompe de serie.
ATTENDUS = {
    "Lithium": {"unite": "dollars per metric ton",
                "valeurs": [11700, 63700, 39000, 11800, 9000]},
    "Cobalt": {"unite": "dollars per pound",
               "valeurs": [23.24, 28.84, 15.33, 11.79, 15.00]},
    "Nickel": {"unite": "dollars per metric ton",
               "valeurs": [18476, 25815, 21495, 16812, 15000]},
    "Copper": {"unite": "cents per pound",
               "valeurs": [422.0, 399.9, 384.9, 415.0, 440.0]},
}


@pytest.fixture(scope="module")
def series():
    return cotations.lire_series()


# ==========================================================================
# 1. Les chiffres dessines sont ceux de la source
# ==========================================================================

@pytest.mark.parametrize("metal", sorted(ATTENDUS))
def test_les_valeurs_lues_sont_celles_de_l_usgs(metal, series):
    """
    Un graphique faux se cite et se propage. Celui-ci se verifie.
    """
    lues = series[metal]["valeurs"]
    attendues = ATTENDUS[metal]["valeurs"]
    assert len(lues) == len(attendues), (
        f"{metal} : {len(lues)} annees lues, {len(attendues)} attendues")
    for annee, lue, att in zip(series[metal]["annees"], lues, attendues):
        assert lue == pytest.approx(att, rel=0.01), (
            f"{metal} {annee} : lu {lue}, attendu {att}")


@pytest.mark.parametrize("metal", sorted(ATTENDUS))
def test_l_unite_d_origine_est_conservee(metal, series):
    """
    Le graphique affiche un indice, mais l'unite d'origine doit voyager
    avec : c'est elle qui rend le chiffre verifiable chez la source.
    """
    assert series[metal]["unite"] == ATTENDUS[metal]["unite"]


def test_l_indexation_part_bien_de_cent(series):
    """La base 100 est le seul moyen de comparer des cotations qui ne
    partagent ni unite ni ordre de grandeur."""
    for metal, d in series.items():
        assert d["indice"][0] == pytest.approx(100.0), metal
        for brut, indice in zip(d["valeurs"], d["indice"]):
            assert indice == pytest.approx(brut / d["valeurs"][0] * 100.0)


def test_le_lithium_porte_bien_l_histoire_qu_on_raconte():
    """
    Le texte du site annonce « de 11 700 a 63 700 puis 9 000 ». Si la
    source change, le texte doit changer avec - et ce test le signale
    avant qu'un visiteur ne lise un chiffre faux.
    """
    d = cotations.lire_series()["Lithium"]
    assert d["valeurs"][0] == pytest.approx(11700, rel=0.01)
    assert max(d["valeurs"]) == pytest.approx(63700, rel=0.01)
    assert d["valeurs"][-1] == pytest.approx(9000, rel=0.01)
    assert max(d["indice"]) > 500, (
        "le pic du lithium est passe sous 5 fois la base : le chapeau du "
        "site, qui parle d'un facteur 5,4, devient faux")


# ==========================================================================
# 2. Une seule cotation par metal
# ==========================================================================

def test_chaque_metal_resout_vers_une_seule_cotation(series):
    """
    L'USGS publie plusieurs cotations pour un meme metal - cobalt LME et
    spot americain, cuivre COMEX, LME et producteur. Retenir « la
    premiere trouvee » donnerait un trace qui change au gre de l'ordre
    des lignes.
    """
    intitules = {m: d["detail"] for m, d in series.items()}
    assert len(set(intitules.values())) == len(intitules), (
        f"deux metaux partagent la meme cotation : {intitules}")
    for metal, detail in intitules.items():
        assert detail, f"{metal} : cotation sans intitule"


def test_un_filtre_ambigu_echoue_plutot_que_de_choisir(tmp_path):
    """
    Si le filtre laisse passer deux cotations, le module doit REFUSER.
    Choisir silencieusement melangerait deux series sans le dire.
    """
    lignes = (RACINE / "data" / "exemples" / "usgs_mcs2026_extrait.csv"
              ).read_text(encoding=cotations.ENCODAGE_SOURCE)
    faux = tmp_path / "ambigu.csv"
    faux.write_text(lignes, encoding=cotations.ENCODAGE_SOURCE)

    # Un filtre volontairement trop large sur le cuivre : trois cotations
    # partagent l'unite « cents per pound ».
    ancien = cotations.SERIES
    cotations.SERIES = tuple(
        (m, "" if m == "Copper" else f, u, j) for m, f, u, j in ancien)
    try:
        with pytest.raises(cotations.SourceCotationsIntrouvable,
                           match="ambigue"):
            cotations.lire_series(faux)
    finally:
        cotations.SERIES = ancien


def test_une_source_absente_echoue_fort(tmp_path):
    """Le graphique ne s'invente pas. Mieux vaut un echec de
    construction qu'une page avec un cadre vide."""
    with pytest.raises(cotations.SourceCotationsIntrouvable, match="absent"):
        cotations.lire_series(tmp_path / "nexiste_pas.csv")


# ==========================================================================
# 3. Le trace reste sans dependance
# ==========================================================================

@pytest.fixture(scope="module")
def svg(series):
    return cotations.graphique(series, "fr", contenu.t)


def test_le_trace_ne_sort_pas_chercher_de_ressource(svg):
    """
    Le site est un dossier de fichiers que l'on doit pouvoir lire hors
    ligne. Une bibliotheque de graphiques ou une image distante le
    casserait, et ajouterait une dependance a surveiller.
    """
    for interdit in ("http://", "https://", "<script", "<image", "url("):
        assert interdit not in svg, (
            f"le graphique contient {interdit!r} : il n'est plus "
            f"autonome")


def test_aucune_couleur_n_est_ecrite_en_dur(svg):
    """
    La discipline du projet : les couleurs viennent des jetons. Un
    hexadecimal en dur survivrait a un changement de palette et
    jurerait.
    """
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", svg), (
        "le graphique porte une couleur en dur")
    for attribut in ("stroke=", "fill="):
        assert attribut not in svg, (
            f"le graphique peint via l'attribut {attribut} au lieu des "
            f"classes : la palette ne le suivrait plus")


def test_les_quatre_series_sont_tracees(svg, series):
    assert svg.count('class="cot-trace') == len(series)
    for metal in series:
        attendu = contenu.t(f"cot.{metal.lower()}", "fr")
        assert f">{attendu}</text>" in svg, (
            f"{metal} : l'etiquette {attendu!r} manque au trace")


@pytest.mark.parametrize("langue", ["fr", "en"])
def test_le_trace_porte_une_description_pour_les_lecteurs_d_ecran(langue,
                                                                  series):
    s = cotations.graphique(series, langue, contenu.t)
    assert 'role="img"' in s
    label = re.search(r'aria-label="([^"]+)"', s)
    assert label and len(label.group(1)) > 30, (
        "la description du graphique est absente ou trop courte")
    assert not label.group(1).startswith("cot."), (
        "une cle s'affiche a la place du texte")


# ==========================================================================
# 4. Les etiquettes restent lisibles
# ==========================================================================

def test_les_etiquettes_ne_se_chevauchent_pas(svg):
    """
    Les quatre series finissent entre 65 et 104 en indice, soit quelques
    unites d'ecart sur une echelle logarithmique. Posees a leur hauteur
    exacte, les quatre noms se superposaient - le defaut a ete vu a
    l'ecran avant d'etre corrige.
    """
    hauteurs = sorted(float(y) for y in
                      re.findall(r'class="cot-nom[^"]*"[^>]*y="([\d.]+)"', svg))
    assert len(hauteurs) == 4
    for haute, basse in zip(hauteurs, hauteurs[1:]):
        assert basse - haute >= 12.0, (
            f"deux etiquettes a {haute:.1f} et {basse:.1f} : elles se "
            f"chevauchent")


def test_chaque_etiquette_est_reliee_a_sa_courbe(svg):
    """
    Ecarter les etiquettes les detache de leur trace. Une amorce les
    rattache, sans quoi on ne sait plus quelle courbe porte quel nom.
    """
    assert svg.count('class="cot-amorce') == 4


def test_le_trace_est_fluide_et_non_fixe_en_pixels(svg):
    """Un graphique en largeur fixe deborderait sur telephone. Le
    `viewBox` s'etire ; la feuille de style pose `width: 100%`."""
    assert "viewBox=" in svg
    assert not re.search(r'<svg[^>]*\swidth="\d', svg), (
        "le SVG impose une largeur en dur")
