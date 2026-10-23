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

   Le SENS de l'ecart compte autant que son ampleur, et les deux cas
   appellent deux enquetes opposees. Une somme de 0.93 signale 7 % de masse
   non expliquee : analyse incomplete, phase absente du modele, declaration
   inexacte. Une somme de 1.10 signale l'inverse - le modele attribue au lot
   plus de masse qu'il n'en a - et la cause est alors qu'un element non dose
   laisse sa phase porteuse sans contrainte, ou la resolution deverse la
   masse manquante. Le seuil de rejet est donc asymetrique.

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
from . import i18n
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

# ARBITRE, et le seuil est ASYMETRIQUE : un sur-bouclage se rejette plus tot
# qu'un sous-bouclage.
#
# Un lot peut legitimement contenir de la masse que le modele n'explique pas
# - separateur, solvants, traces non dosees - d'ou la tolerance de 20 % dans
# ce sens. L'inverse n'a pas d'equivalent physique : les phases du modele ne
# peuvent pas peser plus que le lot. Au-dela du bruit, un sur-bouclage est
# donc une erreur, pas une lacune.
#
# Mesure a l'appui, sur 2 500 lots SAINS - bouclage exactement 1, seul le
# bruit analytique de 6 % - repartis sur les cinq profils :
#
#     centile 95   du sur-bouclage   +5,55 pt
#     centile 99                     +7,35 pt
#     centile 99,9                   +9,44 pt
#     PIRE observe                  +10,10 pt
#
# Le bruit seul atteint donc +10 points. Un seuil en dessous refuserait des
# lots sains, et c'est exactement l'erreur que l'arbitrage du sous-bouclage
# avait ecartee en rejetant 3 % et 8 %. 12 % est le premier palier
# strictement au-dessus du plancher mesure.
#
# Consequence assumee : les deux lots reels qui ont revele le defaut restent
# en ALERTE, BM1 a +10,45 pt et BM2 a +7,63 pt. Ils ne sont pas separables
# du bruit par le bouclage. Ce qui les attrape est ailleurs - la prediction
# de fluor a 17,79 % contre 2,44 % certifie, soit un facteur 7, relevee par
# les bandes de plausibilite de composition.
CLOSURE_REJECT_OVER = 0.12

CLOSURE_THRESHOLDS_VALIDATED = True

STATUT_OK = "ok"
STATUT_ALERTE = "alerte"
STATUT_REJET = "rejet"

#: Sens de l'ecart au bouclage. Le STATUT porte la severite - c'est lui qui
#: pilote la couleur et l'exploitabilite - et le SENS porte la direction,
#: c'est lui qui pilote la prose.
#:
#: La distinction manquait, et c'est un defaut trouve en faisant tourner
#: l'outil sur des donnees reelles pour la premiere fois. `check_closure`
#: calculait `abs(total - 1.0)` et perdait le signe, donc un lot a 110,45 %
#: recevait le message du SOUS-bouclage : « une part de la masse n'est pas
#: expliquee par les phases du modele », avec pour causes « analyse
#: incomplete, phase absente du modele, humidite residuelle ». Ce sont les
#: causes de l'autre direction. Le client etait envoye enqueter a l'envers.
SENS_SUR = "sur"      # total > 1 : le modele explique PLUS que la masse reelle
SENS_SOUS = "sous"    # total < 1 : une part de la masse reste inexpliquee

#: Les cles du catalogue qui portent un message de bouclage. Un statut
#: degrade en a DEUX, une par direction : les causes d'un sur-bouclage ne
#: sont pas celles d'un sous-bouclage.
CLES_BOUCLAGE = (
    f"journal.bouclage.{STATUT_OK}",
    f"journal.bouclage.{STATUT_ALERTE}_{SENS_SOUS}",
    f"journal.bouclage.{STATUT_ALERTE}_{SENS_SUR}",
    f"journal.bouclage.{STATUT_REJET}_{SENS_SOUS}",
    f"journal.bouclage.{STATUT_REJET}_{SENS_SUR}",
)

#: Message par cle, VUE FRANCAISE du catalogue.
#:
#: Le texte vivait en clair dans ce module, et `ClosureCheck.message` en
#: figeait une copie au moment du calcul. Des que le rapport s'est mis a
#: traduire depuis le STATUT, il y a eu deux sources de verite pour la meme
#: phrase - et la valorisation reinjectait la copie francaise dans un
#: rapport anglais.
#:
#: Le solveur ne produit qu'un STATUT et un SENS. Le texte est du rendu : il
#: appartient au catalogue, et ce module n'en garde qu'une vue francaise
#: pour les appelants qui lisent `message`.
MSG_BOUCLAGE = {cle: i18n.t(cle, "fr") for cle in CLES_BOUCLAGE}


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
    closure_reject_over: float = CLOSURE_REJECT_OVER
    """Seuil de rejet dans le sens du SUR-bouclage. Distinct du precedent :
    un lot peut contenir de la masse non expliquee, il ne peut pas en
    contenir moins que ce que le modele lui attribue."""


@dataclass
class ClosureCheck:
    """
    Diagnostic de bouclage massique du bulletin.

    Le STATUT est la donnee ; le message n'en est qu'un rendu.

    `message` etait un champ, donc une copie francaise figee au moment du
    calcul. Le rapport s'etant mis a rendre le texte depuis le statut, la
    meme phrase avait deux sources - et `valuation.py` reinjectait la copie
    francaise dans un rapport anglais, en double et begayante :
    « Bouclage massique : Bouclage massique degrade : ... ».

    C'est desormais une PROPRIETE derivee du catalogue. Il n'y a plus qu'une
    source de verite, et un appelant qui veut une autre langue demande
    `message_dans(langue)`.
    """

    total: float
    signed_gap: float
    """Ecart SIGNE au bouclage : `total - 1`. Negatif en sous-bouclage,
    positif en sur-bouclage. C'est la donnee ; `gap` n'en est qu'une vue."""

    status: str

    @property
    def gap(self) -> float:
        """
        L'ecart en valeur absolue, pour les appelants qui comparent aux
        seuils. Derive de `signed_gap` plutot que stocke a cote : deux
        champs pour une meme grandeur peuvent se desynchroniser, et c'est
        precisement la perte du signe qui a produit le defaut d'origine.
        """
        return abs(self.signed_gap)

    @property
    def direction(self) -> str:
        """Le sens de l'ecart. Vaut SENS_SUR ou SENS_SOUS."""
        return SENS_SUR if self.signed_gap > 0.0 else SENS_SOUS

    @property
    def is_exploitable(self) -> bool:
        return self.status != STATUT_REJET

    @property
    def cle_message(self) -> str:
        """
        La cle du catalogue a rendre. Elle est calculee ICI et nulle part
        ailleurs.

        Trois modules la reconstruisaient depuis le statut - ce module,
        `report.py` et `app.py`. Tant qu'un statut valait une cle, les
        trois tombaient d'accord par hasard ; des que la direction entre en
        jeu, deux d'entre eux auraient continue a afficher le texte du
        sous-bouclage. L'objet porte donc sa cle, et les appelants la
        demandent.

        Un bouclage conforme n'a pas de direction a annoncer : il n'y a
        rien a expliquer quand l'ecart est sous le seuil d'alerte.
        """
        if self.status == STATUT_OK:
            return f"journal.bouclage.{STATUT_OK}"
        return f"journal.bouclage.{self.status}_{self.direction}"

    @property
    def message(self) -> str:
        """Le message en francais. Vue, pas donnee."""
        return self.message_dans("fr")

    def message_dans(self, langue: str) -> str:
        """Le message du statut, dans la langue demandee."""
        return i18n.t(self.cle_message, langue)

    def format(self, langue: str = "fr") -> str:
        return i18n.t("journal.bouclage.somme", langue,
                      total=self.total * 100,
                      message=self.message_dans(langue))


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
    reject_over: float = CLOSURE_REJECT_OVER,
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
    # Le SIGNE est conserve. `abs` le perdait, et le diagnostic ne pouvait
    # alors plus distinguer un lot a 93,95 % d'un lot a 110,45 %.
    signed_gap = total - 1.0
    gap = abs(signed_gap)
    # Le seuil de rejet depend du SENS : un lot ne peut pas peser plus que
    # lui-meme, donc le sur-bouclage se rejette plus tot. L'alerte, elle,
    # reste symetrique : a 6 points d'ecart il y a quelque chose a elucider
    # dans les deux directions.
    seuil_rejet = reject_over if signed_gap > 0.0 else reject
    if gap >= seuil_rejet:
        status = STATUT_REJET
    elif gap >= alert:
        status = STATUT_ALERTE
    else:
        status = STATUT_OK
    # Pas de message ici : le solveur produit un STATUT et un SENS, pas de
    # la prose.
    return ClosureCheck(total=total, signed_gap=signed_gap, status=status)


def element_weights(
    b: np.ndarray,
    noise: NoiseModel = DEFAULT_NOISE,
    floor: float = 1e-5,
    elements: list[str] | None = None,
) -> np.ndarray:
    """
    Poids 1 / sigma_e, ou sigma_e est l'incertitude attendue sur l'element.

    Sans ponderation, l'oxygene (~35 % massique) ecraserait le fluor (~1 %)
    et le solveur ignorerait les phases mineures qui portent pourtant
    l'essentiel du diagnostic procede.

    `elements` n'est utile que si le modele de bruit porte une table par
    element. Le sigma est demande au modele et non recalcule ici : la
    formule vivait recopiee a deux endroits, et un bruit par element
    n'aurait honore que celui des deux qu'on aurait pense a modifier.
    """
    sigma = np.maximum(noise.sigmas(b, elements), floor)
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
        w = element_weights(b, config.noise, config.weight_floor,
                            elements=mesures)
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
    closure = check_closure(x, config.closure_alert,
                            config.closure_reject,
                            config.closure_reject_over)

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