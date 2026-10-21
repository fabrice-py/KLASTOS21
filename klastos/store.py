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
import decimal as _dec
import json
import pathlib
import sqlite3
from dataclasses import dataclass

from .service import Analyse, Demande

#: Emplacement par defaut, a cote des donnees du projet.
CHEMIN_DEFAUT = pathlib.Path("data") / "historique.sqlite"

#: Version du schema. Un changement incompatible doit l'incrementer, et
#: `ouvrir` refusera une base plus recente que le code.
#:
#: 1 -> 2 : ajout des tables `cotations` et `taux`. Migration SANS PERTE, par
#: construction : les deux tables sont creees a cote des anciennes, aucune
#: colonne existante ne bouge. Une base v1 s'ouvre, se complete et passe en 2.
SCHEMA_VERSION = 2

#: Les valeurs monetaires sont stockees en TEXT, pas en flottant.
#:
#: Un REAL SQLite est un double IEEE 754 : 15432.10 n'y est pas
#: representable exactement, et une relecture peut rendre 15432.099999999999.
#: Sur un prix a la tonne multiplie par une masse, l'ecart se voit. Le TEXT
#: conserve la valeur DECLAREE chiffre pour chiffre - c'est la meme
#: discipline que la provenance : on range ce qui a ete fourni, pas une
#: approximation de ce qui a ete fourni.
#:
#: La relecture rend des `Decimal`, jamais des `float`.
MONNAIE_EN_TEXTE = True

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

-- ---------------------------------------------------------------------
-- Historique des cotations. Schema 2.
--
-- Chaque ligne porte sa source, sa date de COTATION et sa date de
-- COLLECTE. Les deux ne se confondent pas : une moyenne mensuelle d'octobre
-- relevee le 15 novembre est cotee au 1er octobre et collectee le 15
-- novembre. Confondre les deux ferait passer un releve tardif pour une
-- donnee fraiche.
--
-- `valeur` est du TEXT : voir MONNAIE_EN_TEXTE.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cotations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    metal         TEXT NOT NULL,
    valeur        TEXT NOT NULL,            -- decimal exact, jamais un REAL
    devise        TEXT NOT NULL,
    base          TEXT NOT NULL DEFAULT 'metal',
    cote_le       TEXT NOT NULL,            -- date de cotation
    collecte_le   TEXT NOT NULL,            -- date de collecte
    source        TEXT NOT NULL,
    reference     TEXT NOT NULL,
    note          TEXT NOT NULL DEFAULT '',
    UNIQUE (source, reference, cote_le)
);

CREATE INDEX IF NOT EXISTS idx_cotations_metal
    ON cotations(metal, cote_le DESC);

-- ---------------------------------------------------------------------
-- Historique des taux de change. Schema 2.
--
-- Meme discipline que les cotations, et pour la meme raison : un taux sans
-- source ni date n'est opposable a personne. `taux` est du TEXT, parce
-- qu'un 1.0842 relu en flottant n'est plus le taux que la banque a cote.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS taux (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    paire         TEXT NOT NULL,
    valeur        TEXT NOT NULL,            -- decimal exact, jamais un REAL
    cote_le       TEXT NOT NULL,
    collecte_le   TEXT NOT NULL,
    source        TEXT NOT NULL,
    reference     TEXT NOT NULL,
    note          TEXT NOT NULL DEFAULT '',
    UNIQUE (source, reference, cote_le)
);

CREATE INDEX IF NOT EXISTS idx_taux_paire ON taux(paire, cote_le DESC);
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
        return cx

    trouvee = int(ligne["valeur"])
    if trouvee > SCHEMA_VERSION:
        cx.close()
        raise StoreError(
            f"La base {chemin} est en schema {ligne['valeur']}, ce code lit "
            f"au plus le schema {SCHEMA_VERSION}. Mettez KLASTOS21 a jour "
            "plutot que de risquer une relecture incomplete."
        )
    if trouvee < SCHEMA_VERSION:
        # MIGRATION SANS PERTE. `_SCHEMA` vient d'etre execute ci-dessus en
        # CREATE TABLE IF NOT EXISTS : les tables du schema 2 existent donc
        # desormais, et aucune colonne des tables du schema 1 n'a bouge. Il
        # ne reste qu'a inscrire la nouvelle version.
        #
        # On ne touche JAMAIS aux lignes existantes : un historique de lots
        # est une donnee commerciale, et une migration qui reecrirait des
        # lignes serait irreversible sur un fichier que personne ne sauvegarde.
        cx.execute("UPDATE meta SET valeur = ? WHERE cle = 'schema'",
                   (str(SCHEMA_VERSION),))
        cx.commit()
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

    NI LES PRIX, NI LES TAUX DE CHANGE NE SONT RESTITUES, et ce n'est pas
    un oubli.

    Un prix a une date. Le ressortir tel quel donnerait un jeu perime, qui
    serait refuse - a juste titre. Des prix d'il y a six mois rejoues
    aujourd'hui produiraient une valorisation fausse, et c'est precisement
    le genre de chiffre que ce logiciel refuse de fabriquer.

    Le meme raisonnement vaut mot pour mot pour un taux de change : la
    parite euro-dollar a varie de 0,95 a 1,17 sur vingt-quatre mois.
    `devise_cible` et `taux` restent donc a None, et l'appelant qui veut
    valoriser fournit les prix ET les taux du jour.

    La demande rendue permet de rejouer la RECONSTITUTION, qui ne depend
    d'aucun prix : teneurs, provenance, seuils, graine.
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


# ==========================================================================
# Historique des cotations et des taux. Schema 2.
# ==========================================================================
#
# Pourquoi des lectures en Decimal et jamais en float
# ---------------------------------------------------
# Un REAL SQLite est un double IEEE 754. 15432.10 n'y est pas representable
# exactement : une relecture peut rendre 15432.099999999999, et l'ecart se
# voit des qu'on multiplie par une masse. Les valeurs sont donc rangees en
# TEXT et relues en `Decimal`, ce qui conserve la valeur DECLAREE chiffre
# pour chiffre.

def _texte_monnaie(valeur: object, ou: str) -> str:
    """
    Normalise une valeur monetaire en texte decimal exact.

    Un float en entree est accepte - les structures amont en portent - mais
    il est converti via `repr`, qui rend la representation decimale la plus
    courte redonnant le meme double. On ne range donc jamais une
    approximation plus longue que la valeur fournie.
    """
    if isinstance(valeur, _dec.Decimal):
        texte = format(valeur, "f")
    elif isinstance(valeur, bool):
        raise StoreError(f"{ou} : un booleen n'est pas un montant.")
    elif isinstance(valeur, int):
        texte = str(valeur)
    elif isinstance(valeur, float):
        texte = repr(valeur)
    else:
        texte = str(valeur).strip().replace(",", ".")
    try:
        _dec.Decimal(texte)
    except _dec.InvalidOperation:
        raise StoreError(
            f"{ou} : valeur {valeur!r} non decimale. Les montants sont "
            "ranges en texte decimal exact, jamais en flottant."
        ) from None
    return texte


def _date_texte(valeur: object, ou: str) -> str:
    if isinstance(valeur, _dt.datetime):
        return valeur.date().isoformat()
    if isinstance(valeur, _dt.date):
        return valeur.isoformat()
    try:
        return _dt.date.fromisoformat(str(valeur).strip()[:10]).isoformat()
    except ValueError:
        raise StoreError(
            f"{ou} : date {valeur!r} illisible. Format attendu : AAAA-MM-JJ."
        ) from None


@dataclass(frozen=True)
class Cotation:
    """Une cotation relue de l'historique. `valeur` est un Decimal exact."""

    id: int
    metal: str
    valeur: _dec.Decimal
    devise: str
    base: str
    cote_le: _dt.date
    collecte_le: _dt.date
    source: str
    reference: str
    note: str = ""


@dataclass(frozen=True)
class Taux:
    """Un taux relu de l'historique. `valeur` est un Decimal exact."""

    id: int
    paire: str
    valeur: _dec.Decimal
    cote_le: _dt.date
    collecte_le: _dt.date
    source: str
    reference: str
    note: str = ""


def _cotation(r: sqlite3.Row) -> Cotation:
    return Cotation(
        id=r["id"], metal=r["metal"], valeur=_dec.Decimal(r["valeur"]),
        devise=r["devise"], base=r["base"],
        cote_le=_dt.date.fromisoformat(r["cote_le"]),
        collecte_le=_dt.date.fromisoformat(r["collecte_le"]),
        source=r["source"], reference=r["reference"], note=r["note"] or "")


def _ligne_taux(r: sqlite3.Row) -> Taux:
    return Taux(
        id=r["id"], paire=r["paire"], valeur=_dec.Decimal(r["valeur"]),
        cote_le=_dt.date.fromisoformat(r["cote_le"]),
        collecte_le=_dt.date.fromisoformat(r["collecte_le"]),
        source=r["source"], reference=r["reference"], note=r["note"] or "")


# --------------------------------------------------------------------------
# Enregistrement
# --------------------------------------------------------------------------

def enregistrer_cotations(cx: sqlite3.Connection, prix,
                          collecte_le: _dt.date | None = None) -> int:
    """
    Range les cotations d'un `PriceSet`. Rend le nombre de lignes neuves.

    La contrainte d'unicite porte sur (source, reference, date de cotation) :
    relever deux fois le meme flux le meme jour ne cree pas de doublon, et
    c'est voulu - un historique qui compterait deux fois la meme cotation
    fausserait toute serie construite dessus.

    Un meme (source, reference, date) portant DEUX METAUX differents leve,
    au lieu d'en perdre un en silence. En pratique un libelle de reference
    est propre a un metal - « LME Nickel cash » - mais rien ne l'impose a un
    fournisseur, et une perte silencieuse serait invisible.
    """
    collecte = _date_texte(collecte_le or _dt.date.today(),
                           "date de collecte")
    neuves = 0
    for metal, p in sorted(prix.prices.items()):
        cle = (p.source, p.reference_name, _date_texte(p.as_of, metal))
        existant = cx.execute(
            "SELECT metal FROM cotations "
            "WHERE source = ? AND reference = ? AND cote_le = ?", cle
        ).fetchone()
        if existant is not None:
            if existant["metal"] != metal:
                raise StoreError(
                    f"{p.source} / {p.reference_name} au {cle[2]} porte deja "
                    f"{existant['metal']!r}, et on tente d'y ranger "
                    f"{metal!r}. Deux metaux ne peuvent pas partager une "
                    "reference a la meme date : corrigez le libelle de "
                    "reference du fournisseur."
                )
            continue
        cx.execute(
            "INSERT INTO cotations(metal, valeur, devise, base, cote_le, "
            "collecte_le, source, reference, note) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (metal, _texte_monnaie(p.value_per_tonne, metal), p.currency,
             getattr(p, "basis", "metal"), cle[2], collecte,
             p.source, p.reference_name, getattr(p, "note", "") or ""),
        )
        neuves += 1
    cx.commit()
    return neuves


def enregistrer_taux(cx: sqlite3.Connection, taux,
                     collecte_le: _dt.date | None = None) -> int:
    """
    Range des `ExchangeRate`. Rend le nombre de lignes neuves.

    Meme contrainte d'unicite, et pour la meme raison que les cotations.
    """
    collecte = _date_texte(collecte_le or _dt.date.today(),
                           "date de collecte")
    liste = [taux] if hasattr(taux, "pair") else list(taux)

    neuves = 0
    for t in liste:
        cle = (t.source, t.reference_name, _date_texte(t.as_of, t.pair))
        deja = cx.execute(
            "SELECT paire FROM taux "
            "WHERE source = ? AND reference = ? AND cote_le = ?", cle
        ).fetchone()
        if deja is not None:
            if deja["paire"] != t.pair:
                raise StoreError(
                    f"{t.source} / {t.reference_name} au {cle[2]} porte deja "
                    f"{deja['paire']!r}, et on tente d'y ranger "
                    f"{t.pair!r}. Corrigez le libelle de reference."
                )
            continue
        cx.execute(
            "INSERT INTO taux(paire, valeur, cote_le, collecte_le, source, "
            "reference, note) VALUES(?,?,?,?,?,?,?)",
            (t.pair, _texte_monnaie(t.rate, t.pair), cle[2], collecte,
             t.source, t.reference_name, getattr(t, "note", "") or ""),
        )
        neuves += 1
    cx.commit()
    return neuves


# --------------------------------------------------------------------------
# Les deux requetes neuves
# --------------------------------------------------------------------------

def prix_a_la_date(cx: sqlite3.Connection, metal: str,
                   date: _dt.date | str,
                   source: str | None = None) -> Cotation | None:
    """
    La cotation d'un metal A UNE DATE DONNEE.

    Rend la cotation la plus recente a cette date OU AVANT, parce que c'est
    la question reellement posee : « que valait le nickel le 15 octobre » a
    une reponse meme si la source ne cote pas tous les jours - une moyenne
    mensuelle, un fixing hebdomadaire. Rendre None des qu'il n'y a pas de
    ligne au jour exact obligerait l'appelant a refaire cette recherche, et
    il la referait moins bien.

    Rend None si aucune cotation n'existe a cette date ou avant : c'est un
    resultat, pas une erreur, et surtout pas un zero.
    """
    jour = _date_texte(date, f"prix_a_la_date({metal})")
    requete = "SELECT * FROM cotations WHERE metal = ? AND cote_le <= ?"
    params: list[object] = [metal, jour]
    if source is not None:
        requete += " AND source = ?"
        params.append(source)
    requete += " ORDER BY cote_le DESC, id DESC LIMIT 1"
    r = cx.execute(requete, params).fetchone()
    return _cotation(r) if r is not None else None


def serie_prix(cx: sqlite3.Connection, metal: str,
               depuis: _dt.date | str, jusqu_a: _dt.date | str,
               source: str | None = None) -> list[Cotation]:
    """
    La serie des cotations d'un metal SUR UNE PERIODE, par date croissante.

    Bornes INCLUSES. Une periode vide rend une liste vide, jamais une
    erreur : « ce fournisseur n'a rien cote en aout » est une reponse.
    """
    a, b = _date_texte(depuis, "depuis"), _date_texte(jusqu_a, "jusqu_a")
    if a > b:
        raise StoreError(
            f"Periode inversee : {a} apres {b}. Les bornes sont (depuis, "
            "jusqu_a)."
        )
    requete = ("SELECT * FROM cotations WHERE metal = ? "
               "AND cote_le >= ? AND cote_le <= ?")
    params: list[object] = [metal, a, b]
    if source is not None:
        requete += " AND source = ?"
        params.append(source)
    requete += " ORDER BY cote_le ASC, id ASC"
    return [_cotation(r) for r in cx.execute(requete, params)]


def taux_a_la_date(cx: sqlite3.Connection, paire: str,
                   date: _dt.date | str,
                   source: str | None = None) -> Taux | None:
    """Le taux d'une paire a une date donnee, ou avant. Meme regle."""
    jour = _date_texte(date, f"taux_a_la_date({paire})")
    requete = "SELECT * FROM taux WHERE paire = ? AND cote_le <= ?"
    params: list[object] = [paire.strip().upper(), jour]
    if source is not None:
        requete += " AND source = ?"
        params.append(source)
    requete += " ORDER BY cote_le DESC, id DESC LIMIT 1"
    r = cx.execute(requete, params).fetchone()
    return _ligne_taux(r) if r is not None else None


def serie_taux(cx: sqlite3.Connection, paire: str,
               depuis: _dt.date | str, jusqu_a: _dt.date | str,
               source: str | None = None) -> list[Taux]:
    """La serie des taux d'une paire sur une periode, bornes incluses."""
    a, b = _date_texte(depuis, "depuis"), _date_texte(jusqu_a, "jusqu_a")
    if a > b:
        raise StoreError(f"Periode inversee : {a} apres {b}.")
    requete = ("SELECT * FROM taux WHERE paire = ? "
               "AND cote_le >= ? AND cote_le <= ?")
    params: list[object] = [paire.strip().upper(), a, b]
    if source is not None:
        requete += " AND source = ?"
        params.append(source)
    requete += " ORDER BY cote_le ASC, id ASC"
    return [_ligne_taux(r) for r in cx.execute(requete, params)]
