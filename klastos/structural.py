"""
KLASTOS21 - Quantifications structurales (diffraction des rayons X).

POURQUOI CE MODULE EXISTE
-------------------------
Tout le reste du logiciel dit au client qu'une quantification par
diffraction leverait sa degenerescence. Jusqu'a cette seance, aucun chemin
de code ne permettait d'en saisir une : le produit designait son propre
levier sans l'offrir.

CE QU'UNE DRX FAIT, ET CE QU'ELLE NE FAIT PAS
---------------------------------------------
Une quantification Rietveld porte une incertitude absolue de 1 a 3 points.
Elle entre donc comme un ENCADREMENT, jamais comme une egalite :

    v - u  <=  x_j  <=  v + u

Consequence a retenir, et elle corrige le vocabulaire employe ailleurs :
une contrainte d'inegalite ne supprime aucune direction nulle, elle la
borne. Une DRX reelle ne rend donc RIEN identifiable - elle RETRECIT le
domaine compatible. Seule une mesure d'incertitude nulle, qui n'existe pas,
annulerait la degenerescence.

Mesure a l'appui, sur le lot d'exemple en provenance VE attestee
(nullite 2, largeur cumulee ouverte 61,35 points) :

    phase quantifiee   u=0,5pt  u=1pt  u=2pt  u=3pt
    NMC622              -81 %   -78 %  -72 %  -65 %
    NMC811              -79 %   -73 %  -62 %  -51 %
    NMC111              -77 %   -69 %  -54 %  -39 %
    LFP                 - 9 %   - 2 %  - 0 %  - 0 %
    PVDF                -10 %   - 5 %  - 0 %  - 0 %
    Fe_metal            - 0 %   - 0 %  - 0 %  - 0 %

Toutes les phases ne se valent donc pas, et l'ecart n'est pas marginal :
payer une quantification du fer metallique n'achete rien. C'est la raison
d'etre de `conseil_quantification`.

LES DEUX BASES DE NORMALISATION
-------------------------------
Un diffractogramme ne voit que la matiere cristalline. Le noir de carbone
est largement amorphe, le PVDF semi-cristallin. Un laboratoire rend donc
ses pourcentages sur l'une de deux bases, et la confondre est une erreur
de plusieurs points :

- BASE_ABSOLUE : fraction de la masse TOTALE de l'echantillon. Exige un
  standard interne ou une mesure de l'amorphe. La contrainte porte alors
  sur le NIVEAU de la phase.

- BASE_CRISTALLINE : fraction de la seule matiere cristalline, renormalisee
  a 100 %. La fraction cristalline du lot etant inconnue, le niveau n'est
  PAS contraint. En revanche le RAPPORT entre deux phases quantifiees est
  invariant a cette fraction inconnue, et lui est contraint.

Mesure du cout de cette distinction - nombre de phases a quantifier pour
annuler la degenerescence, dans le cas limite u -> 0 :

    provenance                 degenerescence  absolue  cristalline
    non declaree                     4            4          5
    VE attestee                      2            2          3
    chutes gigafactory               1            1          2

La base cristalline coute exactement une phase, dans les trois cas : n
phases quantifiees ne donnent que n-1 rapports independants.

PROPAGATION SUR UN RAPPORT
--------------------------
Pour r = v_a / v_b, on retient la borne

    u_r / r  <=  u_a / v_a  +  u_b / v_b

et non la somme quadratique. Les pourcentages Rietveld sont renormalises a
100 %, donc correles negativement : la formule d'independance sous-estimerait
l'incertitude. La somme lineaire majore l'erreur quelle que soit la
correlation, ce qui est le sens dans lequel ce logiciel se trompe.
"""

from __future__ import annotations

import csv
import io
import pathlib
import unicodedata
from dataclasses import dataclass, field

import numpy as np

from .phases import PHASES, PHASE_KEYS, phase_label

# ==========================================================================
# Bases de normalisation
# ==========================================================================

BASE_ABSOLUE = "absolue"
BASE_CRISTALLINE = "cristalline"
BASES = (BASE_ABSOLUE, BASE_CRISTALLINE)

LIBELLE_BASE = {
    BASE_ABSOLUE: "fraction de la masse totale (standard interne)",
    BASE_CRISTALLINE: "fraction de la matiere cristalline (renormalisee)",
}

# ==========================================================================
# Garde-fous
# ==========================================================================
# ARBITRES, et non mesures. Ils ne pilotent aucun calcul : ils refusent des
# saisies que l'on sait fausses.

U_MIN = 1e-4            # 0,01 point : en dessous, l'incertitude est factice
U_MAX = 0.25            # 25 points : au dela, la mesure n'informe plus
V_MIN = 1e-4            # une phase quantifiee a 0,00 % n'est pas quantifiee

# Une base cristalline exige au moins deux phases : un rapport a besoin de
# deux termes.
MIN_PHASES_CRISTALLINE = 2


class StructuralRefused(ValueError):
    """
    Saisie structurale refusee.

    Le refus est toujours prefere a une correction silencieuse : une
    quantification mal comprise contraint le systeme vers une solution
    fausse, et plus fermement qu'un bulletin bruite.
    """


# ==========================================================================
# Resolution des libelles de phase
# ==========================================================================


def _normalise(texte: str) -> str:
    """Minuscules, sans accents, sans separateurs : 'NMC 622' -> 'nmc622'."""
    t = unicodedata.normalize("NFKD", str(texte))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return "".join(c for c in t.lower() if c.isalnum())


def _construire_alias() -> dict[str, str]:
    """
    Table alias -> cle de phase.

    Trois entrees par phase : la cle, le libelle, la formule. Un laboratoire
    ecrit 'NMC 622', 'nmc-622' ou 'LiNi0.6Mn0.2Co0.2O2' ; les trois doivent
    tomber sur la meme phase. Une collision serait un bug du modele de
    phases, pas une erreur de saisie : on la leve.
    """
    alias: dict[str, str] = {}

    def poser(texte: str, cle: str) -> None:
        n = _normalise(texte)
        if not n:
            return
        if n in alias and alias[n] != cle:
            raise StructuralRefused(
                f"Collision d'alias de phase : {texte!r} designe a la fois "
                f"{alias[n]} et {cle}. Le modele de phases est a corriger."
            )
        alias[n] = cle

    for cle, p in PHASES.items():
        poser(cle, cle)
        poser(p["label"], cle)
        poser(p["formula"], cle)
    return alias


ALIAS_PHASES: dict[str, str] = _construire_alias()


def resoudre_phase(texte: str) -> str:
    """
    Cle de phase correspondant a un libelle libre.

    Leve StructuralRefused si le libelle est inconnu : accepter une phase
    hors modele reviendrait a contraindre une colonne qui n'existe pas.
    """
    n = _normalise(texte)
    if n not in ALIAS_PHASES:
        raise StructuralRefused(
            f"Phase inconnue : {texte!r}. Phases du modele : "
            f"{', '.join(PHASE_KEYS)}."
        )
    return ALIAS_PHASES[n]


# ==========================================================================
# Structures
# ==========================================================================


@dataclass(frozen=True)
class PhaseQuantification:
    """
    Une phase quantifiee, en fraction massique.

    Parameters
    ----------
    phase_key : cle de PHASES.
    value : valeur rendue par le laboratoire, en fraction (0,124 pour 12,4 %).
    uncertainty : incertitude ABSOLUE, meme unite. Obligatoire : c'est la
        decision structurante de cette seance. Sans elle, la phase sortirait
        en valeur unique et recreerait le piege du sommet ailleurs.
    """

    phase_key: str
    value: float
    uncertainty: float

    @property
    def label(self) -> str:
        return phase_label(self.phase_key)

    @property
    def bas(self) -> float:
        """Borne basse, jamais negative."""
        return max(0.0, self.value - self.uncertainty)

    @property
    def haut(self) -> float:
        return self.value + self.uncertainty

    @property
    def incertitude_relative(self) -> float:
        return self.uncertainty / self.value


@dataclass
class StructuralData:
    """
    Jeu de quantifications structurales d'un lot, et sa base.

    `journal` conserve tout ce qui a ete lu, corrige ou ecarte : un rapport
    client doit pouvoir rendre compte de l'origine de chaque contrainte.
    """

    quantifications: tuple[PhaseQuantification, ...] = ()
    basis: str = BASE_ABSOLUE
    source: str = "non declaree"
    journal: list[str] = field(default_factory=list, compare=False)

    def __post_init__(self) -> None:
        if self.basis not in BASES:
            raise StructuralRefused(
                f"Base de normalisation inconnue : {self.basis!r}. "
                f"Valeurs admises : {', '.join(BASES)}."
            )

    def __len__(self) -> int:
        return len(self.quantifications)

    @property
    def cles(self) -> tuple[str, ...]:
        return tuple(q.phase_key for q in self.quantifications)

    def resume(self) -> str:
        if not self.quantifications:
            return "Aucune quantification structurale."
        parties = ", ".join(
            f"{q.phase_key} {q.value * 100:.2f} +/- {q.uncertainty * 100:.2f} %"
            for q in self.quantifications
        )
        return f"{len(self)} phase(s) sur base {self.basis} : {parties}"


# ==========================================================================
# Validation
# ==========================================================================


def valider(
    quantifications: list[PhaseQuantification],
    basis: str,
    phase_keys: list[str] | None = None,
) -> list[str]:
    """
    Controle une liste de quantifications. Retourne le journal.

    Tout refus est leve, jamais corrige en silence - sauf la troncature de
    la borne basse a zero, qui est une consequence arithmetique de la
    non-negativite et non une correction de la saisie.
    """
    journal: list[str] = []

    if basis not in BASES:
        raise StructuralRefused(
            f"Base de normalisation inconnue : {basis!r}. "
            f"Valeurs admises : {', '.join(BASES)}."
        )

    if not quantifications:
        raise StructuralRefused(
            "Aucune phase quantifiee. Une quantification structurale vide "
            "n'apporte aucune contrainte : ne pas en fournir du tout."
        )

    vues: dict[str, PhaseQuantification] = {}
    for q in quantifications:
        if q.phase_key not in PHASES:
            raise StructuralRefused(f"Phase hors modele : {q.phase_key!r}.")
        if q.phase_key in vues:
            raise StructuralRefused(
                f"Phase {q.phase_key} quantifiee deux fois. Deux mesures "
                "d'une meme phase doivent etre reconciliees avant la saisie, "
                "pas ici."
            )
        vues[q.phase_key] = q

        if not np.isfinite(q.value) or not np.isfinite(q.uncertainty):
            raise StructuralRefused(
                f"{q.phase_key} : valeur ou incertitude non finie."
            )
        if q.value < V_MIN:
            raise StructuralRefused(
                f"{q.phase_key} : valeur {q.value * 100:.4f} % trop faible "
                "pour etre une quantification. Une phase sous la limite de "
                "quantification se declare absente, pas a zero."
            )
        if q.uncertainty < U_MIN:
            raise StructuralRefused(
                f"{q.phase_key} : incertitude {q.uncertainty * 100:.4f} % "
                "non credible. Une quantification Rietveld porte 1 a 3 "
                "points. Une incertitude nulle ferait passer une mesure "
                "pour une verite."
            )
        if q.uncertainty > U_MAX:
            raise StructuralRefused(
                f"{q.phase_key} : incertitude {q.uncertainty * 100:.1f} % "
                f"au dela de {U_MAX * 100:.0f} points. Une telle mesure "
                "n'informe pas : ne pas la fournir."
            )
        if q.haut > 1.0:
            raise StructuralRefused(
                f"{q.phase_key} : borne haute {q.haut * 100:.2f} % au dela "
                "de 100 % de la masse."
            )
        if q.value - q.uncertainty < 0.0:
            journal.append(
                f"{q.phase_key} : borne basse tronquee a 0 "
                f"({(q.value - q.uncertainty) * 100:.2f} % -> 0,00 %), "
                "la non-negativite des fractions massiques l'impose."
            )

    if phase_keys is not None:
        retenues = set(phase_keys)
        hors = [k for k in vues if k not in retenues]
        if hors:
            raise StructuralRefused(
                f"Phase(s) quantifiee(s) mais exclue(s) du modele du lot : "
                f"{sorted(hors)}. Une attestation de provenance les a "
                "ecartees alors que la diffraction les observe : la "
                "contradiction doit etre tranchee par le client, pas par "
                "le logiciel."
            )

    if basis == BASE_CRISTALLINE and len(vues) < MIN_PHASES_CRISTALLINE:
        raise StructuralRefused(
            f"Base cristalline : {len(vues)} phase quantifiee ne contraint "
            "rien. La fraction cristalline du lot etant inconnue, seuls les "
            "RAPPORTS entre phases sont exploitables, et un rapport exige "
            f"au moins {MIN_PHASES_CRISTALLINE} phases."
        )

    somme = sum(q.value for q in quantifications)
    if basis == BASE_ABSOLUE and somme > 1.0:
        raise StructuralRefused(
            f"Base absolue : les phases quantifiees somment a "
            f"{somme * 100:.2f} % de la masse totale. Le laboratoire a "
            "probablement rendu des pourcentages cristallins renormalises : "
            f"declarer la base {BASE_CRISTALLINE!r}."
        )
    if basis == BASE_CRISTALLINE:
        journal.append(
            f"Base cristalline : somme des phases quantifiees "
            f"{somme * 100:.2f} %. Les niveaux ne sont PAS contraints, "
            f"seuls les {len(vues) - 1} rapport(s) independant(s) le sont."
        )

    return journal


# ==========================================================================
# Lecture d'un fichier
# ==========================================================================

COLONNES_PHASE = ("phase", "phases", "mineral", "nom", "espece")
COLONNES_VALEUR = ("valeur", "teneur", "fraction", "pourcentage", "quantite",
                   "value", "wt", "wtpct", "pct")
COLONNES_INCERTITUDE = ("incertitude", "erreur", "sigma", "u", "esd",
                        "uncertainty", "error")


def _colonne(entetes: list[str], candidats: tuple[str, ...]) -> int | None:
    """Indice de la premiere colonne dont l'intitule normalise commence par
    l'un des candidats. L'unite entre parentheses est donc toleree."""
    for i, e in enumerate(entetes):
        n = _normalise(e)
        for c in candidats:
            if n.startswith(c):
                return i
    return None


def _pourcent(entete: str) -> bool:
    """L'intitule porte-t-il une unite en pourcent ?"""
    return "%" in entete or "pourcent" in _normalise(entete)


def _nombre(texte: str, quoi: str) -> float:
    """Lit un nombre en tolerant la virgule decimale francaise."""
    t = str(texte).strip().replace(" ", "").replace(" ", "")
    t = t.replace(",", ".")
    if not t:
        raise StructuralRefused(f"{quoi} : valeur vide.")
    try:
        return float(t)
    except ValueError as exc:
        raise StructuralRefused(f"{quoi} : {texte!r} n'est pas un nombre.") from exc


def parse_structural(
    lignes: list[list[str]],
    basis: str = BASE_ABSOLUE,
    source: str = "fichier",
    phase_keys: list[str] | None = None,
) -> StructuralData:
    """
    Construit un StructuralData depuis des lignes de CSV deja decoupees.

    Format attendu, une phase par ligne :

        Phase,Valeur (%),Incertitude (%)
        NMC622,28.10,2.00
        LFP,12.40,1.50

    Les intitules sont tolerants : 'Phase'/'Mineral', 'Valeur'/'Teneur',
    'Incertitude'/'Sigma'/'ESD'. L'unite se declare dans l'intitule ; sans
    signe de pourcentage, les valeurs sont lues comme des fractions.

    La colonne d'incertitude est OBLIGATOIRE. C'est la decision de la
    seance 17 : sans elle, le logiciel sortirait des phases fermes que le
    client n'a pas mesurees.
    """
    lignes = [l for l in lignes if any(str(c).strip() for c in l)]
    if len(lignes) < 2:
        raise StructuralRefused(
            "Fichier de quantification vide ou reduit a son entete."
        )

    entetes = [str(c).strip() for c in lignes[0]]
    i_ph = _colonne(entetes, COLONNES_PHASE)
    i_v = _colonne(entetes, COLONNES_VALEUR)
    i_u = _colonne(entetes, COLONNES_INCERTITUDE)

    if i_ph is None or i_v is None:
        raise StructuralRefused(
            f"Colonnes illisibles : {entetes}. Attendu une colonne de phase "
            "et une colonne de valeur."
        )
    if i_u is None:
        raise StructuralRefused(
            f"Aucune colonne d'incertitude dans {entetes}. Une quantification "
            "sans incertitude est refusee : elle ferait passer une mesure "
            "Rietveld, precise a 1 ou 3 points, pour une valeur exacte."
        )

    ech_v = 0.01 if _pourcent(entetes[i_v]) else 1.0
    ech_u = 0.01 if _pourcent(entetes[i_u]) else 1.0

    journal = [
        f"Lecture de {source} : colonnes "
        f"phase={entetes[i_ph]!r}, valeur={entetes[i_v]!r}, "
        f"incertitude={entetes[i_u]!r}.",
        f"Unites : valeur x{ech_v}, incertitude x{ech_u}.",
    ]

    quants: list[PhaseQuantification] = []
    for n, ligne in enumerate(lignes[1:], start=2):
        if max(i_ph, i_v, i_u) >= len(ligne):
            raise StructuralRefused(
                f"Ligne {n} : {len(ligne)} colonne(s), "
                f"{max(i_ph, i_v, i_u) + 1} attendues."
            )
        brut = str(ligne[i_ph]).strip()
        if not brut:
            continue
        cle = resoudre_phase(brut)
        if _normalise(brut) != _normalise(cle):
            journal.append(f"Ligne {n} : {brut!r} resolu en {cle}.")
        quants.append(
            PhaseQuantification(
                phase_key=cle,
                value=_nombre(ligne[i_v], f"ligne {n}, valeur") * ech_v,
                uncertainty=_nombre(ligne[i_u], f"ligne {n}, incertitude") * ech_u,
            )
        )

    journal += valider(quants, basis, phase_keys)
    return StructuralData(
        quantifications=tuple(quants), basis=basis, source=source,
        journal=journal,
    )


def lire_fichier(
    chemin: str | pathlib.Path,
    basis: str = BASE_ABSOLUE,
    separateur: str = ",",
    phase_keys: list[str] | None = None,
) -> StructuralData:
    """Lit un fichier CSV de quantification structurale."""
    chemin = pathlib.Path(chemin)
    texte = chemin.read_text(encoding="utf-8-sig")
    lignes = list(csv.reader(io.StringIO(texte), delimiter=separateur))
    return parse_structural(
        lignes, basis=basis, source=str(chemin), phase_keys=phase_keys
    )


# ==========================================================================
# Contraintes lineaires
# ==========================================================================


def contraintes(
    data: StructuralData,
    phase_keys: list[str],
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """
    Traduit les quantifications en inegalites G @ x <= h.

    Forme unique, quelle que soit la base : tout le reste du logiciel n'a
    donc qu'un seul mecanisme a connaitre.

    BASE_ABSOLUE, une phase quantifiee -> deux lignes :

          x_j <=  v + u
         -x_j <= -(v - u)

    BASE_CRISTALLINE, deux phases consecutives -> deux lignes sur leur
    rapport r = v_a / v_b, borne a (1 +/- e) r avec e = u_a/v_a + u_b/v_b :

         x_a - r(1 + e) x_b <= 0
        -x_a + r(1 - e) x_b <= 0

    Le niveau n'apparait nulle part dans le second cas : c'est exactement ce
    qui rend la contrainte valable sans connaitre la fraction cristalline.

    Returns
    -------
    G : (m, n_phases) ndarray, m = 0 si aucune contrainte
    h : (m,) ndarray
    journal : ce qui a ete pose, en clair
    """
    n = len(phase_keys)
    index = {k: j for j, k in enumerate(phase_keys)}

    manquantes = [q.phase_key for q in data.quantifications
                  if q.phase_key not in index]
    if manquantes:
        raise StructuralRefused(
            f"Phase(s) quantifiee(s) absente(s) du modele du lot : "
            f"{sorted(manquantes)}."
        )

    G: list[np.ndarray] = []
    h: list[float] = []
    journal: list[str] = []

    def base_vecteur(cle: str) -> np.ndarray:
        v = np.zeros(n, dtype=float)
        v[index[cle]] = 1.0
        return v

    if not data.quantifications:
        return np.zeros((0, n)), np.zeros(0), journal

    if data.basis == BASE_ABSOLUE:
        for q in data.quantifications:
            e = base_vecteur(q.phase_key)
            G.append(e.copy());  h.append(q.haut)
            G.append(-e);        h.append(-q.bas)
            journal.append(
                f"{q.phase_key} encadre dans "
                f"[{q.bas * 100:.2f} ; {q.haut * 100:.2f}] % de la masse "
                "totale."
            )
    else:
        qs = list(data.quantifications)
        for a, b in zip(qs[:-1], qs[1:]):
            r = a.value / b.value
            eps = a.incertitude_relative + b.incertitude_relative
            haut, bas = r * (1.0 + eps), max(0.0, r * (1.0 - eps))
            ea, eb = base_vecteur(a.phase_key), base_vecteur(b.phase_key)
            G.append(ea - haut * eb);  h.append(0.0)
            G.append(-ea + bas * eb);  h.append(0.0)
            journal.append(
                f"Rapport {a.phase_key}/{b.phase_key} encadre dans "
                f"[{bas:.4f} ; {haut:.4f}] (r = {r:.4f}, "
                f"incertitude relative majoree a {eps * 100:.1f} %). "
                "Les niveaux restent libres."
            )
        journal.append(
            f"{len(qs)} phase(s) quantifiee(s) sur base cristalline donnent "
            f"{len(qs) - 1} rapport(s) independant(s) : une phase de moins "
            "qu'en base absolue."
        )

    return np.vstack(G), np.asarray(h, dtype=float), journal