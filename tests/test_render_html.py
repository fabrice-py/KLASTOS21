"""Tests de klastos/render_html.py.

Le rendu HTML n'est pas de la decoration. C'est la forme sous laquelle le
rapport arrive chez le negociant, et c'est la seule forme qui MONTRE la
distinction que KLASTOS21 vend : une grandeur ferme est un trait fin, un
domaine compatible est une bande large.

Quatre exigences, dans cet ordre de gravite :

  1. Le document est bien forme et tout texte y est echappe.
  2. Une grandeur non identifiable n'est jamais presentee comme un chiffre.
  3. La gravite d'un diagnostic est LUE, jamais devinee dans une phrase.
  4. Dans une section de largeurs, le vocabulaire change : une fourchette de
     20 points ne doit pas s'afficher avec la mention "ferme".
"""

import datetime as dt
import html.parser

import pytest

from klastos import i18n
from klastos.generator import NoiseModel, make_lot
from klastos.market import MetalPrice, PayableTerms, PriceSet
from klastos.provenance import ProvenanceDeclaration
from klastos.render_html import (SECTIONS_LARGEUR, STATUTS, STATUTS_LARGEUR,
                                 _barre, _echelle, to_html)
from klastos.report import (SECTION_VENTILATION, LotReport, ReportRow,
                            ReportSection, build_report)
from klastos.uncertainty import UncertaintyConfig, propagate
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


@pytest.fixture(scope="module")
def rapport() -> LotReport:
    keys, _, journal = ProvenanceDeclaration(
        "vehicule_electrique", attested=True).resolve()
    lot = make_lot(rng=1, profile="mixed_ev", noise=BRUIT, phase_keys=keys)
    rep = propagate(lot.b_measured, phase_keys=keys,
                    config=UncertaintyConfig(noise=BRUIT, seed=0, n_draws=60,
                                             n_bound_draws=15))
    v = value_lot(rep, prices=PRIX_PROD, terms=TERMES, today=AUJ)
    return build_report("LOT-001", "Client Test", rep, v, journal,
                        issued_on=AUJ)


@pytest.fixture(scope="module")
def document(rapport) -> str:
    return to_html(rapport)


# ==========================================================================
# 1. Le document est bien forme
# ==========================================================================

class _Verificateur(html.parser.HTMLParser):
    """Verifie l'appariement des balises. Suffisant ici : on genere le HTML."""

    AUTONOMES = {"meta", "link", "br", "img", "input", "hr"}

    def __init__(self) -> None:
        super().__init__()
        self.pile: list[str] = []
        self.erreurs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.AUTONOMES:
            self.pile.append(tag)

    def handle_endtag(self, tag):
        if not self.pile or self.pile[-1] != tag:
            self.erreurs.append(
                f"</{tag}> ferme {self.pile[-1] if self.pile else 'rien'}"
            )
        else:
            self.pile.pop()


def test_le_document_est_bien_forme(document):
    v = _Verificateur()
    v.feed(document)
    assert v.erreurs == []
    assert v.pile == [], f"balises non fermees : {v.pile}"


def test_le_document_est_autonome(document):
    """Pas de script, pas de feuille de style externe hors polices."""
    assert document.startswith("<!doctype html>")
    assert "<script" not in document.lower()
    assert "<style>" in document
    liens = document.lower().count('<link rel="stylesheet"')
    assert liens <= 1, "une seule feuille externe, les polices"


def test_le_document_declare_son_encodage(document):
    """Sans cela, les accents se cassent a l'ouverture depuis le disque."""
    assert '<meta charset="utf-8">' in document


def test_le_lot_et_le_client_figurent_en_tete(document):
    assert "LOT-001" in document
    assert "Client Test" in document


# ==========================================================================
# 2. Echappement : une injection ne doit pas casser le document
# ==========================================================================

def _rapport_hostile() -> LotReport:
    mechant = '<script>alert("x")</script> & "guillemets" <b>'
    return LotReport(
        lot_id=mechant, client=mechant, issued_on=AUJ,
        sections=[ReportSection(
            title=mechant, intro=mechant,
            rows=[ReportRow(label=mechant, value=mechant, status="ferme",
                            low=0.01, high=0.02)],
            notes=[mechant],
        )],
        warnings=[mechant], limitations=[mechant], traceability=[mechant],
        meta={"degeneracy": 2},
    )


def test_tout_texte_est_echappe():
    """
    Le libelle d'un lot vient du client. Un nom de fichier malicieux ne doit
    pas pouvoir injecter de balise dans un document que nous signons.
    """
    doc = to_html(_rapport_hostile())
    assert "<script>" not in doc
    assert "&lt;script&gt;" in doc
    v = _Verificateur()
    v.feed(doc)
    assert v.erreurs == [] and v.pile == []


# ==========================================================================
# 3. La gravite est une donnee, pas une heuristique de texte
# ==========================================================================

def _tuile_de(doc: str, libelle: str) -> str:
    """Rend la classe CSS de la tuile portant ce libelle."""
    import re

    motifs = re.findall(
        r'<div class="tuile (\w+)"><div class="tuile-k">([^<]*)</div>', doc)
    for classe, lab in motifs:
        if libelle.lower() in lab.lower():
            return classe
    raise AssertionError(f"tuile introuvable : {libelle} (vues : {motifs})")


def test_un_bouclage_en_alerte_s_affiche_en_alerte():
    """
    Regression. La gravite etait devinee en cherchant "ALERTE" dans le
    message de bouclage. Ce message ne contient pas le mot : un lot en
    alerte s'affichait comme conforme, en bleu.
    """
    from klastos.solver import CLOSURE_ALERT, CLOSURE_REJECT

    keys, _, journal = ProvenanceDeclaration(
        "vehicule_electrique", attested=True).resolve()
    manquant = (CLOSURE_ALERT + CLOSURE_REJECT) / 2       # strictement entre
    lot = make_lot(rng=1, profile="mixed_ev", noise=BRUIT, phase_keys=keys,
                   closure=1.0 - manquant)
    rep = propagate(lot.b_measured, phase_keys=keys,
                    config=UncertaintyConfig(noise=BRUIT, seed=0, n_draws=40,
                                             n_bound_draws=10))
    assert rep.meta["closure"].status == "alerte", "le lot teste n'est pas en alerte"

    r = build_report("L", "C", rep, None, journal, issued_on=AUJ)
    assert _tuile_de(to_html(r), "bouclage") == "alerte"


def test_un_bouclage_conforme_s_affiche_comme_conforme(rapport, document):
    assert rapport.section("Diagnostic du bulletin").rows[0].severity == "ok"
    assert _tuile_de(document, "bouclage") == "ok"


def test_la_degenerescence_n_est_pas_une_alerte(rapport, document):
    """
    Deux degres de liberte, c'est la realite du systeme Li-Ni-Mn-Co-O. Le
    rapport la rend visible ; il ne la signale pas comme une anomalie.
    """
    assert rapport.meta["degeneracy"] > 0
    # Le libelle passe par le catalogue : fige en dur et non accentue, il
    # ne correspondait plus des que le rapport a porte ses accents.
    assert _tuile_de(
        document,
        i18n.t("rapport.ligne.degres", rapport.langue)) == "ok"


# ==========================================================================
# 4. Les barres d'intervalle
# ==========================================================================

def test_une_grandeur_sans_bornes_n_a_pas_de_barre():
    assert _barre(ReportRow("x", "1", "ferme"), 1.0) == ""


def test_une_borne_basse_negative_ne_sort_pas_de_la_piste():
    """
    Les bornes calculees valent parfois -1e-18. Sans garde, la bande part
    d'une position negative et deborde a gauche.
    """
    barre = _barre(ReportRow("x", "0", "ouvert", low=-1e-18, high=0.02), 0.5)
    assert "left:0.00%" in barre


def test_une_barre_ne_deborde_jamais_a_droite():
    barre = _barre(ReportRow("x", "", "ouvert", low=0.4, high=9.0), 0.5)
    import re
    g = float(re.search(r"left:([\d.]+)%", barre).group(1))
    w = float(re.search(r"width:([\d.]+)%", barre).group(1))
    assert g + w <= 100.0 + 1e-9


def test_une_barre_ferme_est_plus_fine_qu_un_domaine_compatible(rapport):
    """
    C'EST L'ARGUMENT DU PRODUIT. Si cette assertion tombe, le document ne
    montre plus ce qu'il est cense montrer.

    La comparaison exclut les grandeurs "ferme_large". Ce n'est pas un
    arrangement : une grandeur mal determinee est justement celle dont la
    fourchette est trop large pour etre exploitee, et le rapport la signale
    comme telle. Mesure sur le lot de reference, elle dessinait la barre la
    plus large de la section (36,0 % contre 39,9 % pour le pire domaine
    compatible) : comparer les deux pires revenait a opposer les deux cas
    qui doivent se ressembler, avec 11 % de marge. En s'en tenant aux
    grandeurs reellement fermes, la marge passe a un facteur 3.
    """
    import re

    fermes = rapport.section("Grandeurs fermes")
    vent = rapport.section("Ventilation par grade")
    assert fermes and vent

    def largeurs(section, statuts):
        e = _echelle(section)
        out = []
        for r in section.rows:
            if r.status not in statuts:
                continue
            b = _barre(r, e)
            if b:
                out.append(float(re.search(r"width:([\d.]+)%", b).group(1)))
        return out

    traits = largeurs(fermes, {"ferme"})
    bandes = largeurs(vent, {"ouvert"})
    assert traits and bandes

    assert max(traits) < 0.5 * max(bandes), (
        f"le trait ferme le plus epais fait {max(traits):.1f} % de la piste, "
        f"la bande compatible la plus large {max(bandes):.1f} % : le "
        "document ne montre plus la distinction qu'il vend"
    )


def test_l_echelle_couvre_la_borne_haute_la_plus_elevee(rapport):
    for s in rapport.sections:
        hauts = [r.high for r in s.rows if r.has_bar]
        if hauts:
            assert _echelle(s) >= max(hauts)


def test_l_echelle_n_est_jamais_nulle():
    vide = ReportSection(title="x", rows=[ReportRow("a", "b")])
    assert _echelle(vide) > 0.0


# ==========================================================================
# 5. Le vocabulaire des sections de largeurs
# ==========================================================================

def _bloc_de_section(document: str, titre: str) -> str:
    """
    Isole le HTML d'une section. Le titre est echappe avant la recherche :
    "Comment reduire l'incertitude" sort du rendu en l&#x27;incertitude.
    """
    import html as _h

    marqueur = f"<h2>{_h.escape(titre)}</h2>"
    assert marqueur in document, f"section absente du rendu : {titre}"
    return document.split(marqueur)[1].split("</section>")[0]


def test_les_sections_de_largeurs_existent_dans_le_rapport(rapport):
    """
    Garde-fou : si une CLE change dans report.py, le rendu se trompe.

    Le test comparait les titres. Il ne pouvait donc pas survivre a la
    traduction du rapport : en anglais, aucun titre ne correspondait plus,
    et le garde-fou aurait signale une desynchronisation inexistante.
    """
    cles = {s.cle for s in rapport.sections}
    assert SECTIONS_LARGEUR & cles, (
        "aucune section de largeurs reconnue ; SECTIONS_LARGEUR est "
        "desynchronise de report.py"
    )


def test_une_largeur_n_est_jamais_etiquetee_ferme(rapport, document):
    """
    Regression. Dans "Grandeurs sensibles a la qualite du bulletin", les
    lignes portent status="ferme" pour dire que la largeur est REDUCTIBLE.
    Affichee telle quelle, la mention "ferme" en regard d'une fourchette de
    20 points dit exactement l'inverse de ce qu'il faut lire.
    """
    import re

    section = next((s for s in rapport.sections
                    if s.cle in SECTIONS_LARGEUR and s.rows), None)
    if section is None:
        pytest.skip("aucune section de largeurs dans ce lot")

    bloc = _bloc_de_section(document, section.title)
    mentions = set(re.findall(r'class="st st-\w+">([^<]*)</span>', bloc))
    attendues = {i18n.t(cle, rapport.langue)
                 for cle, _, _ in STATUTS_LARGEUR.values()}
    assert mentions and mentions <= attendues, (
        f"vocabulaire inattendu dans une section de largeurs : {mentions}"
    )
    assert STATUTS["ferme"][0] not in mentions


def test_une_largeur_irreductible_est_distinguee_d_une_reductible():
    """Les deux ne demandent pas la meme action au client."""
    assert (STATUTS_LARGEUR["ouvert"][2]
            != STATUTS_LARGEUR["ferme"][2]), "meme couleur de barre"
    assert (STATUTS_LARGEUR["ouvert"][0]
            != STATUTS_LARGEUR["ferme"][0]), "meme libelle"


def test_l_echelle_d_une_section_de_largeurs_est_en_points(rapport, document):
    section = next((s for s in rapport.sections
                    if s.cle in SECTIONS_LARGEUR and s.rows), None)
    if section is None:
        pytest.skip("aucune section de largeurs dans ce lot")
    bloc = _bloc_de_section(document, section.title)
    assert "<span>0 points</span>" in bloc


# ==========================================================================
# 6. Ce que le document doit dire, et ne pas dire
# ==========================================================================

def test_le_prix_maximal_est_en_tete(document):
    assert "Prix maximal à payer" in document


def test_sans_prix_le_document_le_dit_au_lieu_d_inventer_un_chiffre(rapport):
    nu = LotReport(lot_id="L", client="C", issued_on=AUJ,
                   sections=[s for s in rapport.sections
                             if s.title != "Valorisation"],
                   meta=rapport.meta)
    doc = to_html(nu)
    assert "non calculée" in doc
    assert "Prix maximal" not in doc.split('class="verdict-n"')[0] \
        or "Valorisation" in doc


def test_un_domaine_compatible_est_presente_comme_un_domaine(rapport, document):
    vent = rapport.section(SECTION_VENTILATION)
    if vent is None:
        pytest.skip("lot sans grandeur non identifiable")
    # La table porte une CLE, pas le texte : il se resout a la langue.
    libelle = i18n.t(STATUTS["ouvert"][0], rapport.langue)
    assert libelle in document
    for r in vent.rows:
        assert "–" in r.value or "-" in r.value, (
            f"{r.label} affiche un chiffre unique alors qu'elle est ouverte"
        )


def test_la_banniere_de_demonstration_apparait_si_le_rapport_est_une_demo(rapport):
    rapport.is_demo = True
    try:
        assert "non opposable" in to_html(rapport)
    finally:
        rapport.is_demo = False


def test_les_annexes_sont_rendues(rapport):
    rapport.limitations.append("limite de test")
    rapport.traceability.append("trace de test")
    try:
        doc = to_html(rapport)
        assert "limite de test" in doc and "trace de test" in doc
    finally:
        rapport.limitations.pop()
        rapport.traceability.pop()


def test_une_section_vide_n_est_pas_rendue_en_tableau_fantome():
    r = LotReport(lot_id="L", client="C", issued_on=AUJ,
                  sections=[ReportSection(title="Vide", intro="rien")])
    doc = to_html(r)
    assert "<table>" not in doc


# ==========================================================================
# 7. Impression
# ==========================================================================

def test_le_document_est_regle_pour_l_impression(document):
    assert "@page" in document and "A4" in document
    assert "@media print" in document


def test_le_theme_est_clair_uniquement(document):
    """
    Un rapport client sur fond sombre deconcerte, et l'impression se fait
    toujours sur blanc. Le choix est delibere : pas de media sombre.
    """
    assert "prefers-color-scheme" not in document