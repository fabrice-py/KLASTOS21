"""Tests du scenario « et si l'oxygene etait dose ».

L'oxygene n'est presque jamais dose en analyse de routine de black mass.
Le calcul principal tourne donc SANS lui, et c'est la bonne decision. Reste
une question du client : qu'est-ce que je gagnerais a le faire doser ?

Cette section y repond. Elle est aussi la plus facile a rater, parce qu'il
existe une maniere simple de la produire - reinjecter l'oxygene PREDIT par
la reconstitution - qui donne des chiffres d'apparence exacte et de valeur
nulle. Quatre exigences :

  1. Conditionner ne peut qu'ELARGIR l'information, jamais la degrader.
  2. Le scenario BALAYE la plage compatible, il ne se pose pas sur un point.
  3. Ce qu'un dosage n'apporte pas est dit aussi clairement que ce qu'il
     apporte.
  4. Rien de ce scenario n'entre dans le resultat principal.
"""

import numpy as np
import pytest

from klastos.elements import ELEMENTS
from klastos.identifiability import (SCENARIO_ELEMENTS,
                                     SCENARIO_ELEMENTS_VALIDATED,
                                     compatible_bounds, conditional_bounds,
                                     element_scenario, is_identifiable,
                                     null_space, standard_functionals)
from klastos.ingestion import read_bulletin
from klastos.phases import cathode_indicator, stoichiometry_matrix
from klastos.provenance import ProvenanceDeclaration
from klastos.report import (SECTION_SCENARIO, MENTION_SCENARIO,
                            MENTION_SCENARIO_PIEGE,
                            TITRE_SCENARIO, build_report)
from klastos.solver import solve
from klastos.uncertainty import UncertaintyConfig, propagate

import pathlib

RACINE = pathlib.Path(__file__).resolve().parent.parent
BULLETIN = RACINE / "data" / "exemples" / "bulletin_coherent.csv"


@pytest.fixture(autouse=True)
def _bulletin_present():
    if not BULLETIN.exists():
        pytest.skip("bulletin d'exemple absent")


@pytest.fixture(scope="module")
def contexte():
    """Le chemin REEL : bulletin sans oxygene, provenance attestee."""
    lu = read_bulletin(BULLETIN)
    keys, _, journal = ProvenanceDeclaration(
        "vehicule_electrique", attested=True).resolve()
    els = lu.measured_elements
    A, _, k = stoichiometry_matrix(phase_keys=keys, elements=els)
    A_tot, els_tot, _ = stoichiometry_matrix(phase_keys=keys)
    c_O = A_tot[els_tot.index("O")]
    x0 = solve(lu.b, phase_keys=keys, elements=els).x
    N = null_space(A)
    fs = standard_functionals(phase_keys=keys, elements=els)
    return dict(lu=lu, keys=keys, els=els, A=A, c_O=c_O, x0=x0, N=N,
                fs=fs, k=k, journal=journal)


@pytest.fixture(scope="module")
def scenario(contexte):
    s = element_scenario(contexte["x0"], contexte["N"], contexte["fs"],
                         contexte["c_O"], "O")
    assert s is not None, "aucun scenario sur un bulletin sans oxygene"
    return s


# ==========================================================================
# 1. Le socle : l'oxygene n'est pas dose, et cela se voit
# ==========================================================================

def test_l_oxygene_est_absent_du_bulletin_reel(contexte):
    assert "O" not in contexte["els"]


def test_sans_oxygene_la_degenerescence_augmente_d_un_degre(contexte):
    """Mesure, pas supposition. C'est elle qui justifie tout ce module."""
    A_sans = contexte["A"]
    A_avec, _, _ = stoichiometry_matrix(phase_keys=contexte["keys"])
    n_sans = null_space(A_sans).shape[1]
    n_avec = null_space(A_avec).shape[1]
    assert n_sans == n_avec + 1


def test_cathodes_totales_n_est_pas_ferme_sans_oxygene(contexte):
    """
    L'engagement « Cathodes totales ferme » suppose l'oxygene dose. Sur un
    bulletin reel il ne tient pas, et le rapport doit le dire au lieu de
    l'affirmer.
    """
    c = cathode_indicator(phase_keys=contexte["k"])
    assert not is_identifiable(c, contexte["N"])

    A_avec, _, k_avec = stoichiometry_matrix(phase_keys=contexte["keys"])
    assert is_identifiable(cathode_indicator(phase_keys=k_avec),
                           null_space(A_avec))


# ==========================================================================
# 2. Conditionner ne degrade jamais
# ==========================================================================

def test_conditionner_ne_peut_qu_retrecir_le_domaine(contexte, scenario):
    x0, N, c_O = contexte["x0"], contexte["N"], contexte["c_O"]
    for f in contexte["fs"]:
        lo, hi = compatible_bounds(x0, N, f.c)
        for t in (0.0, 0.5, 1.0):
            v = scenario.value_low + t * scenario.range_width
            a, z = conditional_bounds(x0, N, f.c, c_O, v)
            assert z - a <= (hi - lo) + 1e-9, f.key
            assert lo - 1e-9 <= a <= z <= hi + 1e-9, f.key


def test_sans_espace_nul_conditionner_ne_change_rien(contexte):
    """
    Systeme bien pose : il n'y a plus rien a conditionner, et la valeur
    rendue est la grandeur elle-meme. On la compare DIRECTEMENT a c @ x0
    plutot qu'au resultat de `compatible_bounds` : depuis le refactor les
    deux empruntent le meme chemin, et les opposer ne prouverait plus rien.
    """
    x0 = contexte["x0"]
    vide = np.zeros((len(x0), 0))
    c = contexte["fs"][0].c
    attendu = float(c @ x0)
    lo, hi = conditional_bounds(x0, vide, c, contexte["c_O"], 0.1)
    assert lo == pytest.approx(attendu)
    assert hi == pytest.approx(attendu)


# ==========================================================================
# 3. LE PIEGE. Le scenario balaie, il ne se pose pas sur un point.
# ==========================================================================

def test_la_valeur_predite_produirait_une_precision_fictive(contexte, scenario):
    """
    Ce test DEMONTRE le piege, il ne le valide pas.

    En reinjectant l'oxygene predit par la reconstitution, les grandeurs
    ressortent exactement determinees. Cette precision est un artefact : la
    valeur predite sort de la solution elle-meme, elle n'apporte aucune
    information independante. C'est le piege du sommet, dans sa forme la
    plus pure.
    """
    x0, N, c_O = contexte["x0"], contexte["N"], contexte["c_O"]
    o_predit = float(c_O @ x0)
    c = cathode_indicator(phase_keys=contexte["k"])

    a, z = conditional_bounds(x0, N, c, c_O, o_predit)
    assert z - a < 1e-7, "le piege n'existe plus, ce test n'a plus d'objet"

    lo, hi = compatible_bounds(x0, N, c)
    assert hi - lo > 1e-3, "la grandeur etait deja determinee"


def test_le_scenario_balaie_la_plage_au_lieu_de_s_y_poser(contexte, scenario):
    """
    Verrou. La plage retenue vient de compatible_bounds sur l'oxygene, et
    la valeur predite n'en est qu'un point parmi d'autres.

    La tolerance n'est pas une facilite. La solution NNLS se pose sur un
    SOMMET du domaine compatible : l'oxygene predit coincide ici avec la
    borne haute, au bit pres. Selon la bibliotheque d'algebre lineaire
    installee, le programme lineaire rend cette borne a un ULP pres -
    mesure : 3e-17, soit 3e-15 de la largeur de la plage. Une comparaison
    stricte passe sur une machine et echoue sur une autre.

    C'est aussi un rappel de fond : si le point predit tombe sur un bord,
    s'y poser pour produire le scenario serait doublement trompeur.
    """
    x0, N, c_O = contexte["x0"], contexte["N"], contexte["c_O"]
    o_predit = float(c_O @ x0)
    marge = 1e-6 * scenario.range_width
    assert (scenario.value_low - marge
            <= o_predit
            <= scenario.value_high + marge), (
        f"oxygene predit {o_predit!r} hors de la plage compatible "
        f"[{scenario.value_low!r}, {scenario.value_high!r}]"
    )
    assert scenario.range_width > 1e-3, (
        "plage degeneree : le balayage ne vaudrait pas mieux qu'un point"
    )
    attendu = compatible_bounds(x0, N, c_O)
    assert scenario.value_low == pytest.approx(attendu[0])
    assert scenario.value_high == pytest.approx(attendu[1])


@pytest.fixture(scope="module")
def cas_tendu():
    """
    Un lot ou la largeur conditionnelle VARIE avec la teneur supposee.

    Sans un tel cas, toute cette section est vide de sens. Sur le lot de
    reference, w(v) est constante sur toute la plage : n'importe quelle
    strategie de balayage - trois points, un seul point, la valeur predite -
    donne alors le meme resultat, et aucun test ne peut les distinguer.
    C'est precisement ce qui avait laisse passer un balayage trop grossier.
    """
    from klastos.generator import NoiseModel, make_lot

    bruit = NoiseModel(rel_sigma=0.06, abs_sigma=2e-4, lod=0.0)
    sans_o = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F"]
    keys, _, _ = ProvenanceDeclaration("non_declaree", attested=True).resolve()
    A, _, k = stoichiometry_matrix(phase_keys=keys, elements=sans_o)
    A_tot, els_tot, _ = stoichiometry_matrix(phase_keys=keys)
    c_O = A_tot[els_tot.index("O")]
    lot = make_lot(rng=1, profile="gigafactory_nmc", noise=bruit,
                   phase_keys=keys)
    b = np.array([lot.b_measured[els_tot.index(e)] for e in sans_o])
    x0 = solve(b, phase_keys=keys, elements=sans_o).x
    N = null_space(A)
    fs = standard_functionals(phase_keys=keys, elements=sans_o)
    return dict(x0=x0, N=N, c_O=c_O, fs=fs, k=k, keys=keys)


def _profil_largeur(cas, c, n):
    """w(v) echantillonnee sur n points de la plage compatible."""
    x0, N, c_O = cas["x0"], cas["N"], cas["c_O"]
    lo_el, hi_el = compatible_bounds(x0, N, c_O)
    out = []
    for t in np.linspace(0.0, 1.0, n):
        a, z = conditional_bounds(x0, N, c, c_O, lo_el + t * (hi_el - lo_el))
        out.append(z - a)
    return np.array(out)


def test_la_largeur_conditionnelle_varie_avec_la_teneur_supposee(cas_tendu):
    """Garde-fou du garde-fou : si ce test tombe, les deux suivants sont vides."""
    c = {f.key: f.c for f in cas_tendu["fs"]}["NMC811"]
    w = _profil_largeur(cas_tendu, c, 21)
    assert w.max() - w.min() > 0.05, (
        "w(v) est plate sur ce lot : il ne distingue plus les strategies "
        "de balayage"
    )


def test_le_maximum_est_interieur_donc_trois_points_le_manquent(cas_tendu):
    """
    Mesure, et justification du balayage raffine.

    w(v) est CONCAVE : maximum d'une forme lineaire moins minimum d'une
    forme lineaire, tous deux sur un polytope parametre par son second
    membre. Le maximum d'une fonction concave est generiquement interieur.
    """
    c = {f.key: f.c for f in cas_tendu["fs"]}["NMC811"]
    w = _profil_largeur(cas_tendu, c, 101)
    i = int(w.argmax())
    assert 0 < i < 100, "le maximum est sur un bord : ce lot ne demontre rien"

    trois_points = max(w[0], w[50], w[100])
    assert w[i] - trois_points > 0.005, (
        f"trois points suffiraient ici (ecart {100 * (w[i] - trois_points):.3f} pt)"
    )


def test_le_balayage_retient_bien_le_maximum(cas_tendu):
    """
    LE VERROU DU MODULE.

    Il tombe si le balayage se pose sur la valeur predite, s'il se reduit a
    trois points, a un seul point, ou s'il retient le minimum au lieu du
    maximum. C'est le test qui manquait : l'ancien recopiait les trois
    points de l'implementation et les comparait a eux-memes.
    """
    from klastos.identifiability import _largeur_conditionnelle_maximale

    x0, N, c_O = cas_tendu["x0"], cas_tendu["N"], cas_tendu["c_O"]
    lo_el, hi_el = compatible_bounds(x0, N, c_O)

    for cle in ("NMC811", "NMC622", "cathodes_totales"):
        c = {f.key: f.c for f in cas_tendu["fs"]}[cle]
        reference = _profil_largeur(cas_tendu, c, 201).max()
        obtenu = _largeur_conditionnelle_maximale(
            x0, N, c, c_O, lo_el, hi_el, 1.0)
        # La sous-estimation est le defaut dangereux : elle surevalue le
        # gain annonce au client. On la borne severement.
        assert reference - obtenu < 2e-3, (
            f"{cle} : largeur sous-estimee de "
            f"{100 * (reference - obtenu):.4f} point"
        )
        assert obtenu <= reference + 1e-9, f"{cle} : largeur surestimee"


def test_se_poser_sur_la_valeur_predite_donnerait_un_autre_resultat(cas_tendu):
    """
    Le piege, chiffre. Si ce test tombe, c'est que le lot ne permet plus de
    distinguer le balayage de la faute qu'il evite.
    """
    from klastos.identifiability import _largeur_conditionnelle_maximale

    x0, N, c_O = cas_tendu["x0"], cas_tendu["N"], cas_tendu["c_O"]
    lo_el, hi_el = compatible_bounds(x0, N, c_O)
    c = {f.key: f.c for f in cas_tendu["fs"]}["NMC811"]

    o_predit = float(c_O @ x0)
    a, z = conditional_bounds(x0, N, c, c_O, o_predit)
    au_point = z - a
    balaye = _largeur_conditionnelle_maximale(x0, N, c, c_O, lo_el, hi_el, 1.0)

    assert balaye - au_point > 0.01, (
        f"la valeur predite donne {100 * au_point:.2f} pt, le balayage "
        f"{100 * balaye:.2f} pt : l'ecart est trop faible pour verrouiller "
        "quoi que ce soit"
    )


# ==========================================================================
# 4. Le critere de decision
# ==========================================================================

def test_l_incertitude_utile_est_la_demi_plage(scenario):
    """
    Demonstration dans le docstring de la propriete. Le levier disparait de
    l'inegalite : le critere ne depend que de la plage compatible, donc il
    est le meme pour toutes les grandeurs concernees.
    """
    assert scenario.max_useful_uncertainty == pytest.approx(
        scenario.range_width / 2.0)


def test_le_critere_est_commun_a_toutes_les_grandeurs_rendues_fermes(
        contexte, scenario):
    """
    Pour chaque grandeur que le dosage rend ferme, largeur ouverte =
    |levier| x plage. Donc largeur / (2 |levier|) = plage / 2, la meme
    valeur pour toutes. On le verifie sur les leviers mesures.
    """
    x0, N, c_O = contexte["x0"], contexte["N"], contexte["c_O"]
    par_cle = {f.key: f.c for f in contexte["fs"]}
    fermes = scenario.firm_rows
    assert fermes, "aucune grandeur rendue ferme : le lot teste est mal choisi"

    for r in fermes:
        c = par_cle[r.key]
        bas, _ = conditional_bounds(x0, N, c, c_O, scenario.value_low)
        haut, _ = conditional_bounds(x0, N, c, c_O, scenario.value_high)
        levier = (haut - bas) / scenario.range_width
        assert abs(levier) > 1e-6
        assert r.width_open == pytest.approx(abs(levier) * scenario.range_width,
                                             rel=1e-6)
        u_max = r.width_open / (2 * abs(levier))
        assert u_max == pytest.approx(scenario.max_useful_uncertainty, rel=1e-6)


# ==========================================================================
# 5. Ce que le dosage N'APPORTE PAS
# ==========================================================================

def test_l_oxygene_n_apporte_rien_a_la_ventilation_nmc(scenario):
    """
    Mesure. La degenerescence des grades NMC vit dans le sous-systeme ferme
    Li-Ni-Mn-Co-O, que l'oxygene ne contraint pas. Doser l'oxygene ne la
    reduit PAS d'un point. Le rapport doit le dire : c'est ce qui evite au
    client de payer un essai inutile.
    """
    nmc = [r for r in scenario.rows if r.key.startswith("NMC")]
    assert nmc, "aucun grade NMC dans ce scenario"
    for r in nmc:
        assert r.width_conditional == pytest.approx(r.width_open, rel=1e-6)
        assert not r.becomes_firm
        assert r.gain_fraction < 0.01
    assert set(r.key for r in scenario.useless_rows) >= set(r.key for r in nmc)


def test_une_grandeur_deja_ferme_n_apparait_pas_dans_le_scenario(
        contexte, scenario):
    """Elle n'a rien a y gagner : l'y mettre serait du bruit."""
    cles = {r.key for r in scenario.rows}
    for f in contexte["fs"]:
        if is_identifiable(f.c, contexte["N"]):
            assert f.key not in cles


# ==========================================================================
# 6. Perimetre : quels elements meritent un scenario
# ==========================================================================

def test_seul_l_oxygene_est_propose(contexte):
    """
    L'hydrogene leve formellement un degre de liberte lui aussi. Il est
    ecarte sur un argument physique : dans une black mass, l'hydrogene total
    est domine par l'humidite et les solvants, que le modele ne porte pas.
    """
    assert SCENARIO_ELEMENTS == ("O",)
    assert "H" in ELEMENTS and "H" not in SCENARIO_ELEMENTS


def test_le_perimetre_est_declare_non_arbitre():
    """Choix de modelisation, pas mesure. La dette reste ouverte et visible."""
    assert SCENARIO_ELEMENTS_VALIDATED is False


def test_un_element_deja_determine_ne_donne_pas_de_scenario(contexte):
    """Orthogonal a l'espace nul : le doser ne contraindrait rien de neuf."""
    A_tot, els_tot, _ = stoichiometry_matrix(phase_keys=contexte["keys"])
    c_cu = A_tot[els_tot.index("Cu")]
    assert is_identifiable(c_cu, contexte["N"])
    assert element_scenario(contexte["x0"], contexte["N"], contexte["fs"],
                            c_cu, "Cu") is None


def test_un_systeme_bien_pose_ne_donne_pas_de_scenario(contexte):
    vide = np.zeros((len(contexte["x0"]), 0))
    assert element_scenario(contexte["x0"], vide, contexte["fs"],
                            contexte["c_O"], "O") is None


# ==========================================================================
# 7. Bout en bout : propagation et rapport
# ==========================================================================

@pytest.fixture(scope="module")
def rapport(contexte):
    lu = contexte["lu"]
    rep = propagate(lu.b, phase_keys=contexte["keys"],
                    elements=contexte["els"],
                    config=UncertaintyConfig(seed=0, n_draws=40,
                                             n_bound_draws=10))
    return rep, build_report("L", "C", rep, None, contexte["journal"],
                             allow_demo=True)


def test_la_propagation_porte_le_scenario(rapport):
    rep, _ = rapport
    assert [s.element for s in rep.meta["scenarios"]] == ["O"]


def test_le_rapport_porte_la_section(rapport):
    _, r = rapport
    s = r.section(TITRE_SCENARIO)
    assert s is not None and s.rows


def test_la_section_porte_l_avertissement_sur_le_piege(rapport):
    """
    Le verrou de fond. Sans cette mention, un lecteur pourrait croire que
    l'outil sait ce que vaudrait un dosage qu'il n'a pas.
    """
    _, r = rapport
    notes = " ".join(r.section(TITRE_SCENARIO).notes)
    assert MENTION_SCENARIO_PIEGE in notes
    assert MENTION_SCENARIO in notes


def test_la_section_declare_sa_base_de_mesure(rapport):
    """
    Sans cette mention, le client lit deux largeurs differentes pour la
    meme grandeur dans deux sections voisines - 1,07 point ici, 11,4 points
    la - sans savoir que l'une est structurelle et l'autre totale.
    """
    from klastos.report import MENTION_SCENARIO_BASE

    _, r = rapport
    notes = " ".join(r.section(TITRE_SCENARIO).notes)
    assert MENTION_SCENARIO_BASE in notes
    assert "STRUCTURELLES" in MENTION_SCENARIO_BASE
    assert "analytique" in MENTION_SCENARIO_BASE


def test_les_largeurs_du_scenario_sont_bien_structurelles(rapport, contexte):
    """
    Verification numerique de la mention : la largeur « avant » du scenario
    doit valoir la largeur STRUCTURELLE du bulletin central, pas la
    fourchette totale affichee ailleurs.
    """
    rep, _ = rapport
    x0 = rep.meta["central"].x
    N = contexte["N"]
    par_cle = {f.key: f.c for f in contexte["fs"]}
    for ligne in rep.meta["scenarios"][0].rows:
        lo, hi = compatible_bounds(x0, N, par_cle[ligne.key])
        assert ligne.width_open == pytest.approx(hi - lo, rel=1e-9)


def test_la_section_annonce_la_precision_requise(rapport):
    _, r = rapport
    assert "incertitude" in r.section(TITRE_SCENARIO).intro.lower()


def test_le_scenario_n_entre_pas_dans_les_grandeurs_fermes(rapport):
    """Verrou d'etancheite : la projection ne contamine pas l'engagement."""
    _, r = rapport
    fermes = r.section("Grandeurs fermes")
    assert fermes is not None
    cathodes = [x for x in fermes.rows if x.label == "Cathodes totales"]
    assert cathodes == [], (
        "Cathodes totales est presentee comme ferme alors que l'oxygene "
        "n'est pas dose"
    )


def test_un_bulletin_avec_oxygene_n_a_pas_de_scenario(tmp_path, contexte):
    """Le dosage existe : il n'y a plus rien a projeter."""
    p = tmp_path / "avec_o.csv"
    p.write_text(
        "Ni (%),Co (%),Li (%),Mn (%),Cu (%),Al (%),Fe (%),P (%),"
        "C total (%),F (%),O (%)\n"
        "16.20,4.01,3.28,3.74,2.70,3.20,3.586,1.89,29.79,1.70,16.60\n",
        encoding="utf-8")
    lu = read_bulletin(p)
    assert "O" in lu.measured_elements
    rep = propagate(lu.b, phase_keys=contexte["keys"],
                    elements=lu.measured_elements,
                    config=UncertaintyConfig(seed=0, n_draws=20,
                                             n_bound_draws=5))
    assert rep.meta["scenarios"] == []
    assert build_report("L", "C", rep, None, [], allow_demo=True).section(
        TITRE_SCENARIO) is None


def test_un_oxygene_dose_rend_cathodes_totales_ferme(tmp_path, contexte):
    """La contrepartie : quand le client fournit le dosage, il y gagne."""
    p = tmp_path / "avec_o.csv"
    p.write_text(
        "Ni (%),Co (%),Li (%),Mn (%),Cu (%),Al (%),Fe (%),P (%),"
        "C total (%),F (%),O (%)\n"
        "16.20,4.01,3.28,3.74,2.70,3.20,3.586,1.89,29.79,1.70,16.60\n",
        encoding="utf-8")
    lu = read_bulletin(p)
    A, _, k = stoichiometry_matrix(phase_keys=contexte["keys"],
                                   elements=lu.measured_elements)
    assert is_identifiable(cathode_indicator(phase_keys=k), null_space(A))


def test_le_bulletin_avec_oxygene_est_signale(tmp_path):
    """
    Un oxygene « par difference » ne porte aucune information independante.
    L'ingestion doit demander de verifier qu'il s'agit d'un dosage.
    """
    p = tmp_path / "avec_o.csv"
    p.write_text("Ni (%),Co (%),Li (%),O (%)\n16.20,4.01,3.28,16.60\n",
                 encoding="utf-8")
    assert any("différence" in w.lower()
               for w in read_bulletin(p).warnings)


# ==========================================================================
# 8. Rendu
# ==========================================================================

def test_le_rendu_a_un_vocabulaire_propre_au_scenario():
    from klastos.render_html import (STATUTS, STATUTS_LARGEUR,
                                     STATUTS_SCENARIO, VOCABULAIRE_LARGEUR)

    assert VOCABULAIRE_LARGEUR[SECTION_SCENARIO] is STATUTS_SCENARIO
    for statut in ("ferme", "ouvert"):
        assert (STATUTS_SCENARIO[statut][0] != STATUTS[statut][0]
                != STATUTS_LARGEUR[statut][0])


def test_le_rendu_du_scenario_est_une_section_de_largeurs(rapport):
    from klastos.render_html import SECTIONS_LARGEUR, to_html

    import html as _h

    assert SECTION_SCENARIO in SECTIONS_LARGEUR
    _, r = rapport
    doc = to_html(r)
    # Le titre contient une apostrophe, que le rendu echappe.
    marqueur = f"<h2>{_h.escape(TITRE_SCENARIO)}</h2>"
    assert marqueur in doc
    bloc = doc.split(marqueur)[1].split("</section>")[0]
    assert "deviendrait ferme" in bloc
    assert "resterait ouverte" in bloc
    assert "<span>0 points</span>" in bloc


# ==========================================================================
# 9. Le piege du sommet dans le scenario lui-meme
# ==========================================================================

@pytest.fixture(scope="module")
def cas_epingle():
    """
    Lot ou la non-negativite epingle a elle seule plusieurs grandeurs a une
    largeur nulle - le piege du sommet. Elles ne sont pas identifiables,
    mais elles n'ont rien a gagner a un dosage.
    """
    from klastos.generator import NoiseModel, make_lot

    bruit = NoiseModel(rel_sigma=0.06, abs_sigma=2e-4, lod=0.0)
    sans_o = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F"]
    keys, _, _ = ProvenanceDeclaration("non_declaree", attested=True).resolve()
    A, _, k = stoichiometry_matrix(phase_keys=keys, elements=sans_o)
    A_tot, els_tot, _ = stoichiometry_matrix(phase_keys=keys)
    lot = make_lot(rng=2, profile="gigafactory_nmc", noise=bruit,
                   phase_keys=keys)
    b = np.array([lot.b_measured[els_tot.index(e)] for e in sans_o])
    x0 = solve(b, phase_keys=keys, elements=sans_o).x
    N = null_space(A)
    fs = standard_functionals(phase_keys=keys, elements=sans_o)
    return dict(x0=x0, N=N, c_O=A_tot[els_tot.index("O")], fs=fs)


def test_le_lot_comporte_bien_des_grandeurs_epinglees(cas_epingle):
    """Garde-fou : sans elles, les deux tests suivants sont vides."""
    x0, N = cas_epingle["x0"], cas_epingle["N"]
    epinglees = [f.key for f in cas_epingle["fs"]
                 if not is_identifiable(f.c, N)
                 and compatible_bounds(x0, N, f.c)[1]
                 - compatible_bounds(x0, N, f.c)[0] <= 1e-7]
    assert len(epinglees) >= 3, epinglees


def test_une_grandeur_deja_epinglee_n_entre_pas_dans_le_scenario(cas_epingle):
    """
    Regression. Sa largeur conditionnelle vaut 1e-16 comme sa largeur
    ouverte : elle sortait classee "deviendrait ferme", alors qu'elle ne
    gagne rien. Le rapport la listait simultanement parmi les grandeurs
    auxquelles le dosage n'apporte rien - deux lignes contradictoires dans
    la meme section.
    """
    s = element_scenario(cas_epingle["x0"], cas_epingle["N"],
                         cas_epingle["fs"], cas_epingle["c_O"], "O")
    assert s is not None
    for r in s.rows:
        assert r.width_open > 1e-7, (
            f"{r.key} entre dans le scenario avec une largeur ouverte nulle"
        )


@pytest.mark.parametrize("fixture", ["scenario", "cas_epingle", "cas_tendu"])
def test_ferme_et_inutile_sont_toujours_disjoints(request, fixture):
    """
    Invariant de coherence. Une grandeur ne peut pas a la fois devenir
    ferme grace au dosage et ne rien lui devoir.
    """
    obj = request.getfixturevalue(fixture)
    if isinstance(obj, dict):
        obj = element_scenario(obj["x0"], obj["N"], obj["fs"], obj["c_O"], "O")
        if obj is None:
            pytest.skip("pas de scenario sur ce lot")
    assert not ({r.key for r in obj.firm_rows}
                & {r.key for r in obj.useless_rows})


def test_une_ligne_de_largeur_nulle_n_annonce_aucun_gain():
    """
    `element_scenario` n'en produit plus (le filtre amont les ecarte), mais
    ScenarioRow est une structure publique. Une largeur ouverte nulle ne
    doit jamais se lire comme un gain de 100 %.
    """
    from klastos.identifiability import ScenarioRow

    r = ScenarioRow(key="x", label="x", width_open=0.0,
                    width_conditional=0.0, becomes_firm=False)
    assert r.gain == 0.0
    assert r.gain_fraction == 0.0