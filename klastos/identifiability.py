"""
KLASTOS21 - Analyse d'identifiabilite.

Coeur de la promesse produit : ne jamais afficher un chiffre que la donnee
d'entree ne permet pas de determiner.

Principe
--------
Le systeme A @ x = b peut etre rang-deficient. Soit N une base orthonormee
de l'espace nul de A. Toute solution x0 admet une famille de solutions
strictement indiscernables par analyse elementaire :

    X(x0) = { x0 + N t  |  t reel,  x >= 0,  somme(x) <= 1 }

Une fonctionnelle scalaire f(x) = c @ x est IDENTIFIABLE si et seulement si
c est orthogonal a l'espace nul :  N.T @ c = 0.
Sinon, on borne c @ x sur X(x0) par programmation lineaire et l'on rapporte
un DOMAINE COMPATIBLE au lieu d'un point.

Aucune grandeur n'est declaree ferme a priori : le caractere ferme de
"Cathodes totales" et du bloc "NMC + LCO" est CALCULE, pas suppose.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.linalg import null_space as _scipy_null_space
from scipy.optimize import linprog
from scipy.special import ndtri as _ndtri

from . import i18n
from .elements import ELEMENTS
from .phases import (GROUP_NMC, PHASES, cathode_indicator, indicator,
                     nmc_lco_indicator, phase_label, stoichiometry_matrix)

# Mention normalisee, reprise telle quelle dans le rapport client.
def _fragment(cle: str) -> str:
    """
    Un fragment de phrase, derive du catalogue i18n.

    Ces deux notes existaient ici en clair, sans accents, et le rapport
    les posait avec `.capitalize()`. Depuis que le livrable est bilingue,
    le texte de reference vit au catalogue : le deriver evite d'avoir
    deux ecritures du meme engagement, qui finiraient par diverger.

    On rend la forme fragment - minuscule initiale, sans point final -
    parce que c'est sous cette forme que les appelants la composent.
    """
    texte = i18n.t(cle, "fr").rstrip(".")
    return texte[:1].lower() + texte[1:]


NOTE_NON_IDENTIFIABLE = _fragment("rapport.note.non_identifiable")

NOTE_CARBONE = _fragment("rapport.note.carbone")

# Tolerance d'orthogonalite. A 1e-9, une composante residuelle de l'ordre de
# l'erreur d'arrondi machine (~1e-16) est bien classee comme nulle.
TOL_ORTHO = 1e-9


# ==========================================================================
# Structures
# ==========================================================================

@dataclass(frozen=True)
class Functional:
    """Une grandeur scalaire c @ x que le rapport doit afficher."""

    key: str
    label: str
    c: np.ndarray
    block: str = "autre"        # "ferme_attendu" | "phase" | "ventilation"
    unit: str = "%"
    note: str = ""


@dataclass
class FunctionalResult:
    """Resultat d'evaluation d'une fonctionnelle sur un lot."""

    key: str
    label: str
    block: str
    identifiable: bool
    value: float | None = None      # renseigne si et seulement si identifiable
    lower: float | None = None      # borne inf du domaine compatible
    upper: float | None = None      # borne sup du domaine compatible
    unit: str = "%"
    note: str = ""

    @property
    def width(self) -> float | None:
        """Largeur du domaine compatible, 0.0 si ferme."""
        if self.identifiable:
            return 0.0
        if self.lower is None or self.upper is None:
            return None
        return self.upper - self.lower

    def format_value(self, scale: float = 100.0, decimals: int = 2) -> str:
        if self.identifiable and self.value is not None:
            return f"{self.value * scale:.{decimals}f} {self.unit}"
        if self.lower is not None and self.upper is not None:
            return (
                f"{self.lower * scale:.{decimals}f} \u2013 "
                f"{self.upper * scale:.{decimals}f} {self.unit}"
            )
        return "indetermine"


@dataclass
class IdentifiabilityAnalysis:
    """Diagnostic complet du systeme pour une liste de phases donnee."""

    n_phases: int
    rank: int
    degeneracy: int
    null_directions: list[dict] = field(default_factory=list)

    @property
    def is_well_posed(self) -> bool:
        return self.degeneracy == 0

    def summary(self) -> str:
        if self.is_well_posed:
            return (
                f"Systeme bien pose : {self.n_phases} phases, rang {self.rank}. "
                "Toutes les fractions de phases sont determinees."
            )
        return (
            f"Systeme degenere : {self.n_phases} phases, rang {self.rank}, "
            f"{self.degeneracy} degre(s) de liberte non contraint(s) par "
            "l'analyse elementaire."
        )


# ==========================================================================
# Algebre
# ==========================================================================

def null_space(A: np.ndarray, rcond: float | None = None) -> np.ndarray:
    """Base orthonormee de l'espace nul de A. Colonnes = directions nulles."""
    return _scipy_null_space(A, rcond=rcond)


def degeneracy_dimension(A: np.ndarray) -> int:
    """Nombre de degres de liberte non contraints par l'analyse elementaire."""
    return int(A.shape[1] - np.linalg.matrix_rank(A))


def is_identifiable(c: np.ndarray, N: np.ndarray, tol: float = TOL_ORTHO) -> bool:
    """c @ x est-il constant sur l'ensemble des solutions equivalentes ?"""
    if N.size == 0:
        return True
    return bool(np.all(np.abs(N.T @ c) < tol))


class UnboundedCompatibleSet(RuntimeError):
    """Le domaine compatible n'a pas pu etre borne. C'est un bug, pas un resultat."""


def compatible_bounds(
    x0: np.ndarray,
    N: np.ndarray,
    c: np.ndarray,
    total_mass_cap: float | None = None,
    tol: float = 1e-12,
    extra: tuple[np.ndarray, np.ndarray] | None = None,
) -> tuple[float, float]:
    """
    Bornes de c @ x sur { x = x0 + N t, x >= 0 }.

    LE PLAFOND DE MASSE N'EST PLUS DEMANDE PAR DEFAUT, et c'est un
    correctif.

    Les phases ne peuvent pas peser plus que l'echantillon, d'ou un
    plafond a 1. Mais le representant retenu par le solveur peut, lui,
    depasser 1 - c'est le sur-bouclage. Le plafond se relevait donc a
    max(1, somme(x0)) « pour ne jamais exclure x0 lui-meme », et le
    domaine PUBLIE se mettait a dependre du sommet ou NNLS avait atterri.
    Mesure sur deux representants egalement valides du meme bulletin :

        somme 101,3833 %   « Cathodes totales » [40,000 ; 43,116]
        somme 100,0000 %   « Cathodes totales » [40,000 ; 40,000]

    Meme analyse, deux reponses.

    Le relever a la masse minimale atteignable rendait bien le domaine
    invariant, mais au prix d'un plafond DUR a 1 : combine a un
    ajustement exact, il sur-determine le systeme, reduit le domaine a un
    point sur tout lot qui boucle bien, et rend infaisables les scenarios
    de conseil. Essaye, mesure, abandonne.

    La contrainte physique n'a pas disparu pour autant : elle est portee
    par le POLYTOPE ROBUSTE, qui produit l'intervalle publie et n'a aucun
    ancrage. Ici, ou l'on decrit l'indetermination a bulletin donne, la
    retirer rend le domaine invariant SANS le degenerer - et la largeur
    obtenue est celle que l'outil rendait deja dans le cas courant.

    Un appelant peut toujours en poser un ; il accepte alors que le
    domaine puisse devenir infaisable.

    Deux programmes lineaires en t. Retourne (min, max).

    Deux precautions imposees par l'experience :

    1. Le domaine compatible est defini RELATIVEMENT a x0, donc x0 doit
       toujours y appartenir. Si x0 depasse deja le plafond de masse - ce
       qui arrive des que le bulletin est bruite et que le solveur sort a
       100,3 % - on releve le plafond plutot que de rendre le probleme
       infaisable.

    2. Les directions nulles sommant a zero a la precision machine, la ligne
       de contrainte de masse est numeriquement nulle. On l'ecarte alors :
       elle ne porte aucune information sur t et ne fait que fragiliser le
       solveur lineaire.

    Une infaisabilite residuelle est levee en exception : renvoyer un
    intervalle infini reviendrait a afficher au client une incertitude
    fausse au lieu de signaler une anomalie.

    `extra` : couple (G, h) d'inegalites supplementaires G @ x <= h, par
    exemple celles produites par une quantification structurale. Elles
    RETRECISSENT le domaine sans toucher a l'espace nul : une grandeur non
    identifiable le reste, sa plage se resserre.
    """
    return _bounds_on_domain(x0, N, c, None, None, total_mass_cap, tol, extra)


def _domain_constraints(
    x0: np.ndarray,
    N: np.ndarray,
    total_mass_cap: float | None,
    tol: float,
    extra: tuple[np.ndarray, np.ndarray] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Inegalites decrivant { t : x0 + N t >= 0, somme <= plafond, G x <= h }.

    POINT DE PASSAGE UNIQUE. Toute contrainte de domaine entre ici et nulle
    part ailleurs, faute de quoi une largeur conditionnelle ne serait plus
    comparable a une largeur ouverte.
    """
    k = N.shape[1]
    A_ub = [-N]                              # x >= 0  <=>  -N t <= x0
    b_ub = [x0.copy()]

    if total_mass_cap is not None:
        row = N.sum(axis=0)
        if float(np.max(np.abs(row))) > tol:
            # LE PLAFOND EST DUR. Il se relevait autrefois a
            # max(1, somme(x0)), « pour ne jamais exclure x0 lui-meme » -
            # et c'est ce qui rendait le domaine dependant du SOMMET ou
            # NNLS avait atterri.
            #
            # Il n'est plus demande par defaut : voir le commentaire de
            # `compatible_bounds`. Un appelant qui en pose un accepte que
            # le domaine puisse devenir infaisable, ce qui se signale.
            A_ub.append(row.reshape(1, k))
            b_ub.append(np.array([float(total_mass_cap) - float(np.sum(x0))]))

    if extra is not None:
        G, h = extra
        G = np.atleast_2d(np.asarray(G, dtype=float))
        h = np.asarray(h, dtype=float).ravel()
        if G.size:
            if G.shape[1] != x0.shape[0] or G.shape[0] != h.shape[0]:
                raise ValueError(
                    f"Contraintes supplementaires mal formees : G {G.shape}, "
                    f"h {h.shape}, {x0.shape[0]} phases attendues."
                )
            # G (x0 + N t) <= h  <=>  (G N) t <= h - G x0
            A_ub.append(G @ N)
            b_ub.append(h - G @ x0)

    return np.vstack(A_ub), np.concatenate(b_ub)


def _bounds_on_domain(
    x0: np.ndarray,
    N: np.ndarray,
    c: np.ndarray,
    c_cond: np.ndarray | None,
    value: float | None,
    total_mass_cap: float | None,
    tol: float,
    extra: tuple[np.ndarray, np.ndarray] | None = None,
) -> tuple[float, float]:
    """
    Bornes de c @ x sur le domaine compatible, eventuellement restreint par
    l'egalite c_cond @ x = value.

    C'est le moteur commun de `compatible_bounds` (sans restriction) et de
    `conditional_bounds` (avec). Les deux doivent poser EXACTEMENT les memes
    contraintes de domaine, sans quoi une largeur conditionnelle ne serait
    pas comparable a la largeur ouverte.
    """
    if N.size == 0:
        v = float(c @ x0)
        return v, v

    x0 = np.asarray(x0, dtype=float)
    k = N.shape[1]
    obj = N.T @ c
    const = float(c @ x0)
    A_ub_m, b_ub_m = _domain_constraints(x0, N, total_mass_cap, tol, extra)

    A_eq = b_eq = None
    if c_cond is not None:
        if not np.isfinite(value):
            raise UnboundedCompatibleSet(
                f"Valeur de conditionnement non finie ({value}). "
                "Un programme lineaire ne s'ecrit pas sur un NaN."
            )
        A_eq = (np.asarray(c_cond, dtype=float) @ N).reshape(1, k)
        b_eq = np.array([float(value) - float(c_cond @ x0)])

    bounds = [(None, None)] * k
    lo = linprog(obj, A_ub=A_ub_m, b_ub=b_ub_m, A_eq=A_eq, b_eq=b_eq,
                 bounds=bounds, method="highs")
    hi = linprog(-obj, A_ub=A_ub_m, b_ub=b_ub_m, A_eq=A_eq, b_eq=b_eq,
                 bounds=bounds, method="highs")

    if not lo.success or not hi.success:
        raise UnboundedCompatibleSet(
            "Domaine compatible non borne ou infaisable "
            f"(statuts : min={lo.status}, max={hi.status}). "
            "Verifier la matrice de stoechiometrie et la solution fournie."
        )

    lower = const + float(obj @ lo.x)
    upper = const + float(obj @ hi.x)
    if lower > upper:                       # garde-fou numerique
        lower, upper = upper, lower
    return lower, upper



# ==========================================================================
# Enveloppe robuste
# ==========================================================================
#
# POURQUOI CETTE ROUTE EXISTE, ET CE QU'ELLE REMPLACE
# ---------------------------------------------------
# L'enveloppe publiee pour une grandeur non identifiable etait l'UNION,
# sur une soixantaine de tirages du bulletin, des domaines compatibles
# de chaque tirage. Deux defauts mesures :
#
#   - ELLE NE CONVERGE PAS. De 120 a 240 tirages, la largeur mediane
#     croit encore de 10,5 % et la pire de 120 %. Au reglage de 60,
#     certaines grandeurs etaient jusqu'a 20 % trop ETROITES - dans la
#     direction dangereuse. Le chiffre publie dependait donc d'un
#     reglage, et la docstring promettait une garantie qui n'existait
#     pas.
#
#   - ELLE COUTAIT L'ESSENTIEL DU TEMPS. Deux programmes lineaires par
#     grandeur ET PAR TIRAGE, soit pres de 1 800 pour un lot.
#
# Un min/max sur echantillon n'est pas un estimateur stable : il
# s'elargit mecaniquement avec le nombre de tirages. Ce module le
# documentait deja pour les grandeurs fermes, qui retiennent un
# percentile pour cette raison exacte. L'argument « le domaine est un
# ensemble mathematique, pas un echantillon » vaut pour le domaine d'UN
# tirage ; leur UNION sur les tirages reste un extremum d'echantillon.
#
# LA FORMULATION
# --------------
# On remplace l'union de domaines exacts par UN SEUL polytope, qui dit
# directement ce que l'enveloppe cherchait a dire :
#
#     { x : x >= 0, somme(x) <= 1, | W (A x - b) | <= k }   avec W = 1/sigma
#
# soit « tous les melanges de phases dont le bulletin predit tombe a
# moins de k ecarts-types de celui qu'on a mesure ». Aucun tirage, deux
# programmes lineaires par grandeur en tout, et un resultat EXACT : deux
# executions donnent le meme chiffre.
#
# Mesure sur un lot NMC811 : 0,10 s contre 5,6 s, 52 programmes lineaires
# contre 1 800.
#
# LE RAYON
# --------
# `k` n'est pas un reglage libre : c'est le rayon d'une boite de
# confiance CONJOINTE sur les elements doses, calcule et non arbitre.
# Une boite a 90 % par element couvrirait 0,9^10 = 35 % conjointement
# sur dix elements, ce qui serait bien trop optimiste. On resout donc
# pour le niveau par element qui donne la couverture conjointe visee.
#
#     dix elements    k = 2,56        douze elements   k = 2,62
#
# Calibre contre l'ancienne methode poussee a 240 tirages : a k = 2,56
# le polytope contient 13 des 15 enveloppes echantillonnees, a k = 3 il
# les contient toutes. La largeur mediane passe de 4,1 a 7,6 points -
# ce n'est pas un cout de la methode, c'est la taille honnete de
# l'ensemble compatible, que l'echantillonnage sous-estimait.

#: Couverture CONJOINTE visee par la boite de confiance. Arbitree, et
#: alignee sur les percentiles 5 / 95 deja retenus ailleurs dans le
#: projet pour les grandeurs fermes.
COUVERTURE_ROBUSTE = 0.90


def rayon_robuste(n_elements: int, couverture: float = COUVERTURE_ROBUSTE) -> float:
    """
    Demi-largeur de la boite de confiance, en ecarts-types.

    CALCULE, JAMAIS CODE EN DUR. Le rayon depend du nombre d'elements
    doses : un bulletin a dix elements et un bulletin a douze n'ont pas
    la meme boite pour une meme couverture conjointe. Figer 2,56
    rendrait le second trop optimiste.
    """
    if n_elements <= 0:
        raise ValueError("Une boite de confiance a besoin d'au moins un element.")
    if not 0.0 < couverture < 1.0:
        raise ValueError(f"Couverture hors de ]0 ; 1[ : {couverture}")
    par_element = couverture ** (1.0 / n_elements)
    return float(_ndtri(0.5 + par_element / 2.0))


def contraintes_robustes(
    A: np.ndarray,
    b: np.ndarray,
    sigma: np.ndarray,
    k: float,
    total_mass_cap: float | None = 1.0,
    extra: tuple[np.ndarray, np.ndarray] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Inegalites du polytope robuste, en variable x et non en coordonnee nulle.

    POINT DE PASSAGE UNIQUE, au meme titre que `_domain_constraints`.
    Toute contrainte de domaine robuste entre ici et nulle part ailleurs.

    La contrainte structurale `extra` s'exprime deja en x - elle n'a donc
    pas besoin d'etre projetee, contrairement a la route par espace nul.
    """
    sigma = np.maximum(np.asarray(sigma, dtype=float), 1e-12)
    W_A = A / sigma[:, None]
    W_b = np.asarray(b, dtype=float) / sigma

    blocs = [W_A, -W_A]
    seconds = [W_b + k, -W_b + k]

    if total_mass_cap is not None:
        blocs.append(np.ones((1, A.shape[1])))
        seconds.append(np.array([float(total_mass_cap)]))

    if extra is not None:
        G, h = extra
        G = np.atleast_2d(np.asarray(G, dtype=float))
        h = np.asarray(h, dtype=float).ravel()
        if G.size:
            if G.shape[1] != A.shape[1] or G.shape[0] != h.shape[0]:
                raise ValueError(
                    f"Contraintes supplementaires mal formees : G {G.shape}, "
                    f"h {h.shape}, {A.shape[1]} phases attendues."
                )
            blocs.append(G)
            seconds.append(h)

    return np.vstack(blocs), np.concatenate(seconds)


def rayon_minimal(
    A: np.ndarray,
    b: np.ndarray,
    sigma: np.ndarray,
    total_mass_cap: float | None = 1.0,
    extra: tuple[np.ndarray, np.ndarray] | None = None,
) -> float:
    """
    Plus petit rayon qui rende le polytope robuste non vide.

    POURQUOI CETTE FONCTION EXISTE. Le polytope peut etre VIDE : si aucun
    melange de phases positives ne reproduit le bulletin a k ecarts-types
    pres, c'est que le modele ne sait pas expliquer ce lot. C'est un
    resultat, pas une panne - c'est le constat du garde-fou d'adequation,
    exprime geometriquement - mais il ne doit pas faire echouer le calcul
    avant que le rapport ait pu refuser proprement.

    Le rayon minimal se lit donc comme une mesure : « il a fallu admettre
    4,2 ecarts-types d'erreur analytique pour que le modele explique ce
    bulletin ». Au-dela du rayon vise, la lecture est sans appel.

    Un seul programme lineaire, sur (x, t) :

        minimiser t  sous  | W (A x - b) | <= t,  x >= 0,  somme(x) <= cap
    """
    sigma = np.maximum(np.asarray(sigma, dtype=float), 1e-12)
    W_A = A / sigma[:, None]
    W_b = np.asarray(b, dtype=float) / sigma
    n = A.shape[1]
    m = A.shape[0]

    # Variables : les n phases, puis t.
    un = np.ones((m, 1))
    blocs = [np.hstack([W_A, -un]), np.hstack([-W_A, -un])]
    seconds = [W_b, -W_b]

    if total_mass_cap is not None:
        blocs.append(np.hstack([np.ones((1, n)), np.zeros((1, 1))]))
        seconds.append(np.array([float(total_mass_cap)]))

    if extra is not None:
        G, h = extra
        G = np.atleast_2d(np.asarray(G, dtype=float))
        h = np.asarray(h, dtype=float).ravel()
        if G.size:
            blocs.append(np.hstack([G, np.zeros((G.shape[0], 1))]))
            seconds.append(h)

    objectif = np.zeros(n + 1)
    objectif[-1] = 1.0
    res = linprog(objectif, A_ub=np.vstack(blocs),
                  b_ub=np.concatenate(seconds),
                  bounds=[(0.0, None)] * n + [(0.0, None)])
    if not res.success:
        raise UnboundedCompatibleSet(
            "Aucun melange de phases positives ne reproduit ce bulletin, "
            f"a quelque tolerance que ce soit : {res.message}"
        )
    return float(res.x[-1])


def bornes_robustes(
    A: np.ndarray,
    b: np.ndarray,
    sigma: np.ndarray,
    c: np.ndarray,
    k: float | None = None,
    total_mass_cap: float | None = 1.0,
    extra: tuple[np.ndarray, np.ndarray] | None = None,
) -> tuple[float, float]:
    """
    Bornes de `c @ x` sur le polytope robuste. Deux programmes lineaires.

    Remplace l'enveloppe par tirages pour les grandeurs non
    identifiables. Le resultat est EXACT et reproductible : il ne depend
    ni d'une graine, ni d'un nombre de tirages.

    Leve `UnboundedCompatibleSet` si le polytope est vide ou non borne.
    Un domaine qu'on ne sait pas borner est un bug, pas un resultat - la
    meme regle que sur la route par espace nul.
    """
    if k is None:
        k = rayon_robuste(A.shape[0])
    A_ub, b_ub = contraintes_robustes(A, b, sigma, k, total_mass_cap, extra)
    bornes = [(0.0, None)] * A.shape[1]

    bas = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bornes)
    haut = linprog(-np.asarray(c, dtype=float), A_ub=A_ub, b_ub=b_ub,
                   bounds=bornes)
    if not (bas.success and haut.success):
        raise UnboundedCompatibleSet(
            "Le polytope robuste n'a pas pu etre borne : "
            f"{bas.message if not bas.success else haut.message}"
        )
    return float(bas.fun), float(-haut.fun)

def conditional_bounds(
    x0: np.ndarray,
    N: np.ndarray,
    c: np.ndarray,
    c_cond: np.ndarray,
    value: float,
    total_mass_cap: float | None = None,
    tol: float = 1e-12,
    extra: tuple[np.ndarray, np.ndarray] | None = None,
) -> tuple[float, float]:
    """
    Bornes de c @ x sur le domaine compatible, SACHANT c_cond @ x = value.

    Sert a repondre a une question precise : que deviendrait cette grandeur
    si l'on dosait un element aujourd'hui non dose ?

    AVERTISSEMENT METHODOLOGIQUE. Le resultat depend entierement de `value`,
    qui est une HYPOTHESE. Y injecter la valeur predite par la reconstitution
    elle-meme n'apporte aucune information : la grandeur ressort alors
    exactement determinee, d'une precision qui n'est qu'un artefact du point
    retenu par le solveur. C'est le piege du sommet, dans sa forme la plus
    pure. Le scenario doit donc toujours balayer la plage compatible de
    `value`, jamais se poser sur un point.
    """
    return _bounds_on_domain(x0, N, c, c_cond, value, total_mass_cap, tol, extra)


def describe_null_directions(
    A: np.ndarray,
    phase_keys: list[str],
    tol: float = 1e-8,
) -> list[dict]:
    """
    Rend les directions nulles lisibles : quelles phases s'echangent, et
    dans quelles proportions. Normalise sur la composante dominante.
    """
    N = null_space(A)
    out: list[dict] = []
    for j in range(N.shape[1]):
        v = N[:, j]
        v = v / v[int(np.argmax(np.abs(v)))]
        coeffs = {
            phase_keys[i]: float(v[i]) for i in range(len(v)) if abs(v[i]) > tol
        }
        out.append(
            {
                "direction": j,
                "coefficients": coeffs,
                "somme": float(sum(coeffs.values())),
            }
        )
    return out


def analyse(A: np.ndarray, phase_keys: list[str]) -> IdentifiabilityAnalysis:
    """Diagnostic du systeme, independamment de tout lot."""
    return IdentifiabilityAnalysis(
        n_phases=A.shape[1],
        rank=int(np.linalg.matrix_rank(A)),
        degeneracy=degeneracy_dimension(A),
        null_directions=describe_null_directions(A, phase_keys),
    )


# ==========================================================================
# Jeu de fonctionnelles du rapport (decisions 1, 3 et 4)
# ==========================================================================

def standard_functionals(
    phase_keys: list[str],
    elements: list[str] | None = None,
) -> list[Functional]:
    """
    Construit les grandeurs affichees par le rapport client.

    Bloc "ferme_attendu" : agregats et teneurs elementaires. Ce sont les
        grandeurs sur lesquelles repose la valorisation du lot.
    Bloc "phase" : phases individuelles hors famille degeneree.
    Bloc "ventilation" : grades NMC et LCO, dont l'identifiabilite depend
        de la provenance declaree.

    Le caractere ferme n'est PAS suppose ici : il est calcule par evaluate().
    """
    elements = list(ELEMENTS) if elements is None else list(elements)
    A, els, keys = stoichiometry_matrix(phase_keys=phase_keys, elements=elements)
    fs: list[Functional] = []

    # --- Agregats de masse -------------------------------------------------
    fs.append(
        Functional(
            key="cathodes_totales",
            label="Cathodes totales",
            c=cathode_indicator(phase_keys=keys),
            block="ferme_attendu",
        )
    )
    nmc_present = [k for k in keys if PHASES[k]["group"] == GROUP_NMC]
    if nmc_present and "LCO" in keys:
        fs.append(
            Functional(
                key="nmc_lco",
                label="Bloc NMC + LCO",
                c=nmc_lco_indicator(phase_keys=keys),
                block="ferme_attendu",
            )
        )
    elif nmc_present:
        fs.append(
            Functional(
                key="nmc_total",
                label="NMC total",
                c=indicator(nmc_present, phase_keys=keys),
                block="ferme_attendu",
            )
        )

    # --- Teneurs elementaires : base de la valorisation --------------------
    for el in ["Li", "Ni", "Co", "Mn", "Fe", "Cu", "Al", "P", "F", "C"]:
        if el not in els:
            continue
        row = A[els.index(el)]
        if not np.any(row > 0):
            continue
        fs.append(
            Functional(
                key=f"el_{el}",
                label=f"{el} total",
                c=row,
                block="ferme_attendu",
            )
        )

    # --- Phases hors famille degeneree ------------------------------------
    degeneree = set(nmc_present) | {"LCO"}
    for pk in keys:
        if pk in degeneree:
            continue
        c = indicator([pk], phase_keys=keys)
        fs.append(
            Functional(
                key=pk,
                label=phase_label(pk),
                c=c,
                block="phase",
                note=NOTE_CARBONE if pk == "C_total" else "",
            )
        )

    # --- Ventilation par grade --------------------------------------------
    for pk in keys:
        if pk not in degeneree:
            continue
        fs.append(
            Functional(
                key=pk,
                label=phase_label(pk),
                c=indicator([pk], phase_keys=keys),
                block="ventilation",
            )
        )

    return fs


# ==========================================================================
# Evaluation
# ==========================================================================

def evaluate(
    x0: np.ndarray,
    A: np.ndarray,
    functionals: list[Functional],
    total_mass_cap: float | None = None,
    tol: float = TOL_ORTHO,
    extra: tuple[np.ndarray, np.ndarray] | None = None,
) -> list[FunctionalResult]:
    """
    Evalue chaque fonctionnelle sur la solution x0, en distinguant les
    grandeurs fermes des grandeurs bornees.

    `extra` resserre les plages compatibles sans changer l'identifiabilite :
    une contrainte d'inegalite borne une direction nulle, elle ne la
    supprime pas. C'est tout l'effet d'une quantification structurale
    reelle, dont l'incertitude n'est jamais nulle.
    """
    x0 = np.asarray(x0, dtype=float)
    if x0.shape[0] != A.shape[1]:
        raise ValueError(
            f"x0 a {x0.shape[0]} composantes, la matrice en attend {A.shape[1]}."
        )

    N = null_space(A)
    results: list[FunctionalResult] = []
    for f in functionals:
        if f.c.shape[0] != A.shape[1]:
            raise ValueError(
                f"Fonctionnelle {f.key!r} : dimension {f.c.shape[0]} "
                f"incompatible avec {A.shape[1]} phases."
            )
        if is_identifiable(f.c, N, tol=tol):
            results.append(
                FunctionalResult(
                    key=f.key,
                    label=f.label,
                    block=f.block,
                    identifiable=True,
                    value=float(f.c @ x0),
                    unit=f.unit,
                    note=f.note,
                )
            )
        else:
            lo, hi = compatible_bounds(x0, N, f.c,
                                       total_mass_cap=total_mass_cap,
                                       extra=extra)
            note = f.note or NOTE_NON_IDENTIFIABLE
            if f.note:
                note = f"{f.note} ; {NOTE_NON_IDENTIFIABLE}"
            results.append(
                FunctionalResult(
                    key=f.key,
                    label=f.label,
                    block=f.block,
                    identifiable=False,
                    lower=lo,
                    upper=hi,
                    unit=f.unit,
                    note=note,
                )
            )
    return results


# ==========================================================================
# Scenario : "et si l'on dosait cet element ?"
# ==========================================================================
#
# L'oxygene n'est presque jamais dose en analyse de routine de black mass :
# le dosage par fusion sous gaz inerte est un essai a part, rarement demande,
# et une valeur "oxygene" obtenue par difference ne vaut rien ici puisqu'elle
# ne porte aucune information independante.
#
# Le calcul principal tourne donc SANS oxygene, et c'est la bonne decision.
# Reste une question legitime du client : qu'est-ce que je gagnerais a le
# faire doser ? Ce bloc y repond sans jamais inventer de chiffre.

#: En deca de cette largeur, la plage compatible d'un element est trop
#: etroite pour qu'un scenario ait un sens : le doser ne changerait rien.
SCENARIO_MIN_RANGE = 1e-4          # 0,01 point de masse

#: Largeur en deca de laquelle on considere qu'une grandeur conditionnelle
#: est determinee. Les programmes lineaires rendent 1e-16, pas zero.
SCENARIO_FIRM_WIDTH = 1e-7

#: Elements non doses pour lesquels un scenario de dosage a un SENS METIER.
#:
#: Le critere n'est pas mathematique. Tout element absent du bulletin et non
#: orthogonal a l'espace nul leve formellement un degre de liberte ; cela ne
#: signifie pas qu'un laboratoire puisse en tirer une information utilisable.
#:
#:   O  RETENU. Le dosage par fusion sous gaz inerte existe comme essai a
#:      part, il est demandable, et l'oxygene du modele est bien celui des
#:      oxydes de cathode. Proposer ce dosage au client a un sens.
#:
#:   H  ECARTE. Dans le modele, l'hydrogene n'existe que dans le PVDF. Dans
#:      une black mass reelle, l'hydrogene total est domine par l'humidite
#:      residuelle et les solvants d'electrolyte, que le modele ne porte pas.
#:      Un dosage d'hydrogene total mesurerait donc surtout ce que le modele
#:      ignore, et ne contraindrait pas le PVDF. L'afficher reviendrait a
#:      recommander un essai qui ne repondrait pas a la question posee.
#:
#: NON ARBITRE : cette liste est un choix de modelisation, pas une mesure.
#: Elle sera revue si un client dispose d'un dosage d'hydrogene corrige de
#: l'humidite.
SCENARIO_ELEMENTS: tuple[str, ...] = ("O",)
SCENARIO_ELEMENTS_VALIDATED = False


@dataclass(frozen=True)
class ScenarioRow:
    """Ce qu'un dosage apporterait a UNE grandeur."""

    key: str
    label: str
    width_open: float          # largeur structurale actuelle
    width_conditional: float   # largeur si l'element etait connu exactement
    becomes_firm: bool

    @property
    def gain(self) -> float:
        return max(0.0, self.width_open - self.width_conditional)

    @property
    def gain_fraction(self) -> float:
        return self.gain / self.width_open if self.width_open > 0 else 0.0


@dataclass
class ElementScenario:
    """
    Ce qu'un dosage de `element` apporterait au lot, grandeur par grandeur.

    `value_low` et `value_high` bornent la teneur de l'element SUR LE DOMAINE
    COMPATIBLE : la reconstitution, sans l'avoir dose, contraint deja cet
    element a cette plage. C'est de la que sort le critere decisif.
    """

    element: str
    value_low: float
    value_high: float
    rows: list[ScenarioRow] = field(default_factory=list)

    @property
    def range_width(self) -> float:
        return self.value_high - self.value_low

    @property
    def max_useful_uncertainty(self) -> float:
        """
        Incertitude maximale du dosage au-dela de laquelle il n'apprend rien.

        Demonstration, en deux lignes. Sur le domaine compatible, une grandeur
        que le dosage rend ferme est fonction AFFINE de la teneur dosee : sa
        largeur ouverte vaut |levier| x (plage compatible). Un dosage
        d'incertitude type u ramene cette largeur a |levier| x 2u. Il y a gain
        si et seulement si 2u < plage, soit u < plage / 2.

        Le levier disparait de l'inegalite : le critere est donc le MEME pour
        toutes les grandeurs concernees, et ne depend que de la plage
        compatible de l'element.
        """
        return self.range_width / 2.0

    @property
    def firm_rows(self) -> list[ScenarioRow]:
        return [r for r in self.rows if r.becomes_firm]

    @property
    def useless_rows(self) -> list[ScenarioRow]:
        """Grandeurs auxquelles le dosage n'apporte rien du tout."""
        return [r for r in self.rows if r.gain_fraction < 0.01]

    def summary(self) -> str:
        n = len(self.firm_rows)
        if n:
            return (
                f"Doser {self.element} rendrait {n} grandeur(s) ferme(s), "
                f"a condition que l'incertitude du dosage reste sous "
                f"{self.max_useful_uncertainty * 100:.2f} point."
            )
        return (
            f"Doser {self.element} ne rendrait aucune grandeur ferme : il "
            f"ne leve qu'une partie de la degenerescence."
        )


#: Balayage de la plage compatible : nombre d'intervalles par passe, et
#: nombre de passes de raffinement autour du maximum provisoire.
SCENARIO_SWEEP_STEPS = 8
SCENARIO_SWEEP_PASSES = 5


def _largeur_conditionnelle_maximale(
    x0: np.ndarray,
    N: np.ndarray,
    c: np.ndarray,
    c_element: np.ndarray,
    lo_el: float,
    hi_el: float,
    total_mass_cap: float | None,
    extra: tuple[np.ndarray, np.ndarray] | None = None,
) -> float | None:
    """
    Plus grande largeur de c @ x que le dosage puisse laisser, sur toute la
    plage compatible de l'element.

    POURQUOI PAS TROIS POINTS. Notons w(v) la largeur conditionnelle a
    l'element dose a v. Le maximum d'une forme lineaire sur un polytope est
    concave en son second membre, le minimum est convexe : leur difference
    w(v) est donc CONCAVE. Le maximum d'une fonction concave est
    generiquement INTERIEUR, et un balayage limite aux extremites et au
    milieu le manque.

    La sous-estimation va dans le sens optimiste - elle fait croire que le
    dosage apporte plus qu'il n'apporte - ce qui est exactement le biais
    qu'un rapport commercial ne doit pas avoir. Mesure sur un lot de
    provenance non declaree, grade NMC 811 : trois points donnent 26,18
    points quand le maximum reel vaut 27,21 points, atteint a 42 % de la
    plage. Un point de masse offert au client.

    La concavite donne aussi la parade. Sur une grille, le maximum reel est
    toujours encadre par les deux voisins du maximum de grille : on balaie
    grossierement, puis on resserre autour de ce maximum. Chaque passe
    divise l'encadrement par SCENARIO_SWEEP_STEPS / 2.

    Rend None si un programme lineaire du balayage est infaisable.
    """
    bas, haut = float(lo_el), float(hi_el)
    meilleur = 0.0

    for _ in range(SCENARIO_SWEEP_PASSES):
        grille = np.linspace(bas, haut, SCENARIO_SWEEP_STEPS + 1)
        largeurs = []
        for v in grille:
            try:
                a, z = conditional_bounds(x0, N, c, c_element, float(v),
                                          extra=extra,
                                          total_mass_cap=total_mass_cap)
            except UnboundedCompatibleSet:
                # v est pose sur le bord exact du domaine ; la tolerance du
                # solveur peut le rejeter. On ignore ce point plutot que de
                # supprimer silencieusement la grandeur entiere.
                largeurs.append(-np.inf)
                continue
            largeurs.append(z - a)

        if not np.isfinite(largeurs).any():
            return None

        i = int(np.argmax(largeurs))
        meilleur = max(meilleur, float(largeurs[i]))
        bas = float(grille[max(0, i - 1)])
        haut = float(grille[min(len(grille) - 1, i + 1)])
        if haut - bas <= 0.0:
            break

    return meilleur


def element_scenario(
    x0: np.ndarray,
    N: np.ndarray,
    functionals: list[Functional],
    c_element: np.ndarray,
    element: str,
    total_mass_cap: float | None = None,
    extra: tuple[np.ndarray, np.ndarray] | None = None,
) -> ElementScenario | None:
    """
    Que deviendrait chaque grandeur si `element` etait dose ?

    Rend None lorsque le dosage n'apporterait rien : soit le systeme est deja
    bien pose, soit la teneur de l'element est orthogonale a l'espace nul -
    auquel cas elle est deja determinee et ne contraint rien de neuf.

    Les largeurs conditionnelles sont prises en BALAYANT la plage compatible
    de l'element, jamais en se posant sur la valeur predite par la
    reconstitution. Voir l'avertissement de `conditional_bounds`, et
    `_largeur_conditionnelle_maximale` pour la facon dont le balayage est
    conduit - trois points n'y suffisent pas.
    """
    if N.size == 0 or N.shape[1] == 0:
        return None
    if float(np.max(np.abs(N.T @ c_element))) <= TOL_ORTHO:
        return None                      # l'element est deja determine

    lo_el, hi_el = compatible_bounds(x0, N, c_element,
                                     total_mass_cap=total_mass_cap,
                                     extra=extra)
    if hi_el - lo_el < SCENARIO_MIN_RANGE:
        return None

    scenario = ElementScenario(element=element, value_low=lo_el,
                               value_high=hi_el)

    for f in functionals:
        if is_identifiable(f.c, N):
            continue                     # deja ferme, rien a gagner

        lo, hi = compatible_bounds(x0, N, f.c, total_mass_cap=total_mass_cap,
                                   extra=extra)

        # Grandeur deja epinglee a largeur nulle par la seule
        # non-negativite - le piege du sommet. Elle n'a RIEN a gagner a un
        # dosage, et l'y faire figurer la declarait "deviendrait ferme"
        # dans la meme section qui la listait parmi les grandeurs auxquelles
        # le dosage n'apporte rien.
        if hi - lo <= SCENARIO_FIRM_WIDTH:
            continue

        largeur_cond = _largeur_conditionnelle_maximale(
            x0, N, f.c, c_element, lo_el, hi_el, total_mass_cap, extra
        )
        if largeur_cond is None:
            continue

        scenario.rows.append(ScenarioRow(
            key=f.key,
            label=f.label,
            width_open=hi - lo,
            width_conditional=min(largeur_cond, hi - lo),
            becomes_firm=largeur_cond < SCENARIO_FIRM_WIDTH,
        ))

    scenario.rows.sort(key=lambda r: (-r.gain, r.key))
    return scenario if scenario.rows else None


# ==========================================================================
# Conseil : "quelle phase ai-je interet a faire quantifier ?"
# ==========================================================================
#
# Le pendant commercial du scenario de dosage, et sans doute la sortie la
# plus utile du logiciel : une quantification par diffraction se paie, et
# toutes les phases ne la valent pas. Mesure sur le lot d'exemple en
# provenance VE attestee, a 2 points d'incertitude : le NMC622 retire 72 %
# de la largeur cumulee, le fer metallique 0 %.
#
# DEUX PRECAUTIONS, TIREES DE LA SEANCE 14.
#
# 1. Le gain depend de l'endroit ou tombera la valeur mesuree, qui est
#    inconnue par definition. On BALAIE donc le placement de l'intervalle
#    dans la plage compatible et on retient le PIRE cas. Le conseil se lit
#    alors "au moins tant", jamais "tant" : se poser sur le milieu de la
#    plage donnerait un gain flatteur, et flatteur dans le sens ou le
#    client paie.
#
# 2. Une contrainte d'inegalite ne supprime aucune direction nulle. Aucune
#    phase ne devient donc identifiable, et ce bloc ne promet que du
#    resserrement.

#: Incertitude supposee, a defaut d'indication du laboratoire. Milieu de la
#: fourchette Rietveld courante, 1 a 3 points.
CONSEIL_U_DEFAUT = 0.02

#: Placements testes de l'intervalle dans la plage compatible.
CONSEIL_SWEEP_STEPS = 7

#: En deca de ce gain, quantifier la phase n'achete rien d'exploitable.
CONSEIL_GAIN_MINIMAL = 0.02

#: Plage en deca de laquelle une phase est deja fermee : rien a gagner.
CONSEIL_LARGEUR_MINIMALE = 1e-6


@dataclass(frozen=True)
class ConseilRow:
    """Ce qu'une quantification de cette phase resserrerait, au pire."""

    key: str
    label: str
    width_open: float          # plage compatible actuelle de la phase
    total_after: float         # largeur cumulee apres, pire placement
    gain: float                # fraction de largeur cumulee retiree
    feasible: bool

    @property
    def useful(self) -> bool:
        return self.feasible and self.gain >= CONSEIL_GAIN_MINIMAL


@dataclass
class ConseilQuantification:
    """Classement des phases par ce que leur quantification rapporterait."""

    uncertainty: float
    total_before: float
    rows: list[ConseilRow] = field(default_factory=list)
    journal: list[str] = field(default_factory=list)

    @property
    def best(self) -> ConseilRow | None:
        return self.rows[0] if self.rows and self.rows[0].useful else None

    @property
    def useless(self) -> list[ConseilRow]:
        return [r for r in self.rows if not r.useful]

    def resume(self) -> str:
        if not self.rows:
            return ("Aucune phase ouverte : une quantification structurale "
                    "n'apporterait rien sur ce lot.")
        b = self.best
        if b is None:
            return (f"A {self.uncertainty * 100:.1f} point(s) d'incertitude, "
                    "aucune quantification ne resserre utilement ce lot.")
        return (f"{b.label} : au moins {b.gain * 100:.0f} % de largeur "
                f"cumulee en moins pour une quantification a "
                f"{self.uncertainty * 100:.1f} point(s).")


def _largeur_cumulee(
    x0: np.ndarray,
    N: np.ndarray,
    n_phases: int,
    total_mass_cap: float | None,
    extra: tuple[np.ndarray, np.ndarray] | None,
) -> float | None:
    """Somme des plages compatibles des phases. None si infaisable."""
    total = 0.0
    for j in range(n_phases):
        c = np.zeros(n_phases, dtype=float)
        c[j] = 1.0
        try:
            lo, hi = compatible_bounds(x0, N, c, total_mass_cap=total_mass_cap,
                                       extra=extra)
        except UnboundedCompatibleSet:
            return None
        total += hi - lo
    return total


def conseil_quantification(
    x0: np.ndarray,
    A: np.ndarray,
    phase_keys: list[str],
    uncertainty: float = CONSEIL_U_DEFAUT,
    total_mass_cap: float | None = None,
    extra: tuple[np.ndarray, np.ndarray] | None = None,
) -> ConseilQuantification:
    """
    Classe les phases par le resserrement qu'une quantification apporterait.

    Parameters
    ----------
    uncertainty : incertitude absolue supposee sur la mesure, en fraction
        massique. Le gain en depend fortement : c'est un parametre du
        conseil, pas une constante du produit.
    extra : contraintes deja en vigueur. Permet de conseiller la SECONDE
        phase a quantifier quand une premiere l'est deja.

    Returns
    -------
    ConseilQuantification, lignes triees par gain decroissant.
    """
    x0 = np.asarray(x0, dtype=float)
    n = len(phase_keys)
    if x0.shape[0] != n or A.shape[1] != n:
        raise ValueError(
            f"Dimensions incoherentes : x0 {x0.shape[0]}, A {A.shape}, "
            f"{n} phases."
        )
    if not np.isfinite(uncertainty) or uncertainty <= 0.0:
        raise ValueError(
            f"Incertitude supposee invalide ({uncertainty}). Une mesure sans "
            "incertitude ferait passer la DRX pour une verite."
        )

    N = null_space(A)
    conseil = ConseilQuantification(uncertainty=uncertainty, total_before=0.0)

    if N.size == 0 or N.shape[1] == 0:
        conseil.journal.append(
            "Systeme non degenere : toutes les phases sont fermes, une "
            "quantification structurale n'apporterait rien."
        )
        return conseil

    avant = _largeur_cumulee(x0, N, n, total_mass_cap, extra)
    if avant is None:
        raise UnboundedCompatibleSet(
            "Largeur cumulee non calculable sur le domaine de depart."
        )
    conseil.total_before = avant
    conseil.journal.append(
        f"Largeur cumulee des {n} phases : {avant * 100:.2f} points. "
        f"Incertitude supposee : {uncertainty * 100:.2f} point(s)."
    )

    for j, cle in enumerate(phase_keys):
        c = np.zeros(n, dtype=float)
        c[j] = 1.0
        lo, hi = compatible_bounds(x0, N, c, total_mass_cap=total_mass_cap,
                                   extra=extra)
        largeur = hi - lo
        if largeur <= CONSEIL_LARGEUR_MINIMALE:
            continue                      # phase deja fermee

        # BALAYAGE du placement : on retient le pire cas, donc la plus
        # grande largeur restante.
        pire = -np.inf
        faisable = False
        for v in np.linspace(lo, hi, CONSEIL_SWEEP_STEPS):
            G = np.vstack([c, -c])
            h = np.array([v + uncertainty, -max(0.0, v - uncertainty)])
            if extra is not None and np.asarray(extra[0]).size:
                G = np.vstack([np.atleast_2d(extra[0]), G])
                h = np.concatenate([np.asarray(extra[1]).ravel(), h])
            apres = _largeur_cumulee(x0, N, n, total_mass_cap, (G, h))
            if apres is None:
                continue                  # placement incompatible, on passe
            faisable = True
            pire = max(pire, apres)

        if not faisable:
            conseil.rows.append(ConseilRow(
                key=cle, label=phase_label(cle), width_open=largeur,
                total_after=float("nan"), gain=0.0, feasible=False))
            continue

        gain = 0.0 if avant <= 0 else max(0.0, 1.0 - pire / avant)
        conseil.rows.append(ConseilRow(
            key=cle, label=phase_label(cle), width_open=largeur,
            total_after=pire, gain=gain, feasible=True))

    conseil.rows.sort(key=lambda r: (-r.gain, r.key))

    inutiles = [r.key for r in conseil.rows if not r.useful]
    if inutiles:
        conseil.journal.append(
            f"Sans gain exploitable a cette incertitude : "
            f"{', '.join(inutiles)}."
        )
    return conseil


# ==========================================================================
# Repositionnement du representant sous contraintes
# ==========================================================================


def representant_proche(
    x0: np.ndarray,
    N: np.ndarray,
    prior: np.ndarray,
    total_mass_cap: float | None = None,
    tol: float = 1e-12,
) -> np.ndarray:
    """
    Le representant admissible le plus proche du prior, au sens L1.

    POURQUOI CETTE FONCTION A REMPLACE UNE PENALITE.

    Le solveur exprimait le prior comme un terme de penalite ajoute au
    moindre carre : `lambda_null * ||P_N (x - prior)||^2`. Le bloc de
    penalite est EXACTEMENT orthogonal au bloc de donnees - on a mesure
    `||A . P_N|| = 5e-16` - donc, sans contrainte de positivite, le
    probleme se separe et n'importe quel lambda strictement positif
    epinglerait la composante nulle sur le prior.

    Avec `x >= 0`, il n'en va plus ainsi : le poids du bloc de donnees
    vaut 1/sigma, soit 47 a 1764, tandis que celui de la penalite vaut
    sqrt(lambda), soit 0,01 au reglage par defaut. La penalite est cinq
    ordres de grandeur trop faible pour deplacer l'ensemble actif de
    NNLS. Elle n'agit donc que lorsque cet ensemble est deja indifferent.

    Mesure, sur deux lots :

        lot d'essai, douze elements doses, deux directions nulles
            ||P_N x|| = 0,0000   prior deplace de 12,99 points   -> marche
        bulletin reel, dix elements doses, quatre directions nulles
            ||P_N x|| = 0,3014   prior deplace de  0,00 point    -> MORT

    Le parametre n'etait donc pas inerte : il etait SILENCIEUSEMENT
    INOPERANT sur les lots reels, et operant sur ceux des tests. C'est
    pire qu'une panne franche.

    Monter lambda jusqu'a ce qu'il morde n'est pas une issue : a 1e2 le
    residu pondere passe de 0,00 a 1,40, a 1e4 il atteint 9,35. La
    penalite n'achete alors du deplacement qu'en abimant l'ajustement.

    CE QUE FAIT CETTE FONCTION A LA PLACE

    Elle deplace le representant LE LONG DE L'ESPACE NUL, donc sans
    toucher a aucune grandeur identifiable, puisque `A @ (N t) = 0` par
    construction. L'ajustement est intact par definition, et le
    representant atteint exactement le point admissible le plus proche
    du prior. Aucun reglage, aucun compromis.

    La norme L1 est retenue pour la meme raison que dans
    `projeter_dans_domaine`, dont c'est la jumelle : elle se resout par
    un programme lineaire, et elle ne deplace pas plus que necessaire.

    Raises
    ------
    UnboundedCompatibleSet
        Si aucun representant admissible n'existe. C'est un resultat a
        rapporter, pas un bug a contourner.
    """
    x0 = np.asarray(x0, dtype=float)
    prior = np.asarray(prior, dtype=float)
    if prior.shape != x0.shape:
        raise ValueError(
            f"Prior de dimension {prior.shape}, {x0.shape} attendu.")
    if N.size == 0 or N.shape[1] == 0:
        # Systeme bien pose : il n'y a qu'un representant, et le prior
        # n'a rien a dire. Ce n'est pas une erreur.
        return x0.copy()

    k = N.shape[1]
    A_dom, b_dom = _domain_constraints(x0, N, total_mass_cap, tol)

    # Variables : t = tp - tm, puis les ecarts e >= |x - prior|.
    # On minimise 1'e sous  -e <= x0 + N t - prior <= e.
    n = x0.shape[0]
    d = x0 - prior
    zero_dom = np.zeros((A_dom.shape[0], n))
    blocs = [np.hstack([A_dom[:, :k], -A_dom[:, :k], zero_dom])]
    seconds = [b_dom]
    #  N t - e <= prior - x0
    blocs.append(np.hstack([N, -N, -np.eye(n)]))
    seconds.append(-d)
    # -N t - e <= x0 - prior
    blocs.append(np.hstack([-N, N, -np.eye(n)]))
    seconds.append(d)

    objectif = np.concatenate([np.zeros(2 * k), np.ones(n)])
    r = linprog(objectif, A_ub=np.vstack(blocs),
                b_ub=np.concatenate(seconds),
                bounds=[(0.0, None)] * (2 * k + n), method="highs")
    if not r.success:
        raise UnboundedCompatibleSet(
            "Aucun representant admissible ne peut etre rapproche du "
            f"prior : {r.message}"
        )
    t = r.x[:k] - r.x[k:2 * k]
    return x0 + N @ t


def projeter_dans_domaine(
    x0: np.ndarray,
    N: np.ndarray,
    extra: tuple[np.ndarray, np.ndarray],
    total_mass_cap: float | None = None,
    tol: float = 1e-12,
) -> np.ndarray:
    """
    Deplace x0 LE LONG DE L'ESPACE NUL jusqu'a satisfaire G @ x <= h.

    POURQUOI C'EST LICITE, ET MEME NECESSAIRE.

    Le domaine compatible est parametre relativement a x0 : si x0 viole les
    contraintes, les programmes lineaires de `compatible_bounds` sont
    infaisables et le calcul s'arrete. Or x0 n'est pas une estimation, c'est
    un representant arbitraire choisi par le solveur dans la famille des
    solutions equivalentes. Le deplacer dans l'espace nul ne change AUCUNE
    grandeur identifiable, puisque A @ (N t) = 0 par construction.

    Une quantification structurale est donc, pour la valeur ponctuelle, un
    choix de representant - exactement le role que joue deja le `prior` du
    solveur - et, pour les plages, un resserrement du domaine.

    On retient le representant admissible le plus PROCHE au sens L1, pour ne
    pas bouger plus que necessaire.

    Raises
    ------
    UnboundedCompatibleSet
        Si aucun deplacement n'y suffit : la quantification contredit alors
        le bulletin elementaire, et c'est un resultat a rapporter, pas un
        bug a contourner.
    """
    x0 = np.asarray(x0, dtype=float)
    G, h = extra
    G = np.atleast_2d(np.asarray(G, dtype=float))
    h = np.asarray(h, dtype=float).ravel()

    if not G.size:
        return x0.copy()
    if np.all(G @ x0 <= h + tol):
        return x0.copy()                      # deja admissible
    if N.size == 0 or N.shape[1] == 0:
        raise UnboundedCompatibleSet(
            "Quantification structurale incompatible avec le bulletin : le "
            "systeme n'a aucune direction nulle, donc aucun representant "
            "alternatif. Les deux mesures se contredisent."
        )

    k = N.shape[1]
    A_ub, b_ub = _domain_constraints(x0, N, total_mass_cap, tol, (G, h))
    # t = tp - tm, tp, tm >= 0 ; on minimise 1'(tp + tm)
    A2 = np.hstack([A_ub, -A_ub])
    obj = np.ones(2 * k)
    r = linprog(obj, A_ub=A2, b_ub=b_ub,
                bounds=[(0.0, None)] * (2 * k), method="highs")
    if not r.success:
        ecart = float(np.max((G @ x0) - h))
        raise UnboundedCompatibleSet(
            "Quantification structurale incompatible avec le bulletin "
            f"elementaire (depassement maximal {ecart * 100:.2f} point(s) de "
            "masse). Aucune repartition des phases ne satisfait a la fois "
            "l'analyse chimique et la quantification declaree : l'une des "
            "deux mesures est fausse, ou les phases ne sont pas celles du "
            "modele."
        )
    t = r.x[:k] - r.x[k:]
    return x0 + N @ t