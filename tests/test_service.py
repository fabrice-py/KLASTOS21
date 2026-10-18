"""Tests de klastos/service.py.

Le service est le chemin UNIQUE d'une analyse. Il existe pour une seule
raison : empecher la ligne de commande et l'interface graphique de diverger.

Tant qu'il n'y avait qu'un point d'entree, la chaine pouvait vivre dans
`cli.py` sans dommage. Avec deux, le risque est toujours le meme : l'un
recoit un correctif, l'autre non ; l'un pose un verrou, l'autre l'oublie. Le
jour ou le rapport de l'interface ne dit plus la meme chose que celui de la
ligne de commande, le client a raison et nous avons tort.

Quatre exigences :

  1. Un seul chemin, et les adaptateurs n'en reconstruisent pas un second.
  2. Le service ne decide rien : pas de prix implicite, pas de provenance
     supposee, pas de seuil cache.
  3. Les refus du protocole remontent intacts a l'appelant.
  4. Les deux adaptateurs produisent le meme rapport pour la meme demande.
"""

import ast
import datetime as dt
import pathlib

import pytest

from klastos.market import (MetalPrice, PayableTerms, PriceSet,
                            demo_payable_terms, demo_price_set)
from klastos.report import (DESTINATAIRE_INTERNE, DESTINATAIRE_TIERS,
                            ReportRefused)
from klastos.service import Demande, analyser, charger_prix, lire

RACINE = pathlib.Path(__file__).resolve().parent.parent
BULLETIN = RACINE / "data" / "exemples" / "bulletin_coherent.csv"
INCOHERENT = RACINE / "data" / "exemples" / "bulletin_2026-RA-04871.csv"
PRIX_CSV = RACINE / "data" / "prix_client_exemple.csv"
AUJ = dt.date(2026, 9, 7)

PRIX_AGENCE_SANS_LICENCE = PriceSet(
    currency="USD", label="fastmarkets du 2026-09-07",
    is_production_source=True, origin="fastmarkets",
    redistribution_licensed=False,
    prices={
        "Ni": MetalPrice("Ni", 16811.13, "USD", AUJ, "fastmarkets",
                         "LME Ni cash"),
        "Co": MetalPrice("Co", 52359.78, "USD", AUJ, "fastmarkets",
                         "Co std grade"),
    },
)
TERMES = PayableTerms(market="test", payables={"Ni": 0.72, "Co": 0.72},
                      as_of=AUJ, source="contrat client", validated=True)


@pytest.fixture(autouse=True)
def _bulletin_present():
    if not BULLETIN.exists():
        pytest.skip("bulletin d'exemple absent")


def _demande(**kw) -> Demande:
    base = dict(bulletin=BULLETIN, provenance="vehicule_electrique",
                attestee=True, tirages=30, graine=0, emis_le=AUJ)
    base.update(kw)
    return Demande(**base)


# ==========================================================================
# 1. Un seul chemin
# ==========================================================================

def _appels_de(module: str) -> set[str]:
    """Noms de fonctions appelees dans un module, a plat."""
    arbre = ast.parse((RACINE / "klastos" / module).read_text(encoding="utf-8"))
    out: set[str] = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    return out


#: Etapes metier que SEUL le service a le droit d'enchainer. Un adaptateur
#: qui en appelle une refait la chaine dans son coin.
ETAPES_RESERVEES = {"propagate", "value_lot", "build_report"}


@pytest.mark.parametrize("adaptateur", ["cli.py"])
def test_un_adaptateur_ne_refait_pas_la_chaine(adaptateur):
    """
    LE VERROU DU MODULE. Si ce test tombe, c'est qu'un second chemin est en
    train de naitre, et il divergera.
    """
    fautes = _appels_de(adaptateur) & ETAPES_RESERVEES
    assert not fautes, (
        f"{adaptateur} appelle directement {sorted(fautes)} au lieu de passer "
        "par service.analyser(). Deux chemins finiront par dire deux choses."
    )


def test_le_service_enchaine_bien_toutes_les_etapes():
    """La contrepartie : le service, lui, doit les appeler toutes."""
    assert ETAPES_RESERVEES <= _appels_de("service.py")


def test_le_service_n_importe_aucune_interface():
    """
    Ni argparse, ni streamlit. Un module de chaine qui connait son
    affichage ne peut plus en servir deux.
    """
    source = (RACINE / "klastos" / "service.py").read_text(encoding="utf-8")
    arbre = ast.parse(source)
    importes = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            importes |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            importes.add(n.module.split(".")[0])
    assert not (importes & {"argparse", "streamlit", "sys"}), importes


# ==========================================================================
# 2. Le service ne decide rien
# ==========================================================================

def test_sans_prix_pas_de_valorisation():
    """Il n'existe nulle part de jeu de prix implicite."""
    a = analyser(_demande())
    assert a.valorisation is None
    assert not a.valorise
    assert a.rapport.section("Valorisation") is None


def test_un_prix_sans_termes_ne_valorise_pas():
    """Un payable suppose serait une invention commerciale."""
    a = analyser(_demande(prix=demo_price_set(), autoriser_demo=True))
    assert a.valorisation is None


def test_la_provenance_par_defaut_n_exclut_rien():
    a = analyser(Demande(bulletin=BULLETIN, tirages=20, emis_le=AUJ))
    assert a.phases_exclues == []


def test_sans_attestation_aucune_exclusion():
    """Regle non negociable, verifiee aussi a ce niveau."""
    a = analyser(_demande(attestee=False, tirages=20))
    assert a.phases_exclues == []
    assert any("ATTESTATION" in l.upper() for l in a.journal)


def test_les_seuils_de_bouclage_viennent_du_module():
    from klastos.solver import CLOSURE_ALERT, CLOSURE_REJECT

    d = Demande()
    assert d.seuil_alerte == CLOSURE_ALERT
    assert d.seuil_rejet == CLOSURE_REJECT


def test_le_destinataire_par_defaut_est_tiers():
    assert Demande().destinataire == DESTINATAIRE_TIERS


# ==========================================================================
# 3. Les refus remontent intacts
# ==========================================================================

def test_un_bulletin_illisible_remonte_en_erreur_d_ingestion():
    from klastos.ingestion import IngestionError

    with pytest.raises(IngestionError):
        analyser(_demande(bulletin=RACINE / "README.md"))


def test_ni_fichier_ni_lignes_est_refuse():
    from klastos.ingestion import IngestionError

    with pytest.raises(IngestionError, match="soit"):
        analyser(Demande())


def test_fichier_et_lignes_a_la_fois_est_refuse():
    from klastos.ingestion import IngestionError

    with pytest.raises(IngestionError, match="soit"):
        analyser(Demande(bulletin=BULLETIN, lignes={"Ni (%)": "16.2"}))


def test_des_prix_d_agence_sans_licence_refusent_un_rapport_pour_tiers():
    with pytest.raises(ReportRefused, match="licence de rediffusion"):
        analyser(_demande(prix=PRIX_AGENCE_SANS_LICENCE, termes=TERMES))


def test_les_memes_prix_passent_en_interne():
    a = analyser(_demande(prix=PRIX_AGENCE_SANS_LICENCE, termes=TERMES,
                          destinataire=DESTINATAIRE_INTERNE))
    assert a.valorise


def test_des_prix_de_demonstration_sont_refuses_des_la_valorisation():
    """
    Le refus tombe au plus tot : la valorisation elle-meme s'arrete, avant
    meme que le rapport n'ait a se prononcer. Un chiffre faux ne doit pas
    exister, pas seulement ne pas s'afficher.
    """
    from klastos.market import NotAProductionSourceError

    with pytest.raises(NotAProductionSourceError, match="production"):
        analyser(_demande(prix=demo_price_set(),
                          termes=demo_payable_terms()["cif_coree_sud"]))


def test_la_demonstration_assumee_produit_un_document_non_opposable():
    a = analyser(_demande(prix=demo_price_set(),
                          termes=demo_payable_terms()["cif_coree_sud"],
                          autoriser_demo=True))
    assert a.rapport.is_demo is True
    assert a.valorise


# ==========================================================================
# 4. Lecture en memoire : la route de l'interface
# ==========================================================================

def test_un_bulletin_en_memoire_donne_le_meme_resultat_qu_un_fichier():
    """
    L'interface recoit un fichier televerse, pas un chemin. Les deux routes
    doivent mener au meme nombre.
    """
    import csv

    with BULLETIN.open(encoding="utf-8") as fh:
        lignes = next(iter(csv.DictReader(fh)))

    par_fichier = analyser(_demande())
    par_memoire = analyser(_demande(bulletin=None, lignes=lignes,
                                    lot_id=par_fichier.rapport.lot_id))

    assert (par_memoire.lecture.measured_elements
            == par_fichier.lecture.measured_elements)
    assert par_memoire.lecture.b == pytest.approx(par_fichier.lecture.b)
    assert (par_memoire.rapport.to_markdown()
            == par_fichier.rapport.to_markdown())


def test_lire_seul_n_execute_pas_la_chaine():
    """Une interface montre le bulletin lu avant de lancer le calcul."""
    lecture = lire(_demande())
    assert lecture.measured_elements
    assert "O" not in lecture.measured_elements


# ==========================================================================
# 5. Identifiant et resume
# ==========================================================================

def test_l_identifiant_par_defaut_vient_du_nom_de_fichier():
    assert Demande(bulletin=BULLETIN).identifiant() == "bulletin_coherent"


def test_l_identifiant_fourni_l_emporte():
    assert Demande(bulletin=BULLETIN, lot_id="X-1").identifiant() == "X-1"


def test_le_resume_tient_sur_une_ligne_et_dit_le_bouclage():
    r = analyser(_demande()).resume()
    assert "\n" not in r
    assert "bouclage" in r
    assert "sans valorisation" in r


def test_le_resume_porte_la_fourchette_quand_le_lot_est_valorise():
    a = analyser(_demande(prix=charger_prix(PRIX_CSV), termes=TERMES))
    assert "USD/t" in a.resume()


# ==========================================================================
# 6. Chargement des prix, partage par les deux adaptateurs
# ==========================================================================

def test_un_csv_client_n_est_pas_restreint_en_rediffusion():
    """Ses propres prix : aucune licence d'agence ne s'y applique."""
    assert charger_prix(PRIX_CSV).redistribution_licensed is True


def test_un_csv_client_est_une_source_de_production():
    assert charger_prix(PRIX_CSV).is_production_source is True


def test_un_instantane_json_conserve_sa_licence(tmp_path):
    import json

    p = tmp_path / "snap.json"
    p.write_text(json.dumps({
        "label": "fastmarkets", "currency": "USD",
        "is_production_source": True, "redistribution_licensed": False,
        "prices": {"Ni": {"value_per_tonne": 16811.0, "as_of": "2026-09-07",
                          "source": "fastmarkets",
                          "reference_name": "LME Ni cash"}},
    }), encoding="utf-8")
    assert charger_prix(p).redistribution_licensed is False


# ==========================================================================
# 7. Le bulletin incoherent reste detecte par cette route
# ==========================================================================

def test_le_bulletin_physiquement_impossible_est_signale():
    if not INCOHERENT.exists():
        pytest.skip("bulletin incoherent absent")
    a = analyser(_demande(bulletin=INCOHERENT, tirages=20))
    central = a.incertitude.meta["central"]
    assert central.max_element_residual > 0.01
