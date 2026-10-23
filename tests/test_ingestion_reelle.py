"""
Ingestion des formats REELS, sur le fichier brut d'un materiau certifie.

Avant le 22 octobre 2026, le fichier brut d'OREAS etait integralement
refuse : 0 intitule reconnu sur 35, teste avec les separateurs ';' et ','.
Le refus etait propre - il listait les intitules lus - mais il etait total.

Six formes bloquaient, et elles sont toutes dans ce fichier :

    Al, Aluminium (wt.%)    symbole suivi du nom complet
    wt.%                    unite ponctuee
    ppm                     unite de trace
    < 0.050                 valeur censuree
    IND                     incertitude indeterminee
    ;                       separateur point-virgule

REGLE ABSOLUE verifiee ici : un intitule non reconnu reste REFUSE, avec la
liste des intitules lus. Mieux vaut refuser un bulletin que l'interpreter de
travers. Les 25 lignes du fichier qui designent des elements etrangers au
modele - baryum, cerium, zirconium - doivent donc rester refusees.
"""

from __future__ import annotations

import pathlib

import pytest

from klastos.ingestion import (CONCENTRATION_UNITS, IngestionError,
                               parse_column, parse_value, read_bulletin)
from klastos.service import Demande, analyser

BRUT = pathlib.Path("data/exemples/bulletin_reel_OREAS_brut.csv")

#: Les dix elements du modele presents dans le certificat, et leur teneur
#: certifiee en pourcent. Recopies du certificat, pas du code.
OREAS_PCT = {
    "Ni": 23.11, "C": 21.39, "Al": 7.46, "Co": 6.09, "Mn": 5.35,
    "Li": 4.13, "F": 2.44, "Cu": 2.34, "Fe": 1.11, "P": 0.350,
}

#: Bouclage de reference, cas NON ATTESTE - liste de phases complete. Le
#: bouclage depend de l'attestation, donc la configuration fait partie de la
#: valeur de reference.
BOUCLAGE_NON_ATTESTE_PCT = 93.95


@pytest.fixture(scope="module")
def lecture():
    return read_bulletin(BRUT, delimiter=";")


# ==========================================================================
# 1. Le fichier brut se lit directement
# ==========================================================================

def test_le_fichier_brut_existe_dans_le_depot():
    """
    Un cas de non-regression qui vit sur un bureau n'en est pas un. Le
    fichier est verse au depot avec sa note de provenance.
    """
    assert BRUT.exists(), f"{BRUT} absent"
    assert BRUT.with_name("bulletin_reel_OREAS_source.md").exists(), (
        "la note de provenance manque : un bulletin reel sans note n'est "
        "pas opposable")


def test_le_fichier_brut_donne_exactement_dix_elements(lecture):
    assert set(lecture.measured_elements) == set(OREAS_PCT), (
        f"attendu {sorted(OREAS_PCT)}, "
        f"lu {sorted(lecture.measured_elements)}")


def test_les_teneurs_lues_sont_celles_du_certificat(lecture):
    """
    Les six formes acceptees ne doivent rien deformer. Une unite mal
    appliquee se verrait ici d'un facteur 10 000.
    """
    lues = lecture.as_percent()
    for el, attendu in OREAS_PCT.items():
        assert lues[el] == pytest.approx(attendu, abs=1e-3), (
            f"{el} : lu {lues[el]}, certifie {attendu}")


def test_la_somme_du_bulletin_est_celle_du_certificat(lecture):
    assert lecture.total * 100.0 == pytest.approx(73.77, abs=0.01)


# ==========================================================================
# 2. Les six formes, une par une
# ==========================================================================

@pytest.mark.parametrize("intitule,element,unite", [
    ("Al, Aluminium (wt.%)", "Al", "wt.%"),
    ("C, Carbon (wt.%)", "C", "wt.%"),
    ("F, Fluorine (wt.%)", "F", "wt.%"),
    ("P, Phosphorus (wt.%)", "P", "wt.%"),
    ("Mn, Manganese (wt.%)", "Mn", "wt.%"),
    ("Fe, Iron (wt.%)", "Fe", "wt.%"),
])
def test_la_forme_symbole_puis_nom_est_reconnue(intitule, element, unite):
    c = parse_column(intitule)
    assert c.recognized, c.reason
    assert c.element == element
    assert c.unit == unite


@pytest.mark.parametrize("unite", ["wt.%", "wt. %", "wt%", "%", "ppm"])
def test_les_unites_du_certificat_sont_connues(unite):
    """
    `wt.%` manquait, et c'etait un blocage a lui seul : l'unite inconnue
    faisait tomber la colonne entiere.
    """
    assert unite in CONCENTRATION_UNITS, f"unite {unite!r} inconnue"


def test_l_unite_ponctuee_vaut_un_pourcent():
    """Pas seulement reconnue : convertie au bon facteur."""
    assert CONCENTRATION_UNITS["wt.%"] == CONCENTRATION_UNITS["%"]
    assert CONCENTRATION_UNITS["wt. %"] == CONCENTRATION_UNITS["%"]


def test_l_unite_ponctuee_est_extraite_de_l_intitule():
    """
    L'alternance de la regexp est ordonnee du plus long au plus court. Avec
    l'ordre inverse, `%` matcherait le `%` de `wt.%`, laisserait `wt.`
    dehors, et l'ancrage sur la parenthese fermante echouerait.
    """
    assert parse_column("Ni, Nickel (wt.%)").unit == "wt.%"
    assert parse_column("Ba, Barium (ppm)").unit == "ppm"


def test_une_valeur_censuree_passe_par_le_mecanisme_existant():
    """
    « Les valeurs censurees passent par le mecanisme `censored_as`
    existant, ne le reecris pas. » Le test verifie qu'il est bien utilise :
    valeur None, seuil lu.
    """
    valeur, seuil = parse_value("< 0.050")
    assert valeur is None
    assert seuil == pytest.approx(0.050)


def test_une_incertitude_indeterminee_ne_fait_pas_echouer_la_lecture():
    """
    `IND` n'apparait qu'en troisieme colonne du certificat, que le lecteur
    de format long n'utilise pas. Mais un bulletin qui le placerait en
    colonne de valeur ne doit pas lever « Valeur illisible » : c'est une
    valeur non quantifiee, pas une erreur de fichier.
    """
    valeur, seuil = parse_value("IND")
    assert valeur is None
    assert seuil is None
    assert parse_value("ind") == (None, None)


def test_le_separateur_point_virgule_est_accepte(lecture):
    assert len(lecture.measured_elements) == 10


def test_le_meme_fichier_lu_en_virgule_est_refuse_proprement():
    """
    Le refus doit rester propre quand le separateur est faux : une seule
    colonne illisible, et le message liste ce qui a ete lu. C'est le
    comportement d'origine, et la seance demandait de le garder.
    """
    with pytest.raises(IngestionError) as capture:
        read_bulletin(BRUT, delimiter=",")
    message = str(capture.value)
    assert "Element;Value;1SD" in message or "Intitul" in message, message


# ==========================================================================
# 3. La regle absolue : ne jamais deviner
# ==========================================================================

@pytest.mark.parametrize("intitule", [
    "Ba, Barium (ppm)",        # element etranger au modele
    "Ce, Cerium (ppm)",
    "Zr, Zirconium (wt.%)",
    "Si, Silicon (wt.%)",
    "S, Sulphur (wt.%)",
])
def test_un_element_etranger_au_modele_reste_refuse(intitule):
    """
    Le modele connait douze elements. Les vingt-cinq autres lignes du
    certificat doivent rester refusees : accepter du baryum reviendrait a
    inventer une colonne de stoechiometrie.
    """
    c = parse_column(intitule)
    assert not c.recognized
    assert c.element is None


@pytest.mark.parametrize("intitule", [
    "Al, Barium (wt.%)",       # les deux moities se contredisent
    "Ni, Cobalt (wt.%)",
    "Xx, Nickel (wt.%)",       # symbole inconnu, nom connu
    "Ni, Machinchose (wt.%)",  # symbole connu, nom inconnu
])
def test_un_intitule_dont_les_deux_moities_se_contredisent_est_refuse(
        intitule):
    """
    La corroboration remplace la devinette. Un intitule « Al, Barium » est
    corrompu : accepter la moitie que l'on reconnait serait exactement
    l'interpretation de travers que le module refuse.

    Le cas « Ni, Cobalt » est le plus dangereux des quatre : les deux
    moities sont valides separement, et un lecteur laxiste retiendrait l'une
    des deux. Le lot sortirait alors avec un nickel compte comme du cobalt,
    soit un prix faux sans aucun signe exterieur.
    """
    c = parse_column(intitule)
    assert not c.recognized, (
        f"« {intitule} » a ete accepte comme {c.element} : le module a "
        f"devine")
    assert c.element is None


def test_le_refus_liste_les_intitules_lus(lecture):
    """
    Le comportement a garder : le refus dit ce qu'il a lu, pour que
    l'utilisateur voie ou son fichier diverge.
    """
    ignorees = lecture.ignored_columns
    assert len(ignorees) == 25, f"{len(ignorees)} colonnes ignorees"
    assert any("Barium" in c for c in ignorees)
    assert any("Zirconium" in c for c in ignorees)


def test_aucun_element_du_modele_n_est_perdu_dans_les_ignorees(lecture):
    """
    Garde symetrique du precedent. Sans lui, un bug qui ignorerait tout
    passerait le test de refus sans que rien ne le dise.
    """
    for col in lecture.ignored_columns:
        c = parse_column(col)
        assert c.element is None, (
            f"« {col} » designe {c.element} et a pourtant ete ignore")


# ==========================================================================
# 4. De bout en bout, sur le chemin unique
# ==========================================================================

def test_le_bouclage_du_lot_reel_est_celui_mesure():
    """
    Cas de non-regression. La valeur de reference est celle du cas NON
    ATTESTE : le bouclage depend de la liste de phases, donc de
    l'attestation, et citer un chiffre sans sa configuration ne veut rien
    dire. Mesure : 93,95 % sans attestation, 93,42 % en vehicule electrique
    atteste, 94,19 % en DEEE atteste.
    """
    a = analyser(Demande(bulletin=str(BRUT), separateur=";",
                         provenance="non_declaree", tirages=30))
    c = a.incertitude.meta["closure"]
    assert c.total * 100.0 == pytest.approx(BOUCLAGE_NON_ATTESTE_PCT,
                                            abs=0.01)
    assert c.direction == "sous", (
        "OREAS sous-boucle : l'oxygene n'est pas dose")


def test_le_lot_reel_ne_declenche_aucune_alerte_de_plausibilite():
    """
    La contrepartie de la tache 2 : sur ce lot, F et P sont DOSES. Leurs
    teneurs sont des mesures, pas des predictions, et le controle de
    plausibilite ne doit donc rien dire.
    """
    a = analyser(Demande(bulletin=str(BRUT), separateur=";",
                         provenance="non_declaree", tirages=30))
    assert a.plausibilite.depassements == (), (
        "le materiau certifie qui sert d'ancrage declenche une alerte : le "
        "controle sort de son role")
