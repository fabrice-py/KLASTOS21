"""Tests du schema 2 de klastos/store.py.

Deux engagements, et le second est le plus facile a perdre :

    UNE BASE EXISTANTE SE MIGRE SANS PERDRE UNE LIGNE.

    REJOUER UNE ANALYSE NE RESSORT NI LES PRIX, NI LES TAUX.

Le second n'est pas un oubli. Un prix a une date ; des prix d'il y a six
mois rejoues aujourd'hui produiraient une valorisation fausse, et le meme
raisonnement vaut mot pour mot pour un taux de change - la parite
euro-dollar a varie de 0,95 a 1,17 sur vingt-quatre mois. La tentation
naturelle, en ajoutant un historique des prix, est precisement de les
restituer « puisqu'on les a ». C'est pour cela que ce test existe.

Troisieme engagement, plus discret : AUCUNE VALEUR MONETAIRE EN FLOTTANT.
Un REAL SQLite est un double IEEE 754 ; 15432.10 n'y est pas representable
exactement, et l'ecart se voit des qu'on multiplie par une masse.
"""

import datetime as dt
import decimal
import sqlite3

import pytest

from klastos import store
from klastos.fx import ExchangeRate
from klastos.market import MetalPrice, PriceSet
from klastos.store import StoreError

LE_1ER = dt.date(2026, 10, 1)
COLLECTE = dt.date(2026, 10, 15)


def cotation(metal: str, valeur: float, le: dt.date = LE_1ER,
             source: str = "Banque mondiale",
             reference: str | None = None) -> MetalPrice:
    return MetalPrice(metal=metal, value_per_tonne=valeur, currency="USD",
                      as_of=le, source=source,
                      reference_name=reference or f"{metal} mensuel {le:%Y-%m}")


def jeu(*prix: MetalPrice) -> PriceSet:
    return PriceSet(prices={p.metal: p for p in prix}, currency="USD",
                    label="fixture")


def taux(paire: str = "EUR/USD", valeur: float = 1.0842,
         le: dt.date = LE_1ER, reference: str | None = None) -> ExchangeRate:
    return ExchangeRate(pair=paire, rate=valeur, as_of=le,
                        source="banque du client",
                        reference_name=reference or f"spot {paire} {le}")


@pytest.fixture
def cx():
    c = store.ouvrir(":memory:")
    yield c
    c.close()


# ==========================================================================
# REGLE 1. Migration sans perte, et refus d'une base plus recente.
# ==========================================================================

#: Le schema 1, tel qu'il etait. Recopie ici volontairement : une migration
#: ne se teste pas contre le schema courant, sinon on ne teste rien.
SCHEMA_V1 = """
CREATE TABLE meta (cle TEXT PRIMARY KEY, valeur TEXT NOT NULL);
CREATE TABLE lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id TEXT NOT NULL, client TEXT NOT NULL, analyse_le TEXT NOT NULL,
    emis_le TEXT, bulletin TEXT NOT NULL, elements TEXT NOT NULL,
    provenance TEXT NOT NULL, attestee INTEGER NOT NULL,
    grades_declares TEXT, tirages INTEGER NOT NULL, graine INTEGER NOT NULL,
    seuil_alerte REAL NOT NULL, seuil_rejet REAL NOT NULL,
    bouclage_statut TEXT NOT NULL, bouclage_total REAL NOT NULL,
    degenerescence INTEGER NOT NULL, devise TEXT, prix_bas REAL,
    prix_haut REAL, prix_libelle TEXT, prix_origine TEXT,
    licence_rediffusion INTEGER, destinataire TEXT NOT NULL,
    demo INTEGER NOT NULL, rapport_markdown TEXT NOT NULL
);
"""


def base_v1(chemin, lots: int = 3):
    """Une base en schema 1, avec des lignes a ne pas perdre."""
    c = sqlite3.connect(str(chemin))
    c.executescript(SCHEMA_V1)
    c.execute("INSERT INTO meta(cle, valeur) VALUES('schema', '1')")
    for i in range(lots):
        c.execute(
            "INSERT INTO lots(lot_id, client, analyse_le, bulletin, elements,"
            " provenance, attestee, tirages, graine, seuil_alerte,"
            " seuil_rejet, bouclage_statut, bouclage_total, degenerescence,"
            " destinataire, demo, rapport_markdown)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"LOT-{i:03d}", "Client historique", "2026-05-01T10:00:00",
             '{"Ni": 0.162}', '["Ni"]', "vehicule_electrique", 1, 200, 0,
             0.06, 0.20, "ok", 0.97, 2, "tiers", 0, f"# Rapport {i}"),
        )
    c.commit()
    c.close()
    return chemin


def test_une_base_v1_se_migre_sans_perdre_une_ligne(tmp_path):
    """
    LE VERROU DE LA REGLE 1. Un historique de lots est une donnee
    commerciale, sur un fichier que personne ne sauvegarde. Une migration
    qui perdrait une ligne serait irreversible.
    """
    chemin = base_v1(tmp_path / "v1.sqlite", lots=3)

    cx = store.ouvrir(chemin)
    try:
        assert cx.execute("SELECT COUNT(*) FROM lots").fetchone()[0] == 3
        lots = [r["lot_id"] for r in
                cx.execute("SELECT lot_id FROM lots ORDER BY id")]
        assert lots == ["LOT-000", "LOT-001", "LOT-002"]
        # Le contenu, pas seulement le compte.
        r = cx.execute("SELECT * FROM lots WHERE lot_id='LOT-001'").fetchone()
        assert r["client"] == "Client historique"
        assert r["rapport_markdown"] == "# Rapport 1"
    finally:
        cx.close()


def test_une_base_v1_passe_en_version_2(tmp_path):
    chemin = base_v1(tmp_path / "v1.sqlite")
    cx = store.ouvrir(chemin)
    try:
        version = cx.execute(
            "SELECT valeur FROM meta WHERE cle='schema'").fetchone()["valeur"]
        assert int(version) == store.SCHEMA_VERSION == 2
    finally:
        cx.close()


def test_la_migration_cree_les_deux_tables(tmp_path):
    chemin = base_v1(tmp_path / "v1.sqlite")
    cx = store.ouvrir(chemin)
    try:
        tables = {r[0] for r in cx.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"cotations", "taux"} <= tables
    finally:
        cx.close()


def test_la_migration_est_rejouable(tmp_path):
    """Ouvrir deux fois ne doit rien casser ni rien dupliquer."""
    chemin = base_v1(tmp_path / "v1.sqlite", lots=2)
    for _ in range(3):
        cx = store.ouvrir(chemin)
        try:
            assert cx.execute("SELECT COUNT(*) FROM lots").fetchone()[0] == 2
        finally:
            cx.close()


def test_une_base_plus_recente_que_le_code_est_toujours_refusee(tmp_path):
    """
    COMPORTEMENT A GARDER. Une version ulterieure pourrait avoir ajoute une
    colonne dont l'absence fausserait silencieusement une relecture.
    """
    chemin = base_v1(tmp_path / "futur.sqlite")
    c = sqlite3.connect(str(chemin))
    c.execute("UPDATE meta SET valeur='99' WHERE cle='schema'")
    c.commit()
    c.close()

    with pytest.raises(StoreError, match="schema 99"):
        store.ouvrir(chemin)


def test_une_base_neuve_nait_en_version_2(cx):
    version = cx.execute(
        "SELECT valeur FROM meta WHERE cle='schema'").fetchone()["valeur"]
    assert int(version) == 2


# ==========================================================================
# REGLE 2. refaire() ne restaure ni prix, ni taux.
# ==========================================================================

@pytest.fixture
def analyse_enregistree(cx):
    """Une analyse valorisee et convertie, rangee dans l'historique."""
    import pathlib

    from klastos.fx import convertir
    from klastos.market import PayableTerms
    from klastos.service import Demande, analyser

    racine = pathlib.Path(__file__).resolve().parent.parent
    bulletin = racine / "data" / "exemples" / "bulletin_coherent.csv"
    if not bulletin.exists():
        pytest.skip("bulletin d'exemple absent")

    le = dt.date(2026, 9, 7)
    prix = PriceSet(
        prices={m: MetalPrice(m, v, "USD", le, "fixture", f"{m} ref")
                for m, v in (("Ni", 15_000.0), ("Co", 24_000.0),
                             ("Li", 11_000.0))},
        currency="USD", label="fixture", is_production_source=True,
        origin="fixture")
    termes = PayableTerms(
        market="essai", payables={"Ni": 0.7, "Co": 0.7, "Li": 0.4},
        as_of=le, source="fixture", validated=True)

    analyse = analyser(Demande(
        bulletin=bulletin, lot_id="LOT-FX", provenance="vehicule_electrique",
        attestee=True, tirages=20, graine=0, emis_le=le, termes=termes,
        prix=convertir(prix, "EUR",
                       ExchangeRate("EUR/USD", 1.0842, le, "banque", "spot"),
                       aujourdhui=le),
        devise_cible=None))
    return cx, store.enregistrer(cx, analyse)


def test_refaire_ne_restaure_pas_les_prix(analyse_enregistree):
    """
    CE N'EST PAS UN OUBLI. Des prix d'il y a six mois rejoues aujourd'hui
    produiraient une valorisation fausse. Le comportement existait avant le
    schema 2 et doit lui survivre.
    """
    cx, entree_id = analyse_enregistree
    demande = store.refaire(cx, entree_id)
    assert demande.prix is None
    assert demande.termes is None


def test_refaire_ne_restaure_pas_les_taux_de_change(analyse_enregistree):
    """
    L'EXTENSION DE LA MEME DOCTRINE. La parite euro-dollar a varie de 0,95 a
    1,17 sur vingt-quatre mois : un taux de mai rejoue en novembre est aussi
    faux qu'un prix de mai.

    La tentation, en ajoutant un historique des taux, est de les restituer
    « puisqu'on les a ». Ce test l'interdit.
    """
    cx, entree_id = analyse_enregistree
    demande = store.refaire(cx, entree_id)
    assert demande.devise_cible is None
    assert demande.taux is None


def test_refaire_restitue_bien_ce_qui_ne_perime_pas(analyse_enregistree):
    """La contrepartie : tout ce qui ne depend pas d'une date revient."""
    cx, entree_id = analyse_enregistree
    demande = store.refaire(cx, entree_id)
    assert demande.lot_id == "LOT-FX"
    assert demande.provenance == "vehicule_electrique"
    assert demande.attestee is True
    assert demande.graine == 0
    assert demande.tirages == 20


def test_la_doctrine_est_ecrite_dans_la_docstring():
    """
    Un comportement contre-intuitif non ecrit se fait « corriger » par le
    releveur suivant. La raison doit vivre a cote du code.
    """
    assert store.refaire.__doc__
    doc = store.refaire.__doc__.lower()
    assert "ni les prix, ni les taux" in doc
    assert "ce n'est pas" in doc


# ==========================================================================
# REGLE 3. Unicite, et aucune valeur monetaire en flottant.
# ==========================================================================

def test_une_cotation_est_rangee_avec_ses_deux_dates(cx):
    """
    Date de COTATION et date de COLLECTE ne se confondent pas : une moyenne
    mensuelle d'octobre relevee le 15 novembre est cotee au 1er octobre.
    Les confondre ferait passer un releve tardif pour une donnee fraiche.
    """
    assert store.enregistrer_cotations(cx, jeu(cotation("Ni", 15_432.10)),
                                       COLLECTE) == 1
    c = store.prix_a_la_date(cx, "Ni", "2026-10-31")
    assert c.cote_le == LE_1ER
    assert c.collecte_le == COLLECTE


def test_le_meme_releve_deux_fois_ne_cree_pas_de_doublon(cx):
    """
    LE VERROU DE L'UNICITE. Un historique qui compterait deux fois la meme
    cotation fausserait toute serie construite dessus - une moyenne, une
    tendance, un ecart type.
    """
    p = jeu(cotation("Ni", 15_432.10))
    assert store.enregistrer_cotations(cx, p, COLLECTE) == 1
    assert store.enregistrer_cotations(cx, p, COLLECTE) == 0
    assert store.enregistrer_cotations(cx, p, dt.date(2026, 11, 1)) == 0
    assert cx.execute("SELECT COUNT(*) FROM cotations").fetchone()[0] == 1


def test_deux_dates_de_cotation_font_deux_lignes(cx):
    store.enregistrer_cotations(cx, jeu(cotation("Ni", 15_000.0, LE_1ER)),
                                COLLECTE)
    store.enregistrer_cotations(
        cx, jeu(cotation("Ni", 15_900.0, dt.date(2026, 11, 1))), COLLECTE)
    assert cx.execute("SELECT COUNT(*) FROM cotations").fetchone()[0] == 2


def test_deux_metaux_sur_la_meme_reference_levent(cx):
    """
    La contrainte d'unicite porte sur (source, reference, date), donc un
    libelle de reference doit etre propre a un metal. Si un fournisseur
    reutilise le meme libelle, on LEVE au lieu d'en perdre un en silence :
    une cotation manquante dans une serie est invisible.
    """
    store.enregistrer_cotations(
        cx, jeu(cotation("Ni", 15_000.0, reference="indice unique")), COLLECTE)
    with pytest.raises(StoreError, match="partager une reference"):
        store.enregistrer_cotations(
            cx, jeu(cotation("Cu", 8_700.0, reference="indice unique")),
            COLLECTE)


def test_aucune_valeur_monetaire_n_est_stockee_en_flottant(cx):
    """
    LE VERROU DE LA REGLE 3. Un REAL SQLite est un double IEEE 754 :
    15432.10 n'y est pas representable exactement, et une relecture peut
    rendre 15432.099999999999. Sur un prix a la tonne multiplie par une
    masse, l'ecart se voit.
    """
    store.enregistrer_cotations(cx, jeu(cotation("Ni", 15_432.10)), COLLECTE)
    store.enregistrer_taux(cx, taux(), COLLECTE)

    for table in ("cotations", "taux"):
        types = {r["name"]: r["type"].upper() for r in
                 cx.execute(f"PRAGMA table_info({table})")}
        assert types["valeur"] == "TEXT", (table, types["valeur"])
        assert "REAL" not in types.values(), (table, types)

    # Et le type Python reellement stocke, pas seulement la declaration.
    for table in ("cotations", "taux"):
        brut = cx.execute(f"SELECT valeur FROM {table}").fetchone()["valeur"]
        assert isinstance(brut, str), (table, type(brut))


def test_la_valeur_relue_est_exacte(cx):
    """Chiffre pour chiffre : c'est tout l'objet du stockage en texte."""
    store.enregistrer_cotations(cx, jeu(cotation("Ni", 15_432.10)), COLLECTE)
    c = store.prix_a_la_date(cx, "Ni", "2026-10-31")
    assert isinstance(c.valeur, decimal.Decimal)
    assert c.valeur == decimal.Decimal("15432.1")
    assert not isinstance(c.valeur, float)


def test_un_taux_relu_est_exact(cx):
    store.enregistrer_taux(cx, taux(valeur=1.0842), COLLECTE)
    t = store.taux_a_la_date(cx, "EUR/USD", "2026-10-31")
    assert t.valeur == decimal.Decimal("1.0842")


def test_une_valeur_non_decimale_est_refusee(cx):
    mauvais = MetalPrice("Ni", "quinze mille", "USD", LE_1ER, "s", "r")
    with pytest.raises(StoreError, match="non decimale"):
        store.enregistrer_cotations(cx, jeu(mauvais), COLLECTE)


def test_un_taux_est_range_avec_sa_source_et_ses_deux_dates(cx):
    assert store.enregistrer_taux(cx, taux(), COLLECTE) == 1
    t = store.taux_a_la_date(cx, "EUR/USD", "2026-10-31")
    assert t.source == "banque du client"
    assert t.cote_le == LE_1ER
    assert t.collecte_le == COLLECTE
    assert t.reference


def test_plusieurs_taux_se_rangent_en_un_appel(cx):
    lot = [taux("EUR/USD", 1.0842), taux("GBP/USD", 1.2715)]
    assert store.enregistrer_taux(cx, lot, COLLECTE) == 2


# ==========================================================================
# Les deux requetes neuves
# ==========================================================================

@pytest.fixture
def serie(cx):
    """Trois mois de cotations, pour interroger."""
    for mois, valeur in ((8, 14_000.0), (9, 15_000.0), (10, 15_432.10)):
        store.enregistrer_cotations(
            cx, jeu(cotation("Ni", valeur, dt.date(2026, mois, 1))),
            dt.date(2026, mois, 15))
    return cx


def test_le_prix_a_une_date_rend_la_cotation_de_cette_date(serie):
    c = store.prix_a_la_date(serie, "Ni", dt.date(2026, 9, 1))
    assert c.valeur == decimal.Decimal("15000.0")


def test_le_prix_a_une_date_rend_la_plus_recente_avant(serie):
    """
    « Que valait le nickel le 15 octobre » doit avoir une reponse meme si la
    source ne cote qu'une fois par mois. Rendre None au jour pres
    obligerait l'appelant a refaire cette recherche, et il la referait
    moins bien.
    """
    c = store.prix_a_la_date(serie, "Ni", dt.date(2026, 10, 20))
    assert c.cote_le == dt.date(2026, 10, 1)
    assert c.valeur == decimal.Decimal("15432.1")


def test_le_prix_avant_toute_cotation_rend_none(serie):
    """Un resultat, pas une erreur, et surtout pas un zero."""
    assert store.prix_a_la_date(serie, "Ni", dt.date(2026, 1, 1)) is None


def test_un_metal_jamais_cote_rend_none(serie):
    assert store.prix_a_la_date(serie, "Co", dt.date(2026, 10, 20)) is None


def test_la_serie_est_rendue_par_date_croissante(serie):
    lignes = store.serie_prix(serie, "Ni", "2026-08-01", "2026-10-31")
    assert [c.cote_le.month for c in lignes] == [8, 9, 10]
    assert [c.valeur for c in lignes] == [decimal.Decimal("14000.0"),
                                          decimal.Decimal("15000.0"),
                                          decimal.Decimal("15432.1")]


def test_les_bornes_de_la_serie_sont_incluses(serie):
    lignes = store.serie_prix(serie, "Ni", "2026-09-01", "2026-10-01")
    assert [c.cote_le.month for c in lignes] == [9, 10]


def test_une_periode_sans_cotation_rend_une_liste_vide(serie):
    """« Ce fournisseur n'a rien cote en janvier » est une reponse."""
    assert store.serie_prix(serie, "Ni", "2026-01-01", "2026-01-31") == []


def test_une_periode_inversee_est_refusee(serie):
    with pytest.raises(StoreError, match="inversee"):
        store.serie_prix(serie, "Ni", "2026-10-31", "2026-08-01")


def test_la_serie_peut_etre_filtree_par_source(cx):
    store.enregistrer_cotations(
        cx, jeu(cotation("Ni", 15_000.0, source="Banque mondiale")), COLLECTE)
    store.enregistrer_cotations(
        cx, jeu(cotation("Ni", 15_100.0, source="agence X",
                         reference="autre indice")), COLLECTE)
    toutes = store.serie_prix(cx, "Ni", "2026-10-01", "2026-10-31")
    assert len(toutes) == 2
    une = store.serie_prix(cx, "Ni", "2026-10-01", "2026-10-31",
                           source="agence X")
    assert [c.source for c in une] == ["agence X"]


def test_la_serie_des_taux_fonctionne_de_meme(cx):
    for mois, valeur in ((9, 1.08), (10, 1.0842)):
        store.enregistrer_taux(cx, taux("EUR/USD", valeur,
                                        dt.date(2026, mois, 1)), COLLECTE)
    lignes = store.serie_taux(cx, "EUR/USD", "2026-09-01", "2026-10-31")
    assert [t.cote_le.month for t in lignes] == [9, 10]
    assert lignes[-1].valeur == decimal.Decimal("1.0842")


def test_la_paire_est_normalisee_a_la_lecture(cx):
    store.enregistrer_taux(cx, taux("EUR/USD"), COLLECTE)
    assert store.taux_a_la_date(cx, "eur/usd", "2026-10-31") is not None


# ==========================================================================
# Integration avec le reste de la chaine
# ==========================================================================

def test_un_jeu_pink_sheet_se_range_tel_quel(cx, tmp_path):
    """
    L'historique doit avaler ce que les fournisseurs produisent, sans
    adaptateur : sinon chaque nouvelle source demanderait du code ici.
    """
    openpyxl = pytest.importorskip("openpyxl")
    from test_pink_sheet import classeur  # fixture de l'autre module

    from klastos.providers import PinkSheetProvider

    jeu_ps = PinkSheetProvider(classeur(tmp_path / "ps.xlsx")).fetch()
    assert store.enregistrer_cotations(cx, jeu_ps, COLLECTE) == 3
    c = store.prix_a_la_date(cx, "Ni", "2026-10-31")
    assert "Banque mondiale" in c.source
    assert "moyenne mensuelle" in c.reference.lower()


def test_un_jeu_converti_se_range_dans_sa_devise_cible(cx):
    """La conversion ayant eu lieu, c'est le prix en euros qu'on archive."""
    from klastos.fx import convertir

    source = PriceSet(
        prices={"Ni": cotation("Ni", 15_000.0)}, currency="USD",
        label="fixture", is_production_source=True)
    converti = convertir(source, "EUR", taux(), aujourdhui=LE_1ER)
    store.enregistrer_cotations(cx, converti, COLLECTE)
    c = store.prix_a_la_date(cx, "Ni", "2026-10-31")
    assert c.devise == "EUR"
