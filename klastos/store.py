"""
KLASTOS21 - Historique local des lots analyses.

A quoi il sert
--------------
Retrouver un lot six mois plus tard, comparer deux arrivages du meme
fournisseur, reproduire un rapport a l'identique quand un client conteste un
chiffre. C'est le genre de question qui arrive toujours, et toujours au
mauvais moment.

Ce qu'il enregistre, et ce qu'il n'enregistre pas
------------------------------------------------
Il enregistre ce qu'il faut pour REFAIRE l'analyse : le bulletin lu, la
provenance declaree, les seuils, la graine, les prix utilises. Il enregistre
aussi le rapport produit, pour pouvoir le ressortir sans recalcul.

Il n'enregistre aucun resultat qu'on ne saurait pas reproduire. Une base qui
conserverait un prix sans sa source et sa date fabriquerait exactement le
chiffre arbitraire que tout le protocole s'emploie a interdire.

DONNEE SENSIBLE. Un historique de lots est une donnee commerciale : teneurs,
fournisseurs, prix payes. Le fichier reste local, et rien ici ne l'envoie
nulle part.

Independance
------------
Ce module ne connait ni l'interface, ni la ligne de commande. Il parle
`Analyse` et SQLite, rien d'autre.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
import sqlite3
from dataclasses import dataclass

from .service import Analyse, Demande

#: Emplacement par defaut, a cote des donnees du projet.
CHEMIN_DEFAUT = pathlib.Path("data") / "historique.sqlite"

#: Version du schema. Un changement incompatible doit l'incrementer, et
#: `ouvrir` refusera une base plus recente que le code.
SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    cle   TEXT PRIMARY KEY,
    valeur TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id          TEXT NOT NULL,
    client          TEXT NOT NULL,
    analyse_le      TEXT NOT NULL,
    emis_le         TEXT,

    -- de quoi refaire l'analyse a l'identique
    bulletin        TEXT NOT NULL,   -- teneurs lues, JSON
    elements        TEXT NOT NULL,   -- ordre des elements doses, JSON
    provenance      TEXT NOT NULL,
    attestee        INTEGER NOT NULL,
    grades_declares TEXT,            -- JSON ou NULL
    tirages         INTEGER NOT NULL,
    graine          INTEGER NOT NULL,
    seuil_alerte    REAL NOT NULL,
    seuil_rejet     REAL NOT NULL,

    -- ce qui a ete trouve
    bouclage_statut TEXT NOT NULL,
    bouclage_total  REAL NOT NULL,
    degenerescence  INTEGER NOT NULL,

    -- valorisation, si elle a eu lieu
    devise          TEXT,
    prix_bas        REAL,
    prix_haut       REAL,
    prix_libelle    TEXT,
    prix_origine    TEXT,
    licence_rediffusion INTEGER,
    destinataire    TEXT NOT NULL,
    demo            INTEGER NOT NULL,

    rapport_markdown TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lots_lot_id ON lots(lot_id);
CREATE INDEX IF NOT EXISTS idx_lots_date   ON lots(analyse_le DESC);
"""


class StoreError(RuntimeError):
    """L'historique ne peut pas etre utilise en l'etat."""


@dataclass(frozen=True)
class Entree:
    """Une ligne d'historique, telle qu'on la relit."""

    id: int
    lot_id: str
    client: str
    analyse_le: _dt.datetime
    bouclage_statut: str
    bouclage_total: float
    degenerescence: int
    devise: str | None
    prix_bas: float | None
    prix_haut: float | None
    prix_libelle: str | None
    licence_rediffusion: bool | None
    destinataire: str
    demo: bool

    @property
    def valorise(self) -> bool:
        return self.prix_bas is not None

    def fourchette(self) -> str:
        if not self.valorise:
            return "sans valorisation"
        return (f"{self.prix_bas:,.0f}–{self.prix_haut:,.0f} "
                f"{self.devise}/t")


def ouvrir(chemin: str | pathlib.Path | None = None) -> sqlite3.Connection:
    """
    Ouvre - et cree au besoin - la base d'historique.

    Le refus de lire une base plus recente que le code est volontaire : une
    version ulterieure pourrait avoir ajoute une colonne dont l'absence
    fausserait silencieusement une relecture.
    """
    chemin = pathlib.Path(chemin or CHEMIN_DEFAUT)
    if chemin != pathlib.Path(":memory:"):
        chemin.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(str(chemin))
    cx.row_factory = sqlite3.Row
    cx.executescript(_SCHEMA)

    ligne = cx.execute("SELECT valeur FROM meta WHERE cle='schema'").fetchone()
    if ligne is None:
        cx.execute("INSERT INTO meta(cle, valeur) VALUES('schema', ?)",
                   (str(SCHEMA_VERSION),))
        cx.commit()
    elif int(ligne["valeur"]) > SCHEMA_VERSION:
        cx.close()
        raise StoreError(
            f"La base {chemin} est en schema {ligne['valeur']}, ce code lit "
            f"au plus le schema {SCHEMA_VERSION}. Mettez KLASTOS21 a jour "
            "plutot que de risquer une relecture incomplete."
        )
    return cx


def enregistrer(cx: sqlite3.Connection, analyse: Analyse,
                analyse_le: _dt.datetime | None = None) -> int:
    """
    Enregistre une analyse et rend son identifiant.

    Rien n'est recalcule ici : on range ce qui a ete produit.
    """
    d: Demande = analyse.demande or Demande()
    bouclage = analyse.incertitude.meta.get("closure")
    val = analyse.valorisation

    donnees = (
        analyse.rapport.lot_id,
        analyse.rapport.client,
        (analyse_le or _dt.datetime.now()).isoformat(timespec="seconds"),
        analyse.rapport.issued_on.isoformat(),

        json.dumps(analyse.lecture.values, ensure_ascii=False),
        json.dumps(analyse.lecture.measured_elements, ensure_ascii=False),
        d.provenance,
        int(d.attestee),
        json.dumps(list(d.grades_declares)) if d.grades_declares else None,
        d.tirages,
        d.graine,
        d.seuil_alerte,
        d.seuil_rejet,

        bouclage.status if bouclage else "",
        float(bouclage.total) if bouclage else 0.0,
        int(analyse.incertitude.degeneracy),

        val.currency if val else None,
        float(val.max_price_low) if val else None,
        float(val.max_price_high) if val else None,
        val.meta.get("prices_label") if val else None,
        val.meta.get("prices_origin") if val else None,
        int(bool(val.meta.get("redistribution_licensed"))) if val else None,
        d.destinataire,
        int(analyse.rapport.is_demo),

        analyse.rapport.to_markdown(),
    )
    cur = cx.execute(
        """INSERT INTO lots (
               lot_id, client, analyse_le, emis_le,
               bulletin, elements, provenance, attestee, grades_declares,
               tirages, graine, seuil_alerte, seuil_rejet,
               bouclage_statut, bouclage_total, degenerescence,
               devise, prix_bas, prix_haut, prix_libelle, prix_origine,
               licence_rediffusion, destinataire, demo, rapport_markdown
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        donnees,
    )
    cx.commit()
    return int(cur.lastrowid)


def _vers_entree(r: sqlite3.Row) -> Entree:
    return Entree(
        id=r["id"], lot_id=r["lot_id"], client=r["client"],
        analyse_le=_dt.datetime.fromisoformat(r["analyse_le"]),
        bouclage_statut=r["bouclage_statut"],
        bouclage_total=r["bouclage_total"],
        degenerescence=r["degenerescence"],
        devise=r["devise"], prix_bas=r["prix_bas"], prix_haut=r["prix_haut"],
        prix_libelle=r["prix_libelle"],
        licence_rediffusion=(None if r["licence_rediffusion"] is None
                             else bool(r["licence_rediffusion"])),
        destinataire=r["destinataire"], demo=bool(r["demo"]),
    )


def lister(cx: sqlite3.Connection, limite: int = 50,
           lot_id: str | None = None) -> list[Entree]:
    """Les analyses les plus recentes d'abord."""
    if lot_id:
        rows = cx.execute(
            "SELECT * FROM lots WHERE lot_id = ? "
            "ORDER BY analyse_le DESC, id DESC LIMIT ?",
            (lot_id, limite)).fetchall()
    else:
        rows = cx.execute(
            "SELECT * FROM lots ORDER BY analyse_le DESC, id DESC LIMIT ?",
            (limite,)).fetchall()
    return [_vers_entree(r) for r in rows]


def rapport(cx: sqlite3.Connection, entree_id: int) -> str:
    """Le rapport Markdown tel qu'il a ete emis, sans recalcul."""
    r = cx.execute("SELECT rapport_markdown FROM lots WHERE id = ?",
                   (entree_id,)).fetchone()
    if r is None:
        raise StoreError(f"Aucune analyse d'identifiant {entree_id}.")
    return r["rapport_markdown"]


def refaire(cx: sqlite3.Connection, entree_id: int) -> Demande:
    """
    Reconstruit la demande d'une analyse passee, a l'identique.

    Les prix ne sont PAS restitues : ils ont une date, et les ressortir
    telle quelle donnerait un jeu perime qui serait refuse - a juste titre.
    La demande rendue permet de rejouer la reconstitution ; la valorisation
    demande des prix d'aujourd'hui, fournis par l'appelant.
    """
    r = cx.execute("SELECT * FROM lots WHERE id = ?", (entree_id,)).fetchone()
    if r is None:
        raise StoreError(f"Aucune analyse d'identifiant {entree_id}.")

    teneurs = json.loads(r["bulletin"])
    grades = json.loads(r["grades_declares"]) if r["grades_declares"] else None
    return Demande(
        lignes={f"{el} (%)": f"{v * 100:.6f}" for el, v in teneurs.items()},
        lot_id=r["lot_id"],
        client=r["client"],
        provenance=r["provenance"],
        attestee=bool(r["attestee"]),
        grades_declares=tuple(grades) if grades else None,
        tirages=r["tirages"],
        graine=r["graine"],
        seuil_alerte=r["seuil_alerte"],
        seuil_rejet=r["seuil_rejet"],
        destinataire=r["destinataire"],
        emis_le=_dt.date.fromisoformat(r["emis_le"]) if r["emis_le"] else None,
    )


def supprimer(cx: sqlite3.Connection, entree_id: int) -> bool:
    """Retire une analyse. Rend True si une ligne a bien disparu."""
    cur = cx.execute("DELETE FROM lots WHERE id = ?", (entree_id,))
    cx.commit()
    return cur.rowcount > 0