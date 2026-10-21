"""Tests de klastos/report.py.

Le rapport est le point ou le systeme parle au client. Trois exigences :

  1. Il REFUSE de sortir quand les engagements ne sont pas tenus.
  2. Il ne presente jamais une grandeur non identifiable comme un chiffre.
  3. Il distingue identifiable et EXPLOITABLE.
"""

import datetime as dt

import pytest

from klastos.generator import NOISE_FREE, NoiseModel, make_lot
from klastos.identifiability import NOTE_CARBONE, NOTE_NON_IDENTIFIABLE
from klastos.market import (REFERENCE_SPECS, MetalPrice, PayableTerms,
                            PriceSet, demo_payable_terms, demo_price_set)
from klastos.provenance import ProvenanceDeclaration
from klastos import i18n
from klastos.report import (MENTION_DETECTION, MENTION_MAL_DETERMINE,
                            SECTION_FERMES, SECTION_REDUIRE, LotReport,
                            ReportRefused,
                            build_report)
from klastos.uncertainty import (AVERTISSEMENT_SOMMET, UncertaintyConfig,
                                 propagate)
from klastos.valuation import value_lot

AUJ = dt.date(2026, 9, 7)
BRUIT = NoiseModel(rel_sigma=0.03, abs_sigma=2e-4, lod=0.0)

PRIX_PROD = PriceSet(
    currency="USD", label="flux de test", is_production_source=True,
    prices={
        "Ni": MetalPrice("Ni", 16811.13, "USD", AUJ, "flux", "LME Ni cash"),
        "Co": MetalPrice("Co", 52359.78, "USD", AUJ, "flux", "Co std grade"),
    },
)
TERMES = PayableTerms(market="test", payables={"Ni": 0.72, "Co": 0.72},
                      as_of=AUJ, source="contrat client", validated=True)


def _contexte(profil="mixed_ev", atteste=True, closure=1.0, **kw):
    keys, _, journal = ProvenanceDeclaration(
        "vehicule_electrique", attested=atteste
    ).resolve()
    lot = make_lot(rng=1, profile=profil, noise=BRUIT, phase_keys=keys,
                   closure=closure)
    rep = propagate(lot.b_measured, phase_keys=keys,
                    config=UncertaintyConfig(noise=BRUIT, seed=0, n_draws=60,
                                             n_bound_draws=15))
    return lot, rep, journal


@pytest.fixture(scope="module")
def contexte():
    return _contexte()


@pytest.fixture(scope="module")
def rapport(contexte):
    lot, rep, journal = contexte
    v = value_lot(rep, prices=PRIX_PROD, terms=TERMES,
                  spec=REFERENCE_SPECS["ncm_cif_coree"],
                  processing_cost=350.0, margin_rate=0.15, today=AUJ)
    return build_report("LOT-001", "Client Test", rep, v, journal,
                        issued_on=AUJ)


# ==========================================================================
# 1. Verrous de sortie
# ==========================================================================

def test_une_donnee_synthetique_est_refusee(contexte):
    lot, rep, journal = contexte
    with pytest.raises(ReportRefused, match="livrable client"):
        build_report("L", "C", rep, None, journal, lot=lot)


def test_une_source_de_prix_de_demonstration_est_refusee(contexte):
    _, rep, journal = contexte
    v = value_lot(rep, prices=demo_price_set(),
                  terms=demo_payable_terms()["cif_coree_sud"],
                  today=AUJ, allow_stale=True)
    with pytest.raises(ReportRefused, match="production"):
        build_report("L", "C", rep, v, journal)


def test_un_bouclage_hors_tolerance_est_refuse():
    """Le seuil vient du module : le test suit l'arbitrage, pas l'inverse."""
    from klastos.solver import CLOSURE_REJECT

    _, rep, journal = _contexte(closure=1.0 - CLOSURE_REJECT - 0.05)
    with pytest.raises(ReportRefused, match="Bouclage"):
        build_report("L", "C", rep, None, journal)


def test_le_mode_demonstration_marque_le_document(contexte):
    lot, rep, journal = contexte
    r = build_report("L", "C", rep, None, journal, lot=lot, allow_demo=True)
    assert r.is_demo
    assert "NON OPPOSABLE" in r.to_markdown()
    assert any("demonstration" in m.lower() for m in r.limitations)


def test_un_rapport_valide_n_est_pas_marque_demo(rapport):
    assert rapport.is_demo is False
    assert "NON OPPOSABLE" not in rapport.to_markdown()


# ==========================================================================
# 2. Separation ferme / non identifiable
# ==========================================================================

def test_la_ventilation_n_est_jamais_un_chiffre_unique(rapport):
    vent = rapport.section("Ventilation par grade")
    assert vent is not None
    for row in vent.rows:
        assert "\u2013" in row.value, row.label     # toujours une fourchette
        assert row.status == "ouvert"


def test_la_mention_de_non_identifiabilite_figure(rapport):
    vent = rapport.section("Ventilation par grade")
    assert any(NOTE_NON_IDENTIFIABLE in n.lower() for n in vent.notes)
    assert "DOMAINES COMPATIBLES" in vent.intro


def test_aucun_grade_nmc_dans_les_grandeurs_fermes(rapport):
    fermes = rapport.section(SECTION_FERMES)
    for row in fermes.rows:
        assert not row.label.startswith("NMC 1")
        assert not row.label.startswith("NMC 6")
        assert not row.label.startswith("NMC 8")


def test_les_teneurs_elementaires_sont_fermes(rapport):
    fermes = rapport.section(SECTION_FERMES)
    labels = {row.label for row in fermes.rows}
    for el in ("Ni total", "Co total", "Li total"):
        assert el in labels


# ==========================================================================
# 3. Identifiable n'est pas exploitable
# ==========================================================================

def test_le_statut_mal_determine_existe(rapport):
    fermes = rapport.section(SECTION_FERMES)
    statuts = {row.status for row in fermes.rows}
    assert "ferme_large" in statuts, "aucune grandeur mal determinee detectee"
    assert "ferme" in statuts


def test_le_rendu_distingue_les_deux_statuts(rapport):
    md = rapport.to_markdown()
    # Par le catalogue, pas en dur : le libelle est traduit, et un texte
    # francais fige ici ferait echouer le test sur un rapport anglais.
    assert i18n.t("rapport.statut.ferme_large", rapport.langue) in md
    assert MENTION_MAL_DETERMINE in md


def test_les_grandeurs_mal_determinees_sont_listees_en_avertissement(rapport):
    """
    Le libelle vient du catalogue, donc on en extrait la part INVARIANTE :
    ce qui est entre les champs de format. Figer la phrase entiere
    obligerait a reproduire ici le nombre et la liste du lot d'exemple, et
    figer un texte francais ferait echouer le test en anglais.
    """
    modele = i18n.CATALOGUE["rapport.note.mal_determinees"][rapport.langue]
    fragment = modele.split("{liste}")[0].split("}")[-1].strip()
    assert fragment, "modele sans part invariante : le test ne mord plus"
    assert any(fragment in w for w in rapport.warnings), fragment


def test_le_critere_est_relatif_pas_absolu(rapport):
    """
    Une teneur en nickel de 19 % connue a plus ou moins 1 point est bonne.
    Une phase a 0,9 % connue a plus ou moins 1 point ne l'est pas.
    """
    fermes = rapport.section(SECTION_FERMES)
    par_label = {row.label: row for row in fermes.rows}
    assert par_label["Ni total"].status == "ferme"
    assert par_label["Cathodes totales"].status == "ferme"


# ==========================================================================
# 4. Levier d'amelioration : ce que le client peut acheter
# ==========================================================================

def test_les_goulots_structurels_sont_expliques(rapport):
    lev = rapport.section(SECTION_REDUIRE)
    assert lev is not None and lev.rows
    for row in lev.rows:
        assert "DRX" in row.note or "structurale" in row.note
    assert any("DRX" in n for n in lev.notes)


def test_le_piege_du_sommet_est_signale_quand_il_survient(rapport):
    """
    Le piege depend du lot : il ne se declenche pas systematiquement. La
    regle testee est conditionnelle - s'il est detecte, il DOIT etre dit.
    """
    _, rep, _ = _contexte()
    detecte = any(r.apparent_uniqueness_risk for r in rep.results)
    present = AVERTISSEMENT_SOMMET in rapport.to_markdown()
    assert present == detecte


def test_le_piege_du_sommet_est_bien_remonte_sur_un_lot_degenere():
    """Sur liste large, la degenerescence est de rang 2 et le piege apparait."""
    lot, rep, journal = _contexte(atteste=False)
    assert rep.degeneracy == 2
    pieges = [r for r in rep.results if r.apparent_uniqueness_risk]
    if not pieges:
        pytest.skip("aucun piege sur ce tirage")
    r = build_report("L", "C", rep, None, journal)
    assert AVERTISSEMENT_SOMMET in r.warnings
    assert AVERTISSEMENT_SOMMET in r.to_markdown()


# ==========================================================================
# 5. Valorisation
# ==========================================================================

def test_la_valorisation_est_une_fourchette(rapport):
    val = rapport.section("Valorisation")
    ligne = next(r for r in val.rows if "MAXIMAL" in r.label)
    assert "\u2013" in ligne.value
    assert "USD/t" in ligne.value


def test_la_valorisation_declare_son_assise(rapport):
    val = rapport.section("Valorisation")
    assert "Aucune ventilation par grade" in val.intro


def test_les_ecarts_de_specification_sont_remontes(rapport):
    conf = rapport.section("Conformite a la specification")
    if conf is not None:
        assert conf.rows
        assert any("decotes" in n for n in conf.notes)


def test_un_rapport_sans_valorisation_reste_valide(contexte):
    _, rep, journal = contexte
    r = build_report("L", "C", rep, None, journal)
    assert r.section("Valorisation") is None
    assert r.section("Grandeurs fermes") is not None


# ==========================================================================
# 6. Tracabilite et limites
# ==========================================================================

def test_le_journal_de_provenance_est_repris(rapport):
    # Les deux lignes sont traduites : on compare donc la part INVARIANTE
    # de leur gabarit, celle qui vit entre les champs de format. Un texte
    # francais non accentue fige ici ne passerait plus.
    for cle, champ in (("journal.provenance.declaree", "{profil}"),
                       ("journal.provenance.attestation", "{texte}")):
        modele = i18n.CATALOGUE[cle][rapport.langue]
        fragment = modele.split(champ)[0].split("}")[-1].strip(" :«")
        assert fragment, cle
        assert any(fragment in t for t in rapport.traceability), fragment


def test_la_provenance_des_prix_est_reprise(rapport):
    assert any("LME Ni cash" in t for t in rapport.traceability)


def test_les_limites_normalisees_figurent(rapport):
    texte = " ".join(rapport.limitations)
    assert NOTE_CARBONE in texte.lower()
    assert NOTE_NON_IDENTIFIABLE in texte.lower()
    assert MENTION_DETECTION in rapport.limitations


def test_la_limite_de_detection_est_declaree(rapport):
    assert "ne vaut pas certification" in rapport.to_markdown()


def test_les_avertissements_sont_dedupliques(rapport):
    assert len(rapport.warnings) == len(set(rapport.warnings))


# ==========================================================================
# 7. Rendu
# ==========================================================================

def test_le_markdown_est_complet(rapport):
    md = rapport.to_markdown()
    for titre in ("# Rapport de lot LOT-001", "## Grandeurs fermes",
                  "## Ventilation par grade", "## Valorisation",
                  "## Limites méthodologiques déclarées",
                  "## Traçabilité"):
        assert titre in md, titre
    # Le renvoi au protocole clot le document, dans les deux langues.
    assert md.rstrip().endswith("*")
    assert i18n.t("rapport.protocole.renvoi", rapport.langue) in md


def test_le_rapport_porte_client_et_date(rapport):
    md = rapport.to_markdown()
    assert "Client Test" in md
    assert AUJ.isoformat() in md


def test_section_absente_rend_none(rapport):
    assert rapport.section("Section qui n'existe pas") is None


def test_systeme_bien_pose_sans_section_ventilation():
    keys = [k for k in ProvenanceDeclaration().resolve()[0]
            if k not in ("NMC111", "NMC532", "LCO", "LMO")]
    lot = make_lot(rng=4, profile="gigafactory_nmc", noise=BRUIT,
                   phase_keys=keys)
    rep = propagate(lot.b_measured, phase_keys=keys,
                    config=UncertaintyConfig(noise=BRUIT, seed=0, n_draws=40,
                                             n_bound_draws=10))
    r = build_report("L", "C", rep, None, [])
    assert rep.degeneracy == 0
    assert r.section("Ventilation par grade") is None
    assert r.section("Comment reduire l'incertitude") is None


# ==========================================================================
# 6. Licence de rediffusion : le document peut-il sortir de la maison ?
# ==========================================================================

def _prix_agence(licence: bool) -> PriceSet:
    """Instantane d'agence, avec ou sans droit de rediffusion."""
    return PriceSet(
        currency="USD", label="fastmarkets du 2026-09-07",
        is_production_source=True, origin="fastmarkets",
        redistribution_licensed=licence,
        prices={
            "Ni": MetalPrice("Ni", 16811.13, "USD", AUJ, "fastmarkets",
                             "LME Ni cash"),
            "Co": MetalPrice("Co", 52359.78, "USD", AUJ, "fastmarkets",
                             "Co std grade"),
        },
    )


def _valorisation(contexte, licence: bool):
    _, rep, _ = contexte
    return value_lot(rep, prices=_prix_agence(licence), terms=TERMES, today=AUJ)


def test_des_prix_d_agence_sans_licence_ne_sortent_pas_de_la_maison(contexte):
    """
    Un abonnement d'agence couvre l'usage interne, pas la rediffusion. Le
    refus porte sur la SORTIE du document, pas sur le calcul.
    """
    from klastos.report import DESTINATAIRE_TIERS

    _, rep, journal = contexte
    with pytest.raises(ReportRefused, match="licence de rediffusion"):
        build_report("L", "C", rep, _valorisation(contexte, False), journal,
                     issued_on=AUJ, destinataire=DESTINATAIRE_TIERS)


def test_les_memes_prix_passent_en_interne(contexte):
    from klastos.report import DESTINATAIRE_INTERNE

    _, rep, journal = contexte
    r = build_report("L", "C", rep, _valorisation(contexte, False), journal,
                     issued_on=AUJ, destinataire=DESTINATAIRE_INTERNE)
    assert r.lot_id == "L"


def test_avec_licence_le_document_sort(contexte):
    _, rep, journal = contexte
    r = build_report("L", "C", rep, _valorisation(contexte, True), journal,
                     issued_on=AUJ)
    assert r.lot_id == "L"


def test_le_destinataire_par_defaut_est_le_plus_contraignant(contexte):
    """
    Un rapport se fabrique pour un client. Le defaut doit donc etre celui
    qui refuse, pas celui qui laisse passer.
    """
    from klastos.report import DESTINATAIRE_TIERS
    import inspect

    assert (inspect.signature(build_report)
            .parameters["destinataire"].default == DESTINATAIRE_TIERS)


def test_un_destinataire_inconnu_est_refuse(contexte):
    """Une faute de frappe ne doit pas desactiver silencieusement le verrou."""
    _, rep, journal = contexte
    with pytest.raises(ValueError, match="destinataire inconnu"):
        build_report("L", "C", rep, None, journal, issued_on=AUJ,
                     destinataire="Interne")


def test_la_licence_survit_a_l_aller_retour_sur_disque(tmp_path):
    """
    Regression. Le drapeau etait ecrit dans l'instantane puis perdu a la
    relecture : plus rien dans le systeme ne savait si des prix pouvaient
    partir chez un client. Il ne restait que le libelle, du texte.
    """
    import json

    from klastos.market import load_price_set

    p = tmp_path / "snap.json"
    p.write_text(json.dumps({
        "label": "fastmarkets", "currency": "USD",
        "is_production_source": True, "redistribution_licensed": False,
        "prices": {"Ni": {"value_per_tonne": 16811.0, "as_of": "2026-09-07",
                          "source": "fastmarkets",
                          "reference_name": "LME Ni cash"}},
    }), encoding="utf-8")
    assert load_price_set(p).redistribution_licensed is False


def test_un_fichier_de_prix_du_client_n_est_pas_restreint(tmp_path):
    """
    Les prix que le client apporte sont les siens : aucune licence d'agence
    ne s'y applique, et le champ est absent de son fichier.
    """
    import json

    from klastos.market import load_price_set

    p = tmp_path / "prix_client.json"
    p.write_text(json.dumps({
        "label": "prix du client", "currency": "USD",
        "is_production_source": True,
        "prices": {"Ni": {"value_per_tonne": 16811.0, "as_of": "2026-09-07",
                          "source": "contrat client",
                          "reference_name": "LME Ni cash"}},
    }), encoding="utf-8")
    assert load_price_set(p).redistribution_licensed is True
