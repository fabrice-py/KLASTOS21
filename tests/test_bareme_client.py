"""
LE BAREME CLIENT, SEULE ROUTE DE PRIX GRATUITE ET OPPOSABLE.

POURQUOI CE FICHIER EXISTE
--------------------------
Le moteur refuse de valoriser sur un prix de plus de sept jours. Aucune
des deux sources publiques cablees ne passe ce verrou :

    World Bank Pink Sheet   Al, Cu, Ni       mensuelle   30 j  > 7 j
    USGS (MCS / MIS)        Co, Li, Ni, ...  annuelle   365 j  > 7 j

Les deux metaux qui portent la valeur d'une black mass - cobalt et
lithium - ne sont couverts que par l'USGS, en moyenne annuelle. Sans
abonnement d'agence, le seul chiffre opposable est donc celui que
l'acheteur fournit lui-meme.

Cette route existait dans le code mais n'avait NI GABARIT NI TEST. Un
client ne pouvait pas savoir quoi envoyer, et rien ne garantissait que le
fichier d'exemple restait chargeable.

CE QUE CES TESTS GARDENT
------------------------
  1. que le gabarit livre se charge vraiment, sans retouche ;
  2. qu'il produise une source de PRODUCTION, donc un rapport opposable ;
  3. que les pieges de forme les plus couteux echouent FORT - l'unite
     inconnue et la base de cotation du lithium.
"""

from __future__ import annotations

import pathlib

import pytest

from klastos.market import MAX_PRICE_AGE_DAYS
from klastos.providers import ProviderError
from klastos.service import charger_prix

GABARIT = (pathlib.Path(__file__).resolve().parents[1]
           / "data" / "exemples" / "bareme_client.csv")
NOTICE = GABARIT.with_suffix(".md")


@pytest.fixture(scope="module")
def bareme():
    if not GABARIT.exists():
        pytest.fail(f"gabarit de bareme client absent : {GABARIT}")
    return charger_prix(GABARIT)


# ==========================================================================
# 1. Le gabarit se charge
# ==========================================================================

def test_le_gabarit_livre_se_charge_sans_retouche(bareme):
    """
    Un gabarit qu'il faut corriger avant de s'en servir ne sert a rien.
    Celui-ci part chez le client tel quel.
    """
    assert bareme.prices, "aucun prix lu dans le gabarit"


@pytest.mark.parametrize("metal", ["Ni", "Co", "Li", "Cu"])
def test_le_gabarit_couvre_les_metaux_payables(metal, bareme):
    """
    Les quatre metaux qui portent la valeur d'une black mass. Un gabarit
    qui en oublie un laisse le client decouvrir le trou au moment de
    valoriser.
    """
    assert bareme.get(metal) is not None, (
        f"{metal} absent du gabarit : le client ne saura pas qu'il doit "
        f"le fournir")


def test_le_bareme_client_est_une_source_de_production(bareme):
    """
    C'EST TOUT L'INTERET DE CETTE ROUTE. Un jeu de prix qui n'est pas
    declare source de production fait refuser la valorisation. Le
    Pink Sheet, lui, porte explicitement le drapeau inverse.
    """
    assert bareme.is_production_source, (
        "le bareme client n'est pas declare source de production : le "
        "rapport le refusera, et la route ne sert plus a rien")


def test_le_bareme_client_ne_porte_aucune_restriction_de_rediffusion(bareme):
    """
    Ce sont les prix du client. Aucune licence d'agence ne s'y applique,
    donc le rapport peut partir chez un tiers.
    """
    assert bareme.redistribution_licensed is not False, (
        "le bareme client est traite comme un flux d'agence")


def test_une_seule_devise_par_fichier(bareme):
    """Melanger les devises produirait une somme sans signification.
    `check_currency` doit passer."""
    bareme.check_currency()


# ==========================================================================
# 2. Les pieges de forme echouent FORT
# ==========================================================================

def _ecrire(tmp_path, lignes: str) -> pathlib.Path:
    p = tmp_path / "bareme.csv"
    p.write_text(lignes, encoding="utf-8")
    return p


ENTETE = ("metal,value,unit,currency,as_of,source,reference_name,basis,note\n")


def test_une_unite_inconnue_echoue_en_nommant_les_valeurs_admises(tmp_path):
    """
    L'UNITE N'EST JAMAIS DEDUITE, et c'est le piege le plus couteux : une
    erreur d'unite sur le lithium deplace la valeur d'un lot d'un facteur
    cinq. Le refus doit donc nommer le remede, pas seulement constater.
    """
    f = _ecrire(tmp_path, ENTETE
                + "Li,19750,USD par tonne,USD,2026-11-03,client,Li2CO3 CIF,,\n")
    with pytest.raises(ProviderError) as capture:
        charger_prix(f)
    message = str(capture.value)
    assert "USD/t" in message, (
        f"le refus ne dit pas quelles unites sont admises : {message}")


def test_une_colonne_obligatoire_absente_echoue_avec_son_numero_de_ligne(
        tmp_path):
    f = _ecrire(tmp_path, ENTETE + "Ni,,USD/t,USD,2026-11-03,client,LME Ni,,\n")
    with pytest.raises(ProviderError) as capture:
        charger_prix(f)
    assert "ligne 2" in str(capture.value)


def test_la_base_de_cotation_du_lithium_est_lue_et_non_devinee(bareme):
    """
    Une cotation de carbonate porte sur le Li2CO3, pas sur le lithium
    contenu. Sans la colonne `basis`, le lot serait valorise environ cinq
    fois trop cher. KLASTOS21 ne le devine pas depuis l'intitule - et le
    gabarit doit montrer au client comment le declarer.
    """
    assert bareme.get("Li").basis == "Li2CO3", (
        "le gabarit ne declare pas la base de cotation du lithium : le "
        "client ne saura pas que la colonne existe")
    # Colonne laissee vide : la base vaut "metal", c'est-a-dire que la
    # cotation porte sur le metal lui-meme. Ce defaut est PORTEUR DE SENS
    # et non une absence, ce qui est exactement ce qu'on veut d'un champ
    # dont l'oubli couterait un facteur cinq.
    assert bareme.get("Ni").basis == "metal", (
        f"base de cotation inattendue pour le nickel : "
        f"{bareme.get('Ni').basis!r}")


# ==========================================================================
# 3. La notice
# ==========================================================================

def test_la_notice_accompagne_le_gabarit():
    """
    Un CSV sans mode d'emploi se remplit de travers. La notice porte le
    contrat de colonnes et les deux pieges de forme.
    """
    assert NOTICE.exists(), f"notice absente : {NOTICE}"
    texte = NOTICE.read_text(encoding="utf-8")
    for attendu in ("basis", "as_of", "USD/t", str(MAX_PRICE_AGE_DAYS)):
        assert attendu in texte, (
            f"la notice ne mentionne pas {attendu!r}")


def test_la_notice_nomme_les_deux_autres_routes():
    """
    Le client doit savoir que cette route n'est pas la seule, et pourquoi
    c'est celle-la qu'on lui propose.
    """
    texte = NOTICE.read_text(encoding="utf-8")
    assert "Fastmarkets" in texte and "démonstration" in texte.lower()
