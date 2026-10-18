"""Tests de klastos/store.py.

L'historique sert a trois choses, et chacune est une exigence de test :

  1. RETROUVER un lot analyse il y a six mois.
  2. RESSORTIR le rapport tel qu'il a ete emis, sans recalcul - c'est le
     document que le client a recu, pas une reconstitution approchante.
  3. REFAIRE l'analyse a l'identique quand un chiffre est conteste.

Une quatrieme exigence, negative, compte autant : l'historique ne doit pas
restituer de prix perimes comme s'ils etaient d'aujourd'hui.
"""

import datetime as dt
import json
import pathlib
import sqlite3

import pytest

from klastos import store
from klastos.market import MetalPrice, PayableTerms, PriceSet
from klastos.report import DESTINATAIRE_INTERNE
from klastos.service import Demande, analyser, charger_prix

RACINE = pathlib.Path(__file__).resolve().parent.parent
BULLETIN = RACINE / "data" / "exemples" / "bulletin_coherent.csv"
PRIX_CSV = RACINE / "data" / "prix_client_exemple.csv"
AUJ = dt.date(2026, 9, 7)

TERMES = PayableTerms(market="test", payables={"Ni": 0.72, "Co": 0.72},
                      as_of=AUJ, source="contrat client", validated=True)

PRIX_AGENCE = PriceSet(
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


@pytest.fixture(autouse=True)
def _bulletin_present():
    if not BULLETIN.exists():
        pytest.skip("bulletin d'exemple absent")


@pytest.fixture
def cx():
    c = store.ouvrir(":memory:")
    yield c
    c.close()


def _analyse(**kw):
    base = dict(bulletin=BULLETIN, provenance="vehicule_electrique",
                attestee=True, lot_id="2026-RA-00117", client="Negociant",
                tirages=25, graine=0, emis_le=AUJ)
    base.update(kw)
    return analyser(Demande(**base))


@pytest.fixture(scope="module")
def analyse_valorisee():
    return analyser(Demande(
        bulletin=BULLETIN, provenance="vehicule_electrique", attestee=True,
        lot_id="2026-RA-00117", client="Negociant", tirages=25, graine=0,
        emis_le=AUJ, prix=charger_prix(PRIX_CSV), termes=TERMES))


# ==========================================================================
# 1. Ouverture et schema
# ==========================================================================

def test_une_base_neuve_s_ouvre_et_se_cree(tmp_path):
    chemin = tmp_path / "sous" / "dossier" / "h.sqlite"
    c = store.ouvrir(chemin)
    assert chemin.exists()
    c.close()


def test_le_schema_est_versionne(cx):
    v = cx.execute("SELECT valeur FROM meta WHERE cle='schema'").fetchone()
    assert int(v["valeur"]) == store.SCHEMA_VERSION


def test_une_base_plus_recente_que_le_code_est_refusee(tmp_path):
    """
    Une version ulterieure peut avoir ajoute une colonne dont l'absence
    fausserait silencieusement une relecture. Mieux vaut refuser.
    """
    chemin = tmp_path / "h.sqlite"
    c = store.ouvrir(chemin)
    c.execute("UPDATE meta SET valeur = ? WHERE cle='schema'",
              (str(store.SCHEMA_VERSION + 1),))
    c.commit()
    c.close()
    with pytest.raises(store.StoreError, match="schema"):
        store.ouvrir(chemin)


def test_rouvrir_une_base_existante_ne_l_efface_pas(tmp_path, analyse_valorisee):
    chemin = tmp_path / "h.sqlite"
    c = store.ouvrir(chemin)
    store.enregistrer(c, analyse_valorisee)
    c.close()
    c2 = store.ouvrir(chemin)
    assert len(store.lister(c2)) == 1
    c2.close()


# ==========================================================================
# 2. Retrouver
# ==========================================================================

def test_une_analyse_enregistree_se_retrouve(cx, analyse_valorisee):
    i = store.enregistrer(cx, analyse_valorisee)
    entrees = store.lister(cx)
    assert len(entrees) == 1
    e = entrees[0]
    assert e.id == i
    assert e.lot_id == "2026-RA-00117"
    assert e.client == "Negociant"


def test_le_plus_recent_sort_en_premier(cx, analyse_valorisee):
    base = dt.datetime(2026, 9, 1, 10, 0, 0)
    for n, jours in enumerate((0, 5, 2)):
        store.enregistrer(cx, analyse_valorisee,
                          analyse_le=base + dt.timedelta(days=jours))
    dates = [e.analyse_le for e in store.lister(cx)]
    assert dates == sorted(dates, reverse=True)


def test_le_filtre_par_lot_ne_rend_que_ce_lot(cx, analyse_valorisee):
    store.enregistrer(cx, analyse_valorisee)
    store.enregistrer(cx, _analyse(lot_id="AUTRE-01"))
    assert [e.lot_id for e in store.lister(cx, lot_id="AUTRE-01")] == ["AUTRE-01"]


def test_la_limite_est_respectee(cx, analyse_valorisee):
    for _ in range(5):
        store.enregistrer(cx, analyse_valorisee)
    assert len(store.lister(cx, limite=3)) == 3


def test_une_base_vide_rend_une_liste_vide(cx):
    assert store.lister(cx) == []


# ==========================================================================
# 3. Ressortir le rapport emis, sans recalcul
# ==========================================================================

def test_le_rapport_ressort_mot_pour_mot(cx, analyse_valorisee):
    i = store.enregistrer(cx, analyse_valorisee)
    assert store.rapport(cx, i) == analyse_valorisee.rapport.to_markdown()


def test_un_identifiant_inconnu_est_une_erreur_claire(cx):
    with pytest.raises(store.StoreError, match="Aucune analyse"):
        store.rapport(cx, 999)


def test_le_diagnostic_de_bouclage_est_conserve(cx, analyse_valorisee):
    store.enregistrer(cx, analyse_valorisee)
    e = store.lister(cx)[0]
    bouclage = analyse_valorisee.incertitude.meta["closure"]
    assert e.bouclage_statut == bouclage.status
    assert e.bouclage_total == pytest.approx(bouclage.total)


def test_la_degenerescence_est_conservee(cx, analyse_valorisee):
    store.enregistrer(cx, analyse_valorisee)
    assert (store.lister(cx)[0].degenerescence
            == analyse_valorisee.incertitude.degeneracy)


# ==========================================================================
# 4. Refaire a l'identique
# ==========================================================================

def test_la_demande_rejouee_redonne_les_memes_teneurs(cx, analyse_valorisee):
    i = store.enregistrer(cx, analyse_valorisee)
    rejoue = analyser(store.refaire(cx, i))
    assert (rejoue.lecture.measured_elements
            == analyse_valorisee.lecture.measured_elements)
    assert rejoue.lecture.b == pytest.approx(analyse_valorisee.lecture.b,
                                             abs=1e-9)


def test_la_reconstitution_rejouee_est_identique(cx, analyse_valorisee):
    """
    Meme graine, memes seuils, meme provenance : les grandeurs fermes
    doivent ressortir au caractere pres. Sinon « refaire » ne veut rien dire.
    """
    i = store.enregistrer(cx, analyse_valorisee)
    rejoue = analyser(store.refaire(cx, i))
    avant = analyse_valorisee.rapport.section("Grandeurs fermes")
    apres = rejoue.rapport.section("Grandeurs fermes")
    assert [(r.label, r.value, r.status) for r in apres.rows] == \
           [(r.label, r.value, r.status) for r in avant.rows]


def test_la_provenance_et_l_attestation_sont_rejouees(cx):
    a = _analyse(attestee=False)
    i = store.enregistrer(cx, a)
    d = store.refaire(cx, i)
    assert d.provenance == "vehicule_electrique"
    assert d.attestee is False
    assert analyser(d).phases_exclues == []


def test_les_seuils_et_la_graine_sont_rejoues(cx, analyse_valorisee):
    i = store.enregistrer(cx, analyse_valorisee)
    d = store.refaire(cx, i)
    assert d.graine == 0
    assert d.tirages == 25
    assert d.seuil_alerte == analyse_valorisee.demande.seuil_alerte
    assert d.seuil_rejet == analyse_valorisee.demande.seuil_rejet


def test_la_demande_rejouee_ne_porte_aucun_prix(cx, analyse_valorisee):
    """
    EXIGENCE NEGATIVE. Restituer les prix d'un lot de septembre pour
    valoriser en octobre fabriquerait un chiffre faux d'apparence
    irreprochable. L'historique rend de quoi refaire la RECONSTITUTION ;
    les prix du jour sont au seul appelant.
    """
    i = store.enregistrer(cx, analyse_valorisee)
    d = store.refaire(cx, i)
    assert d.prix is None
    assert d.termes is None
    assert analyser(d).valorisation is None


def test_refaire_un_identifiant_inconnu_est_une_erreur_claire(cx):
    with pytest.raises(store.StoreError, match="Aucune analyse"):
        store.refaire(cx, 999)


# ==========================================================================
# 5. Ce que la valorisation laisse comme trace
# ==========================================================================

def test_la_fourchette_est_conservee(cx, analyse_valorisee):
    store.enregistrer(cx, analyse_valorisee)
    e = store.lister(cx)[0]
    v = analyse_valorisee.valorisation
    assert e.valorise
    assert e.prix_bas == pytest.approx(v.max_price_low)
    assert e.prix_haut == pytest.approx(v.max_price_high)
    assert e.devise == v.currency
    assert "USD/t" in e.fourchette()


def test_un_lot_non_valorise_le_dit(cx):
    store.enregistrer(cx, _analyse())
    e = store.lister(cx)[0]
    assert not e.valorise
    assert e.fourchette() == "sans valorisation"


def test_la_licence_de_rediffusion_est_tracee(cx):
    """
    Savoir six mois plus tard si un rapport pouvait legalement partir chez
    un client fait partie de ce qu'un historique doit retenir.
    """
    a = analyser(Demande(
        bulletin=BULLETIN, provenance="vehicule_electrique", attestee=True,
        lot_id="L", tirages=20, emis_le=AUJ, prix=PRIX_AGENCE, termes=TERMES,
        destinataire=DESTINATAIRE_INTERNE))
    store.enregistrer(cx, a)
    e = store.lister(cx)[0]
    assert e.licence_rediffusion is False
    assert e.destinataire == DESTINATAIRE_INTERNE


def test_l_origine_des_prix_est_tracee(cx):
    a = analyser(Demande(
        bulletin=BULLETIN, provenance="vehicule_electrique", attestee=True,
        lot_id="L", tirages=20, emis_le=AUJ, prix=PRIX_AGENCE, termes=TERMES,
        destinataire=DESTINATAIRE_INTERNE))
    i = store.enregistrer(cx, a)
    r = cx.execute("SELECT prix_origine, prix_libelle FROM lots WHERE id=?",
                   (i,)).fetchone()
    assert r["prix_origine"] == "fastmarkets"
    assert "fastmarkets" in r["prix_libelle"]


def test_un_document_de_demonstration_est_marque_comme_tel(cx):
    from klastos.market import demo_payable_terms, demo_price_set

    a = analyser(Demande(
        bulletin=BULLETIN, provenance="vehicule_electrique", attestee=True,
        lot_id="L", tirages=20, emis_le=AUJ, prix=demo_price_set(),
        termes=demo_payable_terms()["cif_coree_sud"], autoriser_demo=True))
    store.enregistrer(cx, a)
    assert store.lister(cx)[0].demo is True


# ==========================================================================
# 6. Suppression
# ==========================================================================

def test_une_entree_se_supprime(cx, analyse_valorisee):
    i = store.enregistrer(cx, analyse_valorisee)
    assert store.supprimer(cx, i) is True
    assert store.lister(cx) == []


def test_supprimer_ce_qui_n_existe_pas_rend_faux(cx):
    assert store.supprimer(cx, 999) is False


# ==========================================================================
# 7. Independance du module
# ==========================================================================

def test_le_store_n_importe_aucune_interface():
    import ast

    arbre = ast.parse(
        (RACINE / "klastos" / "store.py").read_text(encoding="utf-8"))
    importes = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            importes |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            importes.add(n.module.split(".")[0])
    assert not (importes & {"streamlit", "argparse"}), importes


def test_le_bulletin_est_stocke_en_json_relisible(cx, analyse_valorisee):
    i = store.enregistrer(cx, analyse_valorisee)
    r = cx.execute("SELECT bulletin, elements FROM lots WHERE id=?",
                   (i,)).fetchone()
    teneurs = json.loads(r["bulletin"])
    elements = json.loads(r["elements"])
    assert set(elements) <= set(teneurs)
    assert all(isinstance(v, float) for v in teneurs.values())