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
    assert "Traceback" not in detail
    assert detail.strip(), "un refus sans explication n'est pas une decision"

    # Le detail est conserve MOT POUR MOT, sauf pour la source non
    # destinee a la production. Cette assertion valait pour tous les refus
    # jusqu'au 25 octobre 2026, et elle etait trop forte : elle exigeait le
    # verbatim quand la regle reelle est « une explication lisible et
    # actionnable ».
    #
    # Le message de `valuation.py` dit « passer allow_stale=True », ce qui
    # satisfaisait la lettre du test tout en echouant son intention. Un
    # utilisateur a lu ce refus sans savoir le lever. L'interface le
    # remplace donc par la consigne, et deux tests dedies verifient qu'elle
    # nomme la case et ne laisse plus fuir de vocabulaire de code.
    if not isinstance(exc, NotAProductionSourceError):
        assert detail == str(exc)


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
    from klastos import i18n
    from klastos.provenance import PROVENANCE_PROFILES

    assert PROVENANCE_PROFILES["deee"].validated is False
    # Le texte a quitte app.py pour le catalogue i18n : on verifie
    # desormais qu'il existe DANS LES DEUX LANGUES, plutot que sa
    # presence en clair dans la source de l'interface.
    for langue in i18n.LANGUES:
        suffixe = i18n.t("ui.provenance.non_arbitre", langue).strip()
        assert suffixe, langue
        assert i18n.t("ui.provenance.avert_non_arbitre", langue)
    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    assert "ui.provenance.non_arbitre" in src


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
    from klastos import i18n

    # Le texte vit au catalogue depuis que l'interface est bilingue. Le
    # verrou porte donc sur LES DEUX LANGUES : une promesse de phases
    # fermes faite au seul lecteur anglophone recreerait le piege du
    # sommet a l'endroit meme que ce module protege.
    fr = i18n.t("ui.methode.drx_posee", "fr", n=1, base="absolue")
    assert "encadrement" in fr
    assert "aucune grandeur ferme" in fr
    assert "ne la supprime pas" in fr

    en = i18n.t("ui.methode.drx_posee", "en", n=1, base="absolute")
    assert "bound" in en
    assert "no quantity determined" in en
    assert "does not remove it" in en


def test_l_interface_expose_le_taux_de_conflit():
    """
    Un bulletin bruite peut contredire la quantification. Les tirages
    concernes sont CONSERVES, et le taux doit etre montre : l'ecarter
    silencieusement resserrerait l'incertitude du laboratoire au motif d'une
    mesure qui ne porte pas sur elle.
    """
    from klastos import i18n

    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    assert "structural_conflict_rate" in src
    # Le mot qui compte - les tirages sont CONSERVES, pas ecartes - doit
    # sortir dans les deux langues.
    assert "conservés" in i18n.t("ui.drx.conflit", "fr",
                                 n=1, total=10, taux=10)
    assert "kept" in i18n.t("ui.drx.conflit", "en", n=1, total=10, taux=10)


def test_l_interface_exige_l_incertitude_de_la_drx():
    """
    L'exigence est portee par le catalogue depuis que l'interface est
    bilingue. On la verifie DANS LES DEUX LANGUES : un avertissement qui ne
    sortirait qu'en francais laisserait un operateur anglophone deposer une
    quantification sans incertitude, et cette mesure passerait pour exacte.
    """
    from klastos import i18n

    for langue in i18n.LANGUES:
        aide = i18n.t("ui.drx.aide", langue)
        assert "Rietveld" in aide, langue
        assert ("OBLIGATOIRE" in aide or "MANDATORY" in aide), langue


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

# ==========================================================================
# Interface bilingue
# ==========================================================================

def test_les_cles_de_pages_ne_sont_pas_des_libelles():
    """
    LE VERROU DE LA NAVIGATION. `PAGES` contenait les libelles francais, et
    `main()` routait sur `page == "Analyse"`. Traduire la navigation aurait
    donc envoye toutes les pages sur la page d'aide - la branche `else` -
    sans erreur, sans trace, et avec un ecran qui s'affiche quand meme.
    """
    from klastos import app, i18n

    for cle in app.PAGES:
        assert cle.islower() and " " not in cle, cle
        # Chaque cle doit avoir un libelle dans les deux langues.
        for langue in i18n.LANGUES:
            assert i18n.t(f"ui.page.{cle}", langue)


def test_le_routage_couvre_toutes_les_pages_declarees():
    """Une page declaree sans branche de routage tomberait sur l'aide."""
    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    routage = src.split("def main(")[1]
    for cle in ("analyse", "prix", "historique"):
        assert f'== "{cle}"' in routage, cle


def test_l_interface_transporte_la_langue_jusqu_au_rapport():
    """
    Le rapport doit sortir dans la langue de l'ecran. Sans ce passage, un
    operateur travaillant en anglais telechargeait un document francais.
    """
    from klastos import i18n
    from klastos.app import construire_demande

    for langue in i18n.LANGUES:
        d = construire_demande(
            {"Ni (%)": "16.2"}, lot_id="L", client="C",
            provenance="non_declaree", attestee=False, grades=None,
            tirages=20, graine=0, seuil_alerte=0.06, seuil_rejet=0.2,
            langue=langue)
        assert d.langue == langue


def test_la_langue_par_defaut_de_la_demande_est_le_francais():
    from klastos import i18n
    from klastos.app import construire_demande

    d = construire_demande(
        {"Ni (%)": "16.2"}, lot_id="L", client="C",
        provenance="non_declaree", attestee=False, grades=None,
        tirages=20, graine=0, seuil_alerte=0.06, seuil_rejet=0.2)
    assert d.langue == i18n.DEFAUT


def test_le_separateur_est_pose_a_cote_du_televersement():
    """
    Il vivait dans le volet « Seuils et calcul », ou personne ne cherche un
    reglage de lecture de fichier. Deux analyses d'affilee avaient echoue
    sur un CSV en point-virgule.
    """
    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    avant_volet = src.split('T("ui.volet.seuils")')[0]
    assert 'key="separateur"' in avant_volet, (
        "le separateur est repasse apres le volet des seuils")


def test_le_separateur_n_a_plus_a_etre_saisi():
    """
    L'aide nommait le cas de l'Excel francais, parce qu'il fallait que
    l'utilisateur pense lui-meme a saisir « ; ». Le separateur est
    desormais DETECTE : le champ ne sert plus qu'a forcer un cas
    particulier, et son defaut est vide.

    C'est une garantie plus forte qu'un texte d'aide bien redige : elle ne
    depend pas de ce que le lecteur a remarque.
    """
    from klastos import i18n

    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    bloc = src[src.index('key="separateur"') - 400:
               src.index('key="separateur"') + 200]
    assert 'value=""' in bloc, (
        "le champ impose de nouveau un separateur par defaut, donc la "
        "detection ne joue jamais")
    for langue in i18n.LANGUES:
        aide = i18n.t("ui.separateur.aide", langue)
        assert any(m in aide.lower() for m in ("détect", "detect")), langue


def test_l_interface_ne_porte_plus_de_texte_francais_en_dur():
    """
    LE VERROU DE LA TRANCHE. Chaque libelle de l'interface passe par le
    catalogue, donc par `T()`. Une chaine francaise reintroduite en clair
    ressortirait en francais sur un ecran anglais, et rien ne le signalerait
    : l'ecran s'affiche, simplement dans la mauvaise langue.

    Ne sont pas comptees : les docstrings, qui ne sont pas affichees, et les
    fragments de balisage HTML, qui ne portent pas de texte.
    """
    import re

    src = (RACINE / "klastos" / "app.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)
    docstrings = {
        ast.get_docstring(n, clean=False)
        for n in ast.walk(arbre)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
    }
    #: Trois mots de suite : de la prose, pas un identifiant ni une unite.
    PROSE = re.compile(r"[A-Za-zÀ-ÿ]{3,}\s+[a-zà-ÿ']{2,}\s+[A-Za-zÀ-ÿ']{2,}")

    # `ast.walk` visite une f-string ET chacun de ses fragments. Un
    # fragment n'est pas un texte : coupe au milieu d'un bloc de style, il
    # perd son `<style>` et la regle le prenait pour de la prose. On ne
    # garde donc que la chaine COMPLETE.
    fragments = {id(v) for n in ast.walk(arbre)
                 if isinstance(n, ast.JoinedStr)
                 for v in n.values if isinstance(v, ast.Constant)}

    fautes = []
    for n in ast.walk(arbre):
        texte = None
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if id(n) in fragments:
                continue
            texte = n.value
        elif isinstance(n, ast.JoinedStr):
            texte = "".join(v.value for v in n.values
                            if isinstance(v, ast.Constant)
                            and isinstance(v.value, str))
        if not texte or texte in docstrings:
            continue
        if texte.lstrip().startswith(("ui.", "rapport.")):
            continue              # une cle de catalogue, pas du texte
        # Le CORPS d'un bloc de style n'est pas du texte affiche. Retirer
        # les seules balises laissait passer « width: auto; height: auto;
        # flex: none », que la regle de prose prenait pour une phrase.
        #
        sans_style = re.sub(r"<style>.*?</style>", " ", texte, flags=re.S)
        sans_balises = re.sub(r"<[^>]*>", " ", sans_style)
        if PROSE.search(sans_balises):
            fautes.append((n.lineno, " ".join(sans_balises.split())[:70]))

    assert not fautes, (
        "texte en dur dans l'interface, a porter au catalogue i18n : "
        + "; ".join(f"L{l} {s!r}" for l, s in sorted(set(fautes)))
    )


# ==========================================================================
# Les sources gratuites, et la case qui leve le refus
# ==========================================================================
#
# Defaut trouve le 25 octobre 2026 sur une capture d'ecran d'utilisateur :
# la tuile « prix maximal a payer » affichait « n.d. - aucun prix fourni »
# sur un lot parfaitement analyse.
#
# La cause n'etait pas un calcul. Les deux sources de prix GRATUITES du
# projet - USGS et Pink Sheet - n'existaient que pour la ligne de commande.
# L'interface n'offrait qu'un televersement de fichier et les flux d'agence
# PAYANTS. Un utilisateur sans fichier de prix et sans abonnement n'avait
# donc aucun chemin vers une valorisation, et aucun ecran ne le lui disait.
#
# Second defaut, enchaine au premier : `autoriser_demo` n'etait activable
# NULLE PART dans l'interface. Meme en branchant les sources gratuites,
# l'analyse aurait refuse - a juste titre, ce sont des moyennes - et
# l'utilisateur serait passe d'un « n.d. » muet a un mur rouge.

def test_les_trois_modes_de_prix_sont_offerts():
    """
    Le mode gratuit doit exister ET venir en premier : c'est le seul qui ne
    demande ni fichier ni abonnement, donc le seul utilisable a froid.
    """
    source = pathlib.Path("klastos/app.py").read_text(encoding="utf-8")
    assert '["gratuit", "fichier", "agence"]' in source, (
        "les trois modes de source de prix ne sont plus offerts dans cet "
        "ordre : le mode gratuit doit rester le premier")


def test_les_deux_sources_gratuites_sont_declarees():
    from klastos.app import SOURCES_GRATUITES

    assert set(SOURCES_GRATUITES) == {"usgs", "pink"}


def test_la_case_de_valorisation_indicative_atteint_la_demande():
    """
    LE verrou de la seconde moitie du defaut. Sans ce passage, cocher la
    case ne ferait rien et l'analyse refuserait toujours.
    """
    d = construire_demande(
        {"Ni (%)": "20"}, lot_id="L", client="C",
        provenance="non_declaree", attestee=False, grades=None,
        tirages=40, graine=0, seuil_alerte=0.06, seuil_rejet=0.20,
        autoriser_demo=True)
    assert d.autoriser_demo is True

    d2 = construire_demande(
        {"Ni (%)": "20"}, lot_id="L", client="C",
        provenance="non_declaree", attestee=False, grades=None,
        tirages=40, graine=0, seuil_alerte=0.06, seuil_rejet=0.20)
    assert d2.autoriser_demo is False, (
        "le refus doit rester le comportement par defaut")


def test_le_reglage_indicatif_sort_bien_des_reglages():
    """
    Garde de source. `_reglages()` assemble le dictionnaire que la page
    d'analyse consomme ; si la cle n'y est pas, l'appel leve KeyError au
    premier lot et l'ecran montre une trace d'appel.
    """
    source = pathlib.Path("klastos/app.py").read_text(encoding="utf-8")
    assert "autoriser_demo=autoriser_demo," in source, (
        "la case n'est plus transmise par _reglages()")
    assert 'autoriser_demo=reglages["autoriser_demo"],' in source, (
        "la page d'analyse ne lit plus le reglage")


def test_la_tuile_sans_prix_nomme_son_remede():
    """
    Elle enoncait un probleme sans adresse : « aucun prix fourni ». Le
    projet exige ailleurs qu'un refus dise quoi faire ensuite - c'est la
    regle qui a fait nommer la phase porteuse dans les alertes de
    plausibilite, et les dosages manquants dans les conseils.
    """
    from klastos import i18n

    #: L'onglet et la source a nommer, dans chaque langue. Une assertion
    #: commune aux deux serait paresseuse : « Prices » ne contient pas la
    #: meme sous-chaine que « Prix ».
    ATTENDUS = {"fr": ("onglet Prix", "gratuite"),
                "en": ("Prices tab", "free")}
    for langue, mots in ATTENDUS.items():
        texte = i18n.t("ui.tuile.sans_prix", langue)
        for mot in mots:
            assert mot in texte, (
                f"[{langue}] la tuile ne nomme plus « {mot} » : elle est "
                f"revenue a un constat sans remede")


def test_la_chaine_complete_donne_un_prix_avec_les_sources_gratuites():
    """
    LE test de bout en bout du defaut de la capture d'ecran. Il refait
    exactement ce que fait l'ecran : prix publics, conditions commerciales,
    case indicative cochee - et verifie qu'un prix sort.

    Sans la case, le meme appel doit REFUSER : les deux moities du defaut
    sont donc tenues par un seul test.
    """
    from klastos.market import NotAProductionSourceError
    from klastos.providers import (USGS_ATTRIBUTION, UsgsProvider,
                                   build_price_set)
    from klastos.service import analyser, charger_termes

    extrait = pathlib.Path("data/exemples/usgs_mcs2026_extrait.csv")
    fournisseur = UsgsProvider(extrait)
    prix = build_price_set(
        fournisseur.quotes(), label="USGS",
        is_production_source=fournisseur.is_production_source,
        origin=USGS_ATTRIBUTION,
        redistribution_licensed=fournisseur.redistribution_licensed)
    termes = charger_termes("data/payable_terms.json", "exw_europe")

    lignes = lignes_depuis_csv(
        pathlib.Path("data/exemples/bulletin_coherent.csv").read_bytes())
    commun = dict(lignes=lignes, lot_id="CAPTURE", client="C",
                  provenance="vehicule_electrique", attestee=True,
                  grades=None, tirages=30, graine=0,
                  seuil_alerte=0.06, seuil_rejet=0.20,
                  prix=prix, termes=termes)

    # Sans la case : refus, et c'est le comportement voulu.
    with pytest.raises(NotAProductionSourceError):
        analyser(construire_demande(**commun))

    # Avec : une valorisation indicative sort, et le document le dit.
    a = analyser(construire_demande(**commun, autoriser_demo=True))
    assert a.valorisation is not None, (
        "aucune valorisation : l'utilisateur reverrait « n.d. »")
    assert a.valorisation.max_price_high > a.valorisation.max_price_low > 0
    assert a.rapport.is_demo, (
        "un prix bati sur des moyennes publiques doit sortir sur un "
        "document marque non opposable")


def test_le_bouton_de_rapport_existe_bien():
    """
    L'utilisateur a signale ne pas le trouver. Il existe, dans le quatrieme
    onglet. Ce test fige son existence, pour que la reponse « il est dans
    l'onglet Rapport » reste vraie.
    """
    source = pathlib.Path("klastos/app.py").read_text(encoding="utf-8")
    assert "download_button" in source
    assert 'T("ui.rapport.telecharger")' in source
    assert 'T("ui.onglet.rapport")' in source, (
        "l'onglet qui porte le bouton a disparu de la barre d'onglets")


# ==========================================================================
# Un refus doit nommer l'ACTION, pas le parametre Python
# ==========================================================================
#
# Defaut signale le 25 octobre 2026, sur un ecran reel. Des prix publics
# etaient charges, l'analyse les refusait a juste titre, et le bandeau
# affichait le message de `valuation.py` :
#
#     « Brancher un flux via PriceProvider, ou passer allow_stale=True
#       pour une demonstration. »
#
# C'est exact, et c'est adresse a un DEVELOPPEUR. L'utilisateur, lui, lit un
# refus qu'il ne sait pas lever. La case existait pourtant, mais repliee
# dans un volet de la barre laterale.
#
# Trois corrections tenues ici : le refus nomme la case, le volet s'ouvre,
# et la page Prix previent au moment du chargement plutot qu'au refus deux
# ecrans plus loin.

def test_le_refus_de_source_nomme_la_case_a_cocher():
    from klastos import i18n
    from klastos.market import NotAProductionSourceError

    _, detail = message_de_refus(
        NotAProductionSourceError("message technique brut"))

    assert i18n.t("ui.demo.libelle") in detail, (
        "le refus ne nomme pas la case qui le leve")
    assert i18n.t("ui.volet.valorisation") in detail, (
        "le refus ne dit pas dans quel volet chercher")


def test_le_refus_ne_laisse_plus_fuir_le_vocabulaire_du_code():
    """
    Le message d'origine nommait un parametre Python et une classe. Les
    deux sont justes dans une bibliotheque, et inutilisables a l'ecran.
    """
    from klastos.market import NotAProductionSourceError

    _, detail = message_de_refus(NotAProductionSourceError(
        "n'est pas declare comme source de production. Brancher un flux "
        "via PriceProvider, ou passer allow_stale=True."))

    for fuite in ("allow_stale", "PriceProvider", "=True"):
        assert fuite not in detail, (
            f"« {fuite} » arrive jusqu'a l'ecran : c'est du vocabulaire de "
            f"code, pas une consigne")


def test_le_refus_annonce_la_consequence():
    """
    Lever le refus n'est pas neutre : le document sort NON OPPOSABLE. Le
    dire au moment ou l'on propose de cocher evite une mauvaise surprise au
    moment de remettre le rapport.
    """
    from klastos.market import NotAProductionSourceError

    _, detail = message_de_refus(NotAProductionSourceError("x"))
    assert "non opposable" in detail.lower()


def test_le_volet_qui_porte_la_case_est_deplie():
    """
    Replie, le volet rendait la case introuvable - et c'est exactement ce
    qui est arrive. Un reglage qui leve un refus doit etre visible sans
    qu'on sache deja qu'il existe.
    """
    source = pathlib.Path("klastos/app.py").read_text(encoding="utf-8")
    assert 'T("ui.volet.valorisation"), expanded=True' in source, (
        "le volet Valorisation s'est referme : la case indicative "
        "redevient introuvable")


def test_la_page_prix_previent_des_le_chargement():
    """
    Prevenir au refus, deux ecrans plus loin, est trop tard. La page Prix
    sait des le chargement que le jeu n'est pas une source de production.
    """
    source = pathlib.Path("klastos/app.py").read_text(encoding="utf-8")
    assert "if not prix.is_production_source:" in source
    assert 'T("ui.prix.indicatif_requis"' in source


def test_le_rapport_porte_la_valorisation_quand_elle_existe():
    """
    Second point signale : « l'estimation devrait faire partie du rapport ».
    Elle en fait partie, et ce test le fige - il manquait seulement un prix
    a mettre dedans.
    """
    from klastos.providers import (USGS_ATTRIBUTION, UsgsProvider,
                                   build_price_set)
    from klastos.render_html import to_html
    from klastos.report import SECTION_VALORISATION
    from klastos.service import analyser, charger_termes

    f = UsgsProvider("data/exemples/usgs_mcs2026_extrait.csv")
    prix = build_price_set(
        f.quotes(), label="USGS",
        is_production_source=f.is_production_source,
        origin=USGS_ATTRIBUTION,
        redistribution_licensed=f.redistribution_licensed)
    lignes = lignes_depuis_csv(
        pathlib.Path("data/exemples/bulletin_coherent.csv").read_bytes())
    a = analyser(construire_demande(
        lignes=lignes, lot_id="T", client="C",
        provenance="vehicule_electrique", attestee=True, grades=None,
        tirages=30, graine=0, seuil_alerte=0.06, seuil_rejet=0.20,
        prix=prix, termes=charger_termes("data/payable_terms.json",
                                         "exw_europe"),
        autoriser_demo=True))

    assert a.rapport.section(SECTION_VALORISATION) is not None, (
        "le rapport ne porte pas de section de valorisation")
    html = to_html(a.rapport)
    assert "USD/t" in html, "le prix n'apparait pas dans le document"
    assert f"{a.valorisation.max_price_high:,.0f}".replace(",", " ") in \
        html.replace(",", " ").replace(" ", " "), (
        "la borne haute du prix n'est pas dans le document")


# ==========================================================================
# Le PDF est l'action principale, et en un clic
# ==========================================================================
#
# Signale le 25 octobre 2026 : « le fichier est certes telechargeable mais
# toujours sous format html, je veux le fichier telecharge en pdf ».
#
# Le PDF existait pourtant. Mais il etait en TROISIEME position, derriere un
# bouton BLEU intitule « Telecharger le rapport (HTML) », et demandait DEUX
# clics - preparer, puis telecharger. L'utilisateur a clique sur le bouton
# bleu, obtenu du HTML, et cherche le PDF sans le trouver.
#
# Le format que l'on remet a un client est le PDF. C'est donc lui qui porte
# l'action principale, en tete et en un seul clic.

def test_le_pdf_est_le_premier_bouton():
    source = pathlib.Path("klastos/app.py").read_text(encoding="utf-8")
    pos_pdf = source.index("_bouton_pdf(a, html, c1)")
    pos_html = source.index('T("ui.rapport.telecharger"), data=html')
    assert pos_pdf < pos_html, (
        "le HTML est repasse devant le PDF : c'est l'agencement qui a fait "
        "telecharger du HTML a un utilisateur qui voulait un PDF")


def test_le_pdf_porte_l_action_principale_et_pas_le_html():
    """
    Un seul bouton peut etre `type="primary"`. Si le HTML le redevient, on
    a refait exactement la faute signalee.
    """
    source = pathlib.Path("klastos/app.py").read_text(encoding="utf-8")
    debut = source.index("def _bouton_pdf")
    fin = source.index("def _rapport")
    assert 'type="primary"' in source[debut:fin], (
        "le bouton PDF n'est plus l'action principale")

    # Le bloc du bouton HTML, lui, ne doit plus la porter.
    bloc_html = source[source.index('T("ui.rapport.telecharger"), data=html'):]
    bloc_html = bloc_html[:bloc_html.index("c3.download_button")]
    assert 'type="primary"' not in bloc_html, (
        "le bouton HTML est redevenu l'action principale")


def test_le_pdf_ne_demande_plus_deux_clics():
    """
    Le parcours « preparer puis telecharger » a disparu : les octets sont
    prets au rendu, donc un seul clic suffit.
    """
    from klastos import i18n

    assert "ui.rapport.pdf_preparer" not in i18n.CATALOGUE, (
        "la cle du parcours en deux temps est revenue")
    source = pathlib.Path("klastos/app.py").read_text(encoding="utf-8")
    assert "pdf_preparer" not in source


def test_l_impression_rend_son_erreur_au_lieu_de_la_lever():
    """
    LE point subtil du cache. Une exception traversant `st.cache_data`
    n'est PAS mise en cache : un moteur defaillant serait donc relance a
    chaque reaffichage de la page, et l'ecran ramerait sans raison visible.

    `_imprimer_pdf` rend donc (octets, erreur) et ne leve rien, pour que
    l'echec soit cache comme le succes.
    """
    import inspect

    from klastos.app import _imprimer_pdf

    # La fonction est decoree : on lit la source de la fonction enveloppee.
    brute = getattr(_imprimer_pdf, "__wrapped__", _imprimer_pdf)
    source = inspect.getsource(brute)
    assert "return None, str(e)" in source, (
        "l'erreur n'est plus rendue : elle traversera le cache et le "
        "moteur sera relance a chaque reaffichage")
    assert "raise" not in source.split('"""')[-1], (
        "une exception est levee hors du cache")


def test_l_impression_est_mise_en_cache():
    """
    Sans cache, les octets seraient reproduits a CHAQUE reaffichage de la
    page - donc a chaque case cochee ailleurs dans l'ecran -, chacun
    lancant un navigateur sans tete.
    """
    source = pathlib.Path("klastos/app.py").read_text(encoding="utf-8")
    assert "@st.cache_data" in source
    debut = source.index("@st.cache_data")
    assert "def _imprimer_pdf" in source[debut:debut + 300], (
        "le cache ne porte plus sur l'impression du PDF")


@pytest.mark.skipif(
    not __import__("klastos.pdf", fromlist=["x"]).pdf_disponible(),
    reason="aucun navigateur sur cette machine")
def test_l_impression_rend_de_vrais_octets_de_pdf():
    from klastos.app import _imprimer_pdf

    html = ("<!doctype html><html><head><meta charset='utf-8'></head>"
            "<body><h1>KLASTOS21</h1></body></html>")
    octets, erreur = _imprimer_pdf(html)
    assert erreur == ""
    assert octets is not None
    assert octets[:5] == b"%PDF-", (
        "ce ne sont pas des octets de PDF : c'est exactement le defaut "
        "signale, un fichier HTML rendu sous un nom de PDF")
