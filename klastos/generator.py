"""
KLASTOS21 - Generateur de lots synthetiques.

STATUT : OUTIL DE TEST INTERNE. CE MODULE N'EST PAS UN ORACLE DU REEL.
=====================================================================
Ce generateur sert exclusivement a valider la mecanique du solveur en
l'absence de donnees reelles. Il ne decrit PAS la population reelle des
lots de black mass, et aucune de ses sorties ne doit apparaitre dans un
livrable client, ni servir de reference de composition.

Les bornes de composition sont des HYPOTHESES METIER, non sourcees et non
statistiques. Elles seront revisees a partir de donnees de lots reels.
Engagement de version : la v1.1 integrera les statistiques de composition
observees sur lots reels, en remplacement des bornes actuelles.

Tout lot produit ici porte `meta["data_class"] == "synthetique"`. Les
modules aval (rapport, valorisation) doivent refuser de traiter un lot
portant ce marqueur en mode client.

Fonctionnement
--------------
On tire un melange de phases connu, on calcule le bulletin d'analyse
elementaire par stoechiometrie exacte, on le bruite comme le ferait un
laboratoire, et l'on verifie que le solveur retrouve le melange.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from .elements import ELEMENTS
from .phases import PHASE_KEYS, PHASES, stoichiometry_matrix

# ==========================================================================
# Qualification des donnees produites par ce module
# ==========================================================================

DATA_CLASS = "synthetique"

SYNTHETIC_WARNING = (
    "Donnee synthetique produite par le generateur de test KLASTOS21. "
    "Ne decrit pas un lot reel. Ne doit figurer dans aucun livrable client."
)

REVISION_COMMITMENT = (
    "Les bornes de composition sont des hypotheses metier non sourcees. "
    "Engagement : la v1.1 integrera les statistiques de composition "
    "observees sur lots reels."
)


class SyntheticDataInClientContext(RuntimeError):
    """Levee si une donnee synthetique atteint un contexte client."""


def assert_client_grade(lot: "SyntheticLot") -> None:
    """
    Garde-fou destine aux modules aval (rapport, valorisation).

    A appeler avant tout rendu destine a un client. Leve si le lot provient
    du generateur de test.
    """
    if getattr(lot, "meta", {}).get("data_class") == DATA_CLASS:
        raise SyntheticDataInClientContext(SYNTHETIC_WARNING)


# ==========================================================================
# Modele de bruit analytique
# ==========================================================================

@dataclass(frozen=True)
class NoiseModel:
    """
    Trois effets distincts d'un bulletin de laboratoire :
      1. erreur relative      - fidelite sur les elements majeurs ;
      2. erreur absolue       - bruit de fond sur les mineurs ;
      3. limite de detection  - censure a gauche.

    CALIBRATION DE L'ERREUR RELATIVE
    --------------------------------
    Source : materiau de reference certifie LNE-LiB01, black mass de cellules
    de vehicules electriques, caracterise par digestion micro-ondes et ICP-MS
    avec ajouts doses, valide par comparaison interlaboratoires, certifie
    ISO 33405.
    https://www.lne.fr/en/materiau-reference/lne-lib01-black-mass-lithium-batteries

    Le certificat donne des incertitudes ELARGIES de 10 a 15 % selon
    l'element. Une incertitude elargie a k = 2 vaut deux fois l'incertitude
    type, donc 5 a 7,5 %. On retient le milieu de fourchette.

    Les deux autres parametres restent A VALIDER : le bruit de fond et la
    limite de detection dependent du laboratoire et de la methode. A
    remplacer par ceux des bulletins reels des le premier lot client.
    """

    rel_sigma: float = 0.06      # incertitude type, source LNE-LiB01
    abs_sigma: float = 2e-4      # A VALIDER : 0.02 % massique de bruit de fond
    lod: float = 5e-5            # A VALIDER : 0.005 % massique de limite de detection
    validated: bool = True       # l'erreur relative est sourcee

    rel_sigma_par_element: tuple[tuple[str, float], ...] = ()
    """
    Incertitude relative PAR ELEMENT, en paires (symbole, sigma).

    Vide par defaut, et c'est delibere : le modele reste a 6 % uniformes
    tant que la contradiction entre les deux certificats n'est pas tranchee
    (voir PROTOCOLE.md § 1.3 bis). Un bruit par element est donc un CHOIX
    EXPLICITE de l'appelant, jamais une valeur par defaut.

    Un tuple de paires et non un dictionnaire : la classe est `frozen`, donc
    hashable, et un dictionnaire ne l'est pas.

    ATTENTION. Un bruit plus etroit resserre tous les intervalles, donc le
    prix annonce. C'est la direction DANGEREUSE : une fausse precision sur un
    prix d'achat se paie comptant. Ne resserrer qu'apres arbitrage.

    ET N'Y METTEZ PAS LES RSD DU CERTIFICAT OREAS. La capacite existe, cette
    table-la n'est pas le bon contenu, pour deux raisons mesurees.

    1. L'effet CHANGE DE SIGNE selon la chimie du lot. Sur un lot type NMC
       il resserre l'intervalle de prix de 84 % ; sur un lot riche en LFP il
       elargit l'intervalle de la phase LFP de 125 %. Ce n'est pas un
       reglage, ce sont deux effets opposes.

    2. La table EXTRAPOLE une precision de trace vers une concentration
       majeure. Le RSD de 18,57 % sur le phosphore a ete mesure a 0,350 %,
       pres de la limite de detection. L'appliquer a un lot LFP ou le
       phosphore vaut 8,86 % n'a aucune justification : la precision
       relative s'ameliore avec la concentration, et la correlation le
       confirme - log(RSD) contre log(concentration) donne r = -0,59.

    Voir PROTOCOLE.md § 1.3 bis.
    """

    def rel_sigma_pour(
        self, elements: list[str] | None = None
    ) -> float | np.ndarray:
        """
        Le sigma relatif : un scalaire, ou un vecteur si une table existe.

        Rend le SCALAIRE quand aucune table n'est fournie, afin que
        l'arithmetique aval soit rigoureusement inchangee - un vecteur
        constant donnerait le meme resultat mathematique, mais la
        verification « rien n'a bouge par defaut » serait moins directe.
        """
        if not self.rel_sigma_par_element or elements is None:
            return self.rel_sigma
        table = dict(self.rel_sigma_par_element)
        return np.array([table.get(e, self.rel_sigma) for e in elements],
                        dtype=float)

    def sigmas(
        self, b: np.ndarray, elements: list[str] | None = None
    ) -> np.ndarray:
        """
        L'incertitude attendue sur chaque element du vecteur `b`.

        Un seul endroit calcule cette formule. Elle vivait recopiee dans
        `solver.element_weights` et dans `uncertainty._tirer_bulletin`, donc
        un bruit par element n'aurait honore que celui des deux qu'on aurait
        pense a modifier.
        """
        return self.rel_sigma_pour(elements) * np.abs(b) + self.abs_sigma

    def apply(
        self, b_true: np.ndarray, rng: np.random.Generator,
        elements: list[str] | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Retourne (bulletin bruite et censure, masque des elements sous LOD)."""
        noise = rng.normal(0.0, 1.0, size=b_true.shape)
        b = b_true * (1.0 + self.rel_sigma_pour(elements) * noise)
        b = b + rng.normal(0.0, self.abs_sigma, size=b_true.shape)
        b = np.maximum(b, 0.0)
        below = b < self.lod
        return np.where(below, 0.0, b), below


DEFAULT_NOISE = NoiseModel()

# Bulletin de haute qualite, pour isoler les erreurs de modele du bruit.
NOISE_FREE = NoiseModel(rel_sigma=0.0, abs_sigma=0.0, lod=0.0, validated=True)


# ==========================================================================
# Profils de composition
# ==========================================================================

@dataclass(frozen=True)
class CompositionProfile:
    """
    Un domaine geometallurgique : une origine de matiere, donc une
    population de compositions distincte.

    `ranges` : phase -> (borne basse, borne haute) en fraction massique.
    Les phases absentes du dictionnaire sont a zero.
    """

    key: str
    label: str
    ranges: dict[str, tuple[float, float]]
    validated: bool = False
    rationale: str = ""

    def with_ranges(self, **overrides: tuple[float, float]) -> "CompositionProfile":
        """Variante du profil avec des bornes remplacees. Utile en calibration."""
        new = dict(self.ranges)
        new.update(overrides)
        return replace(self, ranges=new)


# --------------------------------------------------------------------------
# A VALIDER - aucune de ces fourchettes n'est arbitree.
# --------------------------------------------------------------------------
COMPOSITION_PROFILES: dict[str, CompositionProfile] = {
    "gigafactory_nmc": CompositionProfile(
        key="gigafactory_nmc",
        label="Chutes de production, chimie NMC tracee",
        ranges={
            "NMC622": (0.30, 0.50),
            "NMC811": (0.10, 0.30),
            "C_total": (0.20, 0.35),
            "Cu_metal": (0.005, 0.03),
            "Al_metal": (0.005, 0.03),
            "PVDF": (0.01, 0.04),
            "LiPF6": (0.00, 0.01),
            "Fe_metal": (0.00, 0.005),
        },
        rationale="A VALIDER. Chimie homogene, faible taux d'impuretes.",
    ),
    "mixed_ev": CompositionProfile(
        key="mixed_ev",
        label="Vehicules electriques fin de vie, grades melanges",
        ranges={
            "NMC111": (0.00, 0.15),
            "NMC532": (0.00, 0.20),
            "NMC622": (0.05, 0.25),
            "NMC811": (0.00, 0.20),
            "NCA": (0.00, 0.15),
            "LFP": (0.00, 0.25),
            "C_total": (0.20, 0.35),
            "Cu_metal": (0.01, 0.06),
            "Al_metal": (0.01, 0.06),
            "PVDF": (0.01, 0.05),
            "LiPF6": (0.00, 0.02),
            "Fe_metal": (0.00, 0.02),
        },
        rationale="A VALIDER. Melange de generations et de constructeurs.",
    ),
    "consumer_electronics": CompositionProfile(
        key="consumer_electronics",
        label="Electronique grand public (DEEE)",
        ranges={
            "LCO": (0.20, 0.45),
            "NMC111": (0.00, 0.15),
            "LMO": (0.00, 0.10),
            "C_total": (0.20, 0.35),
            "Cu_metal": (0.02, 0.08),
            "Al_metal": (0.01, 0.05),
            "PVDF": (0.01, 0.05),
            "Fe_metal": (0.00, 0.03),
        },
        rationale="A VALIDER. LCO dominant, forte heterogeneite.",
    ),
    "lfp_heavy": CompositionProfile(
        key="lfp_heavy",
        label="Stationnaire et bus, LFP dominant",
        ranges={
            "LFP": (0.35, 0.55),
            "NMC532": (0.00, 0.10),
            "C_total": (0.25, 0.40),
            "Cu_metal": (0.01, 0.05),
            "Al_metal": (0.01, 0.05),
            "PVDF": (0.01, 0.04),
            "Fe_metal": (0.00, 0.02),
        },
        rationale="A VALIDER. Faible valeur metal, enjeu sur le lithium.",
    ),
    "degenerate_probe": CompositionProfile(
        key="degenerate_probe",
        label="Sonde de degenerescence (test, non commercial)",
        ranges={
            "NMC111": (0.05, 0.20),
            "NMC622": (0.05, 0.20),
            "NMC811": (0.05, 0.20),
            "C_total": (0.25, 0.35),
            "Cu_metal": (0.01, 0.04),
            "Al_metal": (0.01, 0.04),
        },
        validated=True,   # profil de test interne, pas une hypothese metier
        rationale="Force les trois grades colineaires a coexister.",
    ),
}


# ==========================================================================
# Lot synthetique
# ==========================================================================

@dataclass
class SyntheticLot:
    """Verite terrain plus bulletin bruite."""

    x_true: np.ndarray
    b_true: np.ndarray
    b_measured: np.ndarray
    below_lod: np.ndarray
    elements: list[str]
    phase_keys: list[str]
    meta: dict = field(default_factory=dict)

    def as_bulletin(self, decimals: int = 4) -> dict[str, float]:
        """Le bulletin tel qu'un laboratoire le rendrait, en % massiques."""
        return {
            el: (
                0.0
                if self.below_lod[i]
                else round(float(self.b_measured[i] * 100.0), decimals)
            )
            for i, el in enumerate(self.elements)
        }

    def true_mixture(self, tol: float = 1e-9) -> dict[str, float]:
        """La verite terrain, en % massiques, phases non nulles seulement."""
        return {
            pk: round(float(self.x_true[i] * 100.0), 4)
            for i, pk in enumerate(self.phase_keys)
            if self.x_true[i] > tol
        }

    @property
    def closure(self) -> float:
        """Somme des fractions de phases identifiees."""
        return float(self.x_true.sum())

    @property
    def is_client_grade(self) -> bool:
        """Toujours False : ce module ne produit jamais de donnee client."""
        return self.meta.get("data_class") != DATA_CLASS

    def contains(self, phase_key: str, tol: float = 1e-9) -> bool:
        if phase_key not in self.phase_keys:
            return False
        return bool(self.x_true[self.phase_keys.index(phase_key)] > tol)


# ==========================================================================
# Tirage
# ==========================================================================

def _as_generator(rng: np.random.Generator | int | None) -> np.random.Generator:
    if isinstance(rng, np.random.Generator):
        return rng
    return np.random.default_rng(rng)


def sample_mixture(
    rng: np.random.Generator | int | None = None,
    profile: str | CompositionProfile = "mixed_ev",
    phase_keys: list[str] | None = None,
    closure: float = 1.0,
) -> np.ndarray:
    """
    Tire une composition de phases selon un profil.

    `closure` : somme visee des fractions de phases. 1.0 signifie que la
    matiere est entierement decrite par les phases du modele. Une valeur
    inferieure simule une masse non identifiee (humidite, phases absentes
    du modele).
    """
    rng = _as_generator(rng)
    phase_keys = list(PHASE_KEYS) if phase_keys is None else list(phase_keys)

    if isinstance(profile, str):
        if profile not in COMPOSITION_PROFILES:
            raise KeyError(
                f"Profil de composition inconnu : {profile!r}. "
                f"Valeurs admises : {sorted(COMPOSITION_PROFILES)}"
            )
        profile = COMPOSITION_PROFILES[profile]

    if not 0.0 < closure <= 1.0:
        raise ValueError("closure doit etre dans ]0, 1].")

    idx = {pk: i for i, pk in enumerate(phase_keys)}
    x = np.zeros(len(phase_keys), dtype=float)
    for pk, (lo, hi) in profile.ranges.items():
        if pk not in PHASES:
            raise KeyError(f"Profil {profile.key!r} : phase inconnue {pk!r}.")
        if pk in idx:                      # phase exclue par la provenance
            x[idx[pk]] = rng.uniform(lo, hi)

    total = x.sum()
    if total <= 0.0:
        raise ValueError(
            f"Profil {profile.key!r} : aucune phase retenue dans la liste fournie."
        )
    return x * (closure / total)


def make_lot(
    rng: np.random.Generator | int | None = None,
    profile: str | CompositionProfile = "mixed_ev",
    phase_keys: list[str] | None = None,
    noise: NoiseModel = DEFAULT_NOISE,
    closure: float = 1.0,
    x_true: np.ndarray | None = None,
    contaminants: dict[str, float] | None = None,
) -> SyntheticLot:
    """
    Genere un lot synthetique complet.

    `contaminants` : phases injectees de force, en fraction massique, apres
    tirage et renormalisation. Sert a simuler une ATTESTATION FAUSSE - par
    exemple du LCO dans un lot declare vehicule electrique. C'est le seul
    moyen de chiffrer le cout d'une declaration mensongere.
    """
    rng = _as_generator(rng)
    A, elements, keys = stoichiometry_matrix(phase_keys=phase_keys)

    if x_true is None:
        x_true = sample_mixture(
            rng, profile=profile, phase_keys=keys, closure=closure
        )
    else:
        x_true = np.asarray(x_true, dtype=float).copy()
        if x_true.shape[0] != len(keys):
            raise ValueError(
                f"x_true a {x_true.shape[0]} composantes, "
                f"{len(keys)} phases attendues."
            )

    injected: dict[str, float] = {}
    if contaminants:
        idx = {pk: i for i, pk in enumerate(keys)}
        for pk, frac in contaminants.items():
            if pk not in idx:
                raise KeyError(
                    f"Contaminant {pk!r} absent de la liste de phases courante."
                )
            if frac < 0:
                raise ValueError("Une fraction de contaminant doit etre positive.")
            x_true[idx[pk]] += frac
            injected[pk] = frac
        s = x_true.sum()
        if s > 1.0:
            x_true = x_true / s

    if np.any(x_true < -1e-12):
        raise ValueError("Fractions de phases negatives.")
    if x_true.sum() > 1.0 + 1e-9:
        raise ValueError("La somme des fractions de phases depasse 1.")

    b_true = A @ x_true
    b_meas, below = noise.apply(b_true, rng, elements=elements)

    prof_key = profile if isinstance(profile, str) else profile.key
    prof_obj = (
        COMPOSITION_PROFILES.get(prof_key)
        if isinstance(profile, str)
        else profile
    )

    return SyntheticLot(
        x_true=x_true,
        b_true=b_true,
        b_measured=b_meas,
        below_lod=below,
        elements=elements,
        phase_keys=keys,
        meta={
            "data_class": DATA_CLASS,
            "warning": SYNTHETIC_WARNING,
            "revision_commitment": REVISION_COMMITMENT,
            "profile": prof_key,
            "profile_validated": bool(prof_obj.validated) if prof_obj else None,
            "noise": noise,
            "closure": float(x_true.sum()),
            "contaminants": injected,
        },
    )


def make_batch(
    n: int,
    rng: np.random.Generator | int | None = None,
    **kwargs,
) -> list[SyntheticLot]:
    """Serie de lots independants tires du meme generateur aleatoire."""
    rng = _as_generator(rng)
    return [make_lot(rng=rng, **kwargs) for _ in range(n)]


def unvalidated_profiles() -> list[str]:
    """Profils dont les fourchettes ne sont pas arbitrees. Dette technique."""
    return sorted(k for k, p in COMPOSITION_PROFILES.items() if not p.validated)