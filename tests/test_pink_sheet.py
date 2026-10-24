"""Tests de PinkSheetProvider (klastos/providers.py).

Le Pink Sheet rend KLASTOS21 demontrable SANS AUCUN ABONNEMENT d'agence. Il
porte donc un engagement que n'a aucun autre flux :

    LA DONNEE EST PUBLIQUE ET REDIFFUSABLE AVEC ATTRIBUTION.

Et deux limites qu'il ne faut jamais laisser oublier :

    IL NE COTE QUE TROIS METAUX, ET CE SONT DES MOYENNES MENSUELLES.

Le cobalt et le lithium - ou se joue l'essentiel de la valeur d'une black
mass - n'y figurent pas. Les demander doit donner une adresse, pas un zero :
un cobalt a zero traverserait toute la chaine sans qu'aucun controle le
refuse, et sortirait en valorisation.

Aucune vraie cotation ici. Le classeur est CONSTRUIT par le test, reduit a
ce que le lecteur doit savoir lire, et ses valeurs sont choisies pour etre
reconnaissables dans un message d'erreur.
"""

import datetime as dt
import pathlib

import pytest

openpyxl = pytest.importorskip("openpyxl", reason="openpyxl non installe")

from klastos.market import MissingPriceError  # noqa: E402
from klastos.providers import (PINK_SHEET_ATTRIBUTION,  # noqa: E402
                               PINK_SHEET_METAUX, PINK_SHEET_URL,
                               PinkSheetProvider, ProviderError)

RACINE = pathlib.Path(__file__).resolve().parent.parent

#: Valeurs de fixture, volontairement non realistes mais plausibles : elles
#: doivent passer les bandes de `units.py` sans etre confondues avec de
#: vraies cotations si elles fuitaient dans un rapport.
FIXTURE = {"Aluminum": 2_345.67, "Copper": 8_765.43, "Nickel": 15_432.10}


def classeur(
    chemin: pathlib.Path,
    *,
    feuille: str = "Monthly Prices",
    unites: str | None = "($/mt)",
    colonnes: dict[str, float] | None = None,
    mois: list[str] | None = None,
    trous: dict[str, str] | None = None,
) -> pathlib.Path:
    """
    Construit un classeur reduit, au format du Pink Sheet reel.

    Disposition reproduite : deux lignes de titre, une ligne d'en-tetes de
    serie, une ligne d'unites, puis les periodes « AAAAMnn » en premiere
    colonne. C'est le minimum que le lecteur doit savoir traverser.
    """
    from openpyxl import Workbook

    colonnes = FIXTURE if colonnes is None else colonnes
    mois = mois or ["2026M09", "2026M10"]

    wb = Workbook()
    ws = wb.active
    ws.title = feuille
    ws.append(["World Bank Commodity Price Data (The Pink Sheet)"])
    ws.append([f"Monthly prices - {PINK_SHEET_ATTRIBUTION}"])
    ws.append(["", *colonnes.keys()])
    if unites is not None:
        ws.append(["", *([unites] * len(colonnes))])
    for i, periode in enumerate(mois):
        ligne = [periode]
        for nom, valeur in colonnes.items():
            if trous and trous.get(periode) == nom:
                ligne.append(None)
            else:
                # Un leger decalage par mois, pour distinguer les lignes.
                ligne.append(round(valeur * (1 + 0.01 * i), 2))
        ws.append(ligne)
    wb.save(chemin)
    return chemin


@pytest.fixture
def xlsx(tmp_path) -> pathlib.Path:
    return classeur(tmp_path / "pink.xlsx")


# ==========================================================================
# REGLE 1. Exactement trois metaux. Les autres donnent une adresse.
# ==========================================================================

def test_il_couvre_exactement_trois_metaux():
    """Verifie sur l'edition d'octobre 2026 : aluminium, cuivre, nickel."""
    assert set(PINK_SHEET_METAUX) == {"Al", "Cu", "Ni"}


def test_les_trois_metaux_sont_cotes(xlsx):
    cotations = {q.metal: q for q in PinkSheetProvider(xlsx).quotes()}
    assert set(cotations) == {"Al", "Cu", "Ni"}
    assert cotations["Ni"].value == pytest.approx(15_432.10 * 1.01)


@pytest.mark.parametrize("metal,nom", [
    ("Co", "cobalt"),
    ("Li", "lithium"),
    ("Mn", "manganese"),
    ("C", "graphite"),
])
def test_un_metal_absent_leve_avec_l_adresse_ou_le_trouver(xlsx, metal, nom):
    """
    LE VERROU DE LA REGLE 1. Un zero rendu ici traverserait la chaine sans
    qu'aucun controle le refuse : la bande de plausibilite ne voit pas un
    metal manquant, elle voit une valeur. Le refus doit donc arriver ici, et
    dire ou chercher.
    """
    with pytest.raises(MissingPriceError) as exc:
        PinkSheetProvider(xlsx).quotes([metal])

    # Le message se lit tel quel. `MissingPriceError` derive de `KeyError`,
    # dont le `__str__` entourait le message de guillemets : la ligne de
    # commande affichait « prix manquant : "cobalt (Co) absent..." ». La
    # classe surcharge desormais `__str__`, et aucun contournement n'est
    # necessaire ici.
    message = str(exc.value)

    # Le metal est NOMME, et son symbole entre parentheses : c'est la
    # formulation de la branche dediee. Une premiere version de ce test se
    # contentait de chercher « cobalt » dans le message - mais le texte
    # generique nomme deja les quatre metaux absents, si bien que le test
    # passait meme quand la branche dediee etait desactivee. Verifie par
    # mutation.
    assert f"{nom} ({metal})" in message, message
    assert message.startswith(nom), message

    # Il nomme des sources alternatives, pas seulement l'absence.
    assert "Fastmarkets" in message or "agence" in message

    # Cette assertion exigeait « gre a gre », parce que le message affirmait
    # que ces quatre metaux etaient « des marches de gre a gre, SANS
    # COTATION DE BOURSE ». C'etait vrai a l'ecriture et ne l'est plus : le
    # CME, le LME et le GFEX listent des contrats cobalt et lithium depuis
    # 2023. Le test figeait donc une affirmation devenue fausse, et il
    # aurait empeche de la corriger.
    #
    # Ce qui compte n'a pas change : le message doit donner une ADRESSE. Il
    # en donne trois, par cout croissant, et la plus interessante est
    # gratuite.
    assert "klastos usgs" in message, (
        "le message doit nommer la route gratuite, sinon un operateur sans "
        "abonnement reste bloque")
    assert "licenciee" in message, (
        "la distinction entre consulter et rediffuser doit etre dite : "
        "c'est elle qui decide si un chiffre peut figurer dans un rapport "
        "client")


def test_le_cobalt_ne_rend_jamais_zero(xlsx):
    """
    Formulation directe de l'exigence : jamais de valeur par defaut. Un
    cobalt a zero sortirait en valorisation comme un lot sans cobalt.
    """
    with pytest.raises(MissingPriceError):
        PinkSheetProvider(xlsx).quotes(["Ni", "Co"])


def test_un_metal_inconnu_est_aussi_refuse(xlsx):
    with pytest.raises(MissingPriceError, match="Zz"):
        PinkSheetProvider(xlsx).quotes(["Zz"])


# ==========================================================================
# REGLE 2. Moyennes mensuelles, pas des evaluations spot.
# ==========================================================================

def test_ce_n_est_pas_une_source_de_production(xlsx):
    """
    Une moyenne d'octobre ne s'oppose pas a une cargaison du 21 octobre.
    `value_lot` refusera donc ce jeu sans `allow_stale`, et c'est voulu.
    """
    assert PinkSheetProvider.is_production_source is False
    jeu = PinkSheetProvider(xlsx).fetch()
    assert jeu.is_production_source is False


def test_le_mois_utilise_figure_dans_la_reference(xlsx):
    """
    LE VERROU DE LA REGLE 2. Sans le mois, une moyenne mensuelle se lit
    comme une cotation du jour - et c'est precisement ce qu'il ne faut
    jamais laisser passer.
    """
    for q in PinkSheetProvider(xlsx).quotes():
        assert "2026-10" in q.reference_name
        assert "moyenne mensuelle" in q.reference_name.lower()


def test_la_note_dit_que_ce_n_est_pas_du_spot(xlsx):
    for q in PinkSheetProvider(xlsx).quotes():
        assert "MOYENNE MENSUELLE" in q.note
        assert "spot" in q.note


def test_la_date_est_le_premier_jour_du_mois(xlsx):
    """
    Une moyenne mensuelle n'a pas de jour. Lui en inventer un - le 31, le
    jour de la lecture - la ferait passer pour un releve ponctuel.
    """
    for q in PinkSheetProvider(xlsx).quotes():
        assert q.as_of == dt.date(2026, 10, 1)


def test_le_libelle_du_jeu_porte_le_mois(xlsx):
    jeu = PinkSheetProvider(xlsx).fetch()
    assert "2026-10" in jeu.label
    assert "mensuelle" in jeu.label.lower()


def test_un_mois_precis_peut_etre_demande(xlsx):
    cotations = PinkSheetProvider(xlsx, mois="2026M09").quotes()
    assert all(q.as_of == dt.date(2026, 9, 1) for q in cotations)
    assert cotations[0].value == pytest.approx(FIXTURE["Aluminum"])


def test_un_mois_absent_est_refuse_bruyamment(xlsx):
    with pytest.raises(ProviderError, match="2026M01"):
        PinkSheetProvider(xlsx, mois="2026M01").quotes()


def test_le_dernier_mois_complet_est_retenu_par_defaut(tmp_path):
    """Un mois partiellement renseigne ne doit pas eclipser le precedent."""
    f = classeur(tmp_path / "trou.xlsx",
                 mois=["2026M09", "2026M10", "2026M11"],
                 trous={"2026M11": "Nickel"})
    cotations = PinkSheetProvider(f).quotes()
    assert all(q.as_of == dt.date(2026, 10, 1) for q in cotations)


# ==========================================================================
# REGLE 3. Attribution portee dans la provenance et le rapport.
# ==========================================================================

def test_l_attribution_est_celle_exigee_par_la_licence():
    assert PINK_SHEET_ATTRIBUTION == (
        "Banque mondiale, Commodity Price Data (Pink Sheet)")


def test_chaque_cotation_porte_l_attribution(xlsx):
    for q in PinkSheetProvider(xlsx).quotes():
        assert q.source == PINK_SHEET_ATTRIBUTION
        assert PINK_SHEET_ATTRIBUTION in q.note


def test_l_attribution_remonte_jusqu_au_rapport(xlsx):
    """
    C'EST LA CONTREPARTIE DE LA GRATUITE. Une attribution qui mourrait dans
    le fournisseur ne vaudrait rien : elle doit se lire sur le document
    remis au client.
    """
    import datetime as _dt

    from klastos.market import PayableTerms
    from klastos.service import Demande, analyser

    bulletin = RACINE / "data" / "exemples" / "bulletin_coherent.csv"
    if not bulletin.exists():
        pytest.skip("bulletin d'exemple absent")

    jeu = PinkSheetProvider(xlsx).fetch()
    termes = PayableTerms(
        market="essai", payables={"Ni": 0.7, "Cu": 0.0, "Al": 0.0},
        as_of=_dt.date(2026, 10, 1), source="fixture", validated=True)
    analyse = analyser(Demande(
        bulletin=bulletin, provenance="vehicule_electrique", attestee=True,
        tirages=20, graine=0, emis_le=_dt.date(2026, 10, 15),
        prix=jeu, termes=termes,
        # Moyennes mensuelles : le jeu n'est pas une source de production,
        # donc la demonstration doit etre autorisee explicitement.
        autoriser_demo=True))

    # Sur la LIGNE DE PROVENANCE DU PRIX, qui est construite depuis
    # `MetalPrice.source`. Une premiere version de ce test se contentait de
    # chercher l'attribution dans le document entier - or elle y arrivait
    # aussi par le libelle du jeu de prix, si bien que le test passait meme
    # quand la source des cotations etait vidée. Verifie par mutation.
    provenance = " ".join(analyse.valorisation.provenance)
    assert PINK_SHEET_ATTRIBUTION in provenance, provenance

    document = analyse.rapport.to_markdown()
    assert "Banque mondiale" in document
    assert "Pink Sheet" in document


# ==========================================================================
# REGLE 4. Seul flux rediffusable, et le test le distingue des agences.
# ==========================================================================

def test_la_donnee_est_rediffusable(xlsx):
    assert PinkSheetProvider.redistribution_licensed is True
    assert PinkSheetProvider(xlsx).fetch().redistribution_licensed is True


def test_c_est_le_seul_flux_rediffusable_par_defaut():
    """
    LE VERROU DE LA REGLE 4. Les trois flux d'agence posent False : un
    abonnement couvre l'usage interne, pas l'affichage dans un document
    remis a un tiers. Le Pink Sheet est l'exception, parce que la donnee est
    publique - et cette asymetrie doit rester visible et testee.
    """
    from klastos.feeds import BenchmarkFeed, FastmarketsFeed, SMMFeed

    for agence in (FastmarketsFeed, BenchmarkFeed, SMMFeed):
        assert agence.redistribution_licensed is False, agence.__name__
    assert PinkSheetProvider.redistribution_licensed is True


def test_un_rapport_a_un_tiers_passe_avec_le_pink_sheet(xlsx):
    """
    La consequence concrete : la ou un prix d'agence fait REFUSER un
    document destine a un tiers, le Pink Sheet le laisse passer. C'est
    exactement ce qui rend l'outil demontrable sans abonnement.
    """
    import datetime as _dt

    from klastos.market import PayableTerms
    from klastos.report import DESTINATAIRE_TIERS
    from klastos.service import Demande, analyser

    bulletin = RACINE / "data" / "exemples" / "bulletin_coherent.csv"
    if not bulletin.exists():
        pytest.skip("bulletin d'exemple absent")

    termes = PayableTerms(
        market="essai", payables={"Ni": 0.7}, as_of=_dt.date(2026, 10, 1),
        source="fixture", validated=True)
    analyse = analyser(Demande(
        bulletin=bulletin, provenance="vehicule_electrique", attestee=True,
        tirages=20, graine=0, emis_le=_dt.date(2026, 10, 15),
        prix=PinkSheetProvider(xlsx).fetch(), termes=termes,
        destinataire=DESTINATAIRE_TIERS, autoriser_demo=True))
    assert analyse.valorisation is not None


# ==========================================================================
# Echec bruyant, jamais silencieux
# ==========================================================================

def test_un_fichier_absent_echoue_en_nommant_la_commande(tmp_path):
    with pytest.raises(ProviderError) as exc:
        PinkSheetProvider(tmp_path / "jamais.xlsx").quotes()
    message = str(exc.value)
    assert "pink-sheet" in message
    assert "--rafraichir" in message or "rafraichir" in message


def test_une_feuille_renommee_echoue_en_listant_les_feuilles(tmp_path):
    f = classeur(tmp_path / "autre.xlsx", feuille="Mensuel")
    with pytest.raises(ProviderError) as exc:
        PinkSheetProvider(f).quotes()
    assert "Mensuel" in str(exc.value)
    assert "introuvable" in str(exc.value)


def test_une_serie_renommee_echoue_bruyamment(tmp_path):
    """
    La Banque mondiale peut renommer une serie d'une edition a l'autre.
    L'echec doit etre bruyant : une colonne silencieusement ignoree
    donnerait un jeu de prix incomplet, et personne ne le verrait.
    """
    f = classeur(tmp_path / "renomme.xlsx",
                 colonnes={"Aluminium": 2_345.67, "Copper": 8_765.43,
                           "Nickel": 15_432.10})
    with pytest.raises(ProviderError, match="introuvable"):
        PinkSheetProvider(f).quotes()


def test_une_unite_inattendue_est_refusee(tmp_path):
    """
    L'UNITE N'EST JAMAIS DEVINEE. C'est l'engagement de `units.py`, et le
    classeur peut changer de base : une livre prise pour une tonne fausse
    la valorisation d'un facteur 2 205.
    """
    f = classeur(tmp_path / "livres.xlsx", unites="($/lb)")
    with pytest.raises(ProviderError, match="tonne metrique"):
        PinkSheetProvider(f).quotes()


def test_un_classeur_sans_periode_lisible_est_refuse(tmp_path):
    f = classeur(tmp_path / "sansmois.xlsx", mois=["octobre 2026"])
    with pytest.raises(ProviderError, match="2026M10|format"):
        PinkSheetProvider(f).quotes()


# ==========================================================================
# L'URL est configurable, et aucun telechargement n'a lieu a l'analyse
# ==========================================================================

def test_l_url_est_configurable(xlsx):
    """
    DECISION ASSUMEE. L'identifiant de document a deja change entre les
    editions 2025 et 2026 : une URL figee dans le module casserait une
    analyse le jour de la republication.
    """
    autre = "https://example.invalid/CMO.xlsx"
    assert PinkSheetProvider(xlsx, url=autre).url == autre
    assert PinkSheetProvider(xlsx).url == PINK_SHEET_URL
    assert "worldbank.org" in PINK_SHEET_URL


def test_la_lecture_ne_telecharge_rien(xlsx, monkeypatch):
    """
    Le fournisseur lit un fichier LOCAL. Un lien mort ne doit jamais pouvoir
    casser une valorisation : le telechargement est une commande separee.
    """
    import urllib.request

    def interdit(*a, **k):
        raise AssertionError("le fournisseur a tente un acces reseau")

    monkeypatch.setattr(urllib.request, "urlopen", interdit)
    cotations = PinkSheetProvider(xlsx).quotes()
    assert len(cotations) == 3


def test_le_fournisseur_respecte_le_protocole_price_provider(xlsx):
    """Meme interface que les autres routes : `name` et `quotes()`."""
    from klastos.providers import build_price_set

    f = PinkSheetProvider(xlsx)
    assert f.name == "pink_sheet"
    cotations = f.quotes()
    jeu = build_price_set(cotations, label="essai",
                          is_production_source=False, origin=f.name)
    assert jeu.get("Ni").currency == "USD"
