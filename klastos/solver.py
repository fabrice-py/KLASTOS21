"""
KLASTOS21 - Deconvolution des phases a partir du bulletin elementaire.

Probleme
--------
Trouver x >= 0 tel que A @ x ~ b, ou A est la matrice de stoechiometrie,
b le bulletin d'analyse et x les fractions massiques de phases.

Trois difficultes, traitees separement.

1. PONDERATION. Les elements couvrent trois ordres de grandeur (O ~ 35 %,
   F ~ 1 %). Une moindre carre brute serait pilotee par l'oxygene seul. On
   pondere donc chaque residu par l'incertitude analytique attendue sur
   l'element, tiree du modele de bruit.

2. DEGENERESCENCE. Le systeme est rang-deficient (voir identifiability).
   On regularise UNIQUEMENT dans l'espace nul :

       min  || W (A x - b) ||^2  +  lambda * || P_N (x - prior) ||^2

   ou P_N = N N^T projette sur l'espace nul. Comme A @ P_N = 0, ce terme
   n'a AUCUN effet sur les grandeurs identifiables : il ne fait que choisir
   un representant dans la famille de solutions equivalentes.

   Consequence a retenir : la valeur ponctuelle des grandeurs NON
   identifiables est un representant arbitraire, pas une estimation. Seul
   le domaine compatible calcule par identifiability.evaluate() fait foi.

3. BOUCLAGE. Chaque colonne de A somme a 1, donc somme(A @ x) = somme(x).
   La somme du bulletin donne donc directement la masse totale des phases.
   Un bulletin qui somme a 0.93 signale 7 % de masse non expliquee :
   analyse incomplete, phase absente du modele, ou declaration inexacte.

Resolution : moindres carres non negatifs sur le systeme augmente
    [ W A          ]       [ W b            ]
    [ sqrt(l) P_N  ] x  ~  [ sqrt(l) P_N p  ]
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import nnls

from .elements import ELEMENTS
from .generator import DEFAULT_NOISE, NoiseModel
from .identifiability import null_space
from .phases import PHASE_KEYS, stoichiometry_matrix

# ==========================================================================
# Seuils de bouclage
# ==========================================================================
# ARBITRES. Ils ne changent aucun calcul, ils ne pilotent que la severite du
# diagnostic affiche.
#
# Mesure a l'appui : sur des lots ENTIEREMENT decrits par le modele, le seul
# bruit analytique de 6 % produit une masse apparemment inexpliquee de 1,8 %
# en mediane, 5,7 % au 95e centile, et jusqu'a 10,3 % au pire. Les premiers
# seuils proposes (3 % et 8 %) etaient donc SOUS le plancher de bruit : ils
# refusaient des lots sains.
#
# Arbitrage du geometallurgiste : alerte a 6 %, rejet a 20 %. Ce reglage se
# cale sur la realite metallurgique des black masses - separateur, solvants
# d'electrolyte, liants aqueux, traces non dosees - plutot que sur un
# echantillon idealement caracterise.
CLOSURE_ALERT = 0.06     # ecart au bouclage a partir duquel on alerte
CLOSURE_REJECT = 0.20    # ecart au-dela duquel le bulletin est juge inexploitable
CLOSURE_THRESHOLDS_VALIDATED = True

STATUT_OK = "ok"
STATUT_ALERTE = "alerte"
STATUT_REJET = "rejet"

MSG_BOUCLAGE = {
    STATUT_OK: "Bouclage massique conforme.",
    STATUT_ALERTE: (
        "Bouclage massique degrade : une part de la masse n'est pas expliquee "
        "par les phases du modele. Causes possibles : analyse incomplete, "
        "phase absente du modele, humidite residuelle, declaration de "
        "provenance inexacte."
    ),
    STATUT_REJET: (
        "Bouclage massique hors tolerance : bulletin juge inexploitable en "
        "l'etat. Une analyse complementaire est requise avant valorisation."
    ),
}


# ==========================================================================
# Structures
# ==========================================================================

@dataclass(frozen=True)
class SolverConfig:
    """Parametres de resolution."""

    lambda_null: float = 1e-4
    """Poids de la regularisation dans l'espace nul. N'affecte aucune
    grandeur identifiable. Une valeur trop faible rend le representant
    instable numeriquement, une valeur trop forte le tire vers le prior."""

    noise: NoiseModel = DEFAULT_NOISE
    """Sert a ponderer les residus, pas a bruiter."""

    weight_floor: float = 1e-5
    """Plancher d'incertitude, evite une ponderation infinie sur un element
    mesure a zero."""

    use_weights: bool = True

    closure_alert: float = CLOSURE_ALERT
    closure_reject: float = CLOSURE_REJECT


@dataclass
class ClosureCheck:
    """Diagnostic de bouclage massique du bulletin."""

    total: float
    gap: float
    status: str
    message: str

    @property
    def is_exploitable(self) -> bool:
        return self.status != STATUT_REJET

    def format(self) -> str:
        return f"Somme du bulletin : {self.total * 100:.2f} % ({self.message})"


@dataclass
class SolveResult:
    """Solution retenue et diagnostics associes."""

    x: np.ndarray
    phase_keys: list[str]
    elements: list[str]
    b_input: np.ndarray
    b_fitted: np.ndarray
    closure: ClosureCheck
    residual_weighted: float
    residual_absolute: np.ndarray
    degeneracy: int
    config: SolverConfig
    predicted_unmeasured: dict[str, float] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    @property
    def max_element_residual(self) -> float:
        return float(np.max(np.abs(self.residual_absolute)))

    @property
    def explained_mass(self) -> float:
        """
        Part du lot que les phases du modele expliquent.

        C'est la somme des fractions de phases. Les colonnes de A sommant a 1,
        cette somme couvre AUSSI les elements non doses, l'oxygene en premier
        lieu. Un lot a 0,92 signale donc 8 % de masse que le modele n'explique
        pas : humidite, phase absente du modele, ou declaration inexacte.
        """
        return float(np.sum(self.x))

    @property
    def unexplained_mass(self) -> float:
        """Complement de `explained_mass`, positif quand de la masse manque."""
        return 1.0 - self.explained_mass

    def as_dict(self, tol: float = 1e-9) -> dict[str, float]:
        """Fractions de phases non nulles, en % massiques."""
        return {
            pk: round(float(self.x[i] * 100.0), 4)
            for i, pk in enumerate(self.phase_keys)
            if self.x[i] > tol
        }

    @property
    def point_estimate_is_representative(self) -> bool:
        """
        True si le systeme est degenere : les valeurs ponctuelles des
        grandeurs non identifiables sont alors un representant arbitraire.
        """
        return self.degeneracy > 0


# ==========================================================================
# Diagnostics
# ==========================================================================

def check_closure(
    values: np.ndarray,
    alert: float = CLOSURE_ALERT,
    reject: float = CLOSURE_REJECT,
) -> ClosureCheck:
    """
    Bouclage massique : la somme fournie est-elle proche de 1 ?

    ATTENTION - cette fonction s'applique aux FRACTIONS DE PHASES, pas au
    bulletin. Un bulletin reel ne somme jamais a 1 : aucun laboratoire ne
    dose l'oxygene, et il represente pres de 20 % d'une black mass riche en
    oxydes de cathode. Mesurer le bouclage sur le bulletin rejetterait donc
    tous les lots reels.

    Les colonnes de la matrice de stoechiometrie sommant a 1, la somme des
    fractions de phases couvre en revanche l'integralite de la masse, y
    compris les elements non doses. C'est donc elle qui porte le diagnostic.
    """
    total = float(np.sum(values))
    gap = abs(total - 1.0)
    if gap >= reject:
        status = STATUT_REJET
    elif gap >= alert:
        status = STATUT_ALERTE
    else:
        status = STATUT_OK
    return ClosureCheck(
        total=total, gap=gap, status=status, message=MSG_BOUCLAGE[status]
    )


def element_weights(
    b: np.ndarray,
    noise: NoiseModel = DEFAULT_NOISE,
    floor: float = 1e-5,
) -> np.ndarray:
    """
    Poids 1 / sigma_e, ou sigma_e est l'incertitude attendue sur l'element.

    Sans ponderation, l'oxygene (~35 % massique) ecraserait le fluor (~1 %)
    et le solveur ignorerait les phases mineures qui portent pourtant
    l'essentiel du diagnostic procede.
    """
    sigma = noise.rel_sigma * np.abs(b) + noise.abs_sigma
    sigma = np.maximum(sigma, floor)
    return 1.0 / sigma


# ==========================================================================
# Resolution
# ==========================================================================

def solve(
    b: np.ndarray | dict[str, float],
    phase_keys: list[str] | None = None,
    elements: list[str] | None = None,
    config: SolverConfig | None = None,
    prior: np.ndarray | None = None,
) -> SolveResult:
    """
    Deconvolue un bulletin elementaire en fractions massiques de phases.

    Parameters
    ----------
    b : vecteur de fractions massiques elementaires, ou dictionnaire
        {element: pourcentage massique}.
    phase_keys : liste de phases retenue, typiquement issue de
        ProvenanceDeclaration.resolve().
    elements : elements EFFECTIVEMENT DOSES par le laboratoire. Un bulletin
        reel ne contient jamais l'oxygene : il faut alors passer la liste des
        onze autres elements, et le systeme est resolu sur ceux-la seuls.
        Par defaut, les douze elements du modele.
    prior : representant privilegie dans l'espace nul. Par defaut zero, ce
        qui revient a choisir la solution de norme minimale dans la
        direction non identifiable. Un prior non nul n'a d'effet QUE sur les
        grandeurs non identifiables.

    Notes
    -----
    Resoudre sans l'oxygene a deux consequences, toutes deux rapportees :

    - la degenerescence augmente d'un degre, et plusieurs agregats cessent
      d'etre identifiables sans attestation de provenance ;
    - en contrepartie, l'oxygene devient une grandeur PREDITE, et la somme
      des phases mesure la part du lot que le modele explique.
    """
    config = config or SolverConfig()

    mesures = list(ELEMENTS) if elements is None else list(elements)
    inconnus_els = set(mesures) - set(ELEMENTS)
    if inconnus_els:
        raise KeyError(
            f"Element(s) hors modele : {sorted(inconnus_els)}. "
            f"Elements admis : {ELEMENTS}"
        )
    if not mesures:
        raise ValueError("Aucun element dose : rien a resoudre.")

    A, mesures, keys = stoichiometry_matrix(phase_keys=phase_keys, elements=mesures)
    A_full, els_full, _ = stoichiometry_matrix(phase_keys=keys)

    if isinstance(b, dict):
        inconnus = set(b) - set(ELEMENTS)
        if inconnus:
            raise KeyError(f"Element(s) inconnu(s) dans le bulletin : {sorted(inconnus)}")
        b = np.array([b.get(el, 0.0) / 100.0 for el in mesures], dtype=float)
    else:
        b = np.asarray(b, dtype=float)

    if b.shape[0] != len(mesures):
        raise ValueError(
            f"Le bulletin a {b.shape[0]} valeurs, {len(mesures)} elements attendus."
        )
    if np.any(b < 0):
        raise ValueError("Un bulletin ne peut pas contenir de valeur negative.")

    # --- ponderation ------------------------------------------------------
    if config.use_weights:
        w = element_weights(b, config.noise, config.weight_floor)
    else:
        w = np.ones_like(b)
    W = np.diag(w)

    # --- regularisation restreinte a l'espace nul -------------------------
    N = null_space(A)
    n = A.shape[1]
    if prior is None:
        prior = np.zeros(n)
    else:
        prior = np.asarray(prior, dtype=float)
        if prior.shape[0] != n:
            raise ValueError(
                f"Le prior a {prior.shape[0]} composantes, {n} phases attendues."
            )

    blocs_A = [W @ A]
    blocs_b = [W @ b]

    if N.size and config.lambda_null > 0:
        P_N = N @ N.T                       # projecteur orthogonal sur ker(A)
        s = np.sqrt(config.lambda_null)
        blocs_A.append(s * P_N)
        blocs_b.append(s * (P_N @ prior))

    M = np.vstack(blocs_A)
    y = np.concatenate(blocs_b)

    x, _ = nnls(M, y)

    b_fit = A @ x
    residual_abs = b_fit - b
    residual_w = float(np.linalg.norm(w * residual_abs))

    # Le bouclage se mesure sur les PHASES, jamais sur le bulletin : voir
    # la note de check_closure.
    closure = check_closure(x, config.closure_alert, config.closure_reject)

    # Les elements non doses deviennent des grandeurs predites.
    b_pred_full = A_full @ x
    non_doses = [e for e in els_full if e not in set(mesures)]
    predits = {
        e: float(b_pred_full[els_full.index(e)]) for e in non_doses
    }

    return SolveResult(
        x=x,
        phase_keys=keys,
        elements=mesures,
        b_input=b,
        b_fitted=b_fit,
        closure=closure,
        residual_weighted=residual_w,
        residual_absolute=residual_abs,
        degeneracy=int(n - np.linalg.matrix_rank(A)),
        config=config,
        predicted_unmeasured=predits,
        meta={
            "prior_used": bool(np.any(prior)),
            "n_phases": n,
            "measured_elements": list(mesures),
            "unmeasured_elements": non_doses,
        },
    )


def solve_lot(lot, config: SolverConfig | None = None, **kwargs) -> SolveResult:
    """Raccourci : deconvolue un SyntheticLot depuis son bulletin bruite."""
    return solve(
        lot.b_measured, phase_keys=lot.phase_keys, config=config, **kwargs
    )