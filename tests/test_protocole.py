"""
Le protocole est un engagement, donc il est teste.

Ces tests verifient que PROTOCOLE.md reste synchronise avec le code. Si un
engagement disparait du document ou si un verrou technique saute, ils cassent.

Le texte est normalise (espaces compresses, gras retire) avant comparaison :
un simple retour a la ligne dans le Markdown ne doit pas faire echouer un
test d'engagement.
"""

import pathlib
import re
import typing

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent
PROTOCOLE = RACINE / "PROTOCOLE.md"


def _normaliser(s: str) -> str:
    """
    Ramene un texte Markdown a sa substance : on retire les marqueurs de mise
    en forme (citations, gras, italique, titres, code) puis on compresse les
    espaces. Un retour a la ligne ou un blockquote ne doit jamais faire
    echouer un test d'engagement.
    """
    s = re.sub(r"^\s*>+\s?", " ", s, flags=re.MULTILINE)   # citations
    s = re.sub(r"^\s*#+\s*", " ", s, flags=re.MULTILINE)   # titres
    s = s.replace("**", "").replace("`", "")
    s = re.sub(r"(?<!\w)\*(?!\w)", " ", s)                 # italiques isoles
    return re.sub(r"\s+", " ", s).strip()


@pytest.fixture(scope="module")
def texte() -> str:
    assert PROTOCOLE.exists(), "PROTOCOLE.md est absent de la racine du projet."
    return _normaliser(PROTOCOLE.read_text(encoding="utf-8"))


def contient(texte: str, phrase: str) -> bool:
    return _normaliser(phrase).lower() in texte.lower()


# ==========================================================================
# Statut du generateur (directive : outil de test, pas oracle du reel)
# ==========================================================================

def test_le_generateur_est_qualifie_outil_de_test(texte):
    assert contient(texte, "outil de test interne")
    assert contient(texte, "Il n'est pas un oracle du réel")
    assert contient(texte, "ne décrit pas la population réelle")


def test_les_bornes_sont_qualifiees_d_hypotheses_metier(texte):
    assert contient(texte, "hypothèses métier")
    assert contient(texte, "non sourcées")


def test_l_engagement_de_revision_est_ecrit(texte):
    assert contient(texte, "v1.1") or contient(texte, "version 1.1")
    assert contient(texte, "statistiques de composition observées")
    assert contient(texte, "à partir de données de lots réels")


def test_aucune_sortie_synthetique_en_livrable_client(texte):
    assert contient(texte, "aucune de ses sorties ne figure dans un livrable client")


# ==========================================================================
# Verrous techniques annonces par le protocole, verifies dans le code
# ==========================================================================

def test_le_marqueur_de_donnee_synthetique_existe_vraiment(texte):
    from klastos.generator import DATA_CLASS, make_lot

    assert contient(texte, 'data_class')
    assert make_lot(rng=0).meta["data_class"] == DATA_CLASS


def test_le_garde_fou_annonce_existe_vraiment(texte):
    from klastos.generator import (SyntheticDataInClientContext,
                                   assert_client_grade, make_lot)

    assert contient(texte, "assert_client_grade")
    with pytest.raises(SyntheticDataInClientContext):
        assert_client_grade(make_lot(rng=0))


def test_la_regle_d_attestation_est_ecrite_et_appliquee(texte):
    from klastos.provenance import ProvenanceDeclaration

    assert contient(
        texte, "Aucune phase n'est exclue sans attestation écrite du client"
    )
    _, exclues, _ = ProvenanceDeclaration(
        "vehicule_electrique", attested=False
    ).resolve()
    assert exclues == []


# ==========================================================================
# Mentions normalisees reprises dans les rapports
# ==========================================================================

def test_la_mention_de_non_identifiabilite_figure(texte):
    from klastos.identifiability import NOTE_NON_IDENTIFIABLE

    attendue = NOTE_NON_IDENTIFIABLE.replace("elementaire", "élémentaire")
    assert contient(texte, attendue)


def test_la_note_carbone_figure(texte):
    assert contient(texte, "graphite / noir de carbone")
    assert contient(texte, "données texturales ou structurales")


# ==========================================================================
# Garanties produit
# ==========================================================================

def test_la_garantie_sur_les_domaines_figure(texte):
    assert contient(texte, "Le domaine compatible contient toujours la valeur vraie")


def test_la_valorisation_repose_sur_des_grandeurs_fermes(texte):
    assert contient(
        texte,
        "La valorisation du lot et le prix maximal à payer reposent "
        "exclusivement sur des grandeurs fermes",
    )


def test_l_exemple_de_degenerescence_figure(texte):
    assert contient(texte, "rigoureusement indiscernable")


def test_le_signal_de_detection_est_correctement_decrit(texte):
    """Le detecteur est le residu d'ajustement, PAS le bouclage massique."""
    assert contient(texte, "Le signal n'est pas le bouclage massique")
    assert contient(texte, "Le signal est le résidu d'ajustement")


def test_la_limite_de_detection_est_declaree(texte):
    """Une absence d'alerte ne vaut pas certification."""
    assert contient(texte, "ne détecte pas une attestation inexacte")
    assert contient(texte, "Une absence d'alerte ne vaut donc pas certification")
    assert contient(texte, "un filet, pas une garantie")


# ==========================================================================
# Dette technique
# ==========================================================================

def test_la_dette_technique_est_listee_et_reelle(texte):
    from klastos.generator import DEFAULT_NOISE, unvalidated_profiles
    from klastos.provenance import PROVENANCE_PROFILES

    assert contient(texte, "validated=False")
    assert contient(texte, "deee")
    assert unvalidated_profiles(), "la dette generateur a disparu du code"
    assert PROVENANCE_PROFILES["deee"].validated is False


def test_la_dette_sur_le_bruit_est_soldee(texte):
    """
    Le protocole annonce une calibration sur reference certifiee : le code
    doit la porter, et la dette ne doit plus figurer comme ouverte.
    """
    from klastos.generator import DEFAULT_NOISE

    assert DEFAULT_NOISE.validated is True
    assert contient(texte, "LNE-LiB01")
    assert contient(texte, "soldée")


# ==========================================================================
# Incertitudes : les deux natures, le piege du sommet, le conditionnement
# ==========================================================================

def test_les_deux_incertitudes_sont_distinguees(texte):
    assert contient(texte, "Analytique")
    assert contient(texte, "Structurelle")
    assert contient(texte, "rang déficient de la matrice")


def test_la_regle_de_prudence_est_ecrite(texte):
    """On ne vend pas une analyse plus fine pour un probleme d'identifiabilite."""
    assert contient(
        texte,
        "ne recommande jamais une analyse plus fine pour résoudre un problème "
        "d'identifiabilité",
    )
    from klastos.uncertainty import SOURCE_STRUCTURELLE, UncertaintyResult

    r = UncertaintyResult(key="k", label="l", block="ventilation",
                          identifiable=False, total_lower=0.0, total_upper=0.4)
    assert r.dominant_source == SOURCE_STRUCTURELLE
    assert r.reducible_fraction == 0.0


def test_le_piege_du_sommet_est_documente(texte):
    assert contient(texte, "piège du sommet")
    assert contient(texte, "Cette unicité est un artefact")
    assert contient(texte, "peut en réalité balayer 0 à 40 %")


def test_identifiable_n_est_pas_exploitable(texte):
    assert contient(texte, "Identifiable n'est pas exploitable")
    assert contient(texte, "L'identifiabilité est binaire, le conditionnement est continu")


# ==========================================================================
# Valorisation
# ==========================================================================

def test_la_valorisation_repose_sur_les_teneurs_elementaires(texte):
    assert contient(texte, "Aucune ventilation par grade n'entre dans le calcul")


def test_la_convention_de_payable_est_ecrite(texte):
    assert contient(texte, "un payable s'exprime en pourcentage d'un prix de référence")
    assert contient(texte, "LME Nickel cash official price")


def test_la_regle_de_fraicheur_est_ecrite_et_appliquee(texte):
    """Le verrou d'anciennete doit figurer au protocole et exister dans le code."""
    import datetime as dt

    from klastos.market import (MAX_PRICE_AGE_DAYS, StalePriceError,
                                demo_payable_terms, demo_price_set)

    assert contient(texte, "plus de 7 jours")
    assert contient(texte, "interrompt le calcul")
    assert str(MAX_PRICE_AGE_DAYS) == "7"
    assert all(not t.validated for t in demo_payable_terms().values())
    assert demo_price_set().is_production_source is False
    assert issubclass(StalePriceError, RuntimeError)


def test_la_valeur_est_rapportee_en_fourchette(texte):
    assert contient(texte, "rapportés en fourchette, jamais en chiffre unique")


def test_aucun_prix_dans_le_code_est_un_engagement(texte):
    """L'engagement du protocole doit correspondre a l'architecture reelle."""
    import inspect

    from klastos.market import MetalPrice, PayableTerms, PriceSet
    from klastos.valuation import value_lot
    import klastos.market as m

    assert contient(texte, "Le module de valorisation ne contient aucune valeur de prix")
    assert contient(texte, "aucun jeu de prix par défaut")
    assert contient(texte, "PriceProvider")

    sig = inspect.signature(value_lot)
    assert sig.parameters["prices"].default is inspect.Parameter.empty
    for nom in dir(m):
        assert not isinstance(getattr(m, nom), (PriceSet, MetalPrice, PayableTerms)), nom


# ==========================================================================
# Approvisionnement en prix
# ==========================================================================

def test_les_trois_routes_sont_documentees(texte):
    assert contient(texte, "Prix apportés par le client")
    assert contient(texte, "Sources publiques et dérivées")
    assert contient(texte, "Évaluation propre")


def test_l_interdiction_d_extraction_sous_licence(texte):
    assert contient(texte, "n'extrait aucune donnée de site soumis à licence")
    assert contient(texte, "sui generis")


def test_l_unite_n_est_jamais_devinee(texte):
    """Engagement + verrou reel dans le code."""
    from klastos.providers import CSVProvider, RawQuote
    from klastos.units import ImplausiblePriceError, PriceUnit, check_plausible

    assert contient(texte, "Une cotation sans unité déclarée est refusée")
    assert contient(texte, "32 150")
    assert contient(texte, "bande de plausibilité")

    # l'unite est un champ obligatoire de RawQuote
    import inspect
    sig = inspect.signature(RawQuote)
    assert sig.parameters["unit"].default is inspect.Parameter.empty

    # la bande attrape l'oubli de conversion
    with pytest.raises(ImplausiblePriceError):
        check_plausible("Ni", 0.5191)


def test_les_bandes_ne_bornent_aucune_valorisation(texte):
    from klastos.units import PLAUSIBILITY_BANDS

    assert contient(texte, "jamais une opinion de marché")
    for band in PLAUSIBILITY_BANDS.values():
        assert band.high_per_tonne / band.low_per_tonne >= 10.0


def test_la_continuite_de_service_est_engagee(texte):
    assert contient(texte, "Une panne de source n'interrompt pas un rapport")
    assert contient(texte, "conserve sa date d'origine")


# ==========================================================================
# Architecture : la chaine de dependances doit rester lineaire
# ==========================================================================

def test_la_chaine_de_dependances_est_lineaire():
    """
    units -> market -> providers
                    -> valuation

    Un fournisseur de prix ne doit PAS dependre du calcul de valorisation, ni
    l'inverse. Cette separation permet de vendre le service d'approvisionnement
    en prix independamment du service de valorisation.
    """
    import pathlib
    import re

    import klastos

    racine = pathlib.Path(klastos.__file__).parent
    interdits = {
        "units": {"market", "providers", "valuation", "solver", "uncertainty"},
        "market": {"providers", "valuation", "solver", "uncertainty"},
        "providers": {"valuation"},
        "valuation": {"providers"},
    }
    for module, bannis in interdits.items():
        src = (racine / f"{module}.py").read_text(encoding="utf-8")
        imports = set(re.findall(r"^from \.(\w+) import", src, flags=re.MULTILINE))
        collisions = imports & bannis
        assert not collisions, (
            f"{module}.py importe {sorted(collisions)} : la chaine de "
            "dependances n'est plus lineaire."
        )


def test_le_module_pricing_a_bien_disparu():
    """Le decoupage remplace pricing.py par market.py + valuation.py."""
    import pathlib

    import klastos

    assert not (pathlib.Path(klastos.__file__).parent / "pricing.py").exists()


# ==========================================================================
# Rapport client
# ==========================================================================

def test_les_trois_statuts_sont_documentes(texte):
    from klastos.report import MENTION_MAL_DETERMINE

    assert contient(texte, "ferme mais mal déterminée")
    assert contient(texte, "déterminée en théorie, fourchette trop large en pratique")
    assert contient(texte, "non identifiable")
    assert "mal determinee" in MENTION_MAL_DETERMINE.replace("é", "e")


def test_le_critere_d_exploitabilite_est_relatif(texte):
    from klastos.uncertainty import (WELL_DETERMINED_ABS_FLOOR,
                                     WELL_DETERMINED_REL_WIDTH)

    assert contient(texte, "Le critère d'exploitabilité est relatif, pas absolu")
    assert contient(texte, "plancher absolu")
    assert 0 < WELL_DETERMINED_REL_WIDTH < 1
    assert 0 < WELL_DETERMINED_ABS_FLOOR < WELL_DETERMINED_REL_WIDTH


def test_les_verrous_de_sortie_du_rapport(texte):
    from klastos.report import ReportRefused

    assert contient(texte, "Ce que le rapport refuse de faire")
    assert contient(texte, "donnée provenant du générateur de test")
    assert contient(texte, "jeu de prix non destiné à la production")
    assert contient(texte, "bouclage massique est hors tolérance")
    assert contient(texte, "non opposable")
    assert issubclass(ReportRefused, RuntimeError)


# ==========================================================================
# Oxygene et diagnostics
# ==========================================================================

def test_le_traitement_de_l_oxygene_est_documente(texte):
    assert contient(texte, "L'oxygène n'est jamais dosé")
    assert contient(texte, "KLASTOS21 ne l'invente pas")
    assert contient(texte, "L'oxygène par différence est écarté")


def test_le_bouclage_porte_sur_les_phases(texte):
    """Engagement + verrou reel : check_closure recoit x, jamais b."""
    import inspect

    from klastos.solver import check_closure, solve

    assert contient(texte, "Le bouclage se mesure sur les phases, jamais sur le bulletin")
    assert "FRACTIONS DE PHASES" in (check_closure.__doc__ or "")
    src = inspect.getsource(solve)
    assert "check_closure(x," in src, "le bouclage doit etre calcule sur x"


def test_les_deux_diagnostics_sont_distingues(texte):
    from klastos.solver import SolveResult

    assert contient(texte, "Résidu d'ajustement")
    assert contient(texte, "Masse non expliquée")
    assert contient(texte, "Les deux sont indépendants")
    assert hasattr(SolveResult, "explained_mass")
    assert hasattr(SolveResult, "unexplained_mass")


def test_la_degenerescence_accrue_est_declaree(texte):
    assert contient(texte, "La dégénérescence augmente d'un degré")


def test_le_tableau_d_identifiabilite_est_conforme_a_la_mesure(texte):
    """
    Ce test remplace un engagement qui etait FAUX, et il explique pourquoi
    l'erreur avait survecu.

    Le protocole affirmait : « Une attestation de provenance les restaure »,
    en parlant de "Cathodes totales" et du bloc "NMC + LCO". Le test
    d'engagement verifiait que la PHRASE figurait dans le document. Il ne
    verifiait pas qu'elle etait vraie. Mesure faite, l'attestation restaure
    le bloc NMC + LCO et ne restaure pas "Cathodes totales".

    On ne verifie donc plus une phrase : on recalcule la table et on exige
    que le document porte la bonne conclusion.
    """
    from klastos.identifiability import is_identifiable, null_space
    from klastos.phases import (cathode_indicator, nmc_lco_indicator,
                                stoichiometry_matrix)
    from klastos.provenance import ProvenanceDeclaration

    sans_o = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F"]
    attendu = {
        # (provenance, oxygene dose) -> (cathodes ferme, nmc+lco ferme)
        ("non_declaree", True): (True, True),
        ("non_declaree", False): (False, False),
        ("vehicule_electrique", True): (True, True),
        ("vehicule_electrique", False): (False, True),
    }
    for (prov, avec_o), (c_att, n_att) in attendu.items():
        keys, _, _ = ProvenanceDeclaration(prov, attested=True).resolve()
        A, _, k = (stoichiometry_matrix(phase_keys=keys) if avec_o
                   else stoichiometry_matrix(phase_keys=keys, elements=sans_o))
        N = null_space(A)
        assert is_identifiable(cathode_indicator(phase_keys=k), N) is c_att, (
            f"cathodes_totales, {prov}, oxygene dose={avec_o}")
        assert is_identifiable(nmc_lco_indicator(phase_keys=k), N) is n_att, (
            f"nmc_lco, {prov}, oxygene dose={avec_o}")

    assert contient(texte,
                    "« Cathodes totales » n'est ferme que si l'oxygène est dosé")
    assert contient(texte, "Elle ne restaure PAS « Cathodes totales »")


def test_la_portee_de_la_garantie_est_precisee(texte):
    """
    La garantie stricte porte sur les domaines compatibles. Une grandeur
    ferme recoit un intervalle de confiance, pas une garantie.
    """
    assert contient(texte, "Cette garantie porte sur les grandeurs non identifiables")
    assert contient(texte, "intervalle de confiance, pas une garantie")
    assert contient(texte, "90 %")


def test_l_intervalle_affiche_sert_au_classement(texte):
    assert contient(
        texte, "L'intervalle affiché est toujours celui qui sert au classement"
    )


# ==========================================================================
# Connexion aux agences d'evaluation
# ==========================================================================

def test_les_trois_agences_sont_documentees(texte):
    from klastos.feeds import BenchmarkFeed, FastmarketsFeed, SMMFeed

    assert contient(texte, "Fastmarkets")
    assert contient(texte, "Benchmark")
    assert contient(texte, "SMM")
    for cls in (FastmarketsFeed, BenchmarkFeed, SMMFeed):
        assert hasattr(cls, "quotes")


def test_les_identifiants_ne_passent_pas_en_argument(texte):
    assert contient(texte, "jamais passés en argument")
    assert contient(texte, "historique du shell")
    assert contient(texte, "KLASTOS_FM_SERVICE_KEY")


def test_la_borne_retenue_est_declaree(texte):
    from klastos.feeds import load_catalogue

    assert contient(texte, "point bas du cobalt standard grade")
    assert contient(texte, "surestimerait un lot de 7 %")
    assert load_catalogue()["fastmarkets"]["symbols"]["MB-CO-0005"]["field"] == "low"


def test_la_rediffusion_n_est_jamais_supposee(texte):
    from klastos.feeds import BenchmarkFeed, FastmarketsFeed

    assert contient(texte, "Un abonnement d'agence couvre l'usage interne")
    assert contient(texte, "4.3(b)")
    assert contient(texte, "USAGE INTERNE")
    for cls in (FastmarketsFeed, BenchmarkFeed):
        assert cls.redistribution_licensed is False


def test_les_seuils_de_bouclage_sont_arbitres_et_documentes(texte):
    """Dette soldée : le protocole et le code doivent porter les mêmes valeurs."""
    from klastos.solver import (CLOSURE_ALERT, CLOSURE_REJECT,
                                CLOSURE_THRESHOLDS_VALIDATED)

    assert contient(texte, "Seuils de bouclage")
    assert contient(texte, "sous le plancher de bruit")
    assert contient(texte, "réalité métallurgique des black masses")
    assert CLOSURE_THRESHOLDS_VALIDATED is True
    assert CLOSURE_ALERT == pytest.approx(0.06)
    assert CLOSURE_REJECT == pytest.approx(0.20)


# ==========================================================================
# Rendu du rapport
# ==========================================================================

def test_les_deux_formes_du_rapport_sont_documentees(texte):
    """Les deux rendus viennent du meme objet : ils ne peuvent pas diverger."""
    from klastos.render_html import to_html
    from klastos.report import LotReport

    assert contient(texte, "Le rendu montre ce que les chiffres ne disent pas")
    assert contient(texte, "barres d'intervalle")
    assert hasattr(LotReport, "to_markdown")
    # `from __future__ import annotations` laisse les annotations en texte.
    assert typing.get_type_hints(to_html)["rapport"] is LotReport


def test_la_gravite_est_une_donnee_et_non_une_heuristique(texte):
    """
    Engagement de rendu. Le message d'un bouclage degrade ne contient pas le
    mot "alerte" : deduire la gravite du texte affichait un lot en alerte
    comme conforme.
    """
    from klastos.report import ReportRow

    assert contient(texte, "La gravité d'un diagnostic est une donnée")
    assert "severity" in ReportRow.__dataclass_fields__


def test_une_largeur_n_est_jamais_etiquetee_ferme(texte):
    from klastos.render_html import STATUTS, STATUTS_LARGEUR

    assert contient(texte,
                    "Une largeur de fourchette n'est jamais étiquetée « ferme »")
    assert contient(texte, "réductible")
    assert contient(texte, "irréductible")
    libelles = {libelle for libelle, _, _ in STATUTS_LARGEUR.values()}
    assert STATUTS["ferme"][0] not in libelles
    assert STATUTS["ouvert"][0] not in libelles


# ==========================================================================
# Scenario : dosage d'un element absent
# ==========================================================================

def test_le_critere_de_decision_du_dosage_est_ecrit(texte):
    """Une demi-plage : le seul nombre dont le client ait besoin."""
    assert contient(texte, "Ce qu'un dosage d'oxygène apporterait")
    assert contient(texte, "Le critère de décision est une demi-plage")
    assert contient(texte, "u < plage / 2")


def test_le_verrou_contre_la_precision_fictive_est_ecrit(texte):
    """
    L'engagement qui interdit la maniere simple et fausse de produire cette
    section. Le code porte la meme mention, mot pour mot.
    """
    from klastos.report import MENTION_SCENARIO_PIEGE

    assert contient(texte, "Le scénario balaie, il ne se pose jamais sur un point")
    assert contient(texte, "piège du sommet dans sa forme la plus pure")
    assert "ne réinjecte jamais" in MENTION_SCENARIO_PIEGE
    assert "balayant toute la plage compatible" in MENTION_SCENARIO_PIEGE


def test_l_inutilite_du_dosage_sur_la_ventilation_est_declaree(texte):
    """Dire ce qu'un essai n'apporte pas vaut autant que dire ce qu'il apporte."""
    assert contient(texte,
                    "Le dosage n'apporte rien à la ventilation par grade")
    assert contient(texte, "sous-système fermé Li-Ni-Mn-Co-O")


def test_le_scenario_n_est_pas_opposable(texte):
    from klastos.report import MENTION_SCENARIO

    assert contient(texte, "Aucun chiffre de cette section n'est opposable")
    assert "opposable" in MENTION_SCENARIO


def test_le_perimetre_du_scenario_est_declare_non_arbitre(texte):
    from klastos.identifiability import (SCENARIO_ELEMENTS,
                                         SCENARIO_ELEMENTS_VALIDATED)

    assert contient(texte, "Périmètre, non arbitré")
    assert contient(texte, "L'hydrogène lève formellement un degré de liberté")
    assert SCENARIO_ELEMENTS == ("O",)
    assert SCENARIO_ELEMENTS_VALIDATED is False


def test_la_base_de_mesure_du_scenario_est_declaree(texte):
    from klastos.report import MENTION_SCENARIO_BASE

    assert contient(texte, "largeurs structurelles du bulletin central")
    assert "STRUCTURELLES" in MENTION_SCENARIO_BASE


def test_le_balayage_du_scenario_est_justifie(texte):
    """
    Le balayage a trois points sous-estimait la largeur conditionnelle,
    donc SURESTIMAIT le gain annonce au client. Le protocole porte la
    raison - la concavite - et le code porte le remede.
    """
    from klastos.identifiability import (SCENARIO_SWEEP_PASSES,
                                         SCENARIO_SWEEP_STEPS)

    assert contient(texte, "w(v) est concave")
    assert contient(texte, "le maximum d'une fonction concave est")
    assert SCENARIO_SWEEP_STEPS >= 4
    assert SCENARIO_SWEEP_PASSES >= 2


def test_le_droit_de_rediffusion_vit_dans_la_donnee(texte):
    """
    Il etait ecrit dans le fichier puis perdu a la relecture. Le protocole
    doit porter la correction, et le code le champ.
    """
    from klastos.market import PriceSet

    assert contient(texte, "L'autorisation vit dans la donnée, pas dans un message")
    assert "redistribution_licensed" in PriceSet.__dataclass_fields__


def test_le_refus_porte_sur_la_sortie_pas_sur_le_calcul(texte):
    from klastos.report import (DESTINATAIRE_INTERNE, DESTINATAIRE_TIERS,
                                REFUS_REDIFFUSION, build_report)
    import inspect

    assert contient(texte,
                    "Le refus porte sur la sortie du document, pas sur le calcul")
    assert contient(texte, "rapport refusé")
    assert (inspect.signature(build_report)
            .parameters["destinataire"].default == DESTINATAIRE_TIERS)
    assert DESTINATAIRE_INTERNE in REFUS_REDIFFUSION


def test_le_chemin_unique_est_un_engagement(texte):
    """
    Le verrou technique existe (test_service.py). Le protocole doit porter
    la raison : deux chemins paralleles divergent toujours.
    """
    assert contient(texte, "Un seul chemin, deux portes")
    assert contient(texte, "Deux chemins parallèles divergent toujours")
    assert contient(texte, "une seule reconnaissance de format dans le projet")

    from klastos.ingestion import parse_rows
    from klastos.service import analyser

    assert callable(parse_rows) and callable(analyser)


def test_un_graphique_ne_montre_pas_ce_que_la_donnee_ne_porte_pas(texte):
    """
    L'engagement de rendu graphique, et sa demonstration chiffree. Le code
    porte la regle dans charts.donnees_composition.
    """
    from klastos.charts import donnees_composition

    assert contient(texte, "Un graphique ne montre jamais ce que la donnée ne porte pas")
    assert contient(texte, "2,8 × 10⁻¹⁵ point de masse")
    assert contient(texte, "Le camembert porte la composition élémentaire")
    assert contient(texte, "bascule automatiquement sur les phases")
    assert callable(donnees_composition)