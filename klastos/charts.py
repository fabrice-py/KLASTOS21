"""
KLASTOS21 - Graphiques de l'interface.

Regle unique, et elle gouverne tout ce fichier
----------------------------------------------
UN GRAPHIQUE NE MONTRE JAMAIS CE QUE LA DONNEE NE PORTE PAS.

C'est plus exigeant qu'il n'y parait. Un camembert de phases minerales
sommant a 100 %, avec une part par phase, est le visuel que tout le monde
attend - et il est faux sur une black mass. Mesure a l'appui : deux
assemblages differant de 2,86 points sur le PVDF produisent le meme bulletin
d'analyse a 3e-15 point pres. Le solveur en choisit un pour des raisons
numeriques, pas physiques. Dessiner sa part, c'est afficher un arbitrage
d'algorithme comme un resultat de mesure.

D'ou les deux principes :

  1. Le camembert porte la COMPOSITION ELEMENTAIRE, qui est ferme, plus
     l'oxygene predit et la masse non expliquee. Son total fait 100 % sans
     mentir. Il bascule automatiquement sur les phases le jour ou celles-ci
     deviennent fermes - une quantification DRX de deux phases y suffit.
  2. Les phases non identifiables se dessinent en BARRES D'INTERVALLE, qui
     montrent une etendue et non un point.

Ce module ne calcule rien d'autre que de la mise en forme. Il recoit une
`Analyse` et rend des specifications Altair.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

from klastos.service import Analyse

# ==========================================================================
# Palette. Reprise du rapport imprime : l'ecran et le document doivent
# parler le meme langage visuel.
# ==========================================================================

COBALT = "#1F45C8"
AMBRE = "#8A5410"
ROUILLE = "#9D3A1C"
ARDOISE = "#5A6472"
ENCRE = "#13171E"
TRAIT = "#DBE1E9"

#: Couleur par statut. Elle porte un sens, jamais une decoration.
COULEUR_STATUT = {
    "ferme": COBALT,
    "ferme_large": AMBRE,
    "ouvert": ROUILLE,
}

#: Teintes des elements. Ordonnees pour que les majeurs se distinguent.
PALETTE_ELEMENTS = [
    "#1F45C8", "#3C6BE0", "#6B8FEA", "#0E8A7D", "#2BB3A3",
    "#8A5410", "#C08A2E", "#9D3A1C", "#C76A4A", "#6B5BA8",
]

#: Gris reserve a ce que le modele n'explique pas. Jamais utilise ailleurs :
#: cette part doit se reconnaitre d'un coup d'oeil.
GRIS_INEXPLIQUE = "#B7BFCA"
GRIS_PREDIT = "#8E97A4"

POLICE = "IBM Plex Sans, -apple-system, Segoe UI, Roboto, sans-serif"
MONO = "IBM Plex Mono, ui-monospace, Consolas, monospace"


def _base(chart: alt.Chart, hauteur: int) -> alt.Chart:
    """Reglages communs : pas de titre parasite, pas de grille criarde."""
    return chart.properties(height=hauteur).configure_view(
        strokeWidth=0
    ).configure_axis(
        labelFont=POLICE, titleFont=POLICE, labelColor=ARDOISE,
        titleColor=ARDOISE, labelFontSize=11, titleFontSize=11,
        grid=False, domainColor=TRAIT, tickColor=TRAIT,
    ).configure_legend(
        labelFont=POLICE, titleFont=POLICE, labelColor=ENCRE,
        titleColor=ARDOISE, labelFontSize=11, titleFontSize=10,
        symbolType="square", symbolSize=110,
    )


# ==========================================================================
# 1. Camembert de composition
# ==========================================================================

def donnees_composition(analyse: Analyse) -> tuple[pd.DataFrame, str]:
    """
    Rend le tableau du camembert et le MODE retenu.

    Deux modes, choisis par la donnee et non par un reglage :

      "phases"   toutes les phases sont fermes - le cas d'un lot dont la
                 mineralogie est contrainte, par exemple par une DRX. Le
                 camembert porte alors les phases, comme on l'attend.
      "elements" sinon. Les teneurs elementaires sont fermes quoi qu'il
                 arrive ; l'oxygene est predit ; le reste est la masse que
                 le modele n'explique pas.

    Dans les deux cas le total fait 100 % sans qu'aucun chiffre soit force.
    """
    phases = [r for r in analyse.incertitude.results if r.block == "phase"
              or r.block == "ventilation"]
    toutes_fermes = bool(phases) and all(r.identifiable for r in phases)

    if toutes_fermes:
        lignes = [{"part": r.label, "valeur": r.median, "famille": "phase"}
                  for r in phases if r.median > 1e-4]
        reste = 1.0 - sum(l["valeur"] for l in lignes)
        if reste > 1e-4:
            lignes.append({"part": "Masse non expliquée", "valeur": reste,
                           "famille": "inexplique"})
        return pd.DataFrame(lignes), "phases"

    # Composition RECONSTITUEE, A @ x, et non les teneurs du bulletin.
    #
    # La difference est petite - 0,007 point au plus sur un bulletin
    # coherent - mais elle decide de la rigueur du camembert. Les teneurs
    # lues, augmentees de l'oxygene predit, ne bouclent pas exactement a la
    # masse expliquee : il reste le residu d'ajustement. Melanger les deux
    # donnait un total de 100,01 %, et aurait oblige soit a tricher sur la
    # part grise, soit a afficher un camembert qui ne boucle pas.
    #
    # Sum(A @ x) vaut exactement sum(x), donc exactement la masse
    # expliquee : le total fait 100 % par construction, et chaque part est
    # celle que le rapport annonce ailleurs.
    from klastos.phases import stoichiometry_matrix

    central = analyse.incertitude.meta["central"]
    A, els, _ = stoichiometry_matrix(phase_keys=analyse.phases_retenues)
    ajuste = A @ central.x
    doses = set(analyse.lecture.measured_elements)

    lignes = []
    for el, v in sorted(zip(els, ajuste), key=lambda kv: -kv[1]):
        if v <= 1e-5:
            continue
        lignes.append({
            "part": el if el in doses else f"{el} (prédit)",
            "valeur": float(v),
            "famille": "element" if el in doses else "predit",
        })
    inexplique = max(0.0, float(central.unexplained_mass))
    if inexplique > 1e-5:
        lignes.append({"part": "Masse non expliquée", "valeur": inexplique,
                       "famille": "inexplique"})
    return pd.DataFrame(lignes), "elements"


def camembert(analyse: Analyse, taille: int = 320) -> alt.Chart:
    """Le camembert de la maquette, avec des parts que la donnee porte."""
    df, _mode = donnees_composition(analyse)
    df = df.copy()
    df["pourcent"] = df["valeur"] * 100.0
    df["etiquette"] = df["pourcent"].map(lambda v: f"{v:.1f} %")

    couleurs, ordre = [], []
    i = 0
    for _, r in df.iterrows():
        ordre.append(r["part"])
        if r["famille"] == "inexplique":
            couleurs.append(GRIS_INEXPLIQUE)
        elif r["famille"] == "predit":
            couleurs.append(GRIS_PREDIT)
        else:
            couleurs.append(PALETTE_ELEMENTS[i % len(PALETTE_ELEMENTS)])
            i += 1

    arc = alt.Chart(df).mark_arc(innerRadius=taille * 0.30,
                                 outerRadius=taille * 0.46,
                                 stroke="#FFFFFF", strokeWidth=2).encode(
        theta=alt.Theta("pourcent:Q", stack=True),
        color=alt.Color("part:N", title=None,
                        scale=alt.Scale(domain=ordre, range=couleurs),
                        legend=alt.Legend(orient="right", columns=1,
                                          labelLimit=140, symbolSize=90,
                                          rowPadding=1)),
        order=alt.Order("pourcent:Q", sort="descending"),
        tooltip=[alt.Tooltip("part:N", title="Part"),
                 alt.Tooltip("etiquette:N", title="% massique")],
    )
    return _base(arc, taille).configure_view(strokeWidth=0)


# ==========================================================================
# 2. Teneurs elementaires du bulletin
# ==========================================================================

def barres_elements(analyse: Analyse, hauteur: int = 230) -> alt.Chart:
    """
    Les teneurs dosees, par ordre decroissant.

    Ce sont les seules grandeurs que le bulletin donne directement. Elles
    sont fermes : une barre pleine est ici legitime.
    """
    df = pd.DataFrame(
        [{"element": el, "teneur": v * 100.0}
         for el, v in analyse.lecture.values.items()]
    ).sort_values("teneur", ascending=False)
    df["etiquette"] = df["teneur"].map(lambda v: f"{v:.2f}")

    base = alt.Chart(df).encode(
        x=alt.X("element:N", sort="-y", title=None,
                axis=alt.Axis(labelAngle=0)),
        y=alt.Y("teneur:Q", title="% massique"),
        tooltip=[alt.Tooltip("element:N", title="Élément"),
                 alt.Tooltip("teneur:Q", title="% massique", format=".3f")],
    )
    barres = base.mark_bar(size=26, cornerRadiusTopLeft=3,
                           cornerRadiusTopRight=3, color=COBALT)
    texte = base.mark_text(dy=-8, font=MONO, fontSize=10,
                           color=ARDOISE).encode(text="etiquette:N")
    return _base(barres + texte, hauteur)


# ==========================================================================
# 3. Domaines compatibles - la signature du produit
# ==========================================================================

def _statut(r) -> str:
    from klastos.uncertainty import WELL_DETERMINED_WIDTH

    if not r.identifiable:
        return "ouvert"
    largeur = r.total_upper - r.total_lower
    return "ferme" if largeur <= WELL_DETERMINED_WIDTH else "ferme_large"


LIBELLE_STATUT = {
    "ferme": "déterminé",
    "ferme_large": "mal déterminé",
    "ouvert": "domaine compatible",
}


def donnees_domaines(analyse: Analyse) -> pd.DataFrame:
    """Une ligne par phase, avec ses bornes et son statut."""
    lignes = []
    for r in analyse.incertitude.results:
        if r.block not in ("phase", "ventilation"):
            continue
        s = _statut(r)
        lignes.append({
            "phase": r.label.split(" (")[0],
            "bas": r.total_lower * 100.0,
            "haut": r.total_upper * 100.0,
            "centre": r.median * 100.0,
            "largeur": (r.total_upper - r.total_lower) * 100.0,
            "statut": s,
            "libelle": LIBELLE_STATUT[s],
            "valeur": r.format_value(),
        })
    return pd.DataFrame(lignes).sort_values("haut", ascending=False)


def barres_domaines(analyse: Analyse, hauteur: int | None = None) -> alt.Chart:
    """
    CE GRAPHIQUE EST L'ARGUMENT DU PRODUIT.

    Un trait fin se lit « determine ». Une bande large se lit « toute valeur
    de cette bande explique le bulletin aussi bien ». Aucune phrase ne fait
    comprendre cela aussi vite.
    """
    df = donnees_domaines(analyse)
    hauteur = hauteur or max(200, 30 * len(df))
    ordre = list(df["phase"])
    plafond = float(df["haut"].max()) * 1.04

    # UNE SEULE COUCHE. Une piste grise superposee semblait une bonne idee ;
    # en pratique les deux couches recevaient des echelles de bande
    # legerement differentes, les libelles se retrouvaient entre deux
    # barres, et l'axe des x partait a -5 % faute de domaine explicite.
    # Une grandeur a largeur nulle garde une marque visible grace a
    # `size` minimal : un trait, qui est precisement ce qu'il faut lire.
    barres = alt.Chart(df).mark_bar(height=13, cornerRadius=2).encode(
        y=alt.Y("phase:N", sort=ordre, title=None,
                axis=alt.Axis(labelLimit=200)),
        x=alt.X("bas:Q", title="% massique",
                scale=alt.Scale(domain=[0, plafond], nice=False)),
        x2="haut:Q",
        color=alt.Color(
            "libelle:N", title=None,
            scale=alt.Scale(
                domain=[LIBELLE_STATUT[s] for s in
                        ("ferme", "ferme_large", "ouvert")],
                range=[COBALT, AMBRE, ROUILLE]),
            legend=alt.Legend(orient="bottom", direction="horizontal")),
        tooltip=[alt.Tooltip("phase:N", title="Phase"),
                 alt.Tooltip("valeur:N", title="% massique"),
                 alt.Tooltip("libelle:N", title="Statut")],
    )
    # Marqueur de la valeur centrale, utile sur une bande large.
    reperes = alt.Chart(df[df["statut"] != "ouvert"]).mark_tick(
        thickness=2, size=15, color=ENCRE, opacity=.55).encode(
        y=alt.Y("phase:N", sort=ordre, title=None),
        x=alt.X("centre:Q", scale=alt.Scale(domain=[0, plafond], nice=False)),
    )
    return _base(barres + reperes, hauteur)


# ==========================================================================
# 4. Bouclage massique
# ==========================================================================

def barre_bouclage(analyse: Analyse, hauteur: int = 64) -> alt.Chart:
    """
    Masse expliquee contre masse inexpliquee, en une barre empilee.

    La part grise n'est pas un defaut d'affichage : c'est le diagnostic.
    Humidite, phase absente du modele, ou provenance mal declaree.
    """
    central = analyse.incertitude.meta["central"]
    expliquee = float(central.explained_mass) * 100.0
    reste = max(0.0, 100.0 - expliquee)
    df = pd.DataFrame([
        {"part": "Masse expliquée par le modèle", "valeur": expliquee,
         "ordre": 0},
        {"part": "Masse non expliquée", "valeur": reste, "ordre": 1},
    ])
    bouclage = analyse.incertitude.meta.get("closure")
    teinte = {"ok": COBALT, "alerte": AMBRE, "rejet": ROUILLE}.get(
        bouclage.status if bouclage else "ok", COBALT)

    ch = alt.Chart(df).mark_bar(height=22, cornerRadius=3).encode(
        x=alt.X("valeur:Q", stack="zero", title=None,
                scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("part:N", title=None,
                        scale=alt.Scale(
                            domain=["Masse expliquée par le modèle",
                                    "Masse non expliquée"],
                            range=[teinte, GRIS_INEXPLIQUE]),
                        legend=alt.Legend(orient="bottom")),
        order=alt.Order("ordre:Q"),
        tooltip=[alt.Tooltip("part:N", title=""),
                 alt.Tooltip("valeur:Q", title="%", format=".2f")],
    )
    return _base(ch, hauteur)


# ==========================================================================
# 5. Ce qu'un dosage apporterait
# ==========================================================================

def barres_scenario(analyse: Analyse, hauteur: int | None = None) -> alt.Chart | None:
    """
    Largeur actuelle contre largeur apres dosage, par grandeur.

    Rend None si aucun scenario n'a lieu d'etre - par exemple quand
    l'oxygene a bien ete dose.
    """
    scenarios = analyse.incertitude.meta.get("scenarios") or []
    if not scenarios or not scenarios[0].rows:
        return None
    sc = scenarios[0]
    df = pd.DataFrame([
        {"grandeur": r.label.split(" (")[0],
         "avant": r.width_open * 100.0,
         "apres": r.width_conditional * 100.0,
         "verdict": "deviendrait ferme" if r.becomes_firm
                    else "resterait ouverte"}
        for r in sc.rows
    ])
    df = df.sort_values("avant", ascending=False)
    hauteur = hauteur or max(170, 30 * len(df))

    # ORDRE EXPLICITE, partage par les deux couches. Avec un
    # `EncodingSortField` pose separement sur chacune, les deux echelles de
    # bande ne coincident pas toujours : les barres « avant » et « apres »
    # se retrouvent sur deux lignes au lieu d'etre superposees.
    ordre = list(df["grandeur"])
    plafond = float(df["avant"].max()) * 1.04

    avant = alt.Chart(df).mark_bar(height=13, color="#E6EAF0",
                                   cornerRadius=2).encode(
        y=alt.Y("grandeur:N", sort=ordre, title=None,
                axis=alt.Axis(labelLimit=180)),
        x=alt.X("avant:Q", title="largeur, en points de masse",
                scale=alt.Scale(domain=[0, plafond], nice=False)),
        tooltip=[alt.Tooltip("grandeur:N", title="Grandeur"),
                 alt.Tooltip("avant:Q", title="aujourd'hui", format=".2f"),
                 alt.Tooltip("apres:Q", title="après dosage", format=".2f")],
    )
    apres = alt.Chart(df).mark_bar(height=13, cornerRadius=2).encode(
        y=alt.Y("grandeur:N", sort=ordre, title=None),
        x=alt.X("apres:Q", scale=alt.Scale(domain=[0, plafond], nice=False)),
        color=alt.Color("verdict:N", title=None,
                        scale=alt.Scale(
                            domain=["deviendrait ferme", "resterait ouverte"],
                            range=[COBALT, ROUILLE]),
                        legend=alt.Legend(orient="bottom")),
    )
    return _base(avant + apres, hauteur)