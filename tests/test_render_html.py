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

def test_la_valeur_payable_est_en_tete(document):
    """
    L'encadre de tete porte desormais « Valeur payable », avec sa base
    commerciale. Il ne promet plus une deduction de couts qui n'a pas lieu.
    """
    assert "Valeur payable" in document
    assert "Prix maximal à payer" not in document


def test_l_encadre_de_tete_survit_a_un_renommage_du_libelle():
    """
    LE PIEGE QUI A MOTIVE LA CLE DE LIGNE.

    `_verdict` retrouvait la ligne du prix par « "MAXIMAL" in
    r.label.upper() ». Le libelle etant traduit, le rapport ANGLAIS ne
    portait deja pas ce mot : l'encadre y disparaissait silencieusement,
    sans rien lever. La recherche se fait maintenant par cle, donc elle
    survit a la langue comme au renommage.
    """
    import inspect

    import klastos.render_html as rh

    import re

    source = inspect.getsource(rh._verdict)
    # Les commentaires CITENT l'ancienne faute : on ne lit que le CODE.
    code = re.sub(r"#.*", "", source)
    assert "LIGNE_PAYABLE" in code, (
        "la ligne du prix n'est plus retrouvee par sa cle")
    assert ".label" not in code, (
        "le rendu est revenu a une recherche dans le TEXTE AFFICHE")


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

# ==========================================================================
# Refonte visuelle du rapport, 25 octobre 2026
# ==========================================================================
#
# Trois demandes, et un piege trouve en chemin.
#
# TYPOGRAPHIE. Times New Roman pour tout le document : c'est la police des
# pieces contractuelles, et un rapport qui se discute en reunion gagne a en
# avoir l'allure. Interligne ramene a 1,45.
#
# LES BARRES. Elles ne disaient pas ce qu'elles devaient dire. L'echelle est
# commune a la section - 0 a 50 % sur les teneurs - alors que dix valeurs
# sur quatorze valent moins de 5 %. Chaque bande occupait donc 4 % de la
# piste, tassee a gauche, et l'intervalle d'une grandeur ferme faisait moins
# d'un pixel. La barre ne portait aucune information sur la FERMETE, qui est
# pourtant la seule question d'un acheteur.
#
# LA COLONNE PRECISION. « ± 10 % » se lit d'un coup d'oeil et se compare
# d'une ligne a l'autre. L'information existait - dans « 3,19 [2,86 - 3,52] »
# - mais elle demandait un calcul mental par ligne.

def _rapport_complet():
    """Un rapport qui porte toutes les natures de section."""
    from klastos.service import Demande, analyser

    return analyser(Demande(
        bulletin="data/exemples/bulletin_coherent.csv",
        provenance="vehicule_electrique", attestee=True,
        tirages=60, conseil_drx=True)).rapport


# --------------------------------------------------------------------------
# Typographie
# --------------------------------------------------------------------------

def test_les_commentaires_ne_partent_pas_dans_le_document():
    """
    Les commentaires de `CSS` sont ecrits en francais et expliquent des
    choix de rendu : ils s'adressent a qui maintient le module, pas au
    destinataire du rapport.

    Ils partaient pourtant dans CHAQUE document livre. Le test de fuite de
    vocabulaire les a trouves dans un rapport ANGLAIS, sur le mot
    « largeur » - un commentaire que je venais d'ecrire.

    Les retirer regle trois choses : plus de francais dans un document
    anglais, un fichier plus leger d'un tiers, et un client qui ouvre la
    source ne lit pas nos notes de travail.
    """
    from klastos.render_html import CSS, CSS_LIVRE, to_html

    assert "/*" in CSS, "la constante source doit garder ses commentaires"
    assert "/*" not in CSS_LIVRE
    assert len(CSS_LIVRE) < len(CSS) * 0.8

    # Et le document livre ne les porte pas davantage.
    html = to_html(_rapport_complet())
    assert "/*" not in html


def test_la_feuille_allegee_garde_toutes_ses_regles():
    """
    Garde du retrait. Une expression trop gourmande emporterait des regles
    avec les commentaires, et le document sortirait sans mise en page -
    sans qu'aucune erreur ne soit levee.
    """
    from klastos.render_html import CSS_LIVRE

    for regle in ("--f-body:", ".piste {", ".b-ferme", ".b-ouvert {",
                  ".c-prec", "@page", "@media print"):
        assert regle in CSS_LIVRE, (
            f"« {regle} » a disparu de la feuille livree")


def test_le_rapport_est_compose_en_times_new_roman():
    from klastos.render_html import CSS

    assert '--f-body: "Times New Roman"' in CSS
    assert '--f-display: "Times New Roman"' in CSS


def test_les_colonnes_de_chiffres_gardent_une_chasse_fixe():
    """
    Times New Roman n'a pas de chiffres tabulaires : un « 1 » y est plus
    etroit qu'un « 8 », et les virgules decimales d'une colonne cessent de
    s'aligner. Sur un tableau de teneurs, cet alignement est ce qui permet
    de comparer deux lignes d'un coup d'oeil.
    """
    from klastos.render_html import CSS

    assert "--f-mono:" in CSS
    assert "tabular-nums" in CSS
    for classe in (".val", ".prec"):
        bloc = CSS[CSS.index(classe + " {"):]
        bloc = bloc[:bloc.index("}")]
        assert "var(--f-mono)" in bloc, (
            f"{classe} a perdu sa chasse fixe : la colonne ne s'aligne plus")


def test_l_interligne_est_dans_la_fourchette_demandee():
    import re

    from klastos.render_html import CSS

    bloc = CSS[CSS.index("body {"):]
    bloc = bloc[:bloc.index("}")]
    trouve = re.search(r"line-height:\s*([\d.]+)", bloc)
    assert trouve is not None, "le corps n'a plus d'interligne declare"
    valeur = float(trouve[1])
    assert 1.0 <= valeur <= 1.5, (
        f"interligne {valeur} hors de la fourchette 1 a 1,5")


# --------------------------------------------------------------------------
# Les barres
# --------------------------------------------------------------------------

def test_une_grandeur_ferme_reste_visible():
    """
    Sur l'echelle commune, un intervalle ferme represente moins d'un pixel.
    Une largeur minimale le fait lire comme un TRAIT NET, ce qu'il est.
    """
    from klastos.render_html import CSS

    for classe in (".b-ferme", ".b-large", ".b-irr", ".b-ouvert"):
        bloc = CSS[CSS.index(classe + " "):]
        bloc = bloc[:bloc.index("}")]
        assert "min-width" in bloc, (
            f"{classe} n'a plus de largeur minimale : une grandeur ferme "
            f"redevient invisible")


def test_un_domaine_compatible_se_lit_comme_une_bande_floue():
    """
    Il etait dessine en contour vide, ce qui se lit comme une BOITE, donc
    comme des bornes nettes. Un domaine compatible est l'inverse : large et
    sans valeur privilegiee a l'interieur.
    """
    from klastos.render_html import CSS

    bloc = CSS[CSS.index(".b-ouvert {"):]
    bloc = bloc[:bloc.index("}")]
    assert "opacity" in bloc, (
        "le domaine compatible a perdu sa transparence : il redevient une "
        "boite a bornes nettes")


def test_la_piste_porte_des_reperes():
    """
    Ils situent la valeur sans qu'on ait a lire les bornes de l'echelle
    sous le tableau.
    """
    from klastos.render_html import CSS

    bloc = CSS[CSS.index(".piste {"):]
    bloc = bloc[:bloc.index("}")]
    assert "repeating-linear-gradient" in bloc


# --------------------------------------------------------------------------
# La colonne de precision, et le piege qu'elle a failli poser
# --------------------------------------------------------------------------

def test_la_precision_se_calcule_sur_la_valeur_centrale():
    from klastos.report import ReportRow
    from klastos.render_html import _precision

    r = ReportRow(label="x", value="", status="ferme",
                  low=0.90, high=1.10, point=1.00)
    assert _precision(r, "fr") == "± 10 %"


def test_sans_valeur_centrale_rien_n_est_affiche():
    """
    Un DOMAINE COMPATIBLE n'a pas de valeur centrale. En inventer une - le
    milieu de la plage - serait exactement le representant arbitraire que
    ce rapport refuse de presenter comme une estimation.
    """
    from klastos.report import ReportRow
    from klastos.render_html import _precision

    r = ReportRow(label="x", value="", status="ouvert",
                  low=0.0, high=0.33, point=None)
    assert _precision(r, "fr") == ""


def test_un_intervalle_plus_large_que_la_valeur_le_dit():
    from klastos.report import ReportRow
    from klastos.render_html import _precision

    r = ReportRow(label="x", value="", status="ferme_large",
                  low=0.0, high=0.172, point=0.0497)
    assert _precision(r, "fr") == "> 100 %"


def test_aucune_precision_dans_les_sections_de_largeur():
    """
    LE PIEGE, trouve en verifiant plutot qu'en supposant.

    Dans les sections de largeur - reduire, sensibles, scenario, drx,
    conseil - le champ `point` ne porte PAS une valeur centrale mais la
    LARGEUR AVANT dosage, dessinee en fantome derriere la largeur apres. La
    formule y rendait « ± 0 % », c'est-a-dire une precision PARFAITE, sur
    des lignes qui mesurent precisement une incertitude.

    C'est l'inverse exact de ce que le tableau dit. Un lecteur y aurait lu
    que les grandeurs les plus incertaines du rapport sont les mieux
    connues.
    """
    from klastos.render_html import to_html

    html = to_html(_rapport_complet())
    assert "± 0 %" not in html, (
        "une section de largeur affiche de nouveau une precision : « point »"
        " y est une largeur, pas une valeur centrale")
    assert html.count('c-prec">Pr') == 1, (
        "la colonne Precision apparait dans plus d'une section")


def test_la_precision_figure_bien_sur_les_grandeurs_fermes():
    """
    Le pendant positif. Sans lui, exclure la colonne de PARTOUT passerait
    le test ci-dessus sans rien dire.
    """
    import re

    from klastos.render_html import to_html

    html = to_html(_rapport_complet())
    valeurs = set(re.findall(r'class="c-prec prec">([^<]+)<', html))
    valeurs = {v for v in valeurs if v.strip()}
    assert len(valeurs) >= 3, (
        f"seulement {len(valeurs)} precision(s) distincte(s) : la colonne "
        f"n'informe plus")
    assert any("±" in v for v in valeurs)


# ==========================================================================
# L'echelle gradue la piste, et la remplit
# ==========================================================================
#
# Deux defauts du meme endroit, trouves en regardant le rendu plutot qu'en
# relisant le code.

def test_les_paliers_bornent_la_piste_perdue():
    """
    L'ancienne serie - 5, 10, 25, 50, 75, 100 % - etait trop lache. Un pic a
    26 % passait a 50 % : la section de scenario n'occupait que la MOITIE de
    sa piste, et toutes ses bandes etaient comprimees d'autant.

    Ce que garantit la serie, c'est le RAPPORT de deux paliers voisins :
    c'est lui qui borne la piste perdue dans le pire des cas.
    """
    from klastos.render_html import PALIERS

    # En dixiemes de pour-cent : 0,15 / 0,20 vaut 0,7499999999999999 en
    # flottant, et la garantie se jouerait sur le dernier bit.
    entiers = [round(x * 1000) for x in PALIERS]
    pires = [entiers[i] / entiers[i + 1] for i in range(len(entiers) - 1)]
    assert min(pires) >= 0.75, (
        f"un saut de palier laisse {(1 - min(pires)) * 100:.0f} % de la "
        f"piste inutilisee")


def test_les_paliers_restent_des_nombres_ronds():
    """
    Seules les deux bornes de l'echelle sont ecrites ; les reperes au quart
    doivent donc rester estimables de tete. Un palier a 0,37 serrerait mieux
    la piste et rendrait ses reperes illisibles.
    """
    from klastos.render_html import PALIERS

    for palier in PALIERS:
        dixiemes = round(palier * 1000, 6)
        assert dixiemes == int(dixiemes), (
            f"le palier {palier} n'est pas un nombre rond de pour-cent")


def test_les_paliers_sont_croissants():
    """`_echelle` rend le PREMIER palier qui couvre le pic : non trie, elle
    rendrait un palier trop court et les bandes deborderaient."""
    from klastos.render_html import PALIERS

    assert list(PALIERS) == sorted(PALIERS)
    assert PALIERS[-1] == 1.0, "aucun palier ne couvre une teneur de 100 %"


def test_toute_section_remplit_sa_piste():
    """
    Le pendant mesure, sur un vrai rapport : aucune section ne doit gacher
    plus du quart de sa piste.
    """
    from klastos.render_html import _echelle

    rapport = _rapport_complet()
    for section in rapport.sections:
        hauts = [r.high for r in section.rows if r.has_bar and r.high is not None]
        hauts += [r.point for r in section.rows if r.has_bar and r.point is not None]
        if not hauts:
            continue
        part = max(hauts) / _echelle(section)
        assert part >= 0.75, (
            f"« {section.title} » n'occupe que {part * 100:.0f} % de sa "
            f"piste : ses bandes sont comprimees d'autant")


def test_les_bornes_de_l_echelle_graduent_la_piste_et_pas_le_tableau():
    """
    LE SECOND DEFAUT. Les bornes s'etalaient sur toute la largeur du
    tableau : le « 0 % » tombait sous la colonne des libelles et le maximum
    sous celle des statuts, c'est-a-dire de part et d'autre d'une piste qui
    n'occupe qu'un quart de la ligne. Elles graduaient le tableau, pas la
    piste - et un lecteur qui s'y fie place les valeurs a plus de trois fois
    leur abscisse reelle.

    Les caler sur les largeurs declarees ne suffisait pas : quand la colonne
    de precision manque, les colonnes ne somment plus a 100 % et le
    navigateur redistribue le reste a sa guise - les bornes retombaient a
    cote de la piste, d'une section a l'autre et differemment. Elles vivent
    donc DANS la cellule de la piste, ou l'alignement ne depend plus d'aucun
    calcul de largeur.
    """
    import re

    from klastos.render_html import to_html

    html = to_html(_rapport_complet())
    pieds = re.findall(r"<tfoot>.*?</tfoot>", html, flags=re.S)
    assert pieds, "les bornes de l'echelle sont ressorties du tableau"
    for pied in pieds:
        cellule = pied[pied.index('<td class="c-bar">'):]
        cellule = cellule[:cellule.index("</td>")]
        assert 'class="echelle"' in cellule, (
            "les bornes ne sont plus dans la colonne de la piste : elles "
            "graduent de nouveau autre chose qu'elle")

    # Et aucune echelle ne doit subsister hors d'un pied de tableau.
    assert html.count('class="echelle"') == len(pieds)
