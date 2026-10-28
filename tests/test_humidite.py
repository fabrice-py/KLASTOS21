"""Tests de la conversion matiere humide / matiere seche.

La black mass contient de l'eau. Les teneurs d'un bulletin sont presque
toujours exprimees sur matiere SECHE, mais le lot est pese, transporte et
facture HUMIDE. Confondre les deux fait payer l'eau au prix du nickel.

LE POINT DE FOND, ET L'ARBITRAGE QUI LE REGLE
---------------------------------------------
Une humidite declaree deplace le bouclage massique. Mesure sur le bulletin
reel OREAS : sans humidite le lot boucle a 93,4 % et sort en ALERTE ; avec
10 % d'humidite declaree sur base humide il boucle a 103,8 % et passerait
en CONFORME.

Un nombre saisi par le client deviendrait donc un bouton qui eteint le
controle de securite principal de l'outil : il suffirait d'ajuster
l'humidite jusqu'a ce que le voyant passe au vert. L'arbitrage retenu est
le double bouclage : les deux chiffres figurent au rapport, et les SEUILS
continuent de s'appliquer au bulletin TEL QUE LU.
"""

import datetime as dt

import pytest

from klastos.market import MetalPrice, PayableTerms, PriceSet
from klastos.report import (LIGNE_BOUCLAGE_SEC, LIGNE_PAYABLE,
                            LIGNE_PAYABLE_HUMIDE, SECTION_DIAGNOSTIC,
                            SECTION_VALORISATION)
from klastos.service import (BASE_HUMIDE, BASE_SEC, Demande, HumiditeInvalide,
                             analyser, facteur_sec)

AUJ = dt.date(2026, 10, 28)
BULLETIN = "data/exemples/bulletin_coherent.csv"
OREAS = "data/exemples/bulletin_reel_OREAS_brut.csv"

PRIX = PriceSet(
    currency="USD", label="flux de test", is_production_source=True,
    prices={
        "Ni": MetalPrice("Ni", 16811.13, "USD", AUJ, "flux", "LME Ni cash"),
        "Co": MetalPrice("Co", 52359.78, "USD", AUJ, "flux", "Co std grade"),
    },
)
TERMES = PayableTerms(market="EXW Europe", payables={"Ni": 0.72, "Co": 0.72},
                      as_of=AUJ, source="contrat client", validated=True)


def _analyse(**kw):
    base = dict(bulletin=BULLETIN, provenance="vehicule_electrique",
                attestee=True, tirages=30, prix=PRIX, termes=TERMES)
    base.update(kw)
    return analyser(Demande(**base))


# --------------------------------------------------------------------------
# Le facteur lui-meme
# --------------------------------------------------------------------------

def test_sans_humidite_le_facteur_vaut_un():
    assert facteur_sec(None) == 1.0


def test_le_facteur_ramene_une_teneur_humide_sur_sec():
    """teneur_seche = teneur_humide / (1 - h)."""
    assert facteur_sec(10.0) == pytest.approx(1.0 / 0.9)
    assert facteur_sec(0.0) == 1.0


@pytest.mark.parametrize("h", [-1.0, 100.0, 150.0])
def test_une_humidite_hors_domaine_physique_est_refusee(h):
    """
    Un refus, pas un calcul silencieux. A 100 % le lot serait entierement
    constitue d'eau et n'aurait aucune teneur : la division exploserait.
    """
    with pytest.raises(HumiditeInvalide, match="domaine physique"):
        facteur_sec(h)


def test_un_bulletin_declare_humide_sans_humidite_est_refuse():
    """Le logiciel n'invente pas la valeur qui manque : il la reclame."""
    with pytest.raises(HumiditeInvalide, match="sans humidite mesuree"):
        _analyse(base_teneurs=BASE_HUMIDE)


def test_une_base_de_teneurs_inconnue_est_refusee():
    with pytest.raises(HumiditeInvalide, match="Base de teneurs inconnue"):
        _analyse(base_teneurs="tiede")


# --------------------------------------------------------------------------
# La valeur par tonne humide
# --------------------------------------------------------------------------

def test_a_zero_pour_cent_la_valeur_humide_egale_la_valeur_seche():
    v = _analyse(humidite=0.0).valorisation
    assert v.gross_humide_low == pytest.approx(v.gross_low)
    assert v.gross_humide_high == pytest.approx(v.gross_high)


def test_a_dix_pour_cent_la_valeur_humide_vaut_quatre_vingt_dix_pour_cent():
    v = _analyse(humidite=10.0).valorisation
    assert v.gross_humide_low == pytest.approx(0.9 * v.gross_low)
    assert v.gross_humide_high == pytest.approx(0.9 * v.gross_high)


def test_sur_un_bulletin_humide_les_teneurs_sont_divisees_par_un_moins_h():
    """
    teneur_seche = teneur_humide / 0,9. La valeur payable par tonne SECHE
    doit donc monter d'autant par rapport au meme bulletin lu sur sec.
    """
    sec = _analyse(humidite=10.0, base_teneurs=BASE_SEC).valorisation
    humide = _analyse(humidite=10.0, base_teneurs=BASE_HUMIDE).valorisation
    assert humide.gross_low == pytest.approx(sec.gross_low / 0.9, rel=1e-3)


def test_convertir_puis_revenir_retrouve_la_valeur_de_depart():
    """
    Un bulletin lu sur humide, ramene sur sec, puis reexprime par tonne
    pesee doit redonner ce qu'on lisait sans rien convertir.
    """
    brut = _analyse().valorisation
    aller_retour = _analyse(humidite=10.0, base_teneurs=BASE_HUMIDE).valorisation
    assert aller_retour.gross_humide_low == pytest.approx(brut.gross_low,
                                                          rel=1e-3)


# --------------------------------------------------------------------------
# Ce que le rapport dit, et ce qu'il refuse de taire
# --------------------------------------------------------------------------

def test_sans_humidite_aucune_valeur_humide_n_est_affichee():
    val = _analyse().rapport.section(SECTION_VALORISATION)
    assert val.ligne(LIGNE_PAYABLE_HUMIDE) is None
    assert val.ligne(LIGNE_PAYABLE) is not None


def test_sans_humidite_le_rapport_avertit_au_lieu_d_en_inventer_une():
    val = _analyse().rapport.section(SECTION_VALORISATION)
    assert any("Humidité non mesurée" in n for n in val.notes), (
        "le rapport laisse croire que la valeur vaut par tonne pesee")


def test_avec_humidite_les_deux_valeurs_figurent():
    val = _analyse(humidite=10.0).rapport.section(SECTION_VALORISATION)
    assert val.ligne(LIGNE_PAYABLE) is not None
    assert val.ligne(LIGNE_PAYABLE_HUMIDE) is not None
    assert not any("Humidité non mesurée" in n for n in val.notes)


def test_l_humidite_figure_toujours_en_tracabilite():
    """Mesuree ou non. Son absence est elle-meme une information."""
    sans = _analyse().rapport.traceability
    avec = _analyse(humidite=12.5).rapport.traceability
    assert any("non mesurée" in t for t in sans)
    assert any("12.5 %" in t for t in avec)
    assert any("sèche" in t for t in avec)


# --------------------------------------------------------------------------
# LE GARDE-FOU : l'humidite ne libere aucun verrou
# --------------------------------------------------------------------------

def test_le_verdict_de_bouclage_porte_sur_le_bulletin_tel_que_lu():
    """
    LE TEST QUI COMPTE.

    Sur le bulletin reel OREAS, le lot boucle a 93,4 % et sort en ALERTE.
    Declarer 10 % d'humidite sur base humide le ferait boucler a 103,8 %,
    donc CONFORME, si les seuils portaient sur le converti.

    Ils portent sur le bulletin tel que lu : le statut ne bouge pas.
    """
    commun = dict(bulletin=OREAS, separateur=";",
                  provenance="vehicule_electrique", attestee=True, tirages=30)
    nu = analyser(Demande(**commun)).incertitude.meta["closure"]
    converti = analyser(Demande(**commun, humidite=10.0,
                                base_teneurs=BASE_HUMIDE)).incertitude

    assert nu.status == "alerte", "le lot temoin n'est plus en alerte"
    assert converti.meta["closure"].status == nu.status, (
        "une humidite declaree par le client a fait bouger le verdict : "
        "elle est devenue un bouton pour eteindre le controle")
    assert converti.meta["closure"].total == pytest.approx(nu.total, rel=1e-3)

    # Et le converti existe quand meme, pour information.
    assert converti.meta["closure_converti"].total > nu.total


def test_les_deux_bouclages_figurent_au_rapport():
    r = analyser(Demande(bulletin=OREAS, separateur=";",
                         provenance="vehicule_electrique", attestee=True,
                         tirages=30, humidite=10.0, base_teneurs=BASE_HUMIDE))
    diag = r.rapport.section(SECTION_DIAGNOSTIC)
    assert diag.ligne(LIGNE_BOUCLAGE_SEC) is not None
    assert any("TEL QUE LU" in n for n in diag.notes), (
        "le rapport ne dit plus lequel des deux bouclages porte le verdict")


def test_le_bouclage_converti_ne_s_affiche_pas_comme_un_verdict():
    """
    TROUVE EN REGARDANT LE RENDU.

    La tuile du bouclage converti sortait en VERT, a cote d'un bouclage lu
    en ambre : le lecteur prenait le vert pour la conclusion, c'est-a-dire
    exactement l'inverse de l'arbitrage. Le repli du rendu sur la classe
    « ok » quand la gravite est vide etait une supposition silencieuse.

    Elle est desormais NEUTRE : elle informe, elle ne conclut pas.
    """
    import re

    from klastos.render_html import to_html

    r = analyser(Demande(bulletin=OREAS, separateur=";",
                         provenance="vehicule_electrique", attestee=True,
                         tirages=30, humidite=10.0, base_teneurs=BASE_HUMIDE))
    diag = r.rapport.section(SECTION_DIAGNOSTIC)
    assert diag.ligne(LIGNE_BOUCLAGE_SEC).severity == "neutre"

    tuiles = dict(
        (lab, cls) for cls, lab in
        re.findall(r'<div class="tuile (\w+)"><div class="tuile-k">([^<]*)',
                   to_html(r.rapport)))
    converti = next(l for l in tuiles if "conversion" in l)
    assert tuiles[converti] == "neutre", (
        "la tuile informative est repeinte comme un verdict")


def test_sur_bulletin_sec_aucun_second_bouclage_n_est_affiche():
    """Sans conversion, il n'y a qu'un bouclage : en afficher deux
    identiques suggererait un calcul qui n'a pas eu lieu."""
    diag = _analyse(humidite=10.0).rapport.section(SECTION_DIAGNOSTIC)
    assert diag.ligne(LIGNE_BOUCLAGE_SEC) is None


# --------------------------------------------------------------------------
# L'incertitude d'humidite est un facteur COMMUN, pas un bruit de plus
# --------------------------------------------------------------------------

def test_l_incertitude_d_humidite_elargit_les_fourchettes():
    commun = dict(humidite=10.0, base_teneurs=BASE_HUMIDE, tirages=200)
    etroit = _analyse(**commun)
    large = _analyse(**commun, humidite_incertitude=3.0)

    def largeur(a):
        r = next(x for x in a.incertitude.results if x.key == "el_Ni")
        return r.total_upper - r.total_lower

    assert largeur(large) > largeur(etroit), (
        "l'incertitude d'humidite ne se propage pas")


def test_l_incertitude_d_humidite_est_un_facteur_commun():
    """
    L'eau ne dilue pas le nickel plutot que le cobalt : elle deplace
    TOUTES les teneurs ensemble, du meme coefficient. Un bruit independant
    par element se compenserait a la somme et sous-estimerait l'effet.

    On lit la configuration plutot que le resultat : un test de
    comportement ne distinguerait pas les deux modeles de facon fiable sur
    un echantillon fini.
    """
    import inspect

    from klastos import uncertainty

    source = inspect.getsource(uncertainty.propagate)
    bloc = source[source.index("facteur_rel_sigma"):]
    bloc = bloc[:bloc.index("\n\n")]
    assert "rng.normal" in bloc
    assert "size=" not in bloc, (
        "le facteur est tire par element : ce n'est plus un facteur commun")


def test_sur_bulletin_sec_l_incertitude_d_humidite_ne_touche_rien():
    """
    Sur un bulletin deja sec, l'humidite ne change aucune teneur : elle ne
    sert qu'a reexprimer la valeur par tonne pesee. La propager dans les
    tirages melangerait deux incertitudes sans rapport.
    """
    a = _analyse(humidite=10.0, humidite_incertitude=5.0, tirages=60)
    b = _analyse(humidite=10.0, tirages=60)
    ni_a = next(x for x in a.incertitude.results if x.key == "el_Ni")
    ni_b = next(x for x in b.incertitude.results if x.key == "el_Ni")
    assert ni_a.total_lower == pytest.approx(ni_b.total_lower)
    assert ni_a.total_upper == pytest.approx(ni_b.total_upper)
