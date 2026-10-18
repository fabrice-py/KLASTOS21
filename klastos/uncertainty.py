"""
KLASTOS21 - Propagation d'incertitude.

Deux incertitudes de nature differente
--------------------------------------
KLASTOS21 les calcule separement et ne les melange jamais dans un chiffre
unique, parce qu'elles n'appellent pas la meme decision du client.

1. INCERTITUDE ANALYTIQUE - reductible.
   Elle vient du bruit du bulletin. On la propage par reechantillonnage :
   on tire des bulletins compatibles avec l'incertitude du laboratoire, on
   resout chacun, et l'on observe la dispersion des grandeurs.
   Le client la reduit en payant une meilleure analyse.

2. NON-IDENTIFIABILITE STRUCTURELLE - irreductible.
   Elle vient du rang deficient de la matrice de stoechiometrie. Aucune
   precision analytique ne la reduit. Le client ne la reduit qu'en apportant
   une information NOUVELLE : donnee structurale (DRX) ou attestation de
   provenance.

Combinaison
-----------
Pour une grandeur non identifiable, la valeur ponctuelle de chaque tirage
est un representant arbitraire : sa dispersion n'a aucun sens. Ce qui a un
sens est l'ENVELOPPE des domaines compatibles sur l'ensemble des tirages.

    domaine total = [ min des bornes basses , max des bornes hautes ]

Pour une grandeur ferme, le domaine structurel est de largeur nulle et
l'incertitude se reduit a la dispersion analytique.

PIEGE DU SOMMET - la raison d'etre de ce module
-----------------------------------------------
La contrainte x >= 0 peut restaurer l'unicite d'un systeme pourtant
rang-deficient : si le solveur aboutit a un sommet du polytope ou plusieurs
phases valent exactement zero, aucun deplacement dans l'espace nul n'est
possible sans rendre une fraction negative.

Un outil naif conclurait alors "NMC 622 = 0,00 %" avec une apparence de
certitude. C'est faux. Cette unicite est un artefact du bulletin exact : il
suffit de 3 % de bruit analytique pour que le sommet se deplace et que la
meme grandeur balaie 0 a 40 %.

D'ou la regle de ce module : l'incertitude d'une grandeur non identifiable
est TOUJOURS mesuree sur l'enveloppe des tirages, jamais sur le domaine
compatible du seul bulletin central. Le drapeau `apparent_uniqueness_risk`
signale explicitement ces cas.

Message commercial porte par ce module : le client voit quelle part de son
incertitude il peut acheter, et quelle part exige une autre mesure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .elements import ELEMENTS
from .generator import DEFAULT_NOISE, NoiseModel
from .identifiability import (SCENARIO_ELEMENTS, ElementScenario, Functional,
                              UnboundedCompatibleSet, compatible_bounds,
                              element_scenario, is_identifiable, null_space,
                              projeter_dans_domaine, standard_functionals)
from .phases import stoichiometry_matrix
from .solver import SolverConfig, solve

# Origine dominante de l'incertitude, telle qu'affichee au client.
SOURCE_ANALYTIQUE = "analytique"
SOURCE_STRUCTURELLE = "structurelle"
SOURCE_NEGLIGEABLE = "negligeable"

# --------------------------------------------------------------------------
# Seuils d'exploitabilite.
#
# Une grandeur est jugee EXPLOITABLE si sa fourchette est etroite RELATIVEMENT
# a sa valeur. Un critere purement absolu serait faux dans les deux sens : il
# condamnerait une teneur en nickel de 19 % connue a plus ou moins 0,8 point
# (soit 4 %, tres bon), et absoudrait une phase mineure a 0,9 % connue a plus
# ou moins 0,9 point (soit 100 %, inutilisable).
#
# Le plancher absolu evite l'effet inverse : sur une grandeur proche de zero,
# le critere relatif explose alors que l'incertitude absolue reste negligeable.
#
# A VALIDER : seuils d'affichage. Ils n'influencent aucun calcul, seulement la
# maniere dont le rapport qualifie une grandeur.
# --------------------------------------------------------------------------
WELL_DETERMINED_REL_WIDTH = 0.25   # fourchette <= 25 % de la valeur
WELL_DETERMINED_ABS_FLOOR = 0.005  # ou <= 0,5 point de %, quoi qu'il arrive
WELL_DETERMINED_WIDTH = 0.02       # seuil de declenchement du piege du sommet
APPARENT_UNIQUENESS_RATIO = 10.0   # enveloppe / largeur locale

CONSEIL = {
    SOURCE_ANALYTIQUE: (
        "Incertitude dominee par la precision du bulletin. Reductible par une "
        "analyse de meilleure qualite ou des replicats."
    ),
    SOURCE_STRUCTURELLE: (
        "Incertitude dominee par la non-identifiabilite structurelle. NON "
        "reductible par l'analyse elementaire, quelle qu'en soit la precision. "
        "Necessite une donnee structurale (DRX) ou une attestation de provenance."
    ),
    SOURCE_NEGLIGEABLE: "Incertitude negligeable.",
}

AVERTISSEMENT_SOMMET = (
    "Le solveur aboutit a une solution apparemment unique, mais cette unicite "
    "resulte de la contrainte de non-negativite sur le bulletin exact. Elle ne "
    "resiste pas au bruit analytique : seule l'enveloppe indiquee fait foi."
)


@dataclass(frozen=True)
class UncertaintyConfig:
    """Parametres du reechantillonnage."""

    n_draws: int = 400
    """Nombre de bulletins tires. 400 suffit pour des centiles a 5 et 95."""

    noise: NoiseModel = DEFAULT_NOISE
    """Incertitude attribuee au bulletin. A remplacer par celle du laboratoire."""

    n_bound_draws: int = 60
    """Tirages sur lesquels on recalcule les bornes structurelles. L'enveloppe
    converge vite ; recalculer sur les 400 tirages couterait cher pour rien."""

    lower_pct: float = 5.0
    upper_pct: float = 95.0
    seed: int | None = None
    solver: SolverConfig | None = None


@dataclass
class UncertaintyResult:
    """
    Incertitude decomposee d'une grandeur.

    Trois largeurs, mesurees sur l'ensemble des tirages :

    - `struct_width`   : largeur MEDIANE du domaine compatible d'un tirage.
                         C'est l'ignorance irreductible a bulletin donne.
    - `analytic_width` : dispersion des CENTRES de ces domaines. C'est ce que
                         le bruit du laboratoire deplace.
    - `total_width`    : enveloppe [min des bornes basses, max des hautes].
                         C'est la seule largeur opposable au client.
    """

    key: str
    label: str
    block: str
    identifiable: bool
    unit: str = "%"

    median: float | None = None

    analytic_lower: float | None = None
    analytic_upper: float | None = None
    analytic_std: float | None = None

    struct_lower: float | None = None      # domaine du bulletin central
    struct_upper: float | None = None
    struct_typical_width: float = 0.0      # mediane sur les tirages

    total_lower: float | None = None
    total_upper: float | None = None

    # Domaine compatible AVANT toute contrainte structurale. Renseigne
    # uniquement lorsqu'une quantification par diffraction est fournie :
    # c'est le terme de comparaison qui rend le gain lisible.
    open_lower: float | None = None
    open_upper: float | None = None

    note: str = ""
    warning: str = ""

    @property
    def open_width(self) -> float:
        if self.open_lower is None or self.open_upper is None:
            return 0.0
        return max(0.0, self.open_upper - self.open_lower)

    @property
    def structural_gain(self) -> float | None:
        """
        Fraction de largeur retiree par la quantification structurale.

        COMPARAISON A PERIMETRE EGAL. On rapporte le domaine compatible du
        bulletin central AVEC contraintes a celui du meme bulletin SANS
        contraintes. Le comparer a `total_width`, qui est l'enveloppe sur
        les tirages, melangerait deux grandeurs differentes et pouvait
        donner un gain nul la ou la plage s'etait resserree d'un tiers.

        None s'il n'y a pas de terme de comparaison, ou si la grandeur etait
        deja fermee : annoncer un gain sur une largeur nulle n'a aucun sens.
        """
        avant = self.open_width
        if self.open_lower is None or avant < 1e-9:
            return None
        if self.struct_lower is None or self.struct_upper is None:
            return None
        apres = max(0.0, self.struct_upper - self.struct_lower)
        return max(0.0, 1.0 - apres / avant)

    @property
    def analytic_width(self) -> float:
        if self.analytic_lower is None or self.analytic_upper is None:
            return 0.0
        return max(0.0, self.analytic_upper - self.analytic_lower)

    @property
    def struct_width(self) -> float:
        return self.struct_typical_width

    @property
    def total_width(self) -> float:
        if self.total_lower is None or self.total_upper is None:
            return 0.0
        return max(0.0, self.total_upper - self.total_lower)

    @property
    def apparent_uniqueness_risk(self) -> bool:
        """
        Vrai lorsque le domaine local est etroit mais l'enveloppe large :
        le solveur semble certain alors qu'il ne l'est pas. Piege du sommet.
        """
        if self.identifiable or self.total_width < WELL_DETERMINED_WIDTH:
            return False
        if self.struct_width < 1e-9:
            return True
        return self.total_width / self.struct_width > APPARENT_UNIQUENESS_RATIO

    @property
    def relative_width(self) -> float | None:
        """Largeur de la fourchette rapportee a la valeur centrale."""
        centre = self.median
        if centre is None and self.total_lower is not None:
            centre = 0.5 * (self.total_lower + self.total_upper)
        if not centre or abs(centre) < 1e-12:
            return None
        return self.total_width / abs(centre)

    @property
    def well_determined(self) -> bool:
        """
        La grandeur est-elle EXPLOITABLE, et pas seulement identifiable ?

        L'identifiabilite est binaire, le conditionnement est continu. Une
        grandeur peut etre mathematiquement determinee et rester inutilisable.
        """
        if self.total_width <= WELL_DETERMINED_ABS_FLOOR:
            return True
        rel = self.relative_width
        if rel is None:
            return self.total_width <= WELL_DETERMINED_ABS_FLOOR
        return rel <= WELL_DETERMINED_REL_WIDTH

    @property
    def dominant_source(self) -> str:
        """
        Quelle incertitude domine, donc quel conseil donner au client.

        Regle prudente pour les grandeurs NON identifiables : la source est
        toujours declaree structurelle, meme quand la dispersion mesuree
        semble d'origine analytique.

        Raison. Sous le piege du sommet, le bruit deplace un sommet du
        polytope dont la position est arbitraire. La sensibilite observee
        ressemble a de l'incertitude analytique, mais elle est la
        manifestation de la degenerescence. Reduire le bruit ne ferait que
        figer un autre sommet, tout aussi arbitraire. Conseiller une analyse
        plus fine serait vendre au client une depense inutile.
        """
        if self.total_width < 1e-6:
            return SOURCE_NEGLIGEABLE
        if not self.identifiable:
            return SOURCE_STRUCTURELLE
        return SOURCE_ANALYTIQUE

    @property
    def reducible_fraction(self) -> float:
        """
        Part de l'incertitude qu'une meilleure analyse peut supprimer.

        Vaut 1 pour une grandeur ferme et 0 pour une grandeur non
        identifiable, par coherence avec `dominant_source` : on ne promet
        jamais au client qu'un meilleur laboratoire resoudra un probleme
        d'identifiabilite.
        """
        if self.total_width < 1e-12:
            return 0.0
        return 1.0 if self.identifiable else 0.0

    def format_value(self, scale: float = 100.0, decimals: int = 2) -> str:
        if self.identifiable and self.median is not None:
            return (
                f"{self.median * scale:.{decimals}f} "
                f"[{self.analytic_lower * scale:.{decimals}f} \u2013 "
                f"{self.analytic_upper * scale:.{decimals}f}] {self.unit}"
            )
        if self.total_lower is not None and self.total_upper is not None:
            lo = 0.0 if abs(self.total_lower) < 1e-12 else self.total_lower
            return (
                f"{lo * scale:.{decimals}f} \u2013 "
                f"{self.total_upper * scale:.{decimals}f} {self.unit}"
            )
        return "indetermine"

    def advice(self) -> str:
        base = CONSEIL[self.dominant_source]
        if self.apparent_uniqueness_risk:
            return f"{base} {AVERTISSEMENT_SOMMET}"
        return base


@dataclass
class UncertaintyReport:
    """Resultat complet du reechantillonnage sur un bulletin."""

    results: list[UncertaintyResult]
    n_draws: int
    n_failed: int
    degeneracy: int
    config: UncertaintyConfig
    meta: dict = field(default_factory=dict)

    #: Tirages pour lesquels la quantification structurale et le bulletin
    #: bruite sont incompatibles. Le tirage est CONSERVE, avec ses bornes
    #: non contraintes ; ce compteur est un diagnostic, pas un rebut.
    n_structural_conflicts: int = 0

    @property
    def structural_conflict_rate(self) -> float:
        total = self.n_draws
        return 0.0 if total <= 0 else self.n_structural_conflicts / total

    def by_key(self) -> dict[str, UncertaintyResult]:
        return {r.key: r for r in self.results}

    def structural_bottlenecks(self) -> list[UncertaintyResult]:
        """Grandeurs dont l'incertitude exige une mesure supplementaire."""
        return sorted(
            (r for r in self.results
             if r.dominant_source == SOURCE_STRUCTURELLE),
            key=lambda r: -r.total_width,
        )

    def analytic_bottlenecks(self) -> list[UncertaintyResult]:
        """Grandeurs qu'un meilleur laboratoire ameliorerait."""
        return sorted(
            (r for r in self.results
             if r.dominant_source == SOURCE_ANALYTIQUE),
            key=lambda r: -r.total_width,
        )


# ==========================================================================
# Reechantillonnage
# ==========================================================================

def resample_bulletin(
    b: np.ndarray,
    rng: np.random.Generator,
    noise: NoiseModel,
) -> np.ndarray:
    """
    Tire un bulletin compatible avec l'incertitude du laboratoire.

    On ne rebruite PAS un bulletin deja bruite : on explore les valeurs
    vraies plausibles ayant pu produire la mesure observee, sous hypothese
    d'erreur symetrique.
    """
    sigma = noise.rel_sigma * np.abs(b) + noise.abs_sigma
    draw = b + rng.normal(0.0, 1.0, size=b.shape) * sigma
    return np.maximum(draw, 0.0)


def propagate(
    b: np.ndarray | dict[str, float],
    phase_keys: list[str] | None = None,
    elements: list[str] | None = None,
    functionals: list[Functional] | None = None,
    config: UncertaintyConfig | None = None,
    structural=None,
) -> UncertaintyReport:
    """
    Propage l'incertitude analytique et l'assemble avec la non-identifiabilite.

    Retourne, pour chaque grandeur, une decomposition entre ce qui est
    reductible par l'analyse et ce qui ne l'est pas.

    `elements` designe les elements EFFECTIVEMENT DOSES. Sur un bulletin reel,
    l'oxygene en est absent : l'identifiabilite est alors evaluee sur les onze
    autres elements seulement, ce qui augmente la degenerescence d'un degre.
    L'analyse doit refleter ce qui a ete mesure, pas ce qu'on aurait voulu
    mesurer.

    `structural` : StructuralData optionnel, issu d'une quantification par
    diffraction. Ses contraintes RESSERRENT les domaines compatibles sans
    rien rendre identifiable - une inegalite borne une direction nulle, elle
    ne la supprime pas. Les champs `open_lower` / `open_upper` de chaque
    resultat conservent le domaine d'avant, pour que le gain soit lisible.
    """
    config = config or UncertaintyConfig()
    rng = np.random.default_rng(config.seed)

    A, els, keys = stoichiometry_matrix(phase_keys=phase_keys, elements=elements)
    functionals = functionals or standard_functionals(keys, elements=els)
    N = null_space(A)

    # --- contraintes structurales -----------------------------------------
    extra = None
    journal_struct: list[str] = []
    if structural is not None and len(structural):
        from .structural import contraintes as _contraintes_struct

        G, h, journal_struct = _contraintes_struct(structural, keys)
        if G.size:
            extra = (G, h)

    def _recadrer(x: np.ndarray) -> np.ndarray:
        """Representant admissible, obtenu sans toucher a A @ x."""
        if extra is None:
            return x
        return projeter_dans_domaine(x, N, extra)

    if isinstance(b, dict):
        b_vec = np.array([b.get(el, 0.0) / 100.0 for el in els], dtype=float)
    else:
        b_vec = np.asarray(b, dtype=float)

    # --- solution centrale -------------------------------------------------
    centrale = solve(b_vec, phase_keys=keys, elements=els,
                     config=config.solver)
    if extra is not None:
        # Le representant doit respecter la quantification declaree, sans
        # quoi le rapport afficherait une valeur ponctuelle hors de
        # l'intervalle qu'il annonce dans la meme page. Le deplacement est
        # purement dans l'espace nul : somme(x) et A @ x sont inchanges,
        # donc le bouclage aussi.
        centrale.x = _recadrer(centrale.x)

    # --- tirages -----------------------------------------------------------
    n_bounds = min(config.n_bound_draws, config.n_draws)
    fermes = {f.key: is_identifiable(f.c, N) for f in functionals}

    valeurs: dict[str, list[float]] = {f.key: [] for f in functionals}
    largeurs: dict[str, list[float]] = {f.key: [] for f in functionals}
    centres: dict[str, list[float]] = {f.key: [] for f in functionals}
    env_lo: dict[str, float] = {f.key: float("inf") for f in functionals}
    env_hi: dict[str, float] = {f.key: float("-inf") for f in functionals}
    echecs = 0
    conflits = 0

    for i in range(config.n_draws):
        tirage = resample_bulletin(b_vec, rng, config.noise)
        try:
            r = solve(tirage, phase_keys=keys, elements=els,
                      config=config.solver)
        except Exception:
            echecs += 1
            continue

        # Contraintes applicables A CE TIRAGE.
        #
        # Un bulletin bruite peut etre incompatible avec la quantification
        # declaree. On ne JETTE PAS ce tirage : le supprimer reviendrait a
        # calculer les percentiles analytiques sur un echantillon censure,
        # donc a resserrer l'incertitude du laboratoire au motif d'une
        # mesure qui ne porte pas sur elle. Mesure a l'appui : sur le lot
        # d'exemple, 42 tirages sur 60 etaient ecartes de cette facon.
        #
        # Le tirage est donc conserve avec ses bornes NON contraintes, donc
        # plus larges. L'enveloppe reste conservatrice, et le taux de
        # conflit devient un diagnostic rapporte au client.
        extra_i = extra
        if extra is not None:
            try:
                r.x = _recadrer(r.x)
            except UnboundedCompatibleSet:
                conflits += 1
                extra_i = None

        borne_ce_tirage = i < n_bounds
        for f in functionals:
            v = float(f.c @ r.x)
            valeurs[f.key].append(v)

            if fermes[f.key]:
                # domaine local de largeur nulle : la valeur EST la borne
                lo = hi = v
            elif borne_ce_tirage:
                lo, hi = compatible_bounds(r.x, N, f.c, extra=extra_i)
            else:
                continue

            largeurs[f.key].append(hi - lo)
            centres[f.key].append(0.5 * (lo + hi))
            env_lo[f.key] = min(env_lo[f.key], lo)
            env_hi[f.key] = max(env_hi[f.key], hi)

    if not any(valeurs[f.key] for f in functionals):
        raise RuntimeError("Tous les tirages ont echoue.")

    # --- assemblage --------------------------------------------------------
    resultats: list[UncertaintyResult] = []
    for f in functionals:
        v = np.asarray(valeurs[f.key], dtype=float)
        c_arr = np.asarray(centres[f.key], dtype=float)
        w_arr = np.asarray(largeurs[f.key], dtype=float)
        ferme = fermes[f.key]

        s_lo, s_hi = compatible_bounds(centrale.x, N, f.c, extra=extra)
        # Terme de comparaison : le domaine SANS la quantification, sur le
        # meme representant. Sans lui, le gain ne serait pas mesurable.
        o_lo = o_hi = None
        if extra is not None and not ferme:
            o_lo, o_hi = compatible_bounds(centrale.x, N, f.c)

        # dispersion analytique : deplacement des CENTRES sous le bruit
        a_lo = float(np.percentile(c_arr, config.lower_pct))
        a_hi = float(np.percentile(c_arr, config.upper_pct))

        # Les bornes totales dependent de la NATURE de l'incertitude, et
        # l'intervalle affiche doit etre celui qui sert au classement.
        #
        # Grandeur FERME : l'incertitude est purement statistique. L'enveloppe
        # min/max des tirages n'est pas un estimateur stable - elle s'elargit
        # mecaniquement avec le nombre de tirages - donc on retient le
        # percentile. La couverture est celle d'un intervalle de confiance,
        # 90 % par defaut, et non une garantie.
        #
        # Grandeur NON IDENTIFIABLE : le domaine compatible est un ensemble
        # mathematique borne, pas un echantillon. Son enveloppe sur les
        # tirages reste donc significative, et la garantie de contenir la
        # valeur vraie s'applique.
        if ferme:
            t_lo, t_hi = a_lo, a_hi
        else:
            t_lo = float(env_lo[f.key])
            t_hi = float(env_hi[f.key])

        note = f.note
        if not ferme and not note:
            note = "ventilation non identifiable par analyse elementaire seule"

        res = UncertaintyResult(
            key=f.key,
            label=f.label,
            block=f.block,
            identifiable=ferme,
            unit=f.unit,
            median=float(np.median(v)),
            analytic_lower=a_lo,
            analytic_upper=a_hi,
            analytic_std=float(np.std(v, ddof=1)) if v.size > 1 else 0.0,
            struct_lower=s_lo,
            struct_upper=s_hi,
            struct_typical_width=float(np.median(w_arr)) if w_arr.size else 0.0,
            total_lower=t_lo,
            total_upper=t_hi,
            open_lower=o_lo,
            open_upper=o_hi,
            note=note,
        )
        if res.apparent_uniqueness_risk:
            res.warning = AVERTISSEMENT_SOMMET
        resultats.append(res)

    return UncertaintyReport(
        results=resultats,
        n_draws=config.n_draws - echecs,
        n_failed=echecs,
        n_structural_conflicts=conflits,
        degeneracy=int(len(keys) - np.linalg.matrix_rank(A)),
        config=config,
        meta={
            "closure": centrale.closure,
            "central": centrale,
            "scenarios": _scenarios_elements_non_doses(
                centrale.x, N, functionals, keys, els, extra
            ),
            "structural": structural,
            "structural_journal": journal_struct,
        },
    )


def _scenarios_elements_non_doses(
    x0: np.ndarray,
    N: np.ndarray,
    functionals: list[Functional],
    phase_keys: list[str],
    elements: list[str],
    extra: tuple[np.ndarray, np.ndarray] | None = None,
) -> list[ElementScenario]:
    """
    Pour chaque element du modele absent du bulletin, ce qu'un dosage
    apporterait.

    En pratique il n'y en a qu'un, l'oxygene : il n'est presque jamais dose
    en analyse de routine, et une valeur obtenue par difference ne porte
    aucune information independante. Le calcul principal tourne donc sans
    lui - c'est la bonne decision - et ce scenario chiffre ce que le client
    gagnerait a le faire doser, au lieu de le laisser deviner.

    Le balayage est restreint a SCENARIO_ELEMENTS. Lever formellement un
    degre de liberte ne suffit pas : encore faut-il qu'un laboratoire puisse
    en tirer une information utilisable. Voir la note de cette constante.

    Rien ici n'entre dans le resultat principal. Le scenario est une
    PROJECTION SOUS HYPOTHESE, et le rapport doit le dire.
    """
    absents = [el for el in ELEMENTS
               if el not in elements and el in SCENARIO_ELEMENTS]
    if not absents or N.size == 0:
        return []

    A_complet, els_complet, keys_complet = stoichiometry_matrix(
        phase_keys=phase_keys, elements=list(ELEMENTS)
    )
    out: list[ElementScenario] = []
    for el in absents:
        c_el = A_complet[els_complet.index(el)]
        try:
            s = element_scenario(x0, N, functionals, c_el, el, extra=extra)
        except UnboundedCompatibleSet:
            continue
        if s is not None:
            out.append(s)
    return out