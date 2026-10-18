"""Tests de klastos/structural.py.

Ce module porte un engagement unique, et c'est le plus exigeant du produit :

    UNE QUANTIFICATION PAR DIFFRACTION EST UNE MESURE, PAS UNE VERITE.

Elle entre donc en encadrement et jamais en egalite. Un seul test qui
laisserait passer une valeur ponctuelle recreerait le piege du sommet a
l'endroit meme que ce module existe pour proteger : le client croirait
tenir une phase fermee parce qu'un laboratoire a imprime deux decimales.

Le second engagement est physique : un diffractogramme ne voit que la
matiere cristalline. Confondre les deux bases de normalisation est une
erreur de plusieurs points, et elle est silencieuse.
"""

import numpy as np
import pytest
from scipy.optimize import linprog

from klastos import structural as S
from klastos.phases import PHASE_KEYS, stoichiometry_matrix

PH = ["NMC111", "NMC532", "NMC622", "NMC811", "LFP", "C_total", "PVDF"]


def entete(u: bool = True) -> list[str]:
    e = ["Phase", "Valeur (%)"]
    if u:
        e.append("Incertitude (%)")
    return e


def lignes(*triplets, avec_u: bool = True) -> list[list[str]]:
    out = [entete(avec_u)]
    for t in triplets:
        out.append([str(c) for c in (t if avec_u else t[:2])])
    return out


# ==========================================================================
# 1. L'encadrement est obligatoire — LE VERROU DU MODULE
# ==========================================================================


def test_une_quantification_sans_incertitude_est_refusee():
    """
    LE VERROU. Sans colonne d'incertitude, la phase sortirait en valeur
    unique : une mesure Rietveld precise a 1 ou 3 points serait presentee
    comme exacte.
    """
    with pytest.raises(S.StructuralRefused, match="incertitude"):
        S.parse_structural(lignes(("LFP", 12.4), avec_u=False))


def test_une_incertitude_nulle_est_refusee():
    with pytest.raises(S.StructuralRefused, match="credible"):
        S.parse_structural(lignes(("LFP", 12.4, 0.0)))


def test_une_incertitude_infinitesimale_est_refusee():
    """Contourner le verrou par 1e-9 doit echouer comme un zero franc."""
    with pytest.raises(S.StructuralRefused, match="credible"):
        S.parse_structural(lignes(("LFP", 12.4, 1e-9)))


def test_aucune_contrainte_n_est_une_egalite():
    """
    Consequence du verrou, verifiee sur la sortie et non sur la saisie :
    toute ligne produite est une inegalite, et chaque phase quantifiee en
    recoit DEUX, qui ne peuvent pas se refermer sur un point.
    """
    d = S.parse_structural(lignes(("NMC622", 28.1, 2.0), ("LFP", 12.4, 1.5)))
    G, h, _ = S.contraintes(d, PH)
    assert G.shape[0] == 2 * len(d)
    for q in d.quantifications:
        assert q.haut - q.bas > 0.0


def test_la_borne_basse_ne_passe_jamais_sous_zero():
    d = S.parse_structural(lignes(("LFP", 1.0, 2.0)))
    q = d.quantifications[0]
    assert q.bas == 0.0
    assert any("tronquee a 0" in m for m in d.journal)


def test_une_incertitude_absurde_est_refusee():
    with pytest.raises(S.StructuralRefused, match="n'informe pas"):
        S.parse_structural(lignes(("LFP", 30.0, 30.0)))


def test_une_phase_a_zero_est_refusee():
    """Une phase sous la limite de quantification se declare absente."""
    with pytest.raises(S.StructuralRefused, match="trop faible"):
        S.parse_structural(lignes(("LFP", 0.0, 1.5)))


# ==========================================================================
# 2. Les deux bases de normalisation
# ==========================================================================


def test_la_base_absolue_contraint_les_niveaux():
    d = S.parse_structural(lignes(("NMC622", 28.1, 2.0)), basis=S.BASE_ABSOLUE)
    G, h, _ = S.contraintes(d, PH)
    j = PH.index("NMC622")
    # une ligne +e_j <= v+u, une ligne -e_j <= -(v-u)
    assert np.allclose(G[0, j], 1.0) and np.allclose(h[0], 0.301)
    assert np.allclose(G[1, j], -1.0) and np.allclose(h[1], -0.261)
    # aucune autre colonne touchee
    autres = [k for k in range(len(PH)) if k != j]
    assert np.allclose(G[:2, autres], 0.0)


def test_la_base_cristalline_ne_contraint_aucun_niveau():
    """
    LE SECOND VERROU. La fraction cristalline du lot est inconnue : une
    contrainte de niveau serait fausse de plusieurs points. Seuls les
    rapports sont invariants, et un rapport a un second membre nul.
    """
    d = S.parse_structural(
        lignes(("NMC622", 28.1, 2.0), ("LFP", 12.4, 1.5)),
        basis=S.BASE_CRISTALLINE)
    G, h, _ = S.contraintes(d, PH)
    assert np.allclose(h, 0.0), "un rapport ne borne aucun niveau"
    # invariance : multiplier x par un scalaire ne change pas la validite
    x = np.zeros(len(PH))
    x[PH.index("NMC622")] = 0.281
    x[PH.index("LFP")] = 0.124
    for facteur in (0.1, 0.5, 1.0, 2.0, 7.3):
        assert np.all(G @ (facteur * x) <= h + 1e-12), facteur


def test_n_phases_cristallines_donnent_n_moins_un_rapports():
    for n in (2, 3, 4):
        cles = ["NMC111", "NMC532", "NMC622", "NMC811"][:n]
        d = S.parse_structural(
            lignes(*[(c, 10.0, 1.0) for c in cles]),
            basis=S.BASE_CRISTALLINE)
        G, _, _ = S.contraintes(d, PH)
        assert G.shape[0] == 2 * (n - 1), f"{n} phases"


def test_une_seule_phase_cristalline_est_refusee():
    with pytest.raises(S.StructuralRefused, match="ne contraint rien"):
        S.parse_structural(lignes(("LFP", 12.4, 1.5)),
                           basis=S.BASE_CRISTALLINE)


def test_une_somme_superieure_a_cent_en_base_absolue_est_refusee():
    """
    Le cas d'erreur le plus probable en production : un laboratoire rend
    des pourcentages cristallins renormalises et le client declare la base
    absolue. Le message doit nommer la vraie cause.
    """
    with pytest.raises(S.StructuralRefused, match="cristallins renormalises"):
        S.parse_structural(lignes(("NMC622", 60.0, 2.0), ("LFP", 55.0, 1.5)),
                           basis=S.BASE_ABSOLUE)


def test_une_base_inconnue_est_refusee():
    with pytest.raises(S.StructuralRefused, match="Base de normalisation"):
        S.parse_structural(lignes(("LFP", 12.4, 1.5)), basis="peu importe")


# ==========================================================================
# 3. Propagation sur un rapport : majorante, jamais optimiste
# ==========================================================================


def test_l_incertitude_du_rapport_majore_la_somme_quadratique():
    """
    Les pourcentages Rietveld sont renormalises a 100 %, donc correles
    negativement. La formule d'independance sous-estimerait l'incertitude ;
    on retient la somme lineaire, qui majore quelle que soit la correlation.
    """
    va, ua, vb, ub = 0.281, 0.020, 0.124, 0.015
    lineaire = ua / va + ub / vb
    quadratique = float(np.hypot(ua / va, ub / vb))
    assert lineaire > quadratique

    d = S.parse_structural(
        lignes(("NMC622", va * 100, ua * 100), ("LFP", vb * 100, ub * 100)),
        basis=S.BASE_CRISTALLINE)
    G, _, journal = S.contraintes(d, PH)
    ja, jb = PH.index("NMC622"), PH.index("LFP")
    r = va / vb
    # ligne 0 : x_a - r(1+e) x_b <= 0  ->  coefficient -r(1+e) sur b
    haut = -G[0, jb]
    assert haut == pytest.approx(r * (1.0 + lineaire))
    assert haut > r * (1.0 + quadratique)
    assert any("majoree" in m for m in journal)


def test_le_rapport_ne_descend_jamais_sous_zero():
    """Une incertitude relative superieure a 100 % bornerait le rapport
    dans le negatif, ce qui est impossible pour des fractions massiques."""
    d = S.parse_structural(
        lignes(("NMC622", 2.0, 1.8), ("LFP", 2.0, 1.8)),
        basis=S.BASE_CRISTALLINE)
    G, _, _ = S.contraintes(d, PH)
    ja, jb = PH.index("NMC622"), PH.index("LFP")
    bas = G[1, jb]                      # ligne -x_a + bas x_b <= 0
    assert bas >= 0.0


# ==========================================================================
# 4. Resolution des libelles
# ==========================================================================


@pytest.mark.parametrize("ecrit,attendu", [
    ("NMC622", "NMC622"),
    ("NMC 622", "NMC622"),
    ("nmc-622", "NMC622"),
    ("  NMC  622  ", "NMC622"),
    ("LiNi0.6Mn0.2Co0.2O2", "NMC622"),
    ("LFP", "LFP"),
    ("LiFePO4", "LFP"),
    ("Fer metallique", "Fe_metal"),
    ("Fer métallique", "Fe_metal"),
])
def test_les_libelles_de_laboratoire_sont_resolus(ecrit, attendu):
    assert S.resoudre_phase(ecrit) == attendu


def test_une_phase_inconnue_est_refusee_et_nomme_les_phases_admises():
    with pytest.raises(S.StructuralRefused) as exc:
        S.resoudre_phase("hollandite")
    for cle in ("NMC622", "LFP"):
        assert cle in str(exc.value)


def test_chaque_phase_du_modele_est_resolvable():
    """Un alias manquant rendrait une phase inaccessible a la saisie."""
    for cle in PHASE_KEYS:
        assert S.resoudre_phase(cle) == cle


def test_la_table_d_alias_est_saine():
    """
    Une collision leverait au chargement du module. Reste a verifier que
    la table couvre exactement le modele : tout alias tombe sur une phase
    declaree, et toute phase est atteignable par sa cle, son libelle et sa
    formule.
    """
    from klastos.phases import PHASES

    assert set(S.ALIAS_PHASES.values()) == set(PHASE_KEYS)
    for cle, p in PHASES.items():
        for texte in (cle, p["label"], p["formula"]):
            assert S.resoudre_phase(texte) == cle, texte


# ==========================================================================
# 5. Lecture de fichier
# ==========================================================================


def test_la_virgule_decimale_francaise_est_lue():
    d = S.parse_structural(lignes(("LFP", "12,40", "1,50")))
    assert d.quantifications[0].value == pytest.approx(0.124)
    assert d.quantifications[0].uncertainty == pytest.approx(0.015)


def test_sans_signe_de_pourcentage_les_valeurs_sont_des_fractions():
    brut = [["Phase", "Valeur", "Incertitude"], ["LFP", "0.124", "0.015"]]
    d = S.parse_structural(brut)
    assert d.quantifications[0].value == pytest.approx(0.124)


def test_les_intitules_de_colonnes_sont_tolerants():
    brut = [["Mineral", "Teneur (%)", "ESD (%)"], ["LFP", "12.4", "1.5"]]
    d = S.parse_structural(brut)
    assert d.cles == ("LFP",)


def test_un_fichier_vide_est_refuse():
    with pytest.raises(S.StructuralRefused, match="vide"):
        S.parse_structural([["Phase", "Valeur (%)", "Incertitude (%)"]])


def test_une_phase_quantifiee_deux_fois_est_refusee():
    with pytest.raises(S.StructuralRefused, match="deux fois"):
        S.parse_structural(lignes(("LFP", 12.4, 1.5), ("LiFePO4", 11.0, 1.5)))


def test_une_ligne_trop_courte_est_refusee():
    brut = [["Phase", "Valeur (%)", "Incertitude (%)"], ["LFP", "12.4"]]
    with pytest.raises(S.StructuralRefused, match="colonne"):
        S.parse_structural(brut)


def test_un_nombre_illisible_est_refuse():
    with pytest.raises(S.StructuralRefused, match="n'est pas un nombre"):
        S.parse_structural(lignes(("LFP", "douze", "1.5")))


def test_le_fichier_est_lu_depuis_le_disque(tmp_path):
    p = tmp_path / "drx.csv"
    p.write_text("Phase,Valeur (%),Incertitude (%)\nNMC 622,28.1,2.0\n",
                 encoding="utf-8")
    d = S.lire_fichier(p)
    assert d.cles == ("NMC622",)
    assert str(p) in d.source


def test_le_journal_rend_compte_de_la_lecture():
    d = S.parse_structural(lignes(("NMC 622", 28.1, 2.0)))
    joint = " ".join(d.journal)
    assert "Valeur (%)" in joint
    assert "Incertitude (%)" in joint


def test_une_formule_chimique_resolue_est_tracee():
    """
    'NMC 622' se normalise comme 'NMC622' : rien a signaler. Une formule,
    elle, change de forme, et le client doit pouvoir verifier sur quelle
    phase le logiciel l'a posee.
    """
    d = S.parse_structural(lignes(("LiNi0.6Mn0.2Co0.2O2", 28.1, 2.0)))
    assert any("NMC622" in m for m in d.journal)


# ==========================================================================
# 6. Coherence avec le modele du lot
# ==========================================================================


def test_une_phase_exclue_par_la_provenance_est_refusee():
    """
    Contradiction entre l'attestation du client et ce que la diffraction
    observe. Le logiciel ne la tranche pas : il la nomme.
    """
    retenues = [k for k in PH if k != "LFP"]
    with pytest.raises(S.StructuralRefused, match="tranchee par le client"):
        S.parse_structural(lignes(("LFP", 12.4, 1.5)), phase_keys=retenues)


def test_contraintes_refuse_une_phase_hors_du_modele_du_lot():
    d = S.parse_structural(lignes(("LFP", 12.4, 1.5)))
    with pytest.raises(S.StructuralRefused, match="absente"):
        S.contraintes(d, [k for k in PH if k != "LFP"])


def test_sans_quantification_aucune_contrainte():
    d = S.StructuralData()
    G, h, _ = S.contraintes(d, PH)
    assert G.shape == (0, len(PH)) and h.shape == (0,)


# ==========================================================================
# 7. L'effet mesure : une contrainte de niveau resserre plus qu'un rapport
# ==========================================================================


def _bornes(x0, N, c, G=None, h=None, cap=1.0, tol=1e-12):
    if N.size == 0:
        v = float(c @ x0)
        return v, v
    k = N.shape[1]
    A_ub, b_ub = [-N], [x0.copy()]
    row = N.sum(axis=0)
    if float(np.max(np.abs(row))) > tol:
        A_ub.append(row.reshape(1, k))
        b_ub.append(np.array([max(cap, float(np.sum(x0))) - float(np.sum(x0))]))
    if G is not None and len(G):
        Gm = np.atleast_2d(G)
        A_ub.append(Gm @ N)
        b_ub.append(np.asarray(h, float) - Gm @ x0)
    A_ub, b_ub = np.vstack(A_ub), np.concatenate(b_ub)
    obj, const = N.T @ c, float(c @ x0)
    lo = linprog(obj, A_ub=A_ub, b_ub=b_ub, bounds=[(None, None)] * k,
                 method="highs")
    hi = linprog(-obj, A_ub=A_ub, b_ub=b_ub, bounds=[(None, None)] * k,
                 method="highs")
    assert lo.success and hi.success
    a, b = const + float(obj @ lo.x), const + float(obj @ hi.x)
    return min(a, b), max(a, b)


@pytest.fixture(scope="module")
def systeme():
    """Un systeme degenere reel : lot VE atteste, oxygene non dose."""
    from klastos.identifiability import null_space
    from klastos.provenance import ProvenanceDeclaration

    d = ProvenanceDeclaration(profile_key="vehicule_electrique", attested=True)
    r = d.resolve()
    keys = list(r[0]) if isinstance(r, tuple) else list(PHASE_KEYS)
    doses = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F"]
    A, _, keys = stoichiometry_matrix(phase_keys=keys, elements=doses)
    N = null_space(A)
    assert N.shape[1] >= 1, "le systeme doit etre degenere"
    # un point interieur admissible, obtenu par moindres carres non negatifs
    from scipy.optimize import nnls
    b = A @ np.full(len(keys), 1.0 / len(keys))
    x0, _ = nnls(A, b)
    return A, N, x0, keys


def test_une_contrainte_retrecit_le_domaine_sans_le_fermer(systeme):
    """
    L'effet attendu, et le vocabulaire qui va avec : la largeur diminue,
    mais elle ne tombe pas a zero. Une DRX reelle ne rend rien identifiable.
    """
    A, N, x0, keys = systeme
    j = keys.index("NMC622")
    c = np.zeros(len(keys)); c[j] = 1.0
    lo, hi = _bornes(x0, N, c)
    if hi - lo < 1e-6:
        pytest.skip("NMC622 deja ferme sur ce systeme")

    v = 0.5 * (lo + hi)
    d = S.StructuralData(
        quantifications=(S.PhaseQuantification("NMC622", v, 0.02),),
        basis=S.BASE_ABSOLUE)
    G, h, _ = S.contraintes(d, keys)
    lo2, hi2 = _bornes(x0, N, c, G, h)

    assert hi2 - lo2 < hi - lo, "la contrainte doit resserrer"
    assert hi2 - lo2 > 1e-9, "elle ne doit PAS fermer : u > 0"
    assert lo2 >= lo - 1e-9 and hi2 <= hi + 1e-9


def test_le_niveau_resserre_au_moins_autant_que_le_rapport(systeme):
    """
    La mesure qui justifie de distinguer les deux bases : a nombre egal de
    phases quantifiees, la base cristalline en rend moins, parce qu'elle
    perd un degre de liberte en passant au rapport.
    """
    A, N, x0, keys = systeme
    ouvertes = []
    for j, k in enumerate(keys):
        c = np.zeros(len(keys)); c[j] = 1.0
        lo, hi = _bornes(x0, N, c)
        if hi - lo > 1e-4:
            ouvertes.append((k, 0.5 * (lo + hi)))
    if len(ouvertes) < 2:
        pytest.skip("pas assez de phases ouvertes")

    (ka, va), (kb, vb) = ouvertes[0], ouvertes[1]
    quants = (S.PhaseQuantification(ka, va, 0.02),
              S.PhaseQuantification(kb, vb, 0.02))

    def largeur_cumulee(G, h):
        t = 0.0
        for j in range(len(keys)):
            c = np.zeros(len(keys)); c[j] = 1.0
            lo, hi = _bornes(x0, N, c, G, h)
            t += hi - lo
        return t

    nue = largeur_cumulee(None, None)
    Ga, ha, _ = S.contraintes(
        S.StructuralData(quants, basis=S.BASE_ABSOLUE), keys)
    Gc, hc, _ = S.contraintes(
        S.StructuralData(quants, basis=S.BASE_CRISTALLINE), keys)

    abs_, cris = largeur_cumulee(Ga, ha), largeur_cumulee(Gc, hc)
    assert abs_ < nue and cris < nue
    assert abs_ <= cris + 1e-9, (
        "la base absolue doit resserrer au moins autant que la cristalline")


def test_la_contrainte_contient_toujours_la_valeur_declaree(systeme):
    """Garde-fou : un x place sur la valeur declaree doit etre admissible."""
    A, N, x0, keys = systeme
    q = S.PhaseQuantification("NMC622", 0.13, 0.02)
    G, h, _ = S.contraintes(S.StructuralData((q,), S.BASE_ABSOLUE), keys)
    x = np.zeros(len(keys))
    x[keys.index("NMC622")] = q.value
    assert np.all(G @ x <= h + 1e-12)


# ==========================================================================
# 8. Representation
# ==========================================================================


def test_le_resume_nomme_la_base_et_les_valeurs():
    d = S.parse_structural(lignes(("NMC622", 28.1, 2.0)))
    r = d.resume()
    assert "absolue" in r and "28.10" in r and "2.00" in r


def test_le_resume_d_un_jeu_vide_le_dit():
    assert "Aucune" in S.StructuralData().resume()


def test_les_libelles_de_base_sont_tous_renseignes():
    for b in S.BASES:
        assert b in S.LIBELLE_BASE and S.LIBELLE_BASE[b]