"""
KLASTOS21 - Lecture d'un bulletin d'analyse reel.

Entre un certificat de laboratoire et le vecteur attendu par le solveur, il
y a un fosse que ce module comble.

Ce qu'un bulletin reel contient, et que le solveur ne sait pas lire
---------------------------------------------------------------------
- des NOMS variables : "Ni", "Nickel", "Ni (%)", "NiO", et la forme des
  certificats de materiaux de reference, "Ni, Nickel (wt.%)" ;
- des UNITES melangees dans le meme tableau : pourcents pour les majeurs,
  ppm ou mg/kg pour les traces. Facteur 10 000 entre les deux. Et des
  abreviations ponctuees, "wt.%", que les certificats emploient ;
- des OXYDES la ou le modele attend des elements. Un laboratoire de
  geochimie rend volontiers Li2O, NiO, Al2O3, Fe2O3. Confondre Li2O et Li
  fausse la teneur d'un facteur 2,15 ;
- des VALEURS CENSUREES : "< 0,05", "n.d.", "trace", "inf. LD" ;
- des colonnes etrangeres au modele : identifiant d'echantillon, humidite,
  densite, granulometrie.

Et ce qu'il ne contient JAMAIS : l'oxygene. Aucun laboratoire ne le dose, il
n'existe pas de methode de routine economique pour une telle matrice. Ce
module ne l'invente pas : il rapporte les elements effectivement doses, et
le solveur resout sur ceux-la seuls.

Principe directeur
------------------
Aucune interpretation silencieuse. Chaque decision de lecture - conversion
d'oxyde, application d'une unite, traitement d'une censure - est JOURNALISEE
et destinee au rapport client. Une colonne non reconnue n'est jamais
devinee : elle est signalee et ignoree explicitement.

Le corollaire vaut pour la forme « symbole, nom complet » : elle n'est
acceptee que si les DEUX moities designent le meme element. « Ni, Cobalt »
est refuse, bien que chaque moitie soit valide separement - retenir l'une
des deux ferait sortir un lot dont le nickel est compte comme du cobalt,
sans aucun signe exterieur d'erreur.
"""

from __future__ import annotations

import csv
import pathlib
import re
from dataclasses import dataclass, field

import numpy as np

from . import i18n
from .elements import ATOMIC_MASS, ELEMENTS

# ==========================================================================
# Unites de teneur
# ==========================================================================
# Facteur de conversion vers une FRACTION MASSIQUE (kg/kg).
CONCENTRATION_UNITS: dict[str, float] = {
    # « wt.% » et « wt. % » viennent des certificats de materiaux de
    # reference, qui ponctuent l'abreviation. Le bulletin OREAS etait refuse
    # pour cette raison seule : l'unite n'etait pas reconnue, donc la
    # colonne non plus.
    "%": 1e-2, "pct": 1e-2, "wt%": 1e-2, "wt.%": 1e-2, "wt. %": 1e-2,
    "% m/m": 1e-2, "%m/m": 1e-2,
    "g/100g": 1e-2,
    "g/kg": 1e-3,
    "ppm": 1e-6, "mg/kg": 1e-6, "g/t": 1e-6, "ug/g": 1e-6, "µg/g": 1e-6,
    "ppb": 1e-9, "ug/kg": 1e-9, "µg/kg": 1e-9,
    "fraction": 1.0,
}

# Marqueurs de valeur non quantifiee.
CENSORED_TOKENS = {
    "nd", "n.d.", "n/d", "na", "n/a", "-", "--", "", "trace", "tr",
    "ind",   # indetermine, notation des certificats de reference
    "inf. ld", "inf.ld", "<ld", "<lq", "bdl", "n.q.", "nq", "nm",
}

_RE_INFERIEUR = re.compile(r"^\s*[<≤]\s*([\d.,\s]+)\s*$")

# Traitements admis pour une valeur sous la limite de detection.
# A VALIDER : "half" est la convention geochimique courante. Le choix est
# journalise et figure dans le rapport ; il n'est jamais implicite.
CENSORED_MODES = ("zero", "half", "threshold")
DEFAULT_CENSORED_MODE = "half"


# ==========================================================================
# Oxydes
# ==========================================================================

@dataclass(frozen=True)
class Oxide:
    """Un oxyde et son facteur de conversion vers l'element."""

    formula: str
    element: str
    composition: dict[str, float]

    @property
    def factor(self) -> float:
        """Masse d'element par unite de masse d'oxyde."""
        m_ox = sum(ATOMIC_MASS[e] * n for e, n in self.composition.items())
        return ATOMIC_MASS[self.element] * self.composition[self.element] / m_ox


OXIDES: dict[str, Oxide] = {
    "Li2O": Oxide("Li2O", "Li", {"Li": 2, "O": 1}),
    "NiO": Oxide("NiO", "Ni", {"Ni": 1, "O": 1}),
    "CoO": Oxide("CoO", "Co", {"Co": 1, "O": 1}),
    "Co3O4": Oxide("Co3O4", "Co", {"Co": 3, "O": 4}),
    "MnO": Oxide("MnO", "Mn", {"Mn": 1, "O": 1}),
    "MnO2": Oxide("MnO2", "Mn", {"Mn": 1, "O": 2}),
    "Mn3O4": Oxide("Mn3O4", "Mn", {"Mn": 3, "O": 4}),
    "Al2O3": Oxide("Al2O3", "Al", {"Al": 2, "O": 3}),
    "Fe2O3": Oxide("Fe2O3", "Fe", {"Fe": 2, "O": 3}),
    "FeO": Oxide("FeO", "Fe", {"Fe": 1, "O": 1}),
    "P2O5": Oxide("P2O5", "P", {"P": 2, "O": 5}),
    "CuO": Oxide("CuO", "Cu", {"Cu": 1, "O": 1}),
}


# ==========================================================================
# Reconnaissance des intitules de colonnes
# ==========================================================================

ELEMENT_ALIASES: dict[str, str] = {
    "lithium": "Li", "nickel": "Ni", "cobalt": "Co",
    "manganese": "Mn", "manganèse": "Mn",
    "aluminium": "Al", "aluminum": "Al",
    "fer": "Fe", "iron": "Fe",
    "cuivre": "Cu", "copper": "Cu",
    "phosphore": "P", "phosphorus": "P", "phosphore total": "P",
    "fluor": "F", "fluorine": "F", "fluorure": "F", "fluoride": "F",
    "carbone": "C", "carbon": "C",
    "carbone total": "C", "total carbon": "C", "c total": "C", "ctot": "C",
    "oxygene": "O", "oxygène": "O", "oxygen": "O",
    "hydrogene": "H", "hydrogène": "H", "hydrogen": "H",
}

# L'alternance est ordonnee du plus long au plus court : `%` seul matcherait
# le `%` de `wt.%` et laisserait le `wt.` dehors, ce qui ferait echouer
# l'ancrage sur la parenthese fermante et perdre l'unite.
_RE_UNITE_DANS_NOM = re.compile(
    r"[\(\[]\s*("
    r"%\s*m/m|wt\.?\s*%|wt%|pct|%"
    r"|mg/kg|g/kg|g/t|ppm|ppb"
    r"|µg/g|ug/g|µg/kg|ug/kg"
    r")\s*[\)\]]",
    re.IGNORECASE,
)

# Forme « symbole, nom complet » des certificats de materiaux de reference :
# « Al, Aluminium », « F, Fluorine ».
#
# Elle n'est acceptee que si les DEUX moities designent le meme element. Le
# symbole seul ne suffit pas, le nom seul non plus : ils se corroborent. Un
# intitule comme « Al, Barium » est donc REFUSE plutot qu'arbitre, et un
# element inconnu du modele - « Ba, Barium » - l'est aussi. C'est la regle
# absolue du module : ne jamais deviner un element.
_RE_SYMBOLE_ET_NOM = re.compile(
    r"^\s*([A-Za-z]{1,2})\s*,\s*([A-Za-zÀ-ſ][A-Za-zÀ-ſ "
    r"'\-]*)\s*$"
)

# Mots de qualification a retirer avant reconnaissance.
_RE_SUFFIXES = re.compile(
    r"[_\s]*(wt|teneur|grade|assay|dose|dosage|result|resultat|résultat)"
    r"[_\s]*$",
    re.IGNORECASE,
)


class IngestionError(ValueError):
    """Le bulletin ne peut pas etre lu de maniere sure."""


@dataclass
class ColumnReading:
    """Interpretation d'une colonne du bulletin."""

    raw_name: str
    element: str | None
    oxide: str | None
    unit: str | None
    recognized: bool
    reason: str = ""


@dataclass
class BulletinReading:
    """
    Resultat de lecture, avec tout ce qui a ete decide en chemin.

    `measured_elements` et `b` se branchent directement sur le solveur :

        r = read_bulletin("bulletin.csv")
        res = solve(r.b, elements=r.measured_elements, phase_keys=keys)
    """

    values: dict[str, float]            # element -> fraction massique
    measured_elements: list[str]        # ordre canonique, doses seulement
    b: np.ndarray                       # vecteur sur measured_elements
    censored: dict[str, float]          # element -> seuil de detection
    columns: list[ColumnReading]
    journal: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    @property
    def total(self) -> float:
        """Somme des teneurs lues. Ne vaut JAMAIS 1 sur un bulletin reel."""
        return float(sum(self.values.values()))

    @property
    def ignored_columns(self) -> list[str]:
        return [c.raw_name for c in self.columns if not c.recognized]

    @property
    def oxygen_measured(self) -> bool:
        return "O" in self.values

    def as_percent(self) -> dict[str, float]:
        """Les teneurs retenues, en % massiques, pour affichage."""
        return {e: round(self.values[e] * 100.0, 4) for e in self.measured_elements}


# ==========================================================================
# Analyse d'un intitule et d'une valeur
# ==========================================================================

def parse_column(name: str) -> ColumnReading:
    """
    Interprete un intitule de colonne.

    Rien n'est devine : si l'intitule ne correspond a aucun element ni oxyde
    connu, la colonne est declaree non reconnue et sera ignoree.
    """
    brut = (name or "").strip()
    if not brut:
        return ColumnReading(name, None, None, None, False, "intitule vide")

    unite = None
    m = _RE_UNITE_DANS_NOM.search(brut)
    if m:
        unite = m.group(1).strip().lower().replace("µ", "u")
        brut = _RE_UNITE_DANS_NOM.sub(" ", brut)

    noyau = _RE_SUFFIXES.sub("", brut.strip().strip("_-.: ")).strip()

    # Oxyde : comparaison insensible a la casse, forme canonique conservee.
    for formule in OXIDES:
        if noyau.lower() == formule.lower():
            return ColumnReading(name, OXIDES[formule].element, formule, unite, True)

    # Element par symbole.
    for el in ELEMENTS:
        if noyau.lower() == el.lower():
            return ColumnReading(name, el, None, unite, True)

    # Element par nom courant.
    cle = re.sub(r"\s+", " ", noyau.lower())
    if cle in ELEMENT_ALIASES:
        return ColumnReading(name, ELEMENT_ALIASES[cle], None, unite, True)

    # Forme « symbole, nom complet », et seulement si les deux moities
    # s'accordent. Voir le commentaire de `_RE_SYMBOLE_ET_NOM` : la
    # corroboration remplace la devinette.
    m = _RE_SYMBOLE_ET_NOM.match(noyau)
    if m:
        symbole = m.group(1).strip()
        nom = re.sub(r"\s+", " ", m.group(2).strip().lower())
        par_symbole = next(
            (e for e in ELEMENTS if e.lower() == symbole.lower()), None)
        par_nom = ELEMENT_ALIASES.get(nom)
        if par_symbole is not None and par_symbole == par_nom:
            return ColumnReading(name, par_symbole, None, unite, True)
        if par_symbole is not None or par_nom is not None:
            # Une seule moitie reconnue, ou deux moities qui se contredisent.
            # On refuse : l'intitule est ambigu, et l'interpreter de travers
            # coute plus cher que de le rejeter.
            return ColumnReading(
                name, None, None, unite, False,
                "forme « symbole, nom » dont les deux moities ne "
                "s'accordent pas")

    return ColumnReading(name, None, None, unite, False,
                         "ni element ni oxyde reconnu")


def parse_value(brut: str) -> tuple[float | None, float | None]:
    """
    Interprete une valeur de bulletin.

    Returns
    -------
    (valeur, seuil) : la valeur si elle est quantifiee, sinon le seuil de
    detection lorsqu'une notation "< x" le donne. (None, None) pour une
    valeur non quantifiee sans seuil lisible.
    """
    s = (brut or "").strip()
    if s.lower() in CENSORED_TOKENS:
        return None, None

    m = _RE_INFERIEUR.match(s)
    if m:
        return None, _to_float(m.group(1))

    return _to_float(s), None


def _to_float(s: str) -> float:
    """Convertit en nombre en tolerant la virgule decimale et les espaces."""
    nettoye = (s.replace(" ", "").replace(" ", "")
                .replace(" ", "").replace(",", "."))
    try:
        return float(nettoye)
    except ValueError:
        raise IngestionError(f"Valeur illisible : {s!r}")


# ==========================================================================
# Lecture
# ==========================================================================

def read_bulletin(
    path: str | pathlib.Path | None = None,
    rows: dict[str, str] | None = None,
    default_unit: str = "%",
    censored_as: str = DEFAULT_CENSORED_MODE,
    delimiter: str = ",",
    langue: str = i18n.DEFAUT,
) -> BulletinReading:
    """
    Lit un bulletin d'analyse et rend de quoi alimenter le solveur.

    Parameters
    ----------
    path : fichier CSV, soit en format LARGE (une ligne d'intitules puis une
        ligne de valeurs), soit en format LONG (deux colonnes
        element, valeur).
    rows : alternative en memoire, {intitule: valeur}.
    default_unit : unite appliquee aux colonnes qui n'en declarent pas.
        Explicite par choix : une unite absente n'est jamais devinee, elle
        prend la valeur declaree ici, et le journal le mentionne colonne par
        colonne.
    censored_as : traitement des valeurs sous la limite de detection.
        "zero", "half" (convention geochimique, defaut) ou "threshold".
    langue : langue du JOURNAL. Il part dans la tracabilite du rapport
        client, donc il doit sortir dans la langue du document. La lecture
        est faite une fois par analyse, pour un document donne : il n'y a
        pas de journal partage entre deux langues.
    """
    lg = i18n.langue_valide(langue)
    if (path is None) == (rows is None):
        raise IngestionError("Fournir soit `path`, soit `rows`, mais pas les deux.")

    if default_unit not in CONCENTRATION_UNITS:
        raise IngestionError(
            f"Unite par defaut inconnue : {default_unit!r}. "
            f"Valeurs admises : {sorted(CONCENTRATION_UNITS)}"
        )
    if censored_as not in CENSORED_MODES:
        raise IngestionError(
            f"censored_as doit valoir l'une de {CENSORED_MODES}."
        )

    if rows is None:
        rows = _lire_fichier(pathlib.Path(path), delimiter)

    journal: list[str] = []
    warnings: list[str] = []
    colonnes: list[ColumnReading] = []
    valeurs: dict[str, float] = {}
    censures: dict[str, float] = {}

    for intitule, brut in rows.items():
        col = parse_column(intitule)
        colonnes.append(col)
        if not col.recognized:
            warnings.append(i18n.t("journal.colonne_ignoree", lg,
                                   intitule=intitule, raison=col.reason))
            continue

        valeur, seuil = parse_value(brut)
        unite = col.unit or default_unit
        if col.unit is None:
            journal.append(i18n.t("journal.unite_non_declaree", lg,
                                  intitule=intitule, unite=default_unit))
        facteur_unite = CONCENTRATION_UNITS[unite]

        if valeur is None and seuil is None:
            journal.append(i18n.t("journal.non_quantifie", lg,
                                  intitule=intitule))
            v = 0.0
        elif valeur is None:
            seuil_massique = seuil * facteur_unite
            v = {"zero": 0.0,
                 "half": 0.5 * seuil_massique,
                 "threshold": seuil_massique}[censored_as]
            censures[col.element] = seuil_massique
            libelle = i18n.t(f"journal.censure.{censored_as}", lg)
            journal.append(i18n.t("journal.sous_le_seuil", lg,
                                  intitule=intitule, seuil=seuil,
                                  unite=unite, traitement=libelle))
        else:
            v = valeur * facteur_unite

        if v < 0:
            raise IngestionError(
                f"{intitule} : teneur negative ({brut!r})."
            )

        if col.oxide:
            f = OXIDES[col.oxide].factor
            journal.append(i18n.t("journal.oxyde_converti", lg,
                                  intitule=intitule, oxyde=col.oxide,
                                  element=col.element, facteur=f))
            v *= f

        if col.element in valeurs:
            warnings.append(i18n.t("journal.colonnes_multiples", lg,
                                   element=col.element, intitule=intitule))
            valeurs[col.element] += v
        else:
            valeurs[col.element] = v

    if not valeurs:
        raise IngestionError(
            "Aucune colonne exploitable. Intitules lus : "
            f"{sorted(rows)}"
        )

    # Ordre canonique, elements doses seulement.
    mesures = [e for e in ELEMENTS if e in valeurs]
    b = np.array([valeurs[e] for e in mesures], dtype=float)

    total = float(b.sum())
    journal.append(i18n.t("journal.somme_lue", lg, total=total * 100))

    if "O" not in valeurs:
        journal.append(i18n.t("journal.oxygene_absent", lg))
    else:
        warnings.append(i18n.t("journal.oxygene_present", lg))

    if total > 1.02:
        warnings.append(i18n.t("journal.somme_excessive", lg,
                               total=total * 100))

    manquants = [e for e in ("Li", "Ni", "Co", "Mn") if e not in valeurs]
    if manquants:
        warnings.append(i18n.t("journal.cathode_absente", lg,
                               manquants=manquants))

    return BulletinReading(
        values=valeurs,
        measured_elements=mesures,
        b=b,
        censored=censures,
        columns=colonnes,
        journal=journal,
        warnings=warnings,
        meta={
            "source": str(path) if path else "memoire",
            "default_unit": default_unit,
            "censored_as": censored_as,
            "n_columns_read": len(colonnes),
        },
    )


def parse_rows(lignes: list[list[str]], origine: str = "bulletin") -> dict[str, str]:
    """
    Reconnait le format d'un CSV deja decoupe et rend {intitule: valeur}.

    Expose parce que l'interface graphique recoit un fichier TELEVERSE, en
    octets, et non un chemin. Sans ce point d'entree commun, l'adaptateur
    reimplemente la detection de format - et la rate : un bulletin large a
    deux colonnes, « Ni (%) ; Co (%) » suivi de « 16.20 ; 4.01 », se lisait
    comme un format long et produisait {"16.20": "4.01"}.

    Une seule reconnaissance de format dans le projet, donc, et un seul
    endroit a corriger.
    """
    lignes = [l for l in lignes if any(c.strip() for c in l)]
    if len(lignes) < 2:
        raise IngestionError(
            f"{origine} : au moins deux lignes non vides sont attendues."
        )

    # Format LONG : deux colonnes utiles, plusieurs lignes.
    if len(lignes) > 2 and all(len(l) >= 2 for l in lignes):
        premier = [c.strip().lower() for c in lignes[0][:2]]
        entete = premier[0] in ("element", "élément", "analyte", "parametre",
                                "paramètre", "composant")
        depart = 1 if entete else 0
        return {l[0].strip(): l[1].strip() for l in lignes[depart:]
                if l[0].strip()}

    # Format LARGE : intitules puis valeurs.
    entetes, vals = lignes[0], lignes[1]
    if len(vals) < len(entetes):
        vals = list(vals) + [""] * (len(entetes) - len(vals))
    return {h.strip(): v for h, v in zip(entetes, vals) if h.strip()}


def _lire_fichier(p: pathlib.Path, delimiter: str) -> dict[str, str]:
    """Lit un CSV sur disque et delegue la reconnaissance de format."""
    if not p.exists():
        raise IngestionError(f"Fichier introuvable : {p}")

    with p.open(encoding="utf-8-sig", newline="") as fh:
        return parse_rows(list(csv.reader(fh, delimiter=delimiter)), p.name)
