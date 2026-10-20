"""Tests de klastos/fx.py.

La conversion de devises est le premier endroit du logiciel ou un chiffre
JUSTE peut devenir faux sans que rien ne change d'apparence. Un prix de
14 000 reste un prix de 14 000 ; seule l'unite monetaire a bouge, et elle
ne se lit nulle part dans le nombre.

D'ou l'engagement du module :

    UN PRIX CONVERTI PORTE SON TAUX, SA SOURCE ET SA DATE.

Et son corollaire, qui est une decision et non un manque :

    AUCUNE SOURCE DE TAUX N'EST INTEGREE.

Le taux est celui de la banque de l'utilisateur, parce que c'est lui qui
engage sa transaction. Un taux que le logiciel irait chercher seul serait un
chiffre que personne n'a signe.

Aucune vraie cotation ici : toutes les valeurs sont des fixtures
deterministes, choisies pour etre reconnaissables dans un message d'erreur.
"""

import datetime as dt
import json
import pathlib

import pytest

from klastos import fx
from klastos.fx import (ExchangeRate, MissingRateError, PriceSetConverti,
                        RateError, StaleRateError, charger_taux, convertir)
from klastos.market import MetalPrice, PriceSet
from klastos.units import ImplausiblePriceError

AUJ = dt.date(2026, 10, 20)


def prix(metal: str, valeur: float, devise: str,
         le: dt.date | None = None) -> MetalPrice:
    return MetalPrice(metal=metal, value_per_tonne=valeur, currency=devise,
                      as_of=le or AUJ, source="fixture",
                      reference_name=f"{metal} de reference")


def jeu(**metaux: MetalPrice) -> PriceSet:
    return PriceSet(prices=dict(metaux), currency="EUR", label="fixture")


@pytest.fixture
def eur_usd() -> ExchangeRate:
    return ExchangeRate("EUR/USD", 1.0842, AUJ, "banque du client",
                        "spot EUR/USD fixing 16h")


@pytest.fixture
def gbp_usd() -> ExchangeRate:
    return ExchangeRate("GBP/USD", 1.2715, AUJ, "banque du client",
                        "spot GBP/USD fixing 16h")


# ==========================================================================
# REGLE 1. La conversion est un acte explicite. Jamais automatique.
# ==========================================================================

def test_check_currency_refuse_toujours_un_jeu_mixte():
    """
    LE VERROU DE LA REGLE 1. Convertir d'office reviendrait a choisir a la
    place du negociant quel taux engage sa transaction. `check_currency`
    doit donc continuer de refuser, et c'est un acquis a proteger : la
    tentation naturelle, en ajoutant la conversion, est de le rendre
    tolerant.
    """
    mixte = jeu(Ni=prix("Ni", 14_000, "EUR"), Li=prix("Li", 11_000, "USD"))
    with pytest.raises(ValueError, match="heterogenes"):
        mixte.check_currency()


def test_rien_ne_convertit_sans_demande_explicite():
    """
    `service.analyser` ne convertit que si `devise_cible` est renseignee.
    Sans elle, le jeu de prix traverse la chaine inchange.
    """
    import inspect

    from klastos import service

    src = inspect.getsource(service.analyser)
    # La conversion est gardee par la presence d'une devise cible.
    assert "demande.devise_cible" in src
    assert "convertir(" in src
    avant = src.split("convertir(")[0]
    assert "if prix is not None and demande.devise_cible:" in avant


def test_une_devise_cible_sans_fichier_de_taux_est_refusee():
    """
    Demander une conversion sans fournir de taux ne doit pas faire inventer
    un taux au logiciel. Le refus nomme la raison.
    """
    from klastos.service import Demande, analyser

    racine = pathlib.Path(__file__).resolve().parent.parent
    bulletin = racine / "data" / "exemples" / "bulletin_coherent.csv"
    if not bulletin.exists():
        pytest.skip("bulletin d'exemple absent")

    with pytest.raises(RateError, match="Aucune source de taux"):
        analyser(Demande(
            bulletin=bulletin, provenance="non_declaree", tirages=20,
            graine=0, emis_le=AUJ, devise_cible="EUR",
            prix=jeu(Ni=prix("Ni", 15_000, "USD")), taux=None))


def test_le_jeu_converti_est_homogene(eur_usd):
    """Le but de l'operation : un jeu qui passe enfin `check_currency`."""
    mixte = jeu(Ni=prix("Ni", 14_000, "EUR"), Li=prix("Li", 11_000, "USD"))
    converti = convertir(mixte, "EUR", eur_usd, aujourdhui=AUJ)
    converti.check_currency()
    assert converti.currency == "EUR"
    assert {p.currency for p in converti.prices.values()} == {"EUR"}


# ==========================================================================
# REGLE 2. Un taux sans source declaree est refuse.
# ==========================================================================

@pytest.mark.parametrize("source,reference", [
    ("", "spot"),
    ("   ", "spot"),
    ("banque", ""),
    ("banque", "   "),
])
def test_un_taux_sans_source_est_refuse(source, reference):
    """
    MEME EXIGENCE QUE POUR UN PRIX. `load_price_set` refuse un prix sans
    source ni date ; un taux sans source serait un chiffre que personne ne
    peut opposer a personne.
    """
    with pytest.raises(RateError):
        ExchangeRate("EUR/USD", 1.08, AUJ, source, reference)


def test_un_nombre_nu_n_est_pas_un_taux():
    """
    Passer 1.08 au lieu d'un ExchangeRate contournerait l'exigence de
    source. Le refus doit donc arriver a l'entree de `convertir`, pas plus
    tard.
    """
    with pytest.raises(RateError, match="charger_taux"):
        convertir(jeu(Ni=prix("Ni", 14_000, "EUR")), "USD", [1.08],
                  aujourdhui=AUJ)


@pytest.mark.parametrize("paire", ["EURUSD", "EUR/", "/USD", "EUR/EUR"])
def test_une_paire_mal_formee_est_refusee(paire):
    with pytest.raises(RateError):
        ExchangeRate(paire, 1.08, AUJ, "banque", "spot")


@pytest.mark.parametrize("taux", [0.0, -1.08])
def test_un_taux_nul_ou_negatif_est_refuse(taux):
    with pytest.raises(RateError):
        ExchangeRate("EUR/USD", taux, AUJ, "banque", "spot")


# ==========================================================================
# REGLE 3. Chaque prix converti conserve son origine.
# ==========================================================================

def test_le_prix_converti_porte_sa_valeur_et_sa_devise_d_origine(eur_usd):
    """
    UN CHIFFRE SANS ORIGINE EST INTERDIT PARTOUT AILLEURS DANS CE LOGICIEL.
    Ici aussi : sans la valeur d'origine, un acheteur ne peut pas distinguer
    un prix bas d'un taux faux.
    """
    converti = convertir(jeu(Li=prix("Li", 11_000, "USD")), "EUR", eur_usd,
                         aujourdhui=AUJ)
    c = converti.conversions["Li"]
    assert c.value_origine == 11_000
    assert c.devise_origine == "USD"
    assert c.devise_cible == "EUR"
    assert c.convertie is True


def test_le_prix_converti_porte_le_taux_sa_source_et_sa_date(eur_usd):
    converti = convertir(jeu(Li=prix("Li", 11_000, "USD")), "EUR", eur_usd,
                         aujourdhui=AUJ)
    (taux,) = converti.conversions["Li"].taux
    assert taux.as_of == AUJ
    assert "banque du client" in taux.source
    assert "spot EUR/USD" in taux.reference_name
    assert taux.rate == pytest.approx(1.0 / 1.0842)


def test_la_mention_de_provenance_nomme_tout_ce_qu_il_faut(eur_usd):
    """Ce libelle part au rapport : il doit se lire seul."""
    converti = convertir(jeu(Li=prix("Li", 11_000, "USD")), "EUR", eur_usd,
                         aujourdhui=AUJ)
    mention = converti.conversions["Li"].libelle()
    for attendu in ("11,000.00", "USD", "EUR", "spot EUR/USD",
                    "2026-10-20", "banque du client"):
        assert attendu in mention, attendu


def test_un_prix_deja_dans_la_devise_cible_n_est_pas_converti(eur_usd):
    """Pas de taux applique, et la provenance le dit."""
    converti = convertir(jeu(Ni=prix("Ni", 14_000, "EUR")), "EUR", eur_usd,
                         aujourdhui=AUJ)
    c = converti.conversions["Ni"]
    assert c.taux == ()
    assert c.convertie is False
    assert converti.prices["Ni"].value_per_tonne == 14_000
    assert "aucune conversion" in c.libelle()


def test_l_inversion_d_un_taux_conserve_sa_provenance(eur_usd):
    """
    Inverser est une operation ARITHMETIQUE sur un taux declare, pas un
    taux neuf. La source reste celle du releve, et le libelle dit que la
    valeur a ete inversee - sans quoi la provenance laisserait croire que
    la banque a cote USD/EUR alors qu'elle a cote EUR/USD.
    """
    inverse = eur_usd.inverse()
    assert inverse.pair == "USD/EUR"
    assert inverse.rate == pytest.approx(1 / eur_usd.rate)
    assert inverse.source == eur_usd.source
    assert inverse.as_of == eur_usd.as_of
    assert "inverse" in inverse.reference_name


def test_le_jeu_converti_reste_un_price_set(eur_usd):
    """Le reste de la chaine ne doit rien savoir de la conversion."""
    converti = convertir(jeu(Ni=prix("Ni", 14_000, "EUR")), "USD", eur_usd,
                         aujourdhui=AUJ)
    assert isinstance(converti, PriceSet)
    assert isinstance(converti, PriceSetConverti)


def test_les_attributs_du_jeu_d_origine_sont_transmis(eur_usd):
    """Licence de rediffusion comprise : la conversion n'en cree aucune."""
    source = PriceSet(prices={"Ni": prix("Ni", 14_000, "EUR")},
                      currency="EUR", label="agence X",
                      is_production_source=True, origin="agence_x",
                      redistribution_licensed=False)
    converti = convertir(source, "USD", eur_usd, aujourdhui=AUJ)
    assert converti.redistribution_licensed is False
    assert converti.is_production_source is True
    assert converti.origin == "agence_x"
    assert converti.label == "agence X"


# ==========================================================================
# REGLE 4. La bande de plausibilite est re-verifiee.
# ==========================================================================

def test_un_taux_errone_d_un_facteur_cent_est_refuse():
    """
    LE FILET ANTI-ERREUR DE TAUX. Un 108 saisi au lieu de 1,08 - la virgule
    oubliee - porte un nickel de 14 000 EUR/t a 1 512 000 USD/t. La bande
    [5 000 ; 100 000] l'attrape. Sans ce controle, la valorisation sortait
    fausse d'un facteur cent sans aucun signe exterieur.
    """
    faux = ExchangeRate("EUR/USD", 108.0, AUJ, "saisie manuelle",
                        "virgule oubliee")
    with pytest.raises(ImplausiblePriceError, match="1,512,000"):
        convertir(jeu(Ni=prix("Ni", 14_000, "EUR")), "USD", faux,
                  aujourdhui=AUJ)


def test_une_conversion_juste_vers_une_devise_eloignee_n_est_pas_rejetee():
    """
    LA CONTREPARTIE MESUREE. Les bandes de `units.py` sont libellees en USD.
    Appliquees telles quelles a un prix en wons, elles rejetteraient une
    conversion parfaitement juste d'un facteur 1 350. La bande est donc
    verifiee sur la valeur en USD de la chaine, et sur elle seule.
    """
    krw = ExchangeRate("USD/KRW", 1350.0, AUJ, "banque", "spot USD/KRW")
    converti = convertir(jeu(Ni=prix("Ni", 15_120, "USD")), "KRW", krw,
                         aujourdhui=AUJ)
    assert converti.prices["Ni"].value_per_tonne == pytest.approx(20_412_000)
    c = converti.conversions["Ni"]
    assert c.plausibilite_verifiee is True
    assert c.valeur_usd == pytest.approx(15_120)


def test_la_verification_porte_sur_la_valeur_en_usd_de_la_chaine(eur_usd):
    """La valeur au pivot est conservee, pour que le controle soit relisible."""
    converti = convertir(jeu(Ni=prix("Ni", 14_000, "EUR")), "USD", eur_usd,
                         aujourdhui=AUJ)
    c = converti.conversions["Ni"]
    assert c.valeur_usd == pytest.approx(14_000 * 1.0842)
    assert c.plausibilite_verifiee is True


def test_une_chaine_sans_usd_declare_ne_pas_avoir_verifie():
    """
    HONNETETE DU CONTROLE. Un GBP -> EUR par taux direct ne produit aucune
    valeur en dollars : la bande ne peut rien dire. Le module l'ECRIT dans
    la provenance plutot que de laisser croire a un controle qui n'a pas eu
    lieu.
    """
    direct = ExchangeRate("GBP/EUR", 1.1712, AUJ, "banque", "spot GBP/EUR")
    converti = convertir(jeu(Ni=prix("Ni", 12_000, "GBP")), "EUR", direct,
                         aujourdhui=AUJ)
    c = converti.conversions["Ni"]
    assert c.plausibilite_verifiee is False
    assert c.valeur_usd is None
    assert "NON VERIFIEE" in c.libelle()


def test_un_metal_sans_bande_est_refuse_par_defaut(eur_usd):
    """`strict=True` de units.check_plausible : mieux vaut declarer la bande."""
    with pytest.raises(ImplausiblePriceError, match="bande de plausibilite"):
        convertir(jeu(Zz=prix("Zz", 10_000, "EUR")), "USD", eur_usd,
                  aujourdhui=AUJ)


# ==========================================================================
# REGLE 5. Un taux perime est refuse, seuil expose.
# ==========================================================================

def test_un_taux_perime_est_refuse(eur_usd):
    vieux = ExchangeRate("EUR/USD", 1.0842, dt.date(2026, 10, 1),
                         "banque", "spot")
    with pytest.raises(StaleRateError, match="19 jour"):
        convertir(jeu(Ni=prix("Ni", 14_000, "EUR")), "USD", vieux,
                  aujourdhui=AUJ)


def test_le_seuil_de_fraicheur_est_expose_a_l_appelant():
    """
    NON ARBITRE, donc expose - exactement comme les seuils de bouclage le
    sont tant que personne ne les a tranches. Un negociant au comptant
    voudra 1 jour, un contrat mensuel s'accommode de 30.
    """
    vieux = ExchangeRate("EUR/USD", 1.0842, dt.date(2026, 10, 1),
                         "banque", "spot")
    # Refuse au seuil par defaut...
    with pytest.raises(StaleRateError):
        convertir(jeu(Ni=prix("Ni", 14_000, "EUR")), "USD", vieux,
                  aujourdhui=AUJ)
    # ... accepte si l'appelant releve le seuil en connaissance de cause.
    converti = convertir(jeu(Ni=prix("Ni", 14_000, "EUR")), "USD", vieux,
                         aujourdhui=AUJ, max_age=30)
    assert converti.currency == "USD"


def test_la_peremption_suit_la_meme_logique_que_metal_price():
    """Meme calcul d'age, meme comparaison : un seul raisonnement a relire."""
    t = ExchangeRate("EUR/USD", 1.08, dt.date(2026, 10, 17), "b", "spot")
    assert t.age_days(AUJ) == 3
    assert t.is_stale(AUJ, max_age=3) is False
    assert t.is_stale(AUJ, max_age=2) is True


# ==========================================================================
# REGLE 6. Une paire croisee exige deux taux.
# ==========================================================================

def test_un_croisement_sans_les_deux_taux_est_refuse(eur_usd):
    """
    N'INVENTE JAMAIS UN TAUX CROISE A PARTIR D'UN SEUL. C'est exactement
    ainsi qu'on fabrique un chiffre que personne n'a cote.
    """
    with pytest.raises(MissingRateError, match="GBP/USD"):
        convertir(jeu(Ni=prix("Ni", 12_000, "GBP")), "EUR", eur_usd,
                  aujourdhui=AUJ)


def test_un_croisement_sans_le_second_taux_est_refuse(gbp_usd):
    """
    L'AUTRE SENS DE LA MEME REGLE. Avec GBP/USD seul, la premiere jambe de
    GBP -> EUR existe et la seconde manque. Un test qui ne couvrirait que
    le cas inverse laisserait passer un code qui fabrique le croisement des
    qu'une jambe quelconque est disponible - verifie par mutation.
    """
    with pytest.raises(MissingRateError, match="USD/EUR"):
        convertir(jeu(Ni=prix("Ni", 12_000, "GBP")), "EUR", gbp_usd,
                  aujourdhui=AUJ)


def test_un_croisement_porte_ses_deux_taux(eur_usd, gbp_usd):
    converti = convertir(jeu(Ni=prix("Ni", 12_000, "GBP")), "EUR",
                         [gbp_usd, eur_usd], aujourdhui=AUJ)
    c = converti.conversions["Ni"]
    assert len(c.taux) == 2
    assert [t.pair for t in c.taux] == ["GBP/USD", "USD/EUR"]
    attendu = 12_000 * 1.2715 / 1.0842
    assert c.value_convertie == pytest.approx(attendu)


def test_les_deux_taux_du_croisement_figurent_dans_la_provenance(eur_usd,
                                                                 gbp_usd):
    converti = convertir(jeu(Ni=prix("Ni", 12_000, "GBP")), "EUR",
                         [gbp_usd, eur_usd], aujourdhui=AUJ)
    mention = converti.conversions["Ni"].libelle()
    assert "GBP/USD" in mention
    assert "USD/EUR" in mention
    assert "puis" in mention


def test_un_croisement_verifie_la_plausibilite_au_pivot(gbp_usd, eur_usd):
    """
    Le croisement est le cas ou la bande apporte le plus : la valeur au
    pivot est une information NEUVE, que rien n'avait encore controlee.
    """
    faux = ExchangeRate("GBP/USD", 127.15, AUJ, "saisie", "virgule oubliee")
    with pytest.raises(ImplausiblePriceError):
        convertir(jeu(Ni=prix("Ni", 12_000, "GBP")), "EUR", [faux, eur_usd],
                  aujourdhui=AUJ)


def test_les_taux_appliques_sont_listes_sans_doublon(eur_usd, gbp_usd):
    converti = convertir(
        jeu(Ni=prix("Ni", 12_000, "GBP"), Li=prix("Li", 11_000, "USD")),
        "EUR", [gbp_usd, eur_usd], aujourdhui=AUJ)
    paires = sorted(t.pair for t in converti.taux_appliques())
    assert paires == ["GBP/USD", "USD/EUR"]


# ==========================================================================
# Chargement d'un fichier de taux
# ==========================================================================

def test_un_json_complet_est_lu(tmp_path):
    f = tmp_path / "taux.json"
    f.write_text(json.dumps({
        "as_of": "2026-10-20",
        "source": "banque du client",
        "rates": {"EUR/USD": {"rate": 1.0842,
                              "reference_name": "spot EUR/USD"}},
    }), encoding="utf-8")
    (t,) = charger_taux(f)
    assert t.pair == "EUR/USD"
    assert t.rate == pytest.approx(1.0842)
    assert t.as_of == AUJ
    assert t.source == "banque du client"


def test_les_valeurs_communes_du_json_sont_surchargeables(tmp_path):
    f = tmp_path / "taux.json"
    f.write_text(json.dumps({
        "as_of": "2026-10-20", "source": "banque",
        "rates": {
            "EUR/USD": {"rate": 1.08, "reference_name": "spot"},
            "USD/CNY": {"rate": 7.12, "as_of": "2026-10-19",
                        "reference_name": "cloture veille"},
        },
    }), encoding="utf-8")
    par_paire = {t.pair: t for t in charger_taux(f)}
    assert par_paire["EUR/USD"].as_of == dt.date(2026, 10, 20)
    assert par_paire["USD/CNY"].as_of == dt.date(2026, 10, 19)


def test_un_csv_est_lu(tmp_path):
    f = tmp_path / "taux.csv"
    f.write_text("paire,taux,date,source,reference\n"
                 "EUR/USD,1.0842,2026-10-20,banque,spot EUR/USD\n",
                 encoding="utf-8")
    (t,) = charger_taux(f)
    assert t.pair == "EUR/USD"
    assert t.reference_name == "spot EUR/USD"


def test_un_csv_en_point_virgule_est_lu(tmp_path):
    """Excel en locale francaise ecrit des points-virgules."""
    f = tmp_path / "taux.csv"
    f.write_text("paire;taux;date;source;reference\n"
                 "EUR/USD;1,0842;2026-10-20;banque;spot\n",
                 encoding="utf-8")
    (t,) = charger_taux(f)
    assert t.rate == pytest.approx(1.0842)


@pytest.mark.parametrize("champ", ["rate", "as_of", "source",
                                   "reference_name"])
def test_un_champ_manquant_dans_le_json_est_une_erreur(tmp_path, champ):
    """Jamais une valeur par defaut : c'est la discipline de load_price_set."""
    entree = {"rate": 1.08, "as_of": "2026-10-20", "source": "b",
              "reference_name": "spot"}
    del entree[champ]
    f = tmp_path / "taux.json"
    f.write_text(json.dumps({"rates": {"EUR/USD": entree}}), encoding="utf-8")
    with pytest.raises(RateError, match=champ):
        charger_taux(f)


def test_un_champ_manquant_dans_le_csv_est_une_erreur(tmp_path):
    f = tmp_path / "taux.csv"
    f.write_text("paire,taux,date\nEUR/USD,1.0842,2026-10-20\n",
                 encoding="utf-8")
    with pytest.raises(RateError, match="source"):
        charger_taux(f)


def test_une_date_illisible_est_une_erreur(tmp_path):
    f = tmp_path / "taux.csv"
    f.write_text("paire,taux,date,source,reference\n"
                 "EUR/USD,1.0842,20/10/2026,banque,spot\n", encoding="utf-8")
    with pytest.raises(RateError, match="illisible"):
        charger_taux(f)


def test_un_fichier_absent_est_une_erreur(tmp_path):
    with pytest.raises(RateError, match="introuvable"):
        charger_taux(tmp_path / "jamais_ecrit.json")


def test_une_extension_inconnue_est_refusee(tmp_path):
    f = tmp_path / "taux.xlsx"
    f.write_bytes(b"pas un tableur")
    with pytest.raises(RateError, match="non reconnue"):
        charger_taux(f)


def test_les_exemples_livres_se_chargent():
    """`data/` doit porter un exemple qui marche, pas une illustration."""
    racine = pathlib.Path(__file__).resolve().parent.parent
    for nom in ("taux_exemple.json", "taux_exemple.csv"):
        chemin = racine / "data" / nom
        assert chemin.exists(), nom
        taux = charger_taux(chemin)
        assert taux
        assert all(t.source and t.reference_name for t in taux)


# ==========================================================================
# Aucun taux dans le code
# ==========================================================================

def test_aucun_taux_de_change_n_est_ecrit_dans_le_module():
    """
    MEME ENGAGEMENT QUE market.py POUR LES PRIX. Un taux litteral part dans
    le depot, se livre avec le paquet, et se retrouve encore la trois ans
    plus tard. La parite euro-dollar a varie de 0,95 a 1,17 sur
    vingt-quatre mois.

    On cherche les flottants qui ressemblent a une parite. Les entiers de
    configuration - l'age maximal en jours - ne sont pas des taux.
    """
    import re

    racine = pathlib.Path(__file__).resolve().parent.parent
    src = (racine / "klastos" / "fx.py").read_text(encoding="utf-8")
    src = re.sub(r'"""[\s\S]*?"""', "", src)      # docstrings
    src = re.sub(r"#[^\n]*", "", src)             # commentaires

    # Un taux plausible s'ecrit avec des decimales. 1.0 et 0.0 sont de
    # l'arithmetique, pas des cotations.
    suspects = [m for m in re.findall(r"\b\d+\.\d{2,}\b", src)
                if m not in ("1.00", "0.00")]
    assert not suspects, f"taux ecrit en dur dans fx.py : {suspects}"


def test_aucun_appel_reseau_dans_le_module():
    """
    AUCUNE SOURCE DE TAUX N'EST INTEGREE. Pas d'appel a une banque
    centrale, pas de flux : un lien mort ne doit jamais pouvoir casser une
    valorisation.
    """
    import ast

    racine = pathlib.Path(__file__).resolve().parent.parent
    arbre = ast.parse((racine / "klastos" / "fx.py").read_text(encoding="utf-8"))
    interdits = {"urllib", "requests", "http", "httpx", "socket"}
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            noms = {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            noms = {n.module.split(".")[0]}
        else:
            continue
        assert not (noms & interdits), sorted(noms & interdits)


# ==========================================================================
# Integration : la conversion traverse la chaine
# ==========================================================================

@pytest.fixture
def chaine(tmp_path):
    """Un lot reel, des prix mixtes, un fichier de taux."""
    from klastos.market import PayableTerms
    from klastos.service import Demande

    racine = pathlib.Path(__file__).resolve().parent.parent
    bulletin = racine / "data" / "exemples" / "bulletin_coherent.csv"
    if not bulletin.exists():
        pytest.skip("bulletin d'exemple absent")

    f = tmp_path / "taux.json"
    f.write_text(json.dumps({
        "as_of": "2026-09-07", "source": "banque du client",
        "rates": {"EUR/USD": {"rate": 1.0842,
                              "reference_name": "spot EUR/USD fixing 16h"}},
    }), encoding="utf-8")

    prix_mixtes = PriceSet(
        prices={"Ni": prix("Ni", 15_000, "USD", dt.date(2026, 9, 7)),
                "Co": prix("Co", 24_000, "USD", dt.date(2026, 9, 7)),
                "Li": prix("Li", 11_000, "USD", dt.date(2026, 9, 7))},
        currency="USD", label="fixture mixte",
        # `value_lot` refuse un jeu non declare source de production : ici
        # la fixture joue le role d'un flux client, pas d'un instantane de
        # demonstration. Le drapeau fait partie de la fixture, pas du code
        # teste.
        is_production_source=True, origin="fixture")
    termes = PayableTerms(
        market="essai", payables={"Ni": 0.7, "Co": 0.7, "Li": 0.4},
        as_of=dt.date(2026, 9, 7), source="fixture", validated=True)

    def demander(**extra):
        return Demande(bulletin=bulletin, provenance="vehicule_electrique",
                       attestee=True, tirages=20, graine=0,
                       emis_le=dt.date(2026, 9, 7), prix=prix_mixtes,
                       termes=termes, **extra)

    return demander, f


def test_sans_devise_cible_la_valorisation_reste_en_devise_d_origine(chaine):
    """SANS DEMANDE EXPLICITE, RIEN NE CHANGE."""
    from klastos.service import analyser

    demander, _ = chaine
    a = analyser(demander())
    assert a.valorisation.currency == "USD"
    assert a.valorisation.meta.get("fx") == ()


def test_avec_devise_cible_la_valorisation_est_convertie(chaine):
    from klastos.service import analyser

    demander, fichier = chaine
    a = analyser(demander(devise_cible="EUR", taux=fichier))
    assert a.valorisation.currency == "EUR"
    assert a.valorisation.meta["fx"]


def test_la_conversion_ne_change_que_l_echelle(chaine):
    """
    Convertir ne recalcule rien : le prix maximal en euros doit valoir le
    prix en dollars divise par le taux, au centime pres. Un ecart
    signalerait que la conversion s'est glissee dans le calcul au lieu de
    rester sur les prix d'entree.
    """
    from klastos.service import analyser

    demander, fichier = chaine
    usd = analyser(demander()).valorisation
    eur = analyser(demander(devise_cible="EUR", taux=fichier)).valorisation
    assert eur.max_price_low == pytest.approx(usd.max_price_low / 1.0842,
                                              rel=1e-9)
    assert eur.max_price_high == pytest.approx(usd.max_price_high / 1.0842,
                                               rel=1e-9)
