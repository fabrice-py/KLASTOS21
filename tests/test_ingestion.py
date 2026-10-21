"""Tests de klastos/ingestion.py.

Les cinq pieges d'un bulletin reel sont chacun couverts :
  1. base seche ou humide      -> colonne humidite ignoree et signalee
  2. unites melangees          -> % et mg/kg dans le meme tableau
  3. valeurs censurees         -> "< 0,05" selon trois traitements declares
  4. oxydes                    -> Li2O converti, facteur journalise
  5. oxygene jamais dose       -> non invente, signale, predit ensuite
"""

import numpy as np
import pytest

from klastos.elements import ELEMENTS
from klastos import i18n
from klastos.ingestion import (CENSORED_MODES, CONCENTRATION_UNITS,
                               DEFAULT_CENSORED_MODE, OXIDES, IngestionError,
                               parse_column, parse_value, read_bulletin)

BULLETIN = {
    "Ni (%)": "18.24",
    "Co (%)": "5.81",
    "Li2O (%)": "8.44",
    "Mn (%)": "5.74",
    "Cu (ppm)": "27100",
    "Al (%)": "3.38",
    "Fe (mg/kg)": "4290",
    "P (%)": "2.09",
    "C total (%)": "28.9",
    "F (%)": "<0.05",
    "Echantillon": "BM-2026-0142",
    "Humidite (%)": "2.8",
}


# ==========================================================================
# 1. Facteurs de conversion des oxydes
# ==========================================================================

@pytest.mark.parametrize("formule,attendu", [
    ("Li2O", 0.4645), ("NiO", 0.7858), ("CoO", 0.7865), ("Co3O4", 0.7342),
    ("MnO", 0.7745), ("MnO2", 0.6319), ("Al2O3", 0.5293), ("Fe2O3", 0.6994),
    ("FeO", 0.7773), ("P2O5", 0.4364), ("CuO", 0.7989),
])
def test_facteurs_d_oxydes_conformes_a_la_geochimie(formule, attendu):
    assert OXIDES[formule].factor == pytest.approx(attendu, abs=1e-4)


def test_confondre_li2o_et_li_fausse_de_215_pourcent():
    """L'erreur que le module existe pour empecher."""
    assert 1.0 / OXIDES["Li2O"].factor == pytest.approx(2.153, abs=1e-3)


def test_tous_les_oxydes_pointent_vers_un_element_du_modele():
    for formule, ox in OXIDES.items():
        assert ox.element in ELEMENTS, formule
        assert ox.element in ox.composition, formule


# ==========================================================================
# 2. Reconnaissance des intitules
# ==========================================================================

@pytest.mark.parametrize("nom,element,unite", [
    ("Ni", "Ni", None),
    ("Ni (%)", "Ni", "%"),
    ("Cu (ppm)", "Cu", "ppm"),
    ("Fe (mg/kg)", "Fe", "mg/kg"),
    ("Nickel", "Ni", None),
    ("cobalt", "Co", None),
    ("Manganese", "Mn", None),
    ("C total (%)", "C", "%"),
    ("Carbone total", "C", None),
    ("Fluor", "F", None),
])
def test_intitules_reconnus(nom, element, unite):
    col = parse_column(nom)
    assert col.recognized, nom
    assert col.element == element
    assert col.unit == unite


def test_oxyde_reconnu_et_rattache():
    col = parse_column("Li2O (%)")
    assert col.recognized
    assert col.oxide == "Li2O"
    assert col.element == "Li"


def test_intitule_inconnu_jamais_devine():
    for nom in ("Echantillon", "Densite", "Granulometrie D50", "Observations"):
        col = parse_column(nom)
        assert not col.recognized, nom
        assert col.element is None
        assert col.reason


def test_intitule_vide_rejete():
    assert parse_column("   ").recognized is False


# ==========================================================================
# 3. Lecture des valeurs
# ==========================================================================

@pytest.mark.parametrize("brut,attendu", [
    ("18.24", 18.24), ("18,24", 18.24), ("27 100", 27100.0),
    ("4290", 4290.0), ("0.05", 0.05),
])
def test_valeurs_numeriques(brut, attendu):
    v, seuil = parse_value(brut)
    assert v == pytest.approx(attendu)
    assert seuil is None


@pytest.mark.parametrize("brut", ["nd", "N.D.", "n/a", "-", "trace", "", "BDL"])
def test_valeurs_non_quantifiees(brut):
    v, seuil = parse_value(brut)
    assert v is None and seuil is None


@pytest.mark.parametrize("brut,seuil", [
    ("<0.05", 0.05), ("< 0,05", 0.05), ("≤ 0.01", 0.01),
])
def test_valeurs_censurees_avec_seuil(brut, seuil):
    v, s = parse_value(brut)
    assert v is None
    assert s == pytest.approx(seuil)


def test_valeur_illisible_rejetee():
    with pytest.raises(IngestionError, match="illisible"):
        parse_value("environ vingt pourcents")


# ==========================================================================
# 4. Lecture complete
# ==========================================================================

@pytest.fixture
def lu():
    return read_bulletin(rows=BULLETIN)


def test_conversion_des_unites(lu):
    """Le facteur 10 000 entre % et mg/kg doit etre applique."""
    assert lu.values["Ni"] == pytest.approx(0.1824)
    assert lu.values["Cu"] == pytest.approx(0.0271)    # 27 100 ppm
    assert lu.values["Fe"] == pytest.approx(0.00429)   # 4 290 mg/kg


def test_conversion_de_l_oxyde(lu):
    """8,44 % de Li2O donnent 3,92 % de Li, pas 8,44 %."""
    assert lu.values["Li"] == pytest.approx(0.0844 * OXIDES["Li2O"].factor)
    assert lu.values["Li"] == pytest.approx(0.0392, abs=1e-4)


def test_la_conversion_d_oxyde_est_journalisee(lu):
    assert any("Li2O" in j and "facteur" in j for j in lu.journal)


def test_colonnes_etrangeres_ignorees_et_signalees(lu):
    assert set(lu.ignored_columns) == {"Echantillon", "Humidite (%)"}
    assert any("Echantillon" in w for w in lu.warnings)
    assert any("Humidite" in w for w in lu.warnings)


def test_les_elements_doses_sont_en_ordre_canonique(lu):
    ordre = [e for e in ELEMENTS if e in lu.measured_elements]
    assert lu.measured_elements == ordre


def test_le_vecteur_suit_la_liste_des_elements_doses(lu):
    assert lu.b.shape[0] == len(lu.measured_elements)
    for i, e in enumerate(lu.measured_elements):
        assert lu.b[i] == pytest.approx(lu.values[e])


def test_un_bulletin_reel_ne_boucle_pas(lu):
    """Environ 29 % manquent : c'est l'oxygene, et c'est normal."""
    assert 0.65 < lu.total < 0.80
    assert lu.total == pytest.approx(0.7124, abs=1e-3)


def test_l_oxygene_n_est_jamais_invente(lu):
    assert lu.oxygen_measured is False
    assert "O" not in lu.values
    assert "O" not in lu.measured_elements
    # Par le CATALOGUE, pas en dur : le journal part dans la tracabilite du
    # rapport, donc il sort dans la langue du document. Un texte francais
    # fige ici ferait echouer le test sur un rapport anglais.
    attendu = i18n.t("journal.oxygene_absent", "fr")
    assert any(attendu == j for j in lu.journal)


def test_un_oxygene_present_est_signale_comme_suspect():
    r = read_bulletin(rows={**BULLETIN, "O (%)": "28.0"})
    assert r.oxygen_measured is True
    attendu = i18n.t("journal.oxygene_present", "fr")
    assert any(attendu == w for w in r.warnings)


# ==========================================================================
# 5. Traitement des valeurs censurees : trois modes declares
# ==========================================================================

@pytest.mark.parametrize("mode,attendu", [
    ("zero", 0.0), ("half", 0.00025), ("threshold", 0.0005),
])
def test_les_trois_modes_de_censure(mode, attendu):
    r = read_bulletin(rows=BULLETIN, censored_as=mode)
    assert r.values["F"] == pytest.approx(attendu)
    assert r.censored["F"] == pytest.approx(0.0005)


def test_le_mode_de_censure_est_journalise(lu):
    # Le fragment INVARIANT du gabarit, entre les champs de format.
    modele = i18n.CATALOGUE["journal.sous_le_seuil"]["fr"]
    fragment = modele.split("{seuil}")[0].split("}")[-1].strip()
    assert fragment
    assert any(fragment in j for j in lu.journal), fragment
    assert lu.meta["censored_as"] == DEFAULT_CENSORED_MODE


def test_le_mode_par_defaut_est_la_convention_geochimique():
    assert DEFAULT_CENSORED_MODE == "half"
    assert set(CENSORED_MODES) == {"zero", "half", "threshold"}


def test_mode_de_censure_inconnu_rejete():
    with pytest.raises(IngestionError):
        read_bulletin(rows=BULLETIN, censored_as="au_pif")


# ==========================================================================
# 6. Unite par defaut : declaree, jamais devinee
# ==========================================================================

def test_unite_non_declaree_prend_le_defaut_et_le_journalise():
    r = read_bulletin(rows={"Ni": "18.24", "Co": "5.81"})
    assert r.values["Ni"] == pytest.approx(0.1824)
    modele = i18n.CATALOGUE["journal.unite_non_declaree"]["fr"]
    fragment = modele.split("{unite}")[0].split("}")[-1].strip()
    assert fragment
    assert any(fragment in j for j in r.journal), fragment


def test_unite_par_defaut_modifiable():
    r = read_bulletin(rows={"Fe": "4290"}, default_unit="mg/kg")
    assert r.values["Fe"] == pytest.approx(0.00429)


def test_unite_par_defaut_inconnue_rejetee():
    with pytest.raises(IngestionError, match="Unite par defaut"):
        read_bulletin(rows={"Ni": "18"}, default_unit="cuillers")


def test_toutes_les_unites_declarees_sont_coherentes():
    assert CONCENTRATION_UNITS["%"] == 1e-2
    assert CONCENTRATION_UNITS["ppm"] == CONCENTRATION_UNITS["mg/kg"]
    assert CONCENTRATION_UNITS["ppm"] == CONCENTRATION_UNITS["g/t"]
    assert CONCENTRATION_UNITS["g/kg"] == 1e-3


# ==========================================================================
# 7. Garde-fous
# ==========================================================================

def test_teneur_negative_rejetee():
    with pytest.raises(IngestionError, match="negative"):
        read_bulletin(rows={"Ni (%)": "-3.0"})


def test_bulletin_sans_colonne_exploitable_rejete():
    with pytest.raises(IngestionError, match="Aucune colonne exploitable"):
        read_bulletin(rows={"Echantillon": "X", "Densite": "2.4"})


def test_path_et_rows_mutuellement_exclusifs():
    with pytest.raises(IngestionError):
        read_bulletin(path="x.csv", rows=BULLETIN)
    with pytest.raises(IngestionError):
        read_bulletin()


def test_fichier_absent_rejete(tmp_path):
    with pytest.raises(IngestionError, match="introuvable"):
        read_bulletin(tmp_path / "nexiste_pas.csv")


def test_element_renseigne_deux_fois_somme_et_signale():
    r = read_bulletin(rows={"Li (%)": "2.00", "Li2O (%)": "4.31"})
    assert r.values["Li"] == pytest.approx(0.02 + 0.0431 * OXIDES["Li2O"].factor)
    assert any("plusieurs colonnes" in w for w in r.warnings)


def test_somme_aberrante_signalee():
    """Un melange element / oxyde non declare fait deborder la somme."""
    r = read_bulletin(rows={"Ni (%)": "60", "Co (%)": "30", "C total (%)": "25"})
    assert r.total > 1.02
    # Le fragment invariant du gabarit, apres le champ de format.
    modele = i18n.CATALOGUE["journal.somme_excessive"]["fr"]
    fragment = modele.split("{total:.2f}")[-1].split("%.")[-1].strip()
    assert fragment
    assert any(fragment in w for w in r.warnings), fragment


def test_cathode_absente_signalee():
    r = read_bulletin(rows={"Cu (%)": "2.7", "Al (%)": "3.4"})
    assert any("cathode absent" in w for w in r.warnings)


# ==========================================================================
# 8. Lecture de fichier : formats large et long
# ==========================================================================

def test_format_large(tmp_path):
    f = tmp_path / "large.csv"
    f.write_text("Ni (%),Co (%),Li2O (%)\n18.24,5.81,8.44\n", encoding="utf-8")
    r = read_bulletin(f)
    assert r.values["Ni"] == pytest.approx(0.1824)
    assert r.measured_elements == ["Li", "Ni", "Co"]


def test_format_long(tmp_path):
    f = tmp_path / "long.csv"
    f.write_text("element,valeur\nNi (%),18.24\nCo (%),5.81\nLi2O (%),8.44\n",
                 encoding="utf-8")
    r = read_bulletin(f)
    assert r.values["Co"] == pytest.approx(0.0581)
    assert "element" not in str(r.ignored_columns)


def test_format_long_sans_entete(tmp_path):
    f = tmp_path / "long2.csv"
    f.write_text("Ni (%),18.24\nCo (%),5.81\nLi2O (%),8.44\n", encoding="utf-8")
    r = read_bulletin(f)
    assert len(r.measured_elements) == 3


def test_bom_utf8_tolere(tmp_path):
    f = tmp_path / "bom.csv"
    f.write_bytes("﻿Ni (%),Co (%)\n18.24,5.81\n".encode("utf-8"))
    r = read_bulletin(f)
    assert "Ni" in r.values


def test_fichier_d_une_seule_ligne_rejete(tmp_path):
    f = tmp_path / "une.csv"
    f.write_text("Ni (%),Co (%)\n", encoding="utf-8")
    with pytest.raises(IngestionError, match="deux lignes"):
        read_bulletin(f)


# ==========================================================================
# 9. Chaine complete : bulletin -> solveur
# ==========================================================================

def test_le_resultat_se_branche_sur_le_solveur(lu):
    from klastos.solver import solve

    res = solve(lu.b, elements=lu.measured_elements)
    assert res.explained_mass > 0
    assert "O" in res.predicted_unmeasured


def test_l_oxygene_est_predit_par_le_solveur(lu):
    from klastos.solver import solve

    res = solve(lu.b, elements=lu.measured_elements)
    o = res.predicted_unmeasured["O"]
    assert 0.10 < o < 0.30, "ordre de grandeur attendu pour une black mass"


def test_le_residu_discrimine_un_bulletin_incoherent():
    """
    2,09 % de phosphore sans fer ni fluor est impossible : le phosphore ne
    peut venir que du LFP (qui apporte du fer) ou du LiPF6 (qui apporte du
    fluor). Le residu doit exploser.
    """
    from klastos.solver import solve

    coherent = read_bulletin(rows={
        "Ni (%)": "16.20", "Co (%)": "4.01", "Li (%)": "3.28",
        "Mn (%)": "3.74", "Cu (%)": "2.70", "Al (%)": "3.20",
        "Fe (mg/kg)": "35860", "P (%)": "1.89", "C total (%)": "29.79",
        "F (%)": "1.70",
    })
    incoherent = read_bulletin(rows=BULLETIN)

    r_ok = solve(coherent.b, elements=coherent.measured_elements)
    r_ko = solve(incoherent.b, elements=incoherent.measured_elements)

    assert r_ok.max_element_residual < 0.001
    assert r_ko.max_element_residual > 0.01
    assert r_ko.max_element_residual > 10 * r_ok.max_element_residual