"""
KLASTOS21 - Masses atomiques standard.

Source : IUPAC Commission on Isotopic Abundances and Atomic Weights,
"Atomic weights of the elements 2021". Valeurs conventionnelles abregees.

Ce fichier est isole volontairement : c'est la seule source de verite
numerique du projet pour les masses atomiques. Toute correction se fait ici.
"""

from __future__ import annotations

ATOMIC_MASS: dict[str, float] = {
    "H": 1.008,
    "Li": 6.94,
    "C": 12.011,
    "O": 15.999,
    "F": 18.998403163,
    "Na": 22.98976928,
    "Mg": 24.305,
    "Al": 26.9815385,
    "P": 30.973761998,
    "Mn": 54.938044,
    "Fe": 55.845,
    "Co": 58.933194,
    "Ni": 58.6934,
    "Cu": 63.546,
}

# Ordre canonique des lignes du bulletin d'analyse.
ELEMENTS: list[str] = [
    "Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F", "H", "O",
]


def formula_mass(composition: dict[str, float]) -> float:
    """Masse molaire (g/mol) d'une formule donnee en moles d'element."""
    missing = set(composition) - set(ATOMIC_MASS)
    if missing:
        raise KeyError(f"Element(s) inconnu(s) : {sorted(missing)}")
    return sum(ATOMIC_MASS[el] * n for el, n in composition.items())