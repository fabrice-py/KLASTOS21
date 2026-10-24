"""
Tests de la source de prix USGS.

Pourquoi cette source existe
----------------------------
Le Pink Sheet de la Banque mondiale ne cote que l'aluminium, le cuivre et le
nickel. Pour le cobalt et le lithium - les deux metaux qui portent
l'essentiel de la valeur d'une black mass - il fallait une evaluation
d'agence payante ou le fichier de prix du client. KLASTOS21 ne pouvait donc
pas chiffrer un lot de lui-meme.

L'USGS publie les cinq metaux dans un CSV lisible par machine, et son
travail est une oeuvre du gouvernement federal americain : domaine public,
CC0 1.0, redistribuable sans contrepartie.

Ce que ces tests tiennent
-------------------------
Deux promesses contraires, et c'est le point.

  1. La source FONCTIONNE : les cinq cotations sortent aux valeurs du
     certificat, dans les bonnes unites, avec leur base.
  2. La source NE SUFFIT PAS : ce sont des moyennes annuelles, et une
     valorisation opposable doit etre REFUSEE sur elles. Le refus est le
     comportement voulu, pas un defaut a contourner.

Mesure de l'enjeu, qui justifie la seconde promesse : la moyenne annuelle
2025 du carbonate de lithium vaut 9 000 USD/t, quand la cotation Benchmark
CIF Asie du 2 septembre 2026 vaut 19 750 USD/t. Un facteur 2,2. Et sur le
seul fichier, le lithium passe de 63 700 USD/t en 2022 a 9 000 en 2025 : un
facteur 7 en trois ans.
"""

from __future__ import annotations

import datetime as dt
import pathlib

import pytest

from klastos.market import MissingPriceError, StalePriceError
from klastos.providers import (USGS_ECARTEES, USGS_SERIES, ProviderError,
                              UsgsProvider, build_price_set)
from klastos.service import Demande, analyser, charger_termes
from klastos.units import (ImplausiblePriceError, LB_PER_TONNE, PriceUnit,
                           check_plausible)

#: Extrait versionne du fichier USGS. Le classeur complet pese 3,2 Mo et
#: n'est pas dans le depot, comme le Pink Sheet : il se telecharge par
#: `klastos usgs --rafraichir`.
EXTRAIT = pathlib.Path("data/exemples/usgs_mcs2026_extrait.csv")

#: Valeurs 2025 RECOPIEES du fichier de l'USGS, pas du code. Si une ligne
#: change, c'est l'edition qui a change, et il faut le voir.
OFFICIEL_2025 = {
    "Co": (15.0, PriceUnit.PER_POUND),
    "Li": (9000.0, PriceUnit.PER_TONNE),
    "Ni": (15000.0, PriceUnit.PER_TONNE),
    "Cu": (440.0, PriceUnit.PER_POUND_CENT),
    "Al": (180.0, PriceUnit.PER_POUND_CENT),
}


@pytest.fixture
def source():
    return UsgsProvider(EXTRAIT)


# ==========================================================================
# 1. La source fonctionne
# ==========================================================================

def test_l_extrait_est_versionne():
    """
    Un cas de non-regression qui depend d'un telechargement n'en est pas
    un. L'extrait vit dans le depot ; le classeur complet non.
    """
    assert EXTRAIT.exists(), f"{EXTRAIT} absent"
    # Le classeur complet pese 3,2 Mo et git l'ignore : les tests ne
    # doivent donc jamais en dependre. Ce garde attrape le jour ou
    # quelqu'un verserait le classeur entier en croyant bien faire.
    assert EXTRAIT.stat().st_size < 100_000, (
        f"{EXTRAIT} pese {EXTRAIT.stat().st_size:,} octets : ce n'est plus "
        f"un extrait")


def test_cinq_series_sont_offertes(source):
    assert set(USGS_SERIES) == {"Co", "Li", "Ni", "Cu", "Al"}
    assert {q.metal for q in source.quotes()} == set(USGS_SERIES)


@pytest.mark.parametrize("metal", sorted(OFFICIEL_2025))
def test_chaque_valeur_est_celle_du_certificat(source, metal):
    """
    La valeur ET l'unite. Une unite devinee au lieu d'etre lue fausserait
    le cuivre et l'aluminium d'un facteur cent.
    """
    attendue, unite = OFFICIEL_2025[metal]
    q = next(q for q in source.quotes([metal]) if q.metal == metal)
    assert q.value == pytest.approx(attendue)
    assert q.unit is unite
    assert q.currency == "USD"


def test_le_cobalt_et_le_lithium_sont_la(source):
    """
    Le trou que cette source comble. Sans eux, KLASTOS21 ne peut pas
    chiffrer un lot sans le fichier du client.
    """
    metaux = {q.metal for q in source.quotes()}
    assert "Co" in metaux and "Li" in metaux


def test_les_cents_par_livre_valent_bien_un_centieme_du_dollar():
    """
    L'unite qui manquait. Confondre « cents per pound » avec « dollars per
    pound » surevalue le cuivre d'un facteur cent, et la bande de
    plausibilite ne l'attraperait pas forcement - 440 USD/lb fait
    970 000 USD/t, hors bande, mais 4,40 USD/lb ferait 9 700 USD/t, dans la
    bande. L'erreur inverse passe donc inapercue.
    """
    assert PriceUnit.PER_POUND_CENT.units_per_tonne == pytest.approx(
        PriceUnit.PER_POUND.units_per_tonne / 100.0)
    assert PriceUnit.PER_POUND_CENT.to_per_tonne(440.0) == pytest.approx(
        4.40 * LB_PER_TONNE)


@pytest.mark.parametrize("metal,par_tonne", [
    ("Co", 33069.0), ("Li", 9000.0), ("Ni", 15000.0),
    ("Cu", 9700.0), ("Al", 3968.0),
])
def test_la_conversion_vers_la_tonne_est_exacte(source, metal, par_tonne):
    q = next(q for q in source.quotes([metal]) if q.metal == metal)
    assert q.to_metal_price().value_per_tonne == pytest.approx(
        par_tonne, rel=1e-3)


def test_le_lithium_est_declare_en_carbonate(source):
    """
    Le prix de l'USGS porte sur le CARBONATE qualite batterie, pas sur le
    lithium metal. Sans `basis`, la valorisation compterait 9 000 USD/t de
    lithium contenu au lieu de 47 900 : un facteur 5,3 par omission.
    """
    li = source.quotes(["Li"])[0]
    assert li.basis == "Li2CO3"
    autres = [q.basis for q in source.quotes() if q.metal != "Li"]
    assert set(autres) == {"metal"}


def test_la_date_est_la_fin_de_la_periode(source):
    """
    Une moyenne annuelle ne peut pas etre connue avant la fin de l'annee
    qu'elle resume. La dater du 1er janvier la ferait exister avant ses
    propres donnees, et la rajeunirait de douze mois face a la regle de
    fraicheur.
    """
    for q in source.quotes():
        assert q.as_of == dt.date(2025, 12, 31)


def test_une_annee_anterieure_est_lisible():
    """
    Le fichier porte cinq annees. Pouvoir les relire sert a reexaminer une
    decision passee avec les prix de l'epoque.
    """
    q = UsgsProvider(EXTRAIT, annee=2022).quotes(["Li"])[0]
    assert q.value == pytest.approx(63700.0)
    assert q.as_of == dt.date(2022, 12, 31)


def test_la_volatilite_du_lithium_est_dans_le_fichier():
    """
    Ce test n'est pas decoratif : il chiffre pourquoi une moyenne annuelle
    ne peut pas porter un contrat. Le carbonate de lithium passe de
    63 700 USD/t en 2022 a 9 000 en 2025.
    """
    v = {a: UsgsProvider(EXTRAIT, annee=a).quotes(["Li"])[0].value
         for a in (2022, 2025)}
    assert v[2022] / v[2025] > 5.0, (
        f"le rapport {v[2022]}/{v[2025]} ne montre plus la volatilite qui "
        f"justifie le refus d'opposabilite")


# ==========================================================================
# 2. Ce que la source refuse, et pourquoi
# ==========================================================================

def test_le_manganese_est_ecarte_pour_une_raison_d_unite(source):
    """
    Le fichier cote le manganese a 4,50 USD, mais par TONNE-UNITE de
    minerai (dmtu), pas par tonne de metal. Convertir exige la teneur du
    minerai, que l'USGS ne donne pas. On refuse plutot que de deviner.
    """
    with pytest.raises(MissingPriceError) as capture:
        source.quotes(["Mn"])
    message = str(capture.value)
    assert "dmtu" in message
    assert "Mn" in USGS_ECARTEES


def test_la_valeur_brute_du_manganese_serait_refusee_par_la_bande():
    """
    Le second filet, et il est independant du premier. Meme si quelqu'un
    forcait le manganese a 4,50 USD/t, la bande de plausibilite de
    units.py le refuserait. Deux gardes valent mieux qu'un sur une erreur
    qui vaut un facteur cent.
    """
    with pytest.raises(ImplausiblePriceError):
        check_plausible("Mn", 4.5)


def test_le_graphite_est_ecarte_faute_de_bande(source):
    """
    Trois qualites de 470 a 2 600 USD/t, et aucune bande de plausibilite
    pour le carbone dans units.py. Choisir une qualite et poser une bande
    sont deux arbitrages a prendre, pas a deviner.
    """
    with pytest.raises(MissingPriceError) as capture:
        source.quotes(["C"])
    assert "bande de plausibilite" in str(capture.value)


def test_un_metal_inconnu_liste_ce_qui_existe(source):
    with pytest.raises(MissingPriceError) as capture:
        source.quotes(["Au"])
    message = str(capture.value)
    assert "Au" in message
    for m in USGS_SERIES:
        assert m in message


def test_un_fichier_absent_nomme_la_commande_de_telechargement():
    """
    L'echec est bruyant ET actionnable : il dit quoi taper.
    """
    with pytest.raises(ProviderError) as capture:
        UsgsProvider("data/exemples/inexistant.csv").quotes()
    assert "klastos usgs --rafraichir" in str(capture.value)


def test_une_annee_absente_liste_les_annees_disponibles():
    with pytest.raises(ProviderError) as capture:
        UsgsProvider(EXTRAIT, annee=1999).quotes(["Co"])
    message = str(capture.value)
    assert "1999" in message
    assert "2025" in message


def test_l_extrait_reproduit_le_piege_d_encodage():
    """
    Le fichier de l'USGS n'est PAS en UTF-8 : il porte des octets cp1252.
    Le lire en UTF-8 leve UnicodeDecodeError des les premieres lignes.

    L'extrait doit reproduire ce piege, sinon le test d'encodage passerait
    sur une fixture plus propre que la realite.
    """
    brut = EXTRAIT.read_bytes()
    with pytest.raises(UnicodeDecodeError):
        brut.decode("utf-8")
    assert brut.decode("cp1252")


def test_un_fichier_sans_les_colonnes_attendues_est_refuse(tmp_path):
    f = tmp_path / "faux.csv"
    f.write_text("a,b,c\n1,2,3\n", encoding="cp1252")
    with pytest.raises(ProviderError) as capture:
        UsgsProvider(f).quotes()
    assert "Commodity" in str(capture.value)


# ==========================================================================
# 3. La promesse contraire : pas d'opposabilite
# ==========================================================================

def _jeu(source):
    return build_price_set(
        source.quotes(), label="USGS MCS 2026",
        is_production_source=source.is_production_source,
        redistribution_licensed=source.redistribution_licensed,
    )


def test_la_source_est_redistribuable_mais_pas_de_production(source):
    """
    Les deux drapeaux disent des choses differentes, et les deux comptent.

    REDISTRIBUABLE : domaine public, donc le chiffre peut figurer dans un
    document remis a un tiers. C'est le second flux du projet dans ce cas,
    apres le Pink Sheet.

    PAS DE PRODUCTION : ce sont des moyennes annuelles, donc elles ne
    peuvent pas porter une valorisation opposable.
    """
    assert source.redistribution_licensed is True
    assert source.is_production_source is False
    jeu = _jeu(source)
    assert jeu.redistribution_licensed is True
    assert jeu.is_production_source is False


def test_une_valorisation_opposable_est_refusee(source):
    """
    LE test de cette seance. L'outil devient autonome pour CHIFFRER, et
    refuse de faire passer le resultat pour opposable.
    """
    from klastos.market import NotAProductionSourceError

    with pytest.raises(NotAProductionSourceError):
        analyser(Demande(
            bulletin="data/exemples/bulletin_coherent.csv",
            provenance="vehicule_electrique", attestee=True, tirages=25,
            prix=_jeu(source),
            termes=charger_termes("data/payable_terms.json", "exw_europe"),
        ))


def test_le_mode_demonstration_donne_une_valeur_indicative(source):
    """
    Le pendant : l'autonomie qu'on gagne. Un lot se chiffre sans attendre
    le fichier de prix du client, et le document porte la mention.
    """
    a = analyser(Demande(
        bulletin="data/exemples/bulletin_coherent.csv",
        provenance="vehicule_electrique", attestee=True, tirages=25,
        prix=_jeu(source),
        termes=charger_termes("data/payable_terms.json", "exw_europe"),
        autoriser_demo=True,
    ))
    v = a.valorisation
    assert v is not None
    assert v.max_price_low > 0
    assert v.max_price_high > v.max_price_low
    assert a.rapport.is_demo, (
        "un rapport bati sur des moyennes annuelles doit se declarer de "
        "demonstration")


def test_la_note_de_chaque_cotation_dit_que_c_est_une_moyenne(source):
    """
    Le rapport doit pouvoir citer la nature de la source. Sans cette note,
    une moyenne annuelle se lit comme une cotation du jour.
    """
    for q in source.quotes():
        assert "MOYENNE ANNUELLE" in q.note
        assert "2025" in q.note
        assert "redistribuable" in q.note
        assert "Geological Survey" in q.source
        assert "CC0" in q.source, (
            "la licence doit figurer dans la source : c'est elle qui "
            "autorise la redistribution")
