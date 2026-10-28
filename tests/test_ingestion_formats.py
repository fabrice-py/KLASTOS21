"""Tests de la detection de separateur et d'encodage.

POURQUOI CE FICHIER EXISTE
--------------------------
Le seul bulletin REEL du depot, `bulletin_reel_OREAS_brut.csv`, etait
refuse par la lecture par defaut. Il s'ouvre sans difficulte avec
`delimiter=";"`, mais le defaut etait la virgule et rien ne detectait le
separateur. Le point-virgule est le defaut d'Excel en France, en Allemagne,
en Espagne et en Italie : le format le plus courant du marche vise
rebondissait.

Et le refus ne nommait pas la suite - « Aucune colonne exploitable » - ce
qui contredit l'engagement du projet : un refus doit dire quoi faire.

Un second defaut se tenait derriere : un fichier cp1252 contenant des
accents levait une UnicodeDecodeError NON RATTRAPEE, c'est-a-dire une trace
Python au visage de l'utilisateur plutot qu'un refus motive.
"""

import pathlib
import tempfile

import pytest

from klastos.ingestion import (DELIMITEURS_CANDIDATS, ENCODAGES_CANDIDATS,
                               IngestionError, _decoder, detecter_delimiteur,
                               read_bulletin)

OREAS = pathlib.Path("data/exemples/bulletin_reel_OREAS_brut.csv")
REFERENCE = pathlib.Path("data/exemples/bulletin_coherent.csv")


@pytest.fixture
def dossier():
    with tempfile.TemporaryDirectory() as d:
        yield pathlib.Path(d)


def _ecrire(dossier, contenu, encodage="utf-8", nom="b.csv"):
    f = dossier / nom
    f.write_bytes(contenu.encode(encodage))
    return f


# --------------------------------------------------------------------------
# Le cas qui a motive le correctif
# --------------------------------------------------------------------------

def test_le_bulletin_reel_se_lit_sans_aucun_reglage():
    """
    LE TEST QUI COMPTE. Avant ce correctif, cet appel levait
    « Aucune colonne exploitable » sur le seul bulletin reel du depot.
    """
    r = read_bulletin(OREAS)
    assert len(r.measured_elements) == 10
    assert {"Ni", "Co", "Li", "Mn"} <= set(r.measured_elements)


def test_le_separateur_du_bulletin_reel_est_le_point_virgule():
    assert detecter_delimiteur(OREAS.read_text(encoding="utf-8")) == ";"


# --------------------------------------------------------------------------
# Detection du separateur
# --------------------------------------------------------------------------

@pytest.mark.parametrize("sep", [",", ";", "\t", "|"])
def test_les_quatre_separateurs_courants_sont_detectes(dossier, sep):
    source = REFERENCE.read_text(encoding="utf-8")
    assert "," in source and sep not in source.replace(",", "") or sep == ","
    f = _ecrire(dossier, source.replace(",", sep))
    assert len(read_bulletin(f).measured_elements) == 10


def test_un_separateur_explicite_n_est_jamais_contredit(dossier):
    """
    Un appelant qui sait ce qu'il lit ne doit pas etre corrige par une
    heuristique. On lui donne le mauvais separateur : il doit echouer, et
    non se voir discretement sauve par la detection.
    """
    f = _ecrire(dossier, REFERENCE.read_text(encoding="utf-8"))
    with pytest.raises(IngestionError):
        read_bulletin(f, delimiter=";")


def test_la_virgule_decimale_ne_fait_pas_elire_la_virgule(dossier):
    """
    LE PIEGE DE LA DETECTION.

    Un bulletin francais separe par des points-virgules ecrit ses decimales
    avec des virgules. Une heuristique qui ne regarde que le NOMBRE de
    colonnes elit alors la virgule, qui en produit davantage - et decoupe
    les nombres en deux. Le critere de COHERENCE l'en empeche : la virgule
    ne decoupe pas la ligne d'intitules comme les lignes de valeurs.
    """
    texte = ("Ni (%);Co (%);Li (%);Mn (%)\n"
             "16,20;4,01;3,30;5,10\n")
    assert detecter_delimiteur(texte) == ";"


def test_un_fichier_sans_colonnes_est_refuse_en_nommant_les_essais(dossier):
    texte = "ceci n'est pas un tableau\nni celle-ci\n"
    with pytest.raises(IngestionError, match="Aucun separateur"):
        detecter_delimiteur(texte)


def test_le_refus_nomme_les_separateurs_essayes():
    """Un refus qui ne dit pas quoi faire est un mur."""
    with pytest.raises(IngestionError) as e:
        detecter_delimiteur("une seule colonne\nencore une\n")
    message = str(e.value)
    for d in DELIMITEURS_CANDIDATS:
        marque = r"'\t'" if d == "\t" else repr(d)
        assert marque in message, f"{d!r} absent du message de refus"


def test_le_refus_de_colonnes_exploitables_nomme_le_remede(dossier):
    """
    « Aucune colonne exploitable » laissait l'utilisateur devant un mur.
    La cause la plus frequente est un mauvais decoupage, et le message doit
    le dire.
    """
    f = _ecrire(dossier, "Densite;Granulometrie\n2.4;45\n")
    with pytest.raises(IngestionError, match="separateur"):
        read_bulletin(f)


# --------------------------------------------------------------------------
# Encodage
# --------------------------------------------------------------------------

@pytest.mark.parametrize("encodage", ["utf-8", "utf-8-sig", "cp1252"])
def test_les_encodages_courants_passent(dossier, encodage):
    """
    cp1252 est le defaut de l'Excel francais. Un bulletin accentue y
    levait une UnicodeDecodeError NON RATTRAPEE.
    """
    accentue = (
        "Échantillon prélevé,Ni (%),Co (%),Li (%),Opérateur\n"
        "LOT-1,16.20,4.01,3.30,J. Kühn\n"
    )
    f = _ecrire(dossier, accentue, encodage=encodage)
    r = read_bulletin(f)
    assert {"Ni", "Co", "Li"} <= set(r.measured_elements)


def test_un_encodage_inconnu_ne_remonte_jamais_de_trace_python():
    """
    `latin-1` ferme la chaine : tout octet y est decodable. Le but n'est
    pas de deviner juste, c'est de ne JAMAIS laisser fuir une
    UnicodeDecodeError vers l'utilisateur.
    """
    texte, encodage = _decoder(bytes([0x97, 0x41, 0x42]))
    assert isinstance(texte, str)
    assert encodage in ENCODAGES_CANDIDATS


def test_l_ancien_fichier_qui_plantait_rend_un_refus_propre():
    """
    `usgs_mcs2026_extrait.csv` est un fichier de PRIX, pas un bulletin. Le
    lui donner est une erreur d'utilisateur - mais elle doit produire un
    refus motive, pas une UnicodeDecodeError.
    """
    with pytest.raises(IngestionError):
        read_bulletin("data/exemples/usgs_mcs2026_extrait.csv")


# --------------------------------------------------------------------------
# Les trois points d'entree partagent la meme detection
# --------------------------------------------------------------------------

def test_le_service_detecte_aussi():
    from klastos.service import Demande, analyser

    a = analyser(Demande(bulletin=OREAS, provenance="vehicule_electrique",
                         attestee=True, tirages=20))
    assert a.lecture.measured_elements

    from klastos.service import Demande as D
    assert D().separateur is None, (
        "le service force encore un separateur, donc ne detecte jamais")


def test_la_ligne_de_commande_detecte_aussi():
    from klastos.cli import build_parser

    args = build_parser().parse_args(["diag", str(OREAS)])
    assert args.separateur is None


def test_le_televersement_detecte_aussi():
    """
    L'interface recoit des OCTETS, pas un chemin. Elle delegue le decodage
    et la detection a l'ingestion : les reimplementer ici les ferait
    diverger, ce qui est deja arrive une fois sur la reconnaissance de
    format.
    """
    from klastos.app import lignes_depuis_csv

    lignes = lignes_depuis_csv(OREAS.read_bytes())
    assert len(lignes) > 5
