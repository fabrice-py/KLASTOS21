"""Tests de klastos/app.py.

L'interface est un ADAPTATEUR : elle traduit des widgets en `Demande` et
affiche une `Analyse`. Ce qui est testable sans lancer Streamlit, c'est
exactement ce qui compte :

  1. Elle ne refait pas la chaine dans son coin.
  2. La lecture d'un fichier televerse donne le meme resultat qu'un chemin.
  3. La demande construite reflete fidelement ce qui a ete coche, en
     particulier les deux attestations que le systeme refuse de deviner.
  4. Un refus du protocole s'affiche comme une decision motivee, jamais
     comme une trace d'appel.

Les widgets eux-memes ne sont pas testes : Streamlit n'est pas une
dependance du coeur, et une interface qui se charge ne prouve rien sur ce
qu'elle calcule.
"""

import ast
import datetime as dt
import pathlib

import pytest

streamlit = pytest.importorskip(
    "streamlit", reason="interface non installee : pip install streamlit")

from klastos.app import (construire_demande, lignes_depuis_csv,  # noqa: E402
                         message_de_refus)
from klastos.market import MissingPriceError, NotAProductionSourceError  # noqa: E402
from klastos.report import (DESTINATAIRE_INTERNE, DESTINATAIRE_TIERS,  # noqa: E402
                            ReportRefused)
from klastos.service import analyser  # noqa: E402
from klastos.units import ImplausiblePriceError  # noqa: E402

RACINE = pathlib.Path(__file__).resolve().parent.parent
BULLETIN = RACINE / "data" / "exemples" / "bulletin_coherent.csv"
AUJ = dt.date(2026, 9, 7)


@pytest.fixture(autouse=True)
def _bulletin_present():
    if not BULLETIN.exists():
        pytest.skip("bulletin d'exemple absent")


# ==========================================================================
# 1. L'interface ne refait pas la chaine
# ==========================================================================

def test_l_interface_ne_refait_pas_la_chaine():
    """
    Meme verrou que pour la ligne de commande. Si l'interface se met a
    appeler propagate() ou build_report() directement, un second chemin
    nait, et les deux diront un jour deux choses du meme lot.
    """
    # Import SANS prefixe de paquet : `tests/` n'a pas d'__init__.py, donc
    # `tests` n'est importable que si la racine du projet se trouve sur
    # sys.path - ce que `python -m pytest` fait et `pytest` seul ne fait pas.
    # Pytest insere en revanche toujours le dossier du fichier de test.
    from test_service import ETAPES_RESERVEES, _appels_de

    fautes = _appels_de("app.py") & ETAPES_RESERVEES
    assert not fautes, (
        f"app.py appelle directement {sorted(fautes)} au lieu de passer par "
        "service.analyser()."
    )


def test_l_interface_n_ecrit_pas_dans_la_base_metier():
    """
    Elle enregistre via `store`, jamais en SQL direct : sinon le schema
    aurait deux auteurs.
    """
    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    assert "sqlite3" not in src
    assert "INSERT" not in src.upper()


def test_le_coeur_ne_depend_pas_de_l_interface():
    """
    `pip install klastos` doit suffire a tout faire tourner sans Streamlit.

    Seul le niveau MODULE compte : c'est lui qui cree une dependance dure.
    Un import garde a l'interieur d'une fonction - celui du lanceur
    `klastos ui`, qui verifie la presence de Streamlit pour le dire
    proprement - n'empeche aucun autre usage du paquet.
    """
    for module in sorted((RACINE / "klastos").glob("*.py")):
        if module.name == "app.py":
            continue
        arbre = ast.parse(module.read_text(encoding="utf-8"))
        for n in arbre.body:                      # niveau module seulement
            if isinstance(n, ast.Import):
                noms = {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                noms = {n.module.split(".")[0]}
            else:
                continue
            assert "streamlit" not in noms, (
                f"{module.name} importe streamlit au niveau module : le "
                "paquet ne s'installe plus sans l'interface."
            )


def test_le_lanceur_verifie_la_presence_de_streamlit_avant_de_lancer():
    """Un module manquant doit donner un conseil, pas une trace d'appel."""
    src = (RACINE / "klastos" / "cli.py").read_text(encoding="utf-8")
    assert "pip install streamlit" in src
    assert "import streamlit" in src


# ==========================================================================
# 2. Lecture d'un fichier televerse
# ==========================================================================

def test_le_format_large_est_lu():
    lignes = lignes_depuis_csv(BULLETIN.read_bytes())
    assert "Ni (%)" in lignes
    assert lignes["Ni (%)"] == "16.20"


def test_le_format_long_est_lu():
    """L'entete « element, valeur » est reconnue et n'entre pas en donnee."""
    contenu = b"element,valeur\nNi (%),16.20\nCo (%),4.01\n"
    assert lignes_depuis_csv(contenu) == {"Ni (%)": "16.20", "Co (%)": "4.01"}


def test_le_format_long_sans_entete_est_lu():
    contenu = b"Ni (%),16.20\nCo (%),4.01\nLi (%),3.28\n"
    assert lignes_depuis_csv(contenu) == {"Ni (%)": "16.20",
                                          "Co (%)": "4.01",
                                          "Li (%)": "3.28"}


def test_un_bulletin_large_a_deux_colonnes_n_est_pas_pris_pour_un_long():
    """
    Regression. L'adaptateur reconnaissait le format lui-meme et se
    trompait : deux colonnes suffisaient a le faire basculer en format
    long, et « Ni (%) ; Co (%) » puis « 16.20 ; 4.01 » ressortait en
    {"16.20": "4.01"}. La reconnaissance appartient a l'ingestion.
    """
    assert lignes_depuis_csv(b"Ni (%),Co (%)\n16.20,4.01\n") == {
        "Ni (%)": "16.20", "Co (%)": "4.01"}


def test_un_bom_utf8_ne_pollue_pas_le_premier_intitule():
    """Excel francais exporte volontiers en UTF-8 avec BOM."""
    contenu = "﻿Ni (%),Co (%)\n16.20,4.01\n".encode("utf-8")
    assert "Ni (%)" in lignes_depuis_csv(contenu)


def test_un_separateur_point_virgule_est_accepte():
    """Excel en configuration francaise ecrit des points-virgules."""
    contenu = b"Ni (%);Co (%)\n16.20;4.01\n"
    assert lignes_depuis_csv(contenu, ";") == {"Ni (%)": "16.20",
                                               "Co (%)": "4.01"}


def test_un_fichier_sans_valeurs_est_refuse_avec_un_message():
    from klastos.ingestion import IngestionError

    with pytest.raises(IngestionError, match="deux lignes"):
        lignes_depuis_csv(b"Ni (%),Co (%)\n")


def test_les_lignes_vides_sont_ignorees():
    contenu = b"\nNi (%),Co (%)\n\n16.20,4.01\n\n"
    assert lignes_depuis_csv(contenu) == {"Ni (%)": "16.20", "Co (%)": "4.01"}


def test_un_fichier_televerse_donne_le_meme_resultat_qu_un_chemin():
    """
    L'EXIGENCE CENTRALE DE L'ADAPTATEUR. Deux routes d'entree, un seul
    nombre en sortie.
    """
    from klastos.service import Demande

    lignes = lignes_depuis_csv(BULLETIN.read_bytes())
    par_interface = analyser(construire_demande(
        lignes, lot_id="L", client="C", provenance="vehicule_electrique",
        attestee=True, grades=None, tirages=25, graine=0,
        seuil_alerte=0.06, seuil_rejet=0.20, emis_le=AUJ))
    par_fichier = analyser(Demande(
        bulletin=BULLETIN, lot_id="L", client="C",
        provenance="vehicule_electrique", attestee=True, tirages=25,
        graine=0, seuil_alerte=0.06, seuil_rejet=0.20, emis_le=AUJ))

    assert (par_interface.rapport.to_markdown()
            == par_fichier.rapport.to_markdown())


# ==========================================================================
# 3. La demande reflete ce qui a ete coche
# ==========================================================================

def _demande(**kw):
    base = dict(lot_id=" L-1 ", client=" Negociant ",
                provenance="vehicule_electrique", attestee=True, grades=None,
                tirages=50, graine=3, seuil_alerte=0.06, seuil_rejet=0.20)
    base.update(kw)
    return construire_demande({"Ni (%)": "16.2"}, **base)


def test_les_espaces_autour_des_saisies_sont_retires():
    d = _demande()
    assert d.lot_id == "L-1"
    assert d.client == "Negociant"


def test_un_client_vide_recoit_une_valeur_neutre():
    assert _demande(client="   ").client == "Client"


def test_l_attestation_non_cochee_est_transmise_telle_quelle():
    """
    Elle ne doit surtout pas etre deduite du fait qu'une provenance a ete
    choisie : c'est exactement la confusion que la regle interdit.
    """
    d = _demande(attestee=False, provenance="vehicule_electrique")
    assert d.attestee is False
    assert analyser(construire_demande(
        lignes_depuis_csv(BULLETIN.read_bytes()),
        lot_id="L", client="C", provenance="vehicule_electrique",
        attestee=False, grades=None, tirages=20, graine=0,
        seuil_alerte=0.06, seuil_rejet=0.20, emis_le=AUJ)).phases_exclues == []


def test_le_destinataire_par_defaut_est_tiers():
    assert _demande().destinataire == DESTINATAIRE_TIERS


def test_le_destinataire_interne_est_transmis():
    assert _demande(destinataire=DESTINATAIRE_INTERNE).destinataire \
        == DESTINATAIRE_INTERNE


def test_sans_prix_la_demande_n_en_invente_pas():
    d = _demande()
    assert d.prix is None and d.termes is None


def test_les_grades_declares_sont_transmis():
    d = _demande(provenance="chutes_gigafactory", grades=("NMC811",))
    assert d.grades_declares == ("NMC811",)


def test_les_seuils_et_la_graine_sont_transmis():
    d = _demande(tirages=120, graine=7, seuil_alerte=0.05, seuil_rejet=0.3)
    assert (d.tirages, d.graine, d.seuil_alerte, d.seuil_rejet) \
        == (120, 7, 0.05, 0.3)


# ==========================================================================
# 4. Un refus s'affiche comme une decision, pas comme un plantage
# ==========================================================================

@pytest.mark.parametrize("exc, attendu", [
    (ReportRefused("prix d'agence sans licence"), "Rapport refusé"),
    (NotAProductionSourceError("jeu de demo"), "Source de prix non destinée"),
    (MissingPriceError("pas de Ni"), "Prix manquant"),
    (ImplausiblePriceError("facteur 1000"), "Prix invraisemblable"),
    (RuntimeError("autre chose"), "Analyse impossible"),
])
def test_chaque_refus_recoit_un_titre_lisible(exc, attendu):
    titre, detail = message_de_refus(exc)
    assert attendu in titre
    assert detail == str(exc)
    assert "Traceback" not in detail


def test_le_detail_du_refus_est_conserve_mot_pour_mot():
    """Le message du protocole explique quoi faire : il ne doit pas etre
    remplace par une formule generique."""
    e = ReportRefused("Prix d'agence sans licence de rediffusion (fastmarkets).")
    assert message_de_refus(e)[1] == str(e)


# ==========================================================================
# 5. Ce que le client lit
# ==========================================================================

def test_les_libelles_de_provenance_portent_leurs_accents():
    """
    Ils sont affiches dans l'interface et dans le journal de tracabilite du
    rapport. Un outil facture a un negociant n'ecrit pas « Vehicule
    electrique ». Les CLES, elles, restent en ASCII : identifiants
    techniques, passes en ligne de commande.
    """
    from klastos.provenance import PROVENANCE_PROFILES

    assert any(c in p.label for p in PROVENANCE_PROFILES.values()
               for c in "éèêàçÉÈÊÀÇ"), "aucun libelle accentue"
    for cle in PROVENANCE_PROFILES:
        assert cle.isascii(), cle


def test_l_interface_n_affiche_pas_de_cle_technique_brute():
    """Le selecteur montre le libelle metier, pas `non_declaree`."""
    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    assert "format_func=_libelle_profil" in src


def test_un_profil_non_arbitre_est_signale_dans_l_interface():
    """
    Le profil `deee` n'a pas ete arbitre metier. Personne ne doit s'appuyer
    dessus sans le savoir.
    """
    from klastos.provenance import PROVENANCE_PROFILES

    assert PROVENANCE_PROFILES["deee"].validated is False
    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    assert "non arbitré" in src


# ==========================================================================
# 6. Ce que l'interface refuse d'afficher
# ==========================================================================

def test_l_interface_n_invente_aucun_chiffre_de_phase():
    """
    VERROU DE FOND. Le camembert de la maquette initiale portait une valeur
    unique par phase, sommant a 100 %. Sur une black mass, deux assemblages
    differant de 2,86 points sur le PVDF produisent le meme bulletin a
    3e-15 point pres. L'interface passe donc par charts.donnees_composition,
    qui refuse les phases tant qu'elles ne sont pas fermes.
    """
    from klastos import charts
    from klastos.service import Demande, analyser

    a = analyser(Demande(bulletin=BULLETIN, provenance="vehicule_electrique",
                         attestee=True, tirages=20, emis_le=AUJ))
    df, mode = charts.donnees_composition(a)
    assert mode == "elements"

    ouvertes = {r.label for r in a.incertitude.results
                if r.block in ("phase", "ventilation") and not r.identifiable}
    assert ouvertes, "lot mal choisi : aucune phase ouverte"
    assert not (ouvertes & set(df["part"]))


def test_le_tableau_des_phases_affiche_le_statut_de_chaque_ligne():
    """Aucune ligne ne doit sortir sans sa pastille."""
    import re

    from klastos.app import _table_phases
    from klastos.service import Demande, analyser

    a = analyser(Demande(bulletin=BULLETIN, provenance="vehicule_electrique",
                         attestee=True, tirages=20, emis_le=AUJ))
    html = _table_phases(a)
    lignes = html.count("<tr>") - 1          # moins la ligne d'en-tete
    pastilles = len(re.findall(r'class="chip ', html))
    attendu = sum(1 for r in a.incertitude.results
                  if r.block in ("phase", "ventilation"))
    assert pastilles == attendu
    assert lignes == attendu


def test_le_tableau_des_phases_ne_montre_pas_de_valeur_unique_sur_un_domaine():
    """Une grandeur ouverte s'affiche en intervalle, jamais en point."""
    from klastos.app import _table_phases
    from klastos.service import Demande, analyser

    a = analyser(Demande(bulletin=BULLETIN, provenance="vehicule_electrique",
                         attestee=True, tirages=20, emis_le=AUJ))
    html = _table_phases(a)
    for r in a.incertitude.results:
        if r.block in ("phase", "ventilation") and not r.identifiable:
            assert r.format_value() in html
            assert "–" in r.format_value() or "-" in r.format_value()


def test_le_resume_des_statuts_compte_toutes_les_phases():
    from klastos.app import resume_statuts
    from klastos.service import Demande, analyser

    a = analyser(Demande(bulletin=BULLETIN, tirages=20, emis_le=AUJ))
    compte = resume_statuts(a)
    attendu = sum(1 for r in a.incertitude.results
                  if r.block in ("phase", "ventilation"))
    assert sum(compte.values()) == attendu


def test_l_interface_dit_ce_qu_une_drx_fait_et_ne_fait_pas():
    """
    L'interface ingere desormais des quantifications. Le verrou se deplace :
    elle doit dire qu'une mesure entre en ENCADREMENT et ne rend aucune
    grandeur ferme. Promettre des phases fermes serait recreer le piege du
    sommet a l'endroit meme que ce module protege.
    """
    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    assert "encadrement" in src
    assert "aucune grandeur ferme" in src
    assert "ne la supprime pas" in src


def test_l_interface_expose_le_taux_de_conflit():
    """
    Un bulletin bruite peut contredire la quantification. Les tirages
    concernes sont CONSERVES, et le taux doit etre montre : l'ecarter
    silencieusement resserrerait l'incertitude du laboratoire au motif d'une
    mesure qui ne porte pas sur elle.
    """
    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    assert "structural_conflict_rate" in src
    assert "conservés" in src


def test_l_interface_exige_l_incertitude_de_la_drx():
    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    assert "OBLIGATOIRE" in src
    assert "Rietveld" in src


def test_la_demande_transporte_la_quantification():
    """construire_demande reste la fonction pure testee."""
    d = construire_demande(
        {"Ni (%)": "16.2"}, lot_id="L", client="C",
        provenance="non_declaree", attestee=False, grades=None,
        tirages=5, graine=0, seuil_alerte=0.06, seuil_rejet=0.20,
        drx="quelque/part.csv", base_drx="cristalline",
        conseil_drx=True, incertitude_drx=0.03)
    assert d.drx == "quelque/part.csv"
    assert d.base_drx == "cristalline"
    assert d.conseil_drx is True
    assert d.incertitude_drx == 0.03


def test_la_demande_sans_drx_reste_inchangee():
    d = construire_demande(
        {"Ni (%)": "16.2"}, lot_id="L", client="C",
        provenance="non_declaree", attestee=False, grades=None,
        tirages=5, graine=0, seuil_alerte=0.06, seuil_rejet=0.20)
    assert d.drx is None
    assert d.conseil_drx is False