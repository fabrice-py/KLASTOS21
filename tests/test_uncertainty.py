"""Tests de klastos/uncertainty.py.

Invariant central : l'enveloppe rapportee contient la valeur vraie. Et le
conseil donne au client ne promet jamais qu'un meilleur laboratoire resoudra
un probleme d'identifiabilite.
"""

import numpy as np
import pytest

from klastos.generator import NOISE_FREE, NoiseModel, make_lot
from klastos.phases import PHASE_KEYS, stoichiometry_matrix
from klastos.provenance import ProvenanceDeclaration
from klastos.uncertainty import (APPARENT_UNIQUENESS_RATIO, SOURCE_ANALYTIQUE,
                                 SOURCE_STRUCTURELLE, WELL_DETERMINED_WIDTH,
                                 UncertaintyConfig, propagate,
                                 resample_bulletin)

BRUIT = NoiseModel(rel_sigma=0.03, abs_sigma=2e-4, lod=0.0)
CFG = UncertaintyConfig(noise=BRUIT, seed=0, n_draws=120, n_bound_draws=30)
LISTE_BIEN_POSEE = [
    k for k in PHASE_KEYS if k not in ("NMC111", "NMC532", "LCO", "LMO")
]


@pytest.fixture(scope="module")
def rapport():
    lot = make_lot(rng=1, profile="mixed_ev", noise=BRUIT)
    return lot, propagate(lot.b_measured, phase_keys=lot.phase_keys, config=CFG)


# ==========================================================================
# 1. Mecanique du reechantillonnage
# ==========================================================================

def test_reechantillonnage_reste_positif():
    rng = np.random.default_rng(0)
    b = np.array([0.30, 0.001, 0.0])
    for _ in range(50):
        assert np.all(resample_bulletin(b, rng, BRUIT) >= 0.0)


def test_reproductibilite_par_la_graine():
    lot = make_lot(rng=2, profile="mixed_ev", noise=BRUIT)
    a = propagate(lot.b_measured, phase_keys=lot.phase_keys, config=CFG)
    b = propagate(lot.b_measured, phase_keys=lot.phase_keys, config=CFG)
    for ra, rb in zip(a.results, b.results):
        assert ra.total_lower == pytest.approx(rb.total_lower)
        assert ra.total_upper == pytest.approx(rb.total_upper)


def test_aucun_tirage_ne_doit_echouer(rapport):
    _, rep = rapport
    assert rep.n_failed == 0
    assert rep.n_draws == CFG.n_draws


def test_toutes_les_bornes_sont_finies(rapport):
    """Regression : le domaine compatible ne doit jamais sortir a l'infini."""
    _, rep = rapport
    for r in rep.results:
        assert np.isfinite(r.total_lower), r.key
        assert np.isfinite(r.total_upper), r.key
        assert r.total_upper >= r.total_lower


# ==========================================================================
# 2. Invariant : l'enveloppe contient la verite
# ==========================================================================

def _couverture(graines):
    """
    Mesure, sur plusieurs lots, si la valeur vraie tombe dans les bornes.

    Retourne (echecs sur les domaines compatibles, dedans, total) pour les
    grandeurs fermes.
    """
    from klastos.identifiability import standard_functionals

    ko_structurel = []
    dedans = total = 0
    for g in graines:
        lot = make_lot(rng=g, profile="mixed_ev", noise=BRUIT)
        rep = propagate(
            lot.b_measured, phase_keys=lot.phase_keys,
            config=UncertaintyConfig(noise=BRUIT, seed=g, n_draws=120,
                                     n_bound_draws=30),
        )
        _, _, keys = stoichiometry_matrix(phase_keys=lot.phase_keys)
        fs = {f.key: f for f in standard_functionals(keys)}
        for r in rep.results:
            vrai = float(fs[r.key].c @ lot.x_true)
            ok = r.total_lower - 1e-6 <= vrai <= r.total_upper + 1e-6
            if r.identifiable:
                total += 1
                dedans += int(ok)
            elif not ok:
                ko_structurel.append((g, r.key, vrai, r.total_lower, r.total_upper))
    return ko_structurel, dedans, total


def test_le_domaine_compatible_contient_toujours_la_valeur_vraie():
    """
    GARANTIE STRICTE, et elle ne porte que sur les grandeurs NON
    IDENTIFIABLES.

    Un domaine compatible est un ensemble mathematique borne : toute valeur
    qu'il contient explique le bulletin, et la valeur vraie en fait
    necessairement partie. Aucun depassement n'est tolerable.
    """
    ko, _, _ = _couverture(range(12))
    assert not ko, ko


def test_la_couverture_des_intervalles_fermes_est_nominale():
    """
    Une grandeur ferme recoit un INTERVALLE DE CONFIANCE, pas une garantie.

    Son incertitude est purement statistique : l'intervalle 5-95 couvre la
    valeur vraie dans 90 % des cas, et c'est le comportement attendu. Exiger
    une couverture de 100 % imposerait l'enveloppe min/max des tirages, qui
    n'est pas un estimateur stable - elle s'elargit mecaniquement avec le
    nombre de tirages.
    """
    _, dedans, total = _couverture(range(12))
    assert total > 200, "echantillon trop petit pour mesurer une couverture"
    couverture = dedans / total
    assert 0.80 <= couverture <= 0.97, f"couverture mesuree : {couverture:.1%}"


def test_l_intervalle_affiche_est_celui_qui_sert_au_classement():
    """
    Coherence du rapport : afficher [2,93 - 3,57] puis qualifier la grandeur
    de mal determinee sur la base d'un intervalle plus large et invisible
    serait trompeur.
    """
    lot = make_lot(rng=1, profile="mixed_ev", noise=BRUIT)
    rep = propagate(lot.b_measured, phase_keys=lot.phase_keys, config=CFG)
    for r in rep.results:
        if r.identifiable:
            assert r.total_lower == pytest.approx(r.analytic_lower), r.key
            assert r.total_upper == pytest.approx(r.analytic_upper), r.key


def test_l_enveloppe_contient_toujours_le_domaine_local(rapport):
    _, rep = rapport
    for r in rep.results:
        assert r.total_lower <= r.struct_lower + 1e-9, r.key
        assert r.total_upper >= r.struct_upper - 1e-9, r.key


# ==========================================================================
# 3. Decomposition et conseil
# ==========================================================================

def test_grandeurs_fermes_sans_largeur_structurelle(rapport):
    _, rep = rapport
    for r in rep.results:
        if r.identifiable:
            assert r.struct_width == pytest.approx(0.0, abs=1e-9), r.key
            assert r.dominant_source == SOURCE_ANALYTIQUE
            assert r.reducible_fraction == 1.0


def test_grandeurs_non_identifiables_declarees_structurelles(rapport):
    """
    Regle prudente : on ne vend jamais au client une analyse plus fine pour
    resoudre un probleme d'identifiabilite.
    """
    _, rep = rapport
    ouvertes = [r for r in rep.results if not r.identifiable]
    assert ouvertes
    for r in ouvertes:
        assert r.dominant_source == SOURCE_STRUCTURELLE, r.key
        assert r.reducible_fraction == 0.0
        assert "non identifiable" in r.note
        assert "DRX" in r.advice() or "structurale" in r.advice()


def test_le_conseil_analytique_ne_parle_pas_de_drx(rapport):
    _, rep = rapport
    for r in rep.results:
        if r.identifiable and r.total_width > 1e-6:
            assert "DRX" not in r.advice()
            assert "analyse de meilleure qualite" in r.advice()


# ==========================================================================
# 4. Piege du sommet
# ==========================================================================

def test_le_piege_du_sommet_est_signale(rapport):
    """
    La non-negativite peut figer une solution apparemment unique sur un
    systeme degenere. Sans ce drapeau, le rapport afficherait par exemple
    "NMC 622 = 0,00 %" avec une fausse certitude.
    """
    _, rep = rapport
    pieges = [r for r in rep.results if r.apparent_uniqueness_risk]
    assert pieges, "aucun piege detecte sur un lot pourtant degenere"
    for r in pieges:
        assert not r.identifiable
        assert r.total_width > WELL_DETERMINED_WIDTH
        assert r.warning
        assert "ne resiste pas au bruit" in r.warning
        assert r.warning in r.advice()


def test_une_grandeur_ferme_ne_declenche_jamais_le_piege(rapport):
    _, rep = rapport
    for r in rep.results:
        if r.identifiable:
            assert r.apparent_uniqueness_risk is False


def test_le_ratio_du_piege_est_documente():
    assert APPARENT_UNIQUENESS_RATIO > 1.0
    assert 0.0 < WELL_DETERMINED_WIDTH < 1.0


# ==========================================================================
# 5. Identifiable n'est pas exploitable
# ==========================================================================

def test_bien_determine_distingue_de_identifiable():
    """
    Sur liste VE attestee, NMC 532 est identifiable (coefficient nul dans la
    direction nulle) mais mal conditionne : son domaine reste tres large.
    Identifiable ne signifie donc pas exploitable.
    """
    keys, _, _ = ProvenanceDeclaration(
        "vehicule_electrique", attested=True
    ).resolve()
    lot = make_lot(rng=1, profile="mixed_ev", noise=BRUIT, phase_keys=keys)
    rep = propagate(lot.b_measured, phase_keys=keys, config=CFG)
    d = rep.by_key()
    assert d["NMC532"].identifiable is True
    assert d["NMC532"].well_determined is False
    assert d["cathodes_totales"].identifiable is True


# ==========================================================================
# 6. Effet du bruit et de la provenance
# ==========================================================================

def test_moins_de_bruit_resserre_les_grandeurs_fermes():
    lot = make_lot(rng=4, profile="gigafactory_nmc",
                   phase_keys=LISTE_BIEN_POSEE, noise=NOISE_FREE)
    large = propagate(
        lot.b_measured, phase_keys=LISTE_BIEN_POSEE,
        config=UncertaintyConfig(noise=BRUIT, seed=0, n_draws=100),
    ).by_key()
    fin = propagate(
        lot.b_measured, phase_keys=LISTE_BIEN_POSEE,
        config=UncertaintyConfig(
            noise=NoiseModel(rel_sigma=0.003, abs_sigma=2e-5, lod=0.0),
            seed=0, n_draws=100,
        ),
    ).by_key()
    for k in ("el_Ni", "el_Co", "cathodes_totales"):
        assert fin[k].total_width < large[k].total_width, k


def test_systeme_bien_pose_sans_incertitude_structurelle():
    lot = make_lot(rng=4, profile="gigafactory_nmc",
                   phase_keys=LISTE_BIEN_POSEE, noise=BRUIT)
    rep = propagate(lot.b_measured, phase_keys=LISTE_BIEN_POSEE, config=CFG)
    assert rep.degeneracy == 0
    assert all(r.identifiable for r in rep.results)
    assert not rep.structural_bottlenecks()


# ==========================================================================
# 7. Aide a la decision
# ==========================================================================

def test_les_goulots_sont_tries_par_largeur(rapport):
    _, rep = rapport
    for liste in (rep.structural_bottlenecks(), rep.analytic_bottlenecks()):
        largeurs = [r.total_width for r in liste]
        assert largeurs == sorted(largeurs, reverse=True)


def test_les_deux_listes_de_goulots_sont_disjointes(rapport):
    _, rep = rapport
    a = {r.key for r in rep.structural_bottlenecks()}
    b = {r.key for r in rep.analytic_bottlenecks()}
    assert not (a & b)


def test_le_bouclage_est_transmis(rapport):
    _, rep = rapport
    assert "closure" in rep.meta
    assert rep.meta["closure"].status in ("ok", "alerte", "rejet")