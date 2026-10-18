"""Tests de klastos/charts.py.

Un graphique est un engagement comme un autre. Celui-ci en porte un seul,
mais il est central :

    UN GRAPHIQUE NE MONTRE JAMAIS CE QUE LA DONNEE NE PORTE PAS.

Le camembert de phases a valeur unique sommant a 100 % est le visuel que
tout le monde attend, et il est faux sur une black mass. Deux assemblages
differant de 2,86 points sur le PVDF produisent le meme bulletin a 3e-15
point pres : afficher la part de l'un revient a presenter un arbitrage
numerique comme une mesure. Ces tests l'interdisent.
"""

import datetime as dt
import pathlib

import numpy as np
import pytest

from klastos import charts
from klastos.service import Demande, analyser

RACINE = pathlib.Path(__file__).resolve().parent.parent
BULLETIN = RACINE / "data" / "exemples" / "bulletin_coherent.csv"
AUJ = dt.date(2026, 9, 7)


@pytest.fixture(autouse=True)
def _bulletin_present():
    if not BULLETIN.exists():
        pytest.skip("bulletin d'exemple absent")


@pytest.fixture(scope="module")
def analyse():
    return analyser(Demande(bulletin=BULLETIN,
                            provenance="vehicule_electrique", attestee=True,
                            tirages=30, graine=0, emis_le=AUJ))


# ==========================================================================
# 1. Le camembert ne ment pas
# ==========================================================================

def test_le_camembert_boucle_exactement_a_cent(analyse):
    """
    Pas 100,01 %. Melanger teneurs lues et masse reconstituee donnait un
    total faux, qu'il aurait fallu corriger en trichant sur la part grise.
    """
    df, _ = charts.donnees_composition(analyse)
    assert df["valeur"].sum() == pytest.approx(1.0, abs=1e-9)


def test_le_camembert_porte_les_elements_quand_les_phases_sont_ouvertes(analyse):
    """
    LE VERROU DU MODULE. Tant qu'une phase est non identifiable, le
    camembert ne peut pas porter les phases.
    """
    from klastos.identifiability import is_identifiable

    df, mode = charts.donnees_composition(analyse)
    assert mode == "elements"
    assert (df["famille"] == "phase").sum() == 0

    for r in analyse.incertitude.results:
        if r.block in ("phase", "ventilation") and not r.identifiable:
            assert r.label not in set(df["part"]), r.label
            break
    else:
        pytest.skip("toutes les phases sont fermes sur ce lot")


def test_la_masse_non_expliquee_est_une_part_a_part_entiere(analyse):
    """
    Elle n'est pas absorbee dans les autres parts : c'est un diagnostic,
    pas un reste de calcul a cacher.
    """
    df, _ = charts.donnees_composition(analyse)
    ligne = df[df["famille"] == "inexplique"]
    assert len(ligne) == 1
    central = analyse.incertitude.meta["central"]
    assert float(ligne["valeur"].iloc[0]) == pytest.approx(
        central.unexplained_mass, abs=1e-9)


def test_l_oxygene_predit_est_signale_comme_predit(analyse):
    df, _ = charts.donnees_composition(analyse)
    predits = df[df["famille"] == "predit"]
    assert len(predits) >= 1
    assert all("prédit" in p for p in predits["part"])


def test_les_parts_elementaires_valent_la_composition_reconstituee(analyse):
    """
    A @ x, et non les teneurs du bulletin : c'est la seule facon que la
    somme fasse exactement la masse expliquee.
    """
    from klastos.phases import stoichiometry_matrix

    central = analyse.incertitude.meta["central"]
    A, els, _ = stoichiometry_matrix(phase_keys=analyse.phases_retenues)
    ajuste = dict(zip(els, A @ central.x))

    df, _ = charts.donnees_composition(analyse)
    for _, r in df[df["famille"] == "element"].iterrows():
        assert r["valeur"] == pytest.approx(ajuste[r["part"]], abs=1e-12)


def test_le_camembert_bascule_sur_les_phases_quand_elles_sont_fermes(analyse):
    """
    La contrepartie de l'interdiction. Le jour ou une quantification DRX
    rend les phases fermes, le camembert doit porter la mineralogie - sans
    qu'on touche au code.
    """
    import copy

    faux = copy.copy(analyse)
    faux.incertitude = copy.copy(analyse.incertitude)
    faux.incertitude.results = []
    for r in analyse.incertitude.results:
        c = copy.copy(r)
        if c.block in ("phase", "ventilation"):
            c.identifiable = True
        faux.incertitude.results.append(c)

    df, mode = charts.donnees_composition(faux)
    assert mode == "phases"
    assert (df["famille"] == "phase").sum() >= 1
    assert df["valeur"].sum() == pytest.approx(1.0, abs=1e-9)


# ==========================================================================
# 2. Les domaines compatibles
# ==========================================================================

def test_chaque_phase_porte_ses_deux_bornes(analyse):
    df = charts.donnees_domaines(analyse)
    assert len(df) >= 1
    assert (df["haut"] >= df["bas"] - 1e-9).all()


def test_le_statut_suit_l_identifiabilite(analyse):
    from klastos.uncertainty import WELL_DETERMINED_WIDTH

    for r in analyse.incertitude.results:
        if r.block not in ("phase", "ventilation"):
            continue
        s = charts._statut(r)
        if not r.identifiable:
            assert s == "ouvert"
        elif r.total_upper - r.total_lower <= WELL_DETERMINED_WIDTH:
            assert s == "ferme"
        else:
            assert s == "ferme_large"


def test_une_couleur_par_statut_et_pas_de_doublon():
    """La couleur porte un sens : deux statuts ne peuvent pas la partager."""
    valeurs = list(charts.COULEUR_STATUT.values())
    assert len(set(valeurs)) == len(valeurs)


def test_le_graphique_de_domaines_part_de_zero(analyse):
    """
    Regression. Sans domaine explicite, l'axe partait a -5 % de masse, ce
    qui n'a aucun sens pour une fraction massique.
    """
    spec = charts.barres_domaines(analyse).to_dict()
    domaines = _tous_les_domaines_x(spec)
    assert domaines, "aucune echelle x explicite"
    for d in domaines:
        assert d[0] == 0


def _tous_les_domaines_x(spec: dict) -> list:
    """Collecte les domaines de l'encodage x, a tous les niveaux."""
    out = []
    if isinstance(spec, dict):
        enc = spec.get("encoding", {})
        x = enc.get("x", {})
        dom = x.get("scale", {}).get("domain")
        if isinstance(dom, list):
            out.append(dom)
        for v in spec.values():
            out += _tous_les_domaines_x(v)
    elif isinstance(spec, list):
        for v in spec:
            out += _tous_les_domaines_x(v)
    return out


def test_les_deux_couches_partagent_le_meme_ordre(analyse):
    """
    Regression. Avec un tri pose separement sur chaque couche, les deux
    echelles de bande ne coincidaient pas : les libelles se retrouvaient
    entre deux barres.
    """
    spec = charts.barres_domaines(analyse).to_dict()
    tris = []
    for couche in spec.get("layer", []):
        tri = couche.get("encoding", {}).get("y", {}).get("sort")
        if isinstance(tri, list):
            tris.append(tuple(tri))
    assert len(tris) >= 2
    assert len(set(tris)) == 1, "les couches ne partagent pas le meme ordre"


# ==========================================================================
# 3. Bouclage
# ==========================================================================

def test_le_bouclage_est_une_barre_a_deux_parts(analyse):
    spec = charts.barre_bouclage(analyse).to_dict()
    assert "Masse non expliquée" in str(spec)


def test_la_teinte_du_bouclage_suit_le_statut(analyse):
    """Vert, ambre ou rouille : la couleur est le diagnostic."""
    spec = str(charts.barre_bouclage(analyse).to_dict())
    bouclage = analyse.incertitude.meta["closure"]
    attendue = {"ok": charts.COBALT, "alerte": charts.AMBRE,
                "rejet": charts.ROUILLE}[bouclage.status]
    assert attendue in spec


# ==========================================================================
# 4. Scenario
# ==========================================================================

def test_le_scenario_se_dessine_quand_il_existe(analyse):
    graphe = charts.barres_scenario(analyse)
    assert graphe is not None
    spec = graphe.to_dict()
    tris = [c.get("encoding", {}).get("y", {}).get("sort")
            for c in spec.get("layer", [])]
    tris = [tuple(t) for t in tris if isinstance(t, list)]
    assert len(set(tris)) == 1, "les deux couches doivent partager l'ordre"


def test_pas_de_scenario_quand_l_oxygene_est_dose(tmp_path):
    p = tmp_path / "avec_o.csv"
    p.write_text(
        "Ni (%),Co (%),Li (%),Mn (%),Cu (%),Al (%),Fe (%),P (%),"
        "C total (%),F (%),O (%)\n"
        "16.20,4.01,3.28,3.74,2.70,3.20,3.586,1.89,29.79,1.70,16.60\n",
        encoding="utf-8")
    a = analyser(Demande(bulletin=p, provenance="vehicule_electrique",
                         attestee=True, tirages=20, emis_le=AUJ))
    assert charts.barres_scenario(a) is None


# ==========================================================================
# 5. Independance
# ==========================================================================

def test_les_graphiques_n_importent_pas_streamlit():
    """
    charts.py doit pouvoir servir ailleurs - un rapport, un notebook - sans
    trainer l'interface derriere lui.
    """
    import ast

    arbre = ast.parse(
        (RACINE / "klastos" / "charts.py").read_text(encoding="utf-8"))
    for n in arbre.body:
        noms = set()
        if isinstance(n, ast.Import):
            noms = {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            noms = {n.module.split(".")[0]}
        assert "streamlit" not in noms


def test_le_theme_ne_contient_aucun_chiffre_metier():
    """
    theme.py est de l'habillage. Un seuil ou une teneur qui s'y glisserait
    echapperait a tous les tests du protocole.
    """
    import re

    src = (RACINE / "klastos" / "theme.py").read_text(encoding="utf-8")
    src = re.sub(r"#.*", "", src)                      # commentaires
    src = re.sub(r'"""[\s\S]*?"""', "", src)           # docstrings
    src = re.sub(r"#[0-9A-Fa-f]{3,8}\b", "", src)      # couleurs
    src = re.sub(r"\d+(\.\d+)?(px|pt|mm|rem|em|%|deg|s)", "", src)
    src = re.sub(r"[\d.]+(?=\s*[,)])", "", src)        # rgba(...)
    for motif in (r"\b0\.\d+\b", r"\b\d{2,}\.\d+\b"):
        assert not re.search(motif, src), re.search(motif, src).group()


def test_la_palette_est_partagee_avec_le_rapport_imprime():
    """L'ecran et le PDF doivent parler le meme langage visuel."""
    from klastos import render_html, theme

    assert charts.COBALT.lower() in render_html.CSS.lower()
    assert charts.AMBRE.lower() in render_html.CSS.lower()
    assert charts.ROUILLE.lower() in render_html.CSS.lower()
    assert theme.COBALT == charts.COBALT