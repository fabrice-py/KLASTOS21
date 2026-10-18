"""
KLASTOS21 - Phases candidates et matrice de stoechiometrie.

Convention
----------
- `x` : fractions massiques de phases (kg de phase / kg d'echantillon).
- `b` : fractions massiques elementaires (le bulletin d'analyse).
- La matrice A verifie A @ x = b, avec
      A[e, p] = masse de l'element e par unite de masse de la phase p.
  Chaque colonne de A somme donc a 1 (conservation de la masse).

NOTE METIER (validee, v0) - carbone
-----------------------------------
Le graphite et le noir de carbone sont fusionnes en une phase unique
"carbone total". La separation graphite / noir de carbone necessite des
donnees texturales ou structurales, non prises en compte dans cette
premiere version.

NOTE METIER (validee, v0) - grades NMC
--------------------------------------
Les quatre grades NMC sont conserves separement bien que leur ventilation
individuelle ne soit pas identifiable par analyse elementaire seule.
Le rapport affiche "Cathodes totales" et "NMC + LCO" comme grandeurs fermes,
et la ventilation par grade comme domaine compatible explicitement marque.
"""

from __future__ import annotations

import numpy as np

from .elements import ATOMIC_MASS, ELEMENTS, formula_mass

# --------------------------------------------------------------------------
# Groupes de phases. Servent aux agregats du rapport.
# --------------------------------------------------------------------------
GROUP_NMC = "NMC"
GROUP_CATHODE_AUTRE = "cathode_autre"
GROUP_CARBONE = "carbone"
GROUP_COLLECTEUR = "collecteur"
GROUP_LIANT = "liant"
GROUP_ELECTROLYTE = "electrolyte"
GROUP_IMPURETE = "impurete"

# Groupes constituant la matiere active cathodique.
CATHODE_GROUPS: tuple[str, ...] = (GROUP_NMC, GROUP_CATHODE_AUTRE)

# --------------------------------------------------------------------------
# Phases candidates : moles d'element par mole de formule.
# --------------------------------------------------------------------------
PHASES: dict[str, dict] = {
    # ---- Cathodes NMC : LiNi_x Mn_y Co_z O2, avec x + y + z = 1 -----------
    "NMC111": {
        "label": "NMC 111",
        "formula": "LiNi(1/3)Mn(1/3)Co(1/3)O2",
        "group": GROUP_NMC,
        "composition": {"Li": 1.0, "Ni": 1 / 3, "Mn": 1 / 3, "Co": 1 / 3, "O": 2.0},
    },
    "NMC532": {
        "label": "NMC 532",
        "formula": "LiNi0.5Mn0.3Co0.2O2",
        "group": GROUP_NMC,
        "composition": {"Li": 1.0, "Ni": 0.5, "Mn": 0.3, "Co": 0.2, "O": 2.0},
    },
    "NMC622": {
        "label": "NMC 622",
        "formula": "LiNi0.6Mn0.2Co0.2O2",
        "group": GROUP_NMC,
        "composition": {"Li": 1.0, "Ni": 0.6, "Mn": 0.2, "Co": 0.2, "O": 2.0},
    },
    "NMC811": {
        "label": "NMC 811",
        "formula": "LiNi0.8Mn0.1Co0.1O2",
        "group": GROUP_NMC,
        "composition": {"Li": 1.0, "Ni": 0.8, "Mn": 0.1, "Co": 0.1, "O": 2.0},
    },
    # ---- Autres cathodes --------------------------------------------------
    "NCA": {
        "label": "NCA",
        "formula": "LiNi0.8Co0.15Al0.05O2",
        "group": GROUP_CATHODE_AUTRE,
        "composition": {"Li": 1.0, "Ni": 0.8, "Co": 0.15, "Al": 0.05, "O": 2.0},
    },
    "LCO": {
        "label": "LCO",
        "formula": "LiCoO2",
        "group": GROUP_CATHODE_AUTRE,
        "composition": {"Li": 1.0, "Co": 1.0, "O": 2.0},
    },
    "LFP": {
        "label": "LFP",
        "formula": "LiFePO4",
        "group": GROUP_CATHODE_AUTRE,
        "composition": {"Li": 1.0, "Fe": 1.0, "P": 1.0, "O": 4.0},
    },
    "LMO": {
        "label": "LMO",
        "formula": "LiMn2O4",
        "group": GROUP_CATHODE_AUTRE,
        "composition": {"Li": 1.0, "Mn": 2.0, "O": 4.0},
    },
    # ---- Anode / carbone --------------------------------------------------
    "C_total": {
        "label": "Carbone total",
        "formula": "C (graphite + noir de carbone)",
        "group": GROUP_CARBONE,
        "composition": {"C": 1.0},
        "note": (
            "La separation graphite / noir de carbone necessite des donnees "
            "texturales ou structurales, non prises en compte dans cette "
            "premiere version."
        ),
    },
    # ---- Collecteurs de courant -------------------------------------------
    "Cu_metal": {
        "label": "Cuivre metallique",
        "formula": "Cu (collecteur anode)",
        "group": GROUP_COLLECTEUR,
        "composition": {"Cu": 1.0},
    },
    "Al_metal": {
        "label": "Aluminium metallique",
        "formula": "Al (collecteur cathode)",
        "group": GROUP_COLLECTEUR,
        "composition": {"Al": 1.0},
    },
    # ---- Liant et residus d'electrolyte -----------------------------------
    "PVDF": {
        "label": "PVDF (liant)",
        "formula": "(C2H2F2)n",
        "group": GROUP_LIANT,
        "composition": {"C": 2.0, "H": 2.0, "F": 2.0},
    },
    "LiPF6": {
        "label": "Sel d'electrolyte residuel",
        "formula": "LiPF6",
        "group": GROUP_ELECTROLYTE,
        "composition": {"Li": 1.0, "P": 1.0, "F": 6.0},
    },
    # ---- Impuretes --------------------------------------------------------
    "Fe_metal": {
        "label": "Fer metallique",
        "formula": "Fe (usure, boitiers)",
        "group": GROUP_IMPURETE,
        "composition": {"Fe": 1.0},
    },
}

PHASE_KEYS: list[str] = list(PHASES.keys())

MOLAR_MASS: dict[str, float] = {
    k: formula_mass(v["composition"]) for k, v in PHASES.items()
}


def phase_label(key: str) -> str:
    """Libelle client d'une phase, formule comprise."""
    p = PHASES[key]
    return f"{p['label']} ({p['formula']})"


def stoichiometry_matrix(
    phase_keys: list[str] | None = None,
    elements: list[str] | None = None,
) -> tuple[np.ndarray, list[str], list[str]]:
    """
    Construit A telle que A @ x = b, en bases massiques.

    Returns
    -------
    A : (n_elements, n_phases) ndarray
    elements : libelles de lignes
    phase_keys : libelles de colonnes
    """
    elements = list(ELEMENTS) if elements is None else list(elements)
    phase_keys = list(PHASE_KEYS) if phase_keys is None else list(phase_keys)

    unknown = set(phase_keys) - set(PHASES)
    if unknown:
        raise KeyError(f"Phase(s) inconnue(s) : {sorted(unknown)}")

    A = np.zeros((len(elements), len(phase_keys)), dtype=float)
    for j, pk in enumerate(phase_keys):
        comp = PHASES[pk]["composition"]
        M = MOLAR_MASS[pk]
        for i, el in enumerate(elements):
            if el in comp:
                A[i, j] = ATOMIC_MASS[el] * comp[el] / M
    return A, elements, phase_keys


def indicator(
    keys: list[str] | tuple[str, ...],
    phase_keys: list[str] | None = None,
) -> np.ndarray:
    """Vecteur indicateur d'un ensemble de phases nommees."""
    phase_keys = list(PHASE_KEYS) if phase_keys is None else list(phase_keys)
    wanted = set(keys)
    return np.array([1.0 if pk in wanted else 0.0 for pk in phase_keys])


def group_indicator(
    groups: str | tuple[str, ...],
    phase_keys: list[str] | None = None,
) -> np.ndarray:
    """Vecteur indicateur d'un ou plusieurs groupes de phases."""
    phase_keys = list(PHASE_KEYS) if phase_keys is None else list(phase_keys)
    wanted = {groups} if isinstance(groups, str) else set(groups)
    return np.array(
        [1.0 if PHASES[pk]["group"] in wanted else 0.0 for pk in phase_keys]
    )


def cathode_indicator(phase_keys: list[str] | None = None) -> np.ndarray:
    """Indicateur 'Cathodes totales' : grandeur ferme validee en v0."""
    return group_indicator(CATHODE_GROUPS, phase_keys=phase_keys)


def nmc_lco_indicator(phase_keys: list[str] | None = None) -> np.ndarray:
    """Indicateur du bloc 'NMC + LCO' : grandeur ferme validee en v0."""
    phase_keys = list(PHASE_KEYS) if phase_keys is None else list(phase_keys)
    nmc = [pk for pk in phase_keys if PHASES[pk]["group"] == GROUP_NMC]
    return indicator(nmc + ["LCO"], phase_keys=phase_keys)