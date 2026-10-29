"""
Pre-calcul de la demonstration interactive du site.

CE QUE C'EST, ET POURQUOI CE N'EST PAS UNE MAQUETTE
----------------------------------------------------
Le site vitrine explique que KLASTOS21 distingue ce qu'un bulletin
determine de ce qu'il laisse ouvert. Le dire est faible ; le MONTRER sur
une page ou le visiteur choisit lui-meme les elements doses est tout
autre chose.

Les reponses affichees ne sont pas ecrites a la main. Elles sortent de
`klastos.identifiability`, c'est-a-dire du moteur qui produit les rapports
clients. Le balayage complet - les 1 023 combinaisons non vides de dix
elements - coute moins d'une seconde a la construction. Le resultat part
en JSON, et la page le consulte sans aucun serveur.

Un visiteur qui coche « Li » et voit trois phases basculer de « domaine
compatible » a « determinee » a compris le produit en cinq secondes. Aucun
paragraphe ne fait cela.

LA GARANTIE QUE CELA APPORTE
-----------------------------
Le site ne peut plus mentir sur le produit : si le moteur change, la
demonstration change avec lui a la prochaine construction. Un test verifie
d'ailleurs que les chiffres de la page correspondent toujours a ce que le
moteur repond aujourd'hui.
"""

from __future__ import annotations

import itertools
import json
import pathlib

import numpy as np

from klastos.identifiability import analyse, is_identifiable, null_space
from klastos.phases import PHASES, stoichiometry_matrix
from klastos.provenance import ProvenanceDeclaration

#: Les elements que le visiteur peut cocher. Ce sont ceux qu'un bulletin
#: de black mass dose reellement. L'oxygene en fait partie et c'est tout
#: l'interet : aucun laboratoire ne le dose en routine, et son absence est
#: la premiere cause de degenerescence du systeme.
ELEMENTS_DEMO: tuple[str, ...] = (
    "Li", "Ni", "Mn", "Co", "Al", "Fe", "Cu", "P", "F", "C", "O",
)

#: Selection de depart : un bulletin elementaire courant, sans oxygene.
DEPART: tuple[str, ...] = ("Ni", "Mn", "Co", "Al", "Cu", "Fe")

#: Provenance de reference pour la demonstration. Une provenance attestee
#: restreint les phases admissibles, donc le systeme : le dire evite de
#: laisser croire que le resultat vaut pour n'importe quel lot.
PROVENANCE = "vehicule_electrique"


def _phases_retenues() -> list[str]:
    cles, _, _ = ProvenanceDeclaration(PROVENANCE, attested=True).resolve()
    return list(cles)


def _etat(cles: list[str], elements: tuple[str, ...]) -> dict:
    """
    Degenerescence et phases determinees, pour un jeu d'elements doses.

    Une phase est « determinee » si sa fraction est la meme sur TOUTES les
    solutions compatibles avec le bulletin. C'est exactement le critere du
    rapport : la projection sur l'espace nul doit etre nulle.
    """
    A, _, _ = stoichiometry_matrix(phase_keys=cles, elements=list(elements))
    r = analyse(A, cles)
    N = null_space(A)

    determinees = set()
    for i, cle in enumerate(cles):
        c = np.zeros(len(cles))
        c[i] = 1.0
        if is_identifiable(c, N):
            determinees.add(cle)
    # Les phases determinees partent en MASQUE DE BITS plutot qu'en liste
    # de noms : la table compte 2 047 entrees, et repeter douze chaines
    # dans chacune triplait le poids du fichier pour rien.
    masque = 0
    for i, cle in enumerate(cles):
        if cle in determinees:
            masque |= 1 << i
    return {"r": r.rank, "d": r.degeneracy, "f": masque}


def balayage() -> dict:
    """
    Toutes les combinaisons non vides d'elements doses.

    2^11 - 1 = 2 047 entrees, calculees en moins d'une seconde. Les
    pre-calculer evite d'embarquer un solveur dans la page, et garantit que
    la reponse affichee est celle du moteur et non d'une approximation
    ecrite en JavaScript.
    """
    cles = _phases_retenues()
    table: dict[str, dict] = {}
    for k in range(1, len(ELEMENTS_DEMO) + 1):
        for combo in itertools.combinations(ELEMENTS_DEMO, k):
            masque = "".join(
                "1" if e in combo else "0" for e in ELEMENTS_DEMO)
            table[masque] = _etat(cles, combo)
    return {
        "elements": list(ELEMENTS_DEMO),
        "depart": list(DEPART),
        "phases": [{"cle": c,
                    "nom": PHASES.get(c, {}).get("label", c),
                    "formule": PHASES.get(c, {}).get("formula", ""),
                    "groupe": PHASES.get(c, {}).get("group", "")}
                   for c in cles],
        "provenance": PROVENANCE,
        "table": table,
    }


def ecrire(sortie: pathlib.Path) -> pathlib.Path:
    """Ecrit le balayage en JSON compact a cote des pages."""
    donnees = balayage()
    cible = sortie / "demo.json"
    cible.write_text(
        json.dumps(donnees, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    return cible


if __name__ == "__main__":
    import time

    t = time.perf_counter()
    d = balayage()
    print(f"{len(d['table'])} combinaisons en {time.perf_counter() - t:.2f} s")
    print(f"{len(d['phases'])} phases, {len(d['elements'])} elements")
    def lire(sel):
        m = "".join("1" if e in set(sel) else "0" for e in ELEMENTS_DEMO)
        e = d["table"][m]
        return f"rang {e['r']:2d}  deg {e['d']:2d}  fermes {bin(e['f']).count('1'):2d}"

    print("depart  :", lire(DEPART))
    print("avec Li :", lire(set(DEPART) | {"Li"}))
    print("tout    :", lire(ELEMENTS_DEMO))
