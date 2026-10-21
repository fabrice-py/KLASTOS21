"""Tests de l'integration des quantifications structurales dans la chaine.

test_structural.py couvre la lecture et la traduction en contraintes. Ici on
verifie ce que la chaine en fait, et surtout les deux pieges que la seance 17
a reveles :

1. UNE DRX NE REND RIEN IDENTIFIABLE. Une inegalite borne une direction
   nulle, elle ne la supprime pas. Un test qui laisserait passer le
   contraire ferait reapparaitre le piege du sommet.

2. UN TIRAGE INCOMPATIBLE N'EST PAS JETE. Mesure a l'appui : sur le lot
   d'exemple, 42 tirages sur 60 etaient ecartes par une premiere version.
   Les percentiles analytiques auraient alors ete calcules sur un
   echantillon censure, donc l'incertitude du LABORATOIRE resserree au
   motif d'une mesure qui ne porte pas sur elle.
"""

import datetime as dt
import pathlib

import numpy as np
import pytest

from klastos import structural as S
from klastos.identifiability import (UnboundedCompatibleSet,
                                     conseil_quantification, null_space,
                                     projeter_dans_domaine)
from klastos.phases import stoichiometry_matrix
from klastos.report import (SECTION_DRX, TITRE_CONSEIL, TITRE_DRX,
                            libelle_statut)
from klastos.service import Demande, analyser

RACINE = pathlib.Path(__file__).resolve().parent.parent
BULLETIN = RACINE / "data" / "exemples" / "bulletin_coherent.csv"
AUJ = dt.date(2026, 9, 7)


@pytest.fixture(autouse=True)
def _bulletin_present():
    if not BULLETIN.exists():
        pytest.skip("bulletin d'exemple absent")


def _demande(**kw):
    base = dict(bulletin=BULLETIN, provenance="vehicule_electrique",
                attestee=True, tirages=25, graine=0, emis_le=AUJ)
    base.update(kw)
    return Demande(**base)


def _fichier_drx(tmp_path, lignes: str) -> pathlib.Path:
    p = tmp_path / "drx.csv"
    p.write_text("Phase,Valeur (%),Incertitude (%)\n" + lignes,
                 encoding="utf-8")
    return p


@pytest.fixture(scope="module")
def sans_drx():
    return analyser(_demande())


# ==========================================================================
# 1. Le verrou : rien ne devient identifiable
# ==========================================================================


def test_une_drx_ne_rend_rien_identifiable(tmp_path, sans_drx):
    """
    LE VERROU. L'incertitude de la mesure etant non nulle, l'identifiabilite
    est INCHANGEE. Seules les plages se resserrent.
    """
    a = analyser(_demande(drx=_fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")))
    avant = {r.key: r.identifiable for r in sans_drx.incertitude.results}
    apres = {r.key: r.identifiable for r in a.incertitude.results}
    assert avant == apres


def test_la_degenerescence_est_inchangee(tmp_path, sans_drx):
    a = analyser(_demande(drx=_fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")))
    assert a.incertitude.degeneracy == sans_drx.incertitude.degeneracy


def test_les_plages_se_resserrent_vraiment(tmp_path, sans_drx):
    """La contrepartie : sans resserrement, la fonctionnalite n'en est pas une."""
    a = analyser(_demande(drx=_fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")))
    gains = [r.structural_gain for r in a.incertitude.results
             if r.structural_gain is not None]
    assert gains, "aucune grandeur ne porte de terme de comparaison"
    assert max(gains) > 0.30, f"resserrement trop faible : {max(gains):.2f}"


def test_aucune_plage_ne_s_elargit(tmp_path):
    """Une contrainte ne peut que retrecir un domaine, jamais l'etendre."""
    a = analyser(_demande(drx=_fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")))
    for r in a.incertitude.results:
        if r.open_lower is None:
            continue
        apres = (r.struct_upper or 0.0) - (r.struct_lower or 0.0)
        assert apres <= r.open_width + 1e-9, r.key


# ==========================================================================
# 2. Aucun tirage n'est jete
# ==========================================================================


def test_les_tirages_en_conflit_sont_conserves(tmp_path, sans_drx):
    """
    LE SECOND VERROU. Le nombre de tirages retenus ne doit pas dependre de la
    quantification : sinon les percentiles analytiques porteraient sur un
    echantillon censure.
    """
    a = analyser(_demande(drx=_fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")))
    assert a.incertitude.n_draws == sans_drx.incertitude.n_draws
    assert a.incertitude.n_failed == sans_drx.incertitude.n_failed


def test_le_taux_de_conflit_est_rapporte(tmp_path):
    """
    Le compteur doit COMPTER. Un test qui se contente de verifier la
    coherence du ratio laisse passer un compteur cable a zero : c'est
    exactement le mutant qui avait survecu.

    Ce lot produit des conflits reels - sur une part des tirages, la
    non-negativite des autres phases epingle le NMC811 hors de l'intervalle
    declare - et le compteur doit les voir.
    """
    a = analyser(_demande(drx=_fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")))
    u = a.incertitude
    assert u.n_structural_conflicts > 0, (
        "aucun conflit compte sur un lot qui en produit : compteur inerte")
    assert u.n_structural_conflicts <= u.n_draws
    assert u.structural_conflict_rate == pytest.approx(
        u.n_structural_conflicts / u.n_draws)
    assert u.structural_conflict_rate > 0.10


def test_sans_drx_aucun_conflit(sans_drx):
    assert sans_drx.incertitude.n_structural_conflicts == 0
    assert sans_drx.incertitude.structural_conflict_rate == 0.0


def test_un_conflit_eleve_est_signale_dans_le_rapport(tmp_path):
    a = analyser(_demande(drx=_fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")))
    if a.incertitude.structural_conflict_rate <= 0.20:
        pytest.skip("taux de conflit faible sur ce lot")
    sec = [s for s in a.rapport.sections if s.cle == SECTION_DRX]
    assert sec, "section DRX absente"
    joint = " ".join(sec[0].notes)
    assert "conflit" in joint and "CONSERVÉS" in joint


# ==========================================================================
# 3. Le representant est recadre sans toucher a l'identifiable
# ==========================================================================


def test_le_recadrage_ne_change_aucune_grandeur_identifiable(tmp_path,
                                                             sans_drx):
    """
    Deplacer x0 dans l'espace nul laisse A @ x inchange. Les grandeurs
    fermes doivent donc garder exactement leur valeur.
    """
    a = analyser(_demande(drx=_fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")))
    av = {r.key: r for r in sans_drx.incertitude.results}
    for r in a.incertitude.results:
        if not r.identifiable:
            continue
        assert r.median == pytest.approx(av[r.key].median, abs=1e-9), r.key


def test_le_bouclage_est_inchange(tmp_path, sans_drx):
    """somme(x) est invariante dans l'espace nul : le diagnostic ne bouge pas."""
    a = analyser(_demande(drx=_fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")))
    assert (a.incertitude.meta["closure"].status
            == sans_drx.incertitude.meta["closure"].status)


def test_la_valeur_centrale_respecte_la_mesure_declaree(tmp_path):
    """
    Le rapport ne peut pas afficher une valeur ponctuelle hors de
    l'intervalle qu'il annonce dans la meme page.
    """
    a = analyser(_demande(drx=_fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")))
    x = a.incertitude.meta["central"].x
    j = list(a.phases_retenues).index("NMC811")
    q = a.structurale.quantifications[0]
    assert q.bas - 1e-6 <= x[j] <= q.haut + 1e-6


def test_une_quantification_contradictoire_est_refusee(tmp_path):
    """
    Une phase declaree a 80 % que le bulletin ne permet pas : le logiciel
    nomme la contradiction au lieu de l'arbitrer.
    """
    with pytest.raises(UnboundedCompatibleSet, match="incompatible"):
        analyser(_demande(drx=_fichier_drx(tmp_path, "NMC 811,80.0,1.0\n")))


def test_la_projection_est_l_identite_sur_un_point_admissible():
    doses = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F"]
    A, _, ph = stoichiometry_matrix(elements=doses)
    N = null_space(A)
    x = np.full(len(ph), 1.0 / len(ph))
    j = ph.index("NMC622")
    G = np.vstack([np.eye(len(ph))[j], -np.eye(len(ph))[j]])
    h = np.array([x[j] + 0.01, -(x[j] - 0.01)])
    assert np.allclose(projeter_dans_domaine(x, N, (G, h)), x)


# ==========================================================================
# 4. Base cristalline de bout en bout
# ==========================================================================


def test_la_base_cristalline_traverse_la_chaine(tmp_path):
    a = analyser(_demande(
        drx=_fichier_drx(tmp_path, "NMC 811,18.0,3.0\nNMC 622,14.0,3.0\n"),
        base_drx=S.BASE_CRISTALLINE))
    assert a.structurale.basis == S.BASE_CRISTALLINE
    assert a.contrainte_par_drx


def test_la_base_absolue_resserre_au_moins_autant(tmp_path):
    """
    La mesure qui justifie de distinguer les deux bases : n phases donnent
    n-1 rapports, donc une contrainte de moins.
    """
    lignes = "NMC 811,18.0,3.0\nNMC 622,14.0,3.0\n"
    abs_ = analyser(_demande(drx=_fichier_drx(tmp_path, lignes),
                             base_drx=S.BASE_ABSOLUE))
    cri = analyser(_demande(drx=_fichier_drx(tmp_path, lignes),
                            base_drx=S.BASE_CRISTALLINE))

    def cumul(a):
        return sum((r.struct_upper or 0.0) - (r.struct_lower or 0.0)
                   for r in a.incertitude.results
                   if r.block in ("phase", "ventilation"))

    assert cumul(abs_) <= cumul(cri) + 1e-9


# ==========================================================================
# 5. Le conseil de quantification
# ==========================================================================


def test_le_conseil_classe_les_phases(sans_drx):
    a = analyser(_demande(conseil_drx=True, tirages=10))
    assert a.conseil is not None and a.conseil.rows
    gains = [r.gain for r in a.conseil.rows]
    assert gains == sorted(gains, reverse=True), "classement non trie"


def test_le_conseil_distingue_les_phases_sans_effet():
    a = analyser(_demande(conseil_drx=True, tirages=10))
    assert a.conseil.useless, "aucune phase inutile : le conseil n'informe pas"
    assert a.conseil.best is not None
    assert a.conseil.best.gain > max(
        (r.gain for r in a.conseil.useless), default=0.0)


def test_le_conseil_prend_le_pire_placement():
    """
    Un conseil pris au MILIEU de la plage serait flatteur, et flatteur dans
    le sens ou le client paie. Le gain au pire cas doit donc etre inferieur
    ou egal au gain au milieu.
    """
    from klastos.identifiability import compatible_bounds

    a = analyser(_demande(conseil_drx=True, tirages=10))
    ph = list(a.phases_retenues)
    doses = list(a.lecture.measured_elements)
    A, _, _ = stoichiometry_matrix(phase_keys=ph, elements=doses)
    N = null_space(A)
    x0 = a.incertitude.meta["central"].x
    u = a.conseil.uncertainty

    ligne = a.conseil.rows[0]
    j = ph.index(ligne.key)
    c = np.zeros(len(ph)); c[j] = 1.0
    lo, hi = compatible_bounds(x0, N, c)
    v = 0.5 * (lo + hi)
    G = np.vstack([c, -c])
    h = np.array([v + u, -max(0.0, v - u)])
    milieu = sum(
        (lambda b: b[1] - b[0])(
            compatible_bounds(x0, N, np.eye(len(ph))[k], extra=(G, h)))
        for k in range(len(ph)))
    gain_milieu = 1.0 - milieu / a.conseil.total_before
    assert ligne.gain <= gain_milieu + 1e-6


def test_le_conseil_est_hors_du_chemin_par_defaut(sans_drx):
    assert sans_drx.conseil is None


def test_le_conseil_refuse_une_incertitude_nulle():
    doses = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F"]
    A, _, ph = stoichiometry_matrix(elements=doses)
    x = np.full(len(ph), 1.0 / len(ph))
    with pytest.raises(ValueError, match="verite"):
        conseil_quantification(x, A, ph, uncertainty=0.0)


def test_le_conseil_sur_un_systeme_non_degenere_le_dit():
    doses = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F"]
    A, _, ph = stoichiometry_matrix(phase_keys=["C_total", "Cu_metal"],
                                    elements=doses)
    x = np.array([0.5, 0.3])
    c = conseil_quantification(x, A, ["C_total", "Cu_metal"])
    assert not c.rows
    assert "non degenere" in " ".join(c.journal)


# ==========================================================================
# 6. Le rapport
# ==========================================================================


def test_la_section_drx_apparait_et_porte_l_avertissement(tmp_path):
    a = analyser(_demande(drx=_fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")))
    sec = [s for s in a.rapport.sections if s.title == TITRE_DRX]
    assert sec
    assert "encadrement" in sec[0].intro
    assert "aucune grandeur ferme" in sec[0].intro
    assert "NMC 811" in sec[0].intro        # la mesure declaree est citee


def test_la_section_drx_est_absente_sans_quantification(sans_drx):
    assert not [s for s in sans_drx.rapport.sections if s.title == TITRE_DRX]


def test_la_section_conseil_nomme_les_planchers():
    a = analyser(_demande(conseil_drx=True, tirages=10))
    sec = [s for s in a.rapport.sections if s.title == TITRE_CONSEIL]
    assert sec
    assert "PLANCHERS" in sec[0].intro
    assert any("au moins" in r.value for r in sec[0].rows)


def test_le_journal_de_la_drx_est_tracable(tmp_path):
    a = analyser(_demande(drx=_fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")))
    assert any(l.startswith("DRX :") for l in a.rapport.traceability)


def test_les_deux_rendus_disent_la_meme_chose_sur_les_statuts():
    """
    Regression. Le Markdown affichait "ferme" la ou le HTML affichait
    "reductible" : deux documents issus du meme objet se contredisaient sur
    la meme ligne. La table de vocabulaire est desormais unique.

    Le test porte maintenant sur LES DEUX LANGUES. Un vocabulaire traduit
    donne deux occasions de diverger plutot qu'une : il suffit qu'une seule
    entree anglaise manque a l'un des deux rendus pour que les documents se
    contredisent a nouveau, dans la langue que personne ne relit.
    """
    import unicodedata

    from klastos import i18n, render_html

    def nu(t):
        """Sans accents ni emphase : chaque rendu garde sa typographie."""
        t = unicodedata.normalize("NFKD", t)
        t = "".join(ch for ch in t if not unicodedata.combining(ch))
        return t.replace("*", "").strip().lower()

    for langue in i18n.LANGUES:
        for cle_section, table in render_html.VOCABULAIRE_LARGEUR.items():
            for statut, (cle_html, *_) in table.items():
                md = libelle_statut(cle_section, statut, langue)
                html = i18n.t(cle_html, langue)
                assert nu(md) == nu(html), (langue, cle_section, statut,
                                            md, html)


# ==========================================================================
# 7. La ligne de commande
# ==========================================================================


def test_la_cli_accepte_drx_et_base(tmp_path, capsys):
    from klastos.cli import main

    f = _fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")
    code = main(["rapport", str(BULLETIN), "--provenance",
                 "vehicule_electrique", "--atteste", "--drx", str(f),
                 "--tirages", "8"])
    assert code == 0
    assert TITRE_DRX in capsys.readouterr().out


def test_la_cli_refuse_une_base_cristalline_a_une_phase(tmp_path, capsys):
    from klastos.cli import main

    f = _fichier_drx(tmp_path, "NMC 811,18.0,3.0\n")
    code = main(["rapport", str(BULLETIN), "--provenance",
                 "vehicule_electrique", "--atteste", "--drx", str(f),
                 "--base", "cristalline", "--tirages", "8"])
    assert code != 0
    assert "refusée" in capsys.readouterr().err


def test_la_cli_porte_le_conseil(tmp_path, capsys):
    from klastos.cli import main

    code = main(["rapport", str(BULLETIN), "--provenance",
                 "vehicule_electrique", "--atteste", "--conseil-drx",
                 "--tirages", "8"])
    assert code == 0
    assert TITRE_CONSEIL in capsys.readouterr().out


def test_la_cli_refuse_une_quantification_sans_incertitude(tmp_path, capsys):
    from klastos.cli import main

    f = tmp_path / "sans_u.csv"
    f.write_text("Phase,Valeur (%)\nNMC 811,18.0\n", encoding="utf-8")
    code = main(["rapport", str(BULLETIN), "--provenance",
                 "vehicule_electrique", "--atteste", "--drx", str(f),
                 "--tirages", "8"])
    assert code != 0
    assert "incertitude" in capsys.readouterr().err