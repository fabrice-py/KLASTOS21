"""
KLASTOS21 - Assemblage du rapport client.

Ce module ne calcule rien. Il assemble les sorties des modules amont en un
livrable, et il fait respecter les engagements du protocole au moment ou le
resultat quitte le systeme.

Trois responsabilites, et trois seulement
-----------------------------------------
1. SEPARER ce qui est ferme de ce qui ne l'est pas. Un client ne doit jamais
   avoir a deviner quel chiffre il peut opposer a son fournisseur.
2. PORTER les mentions normalisees du protocole : non-identifiabilite, note
   carbone, piege du sommet, limite de detection des attestations.
3. REFUSER de sortir. Une donnee synthetique, une source de prix de
   demonstration ou un bulletin hors tolerance ne doivent pas produire de
   livrable presentable.

Ce que le rapport ne fait jamais
--------------------------------
- Afficher une valeur ponctuelle pour une grandeur non identifiable.
- Presenter une valorisation sans sa fourchette.
- Omettre la provenance d'un prix ou le texte d'une attestation.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

from .identifiability import NOTE_CARBONE, NOTE_NON_IDENTIFIABLE
from .uncertainty import (AVERTISSEMENT_SOMMET, SOURCE_STRUCTURELLE,
                          WELL_DETERMINED_WIDTH, UncertaintyReport)
from .valuation import Valuation

# Mentions reprises telles quelles du protocole.
MENTION_DETECTION = (
    "Le controle du residu ne detecte pas une declaration de provenance "
    "inexacte en dessous d'environ 5 % de phase non declaree. Une absence "
    "d'alerte ne vaut pas certification de la declaration."
)

MENTION_VALORISATION = (
    "La valorisation ne repose que sur les teneurs elementaires, qui sont "
    "identifiables. Aucune ventilation par grade n'entre dans le calcul du prix."
)

MENTION_MAL_DETERMINE = (
    "Grandeur identifiable mais mal determinee : le systeme la contraint en "
    "theorie, mais son conditionnement est tel que la fourchette reste trop "
    "large pour etre exploitee en l'etat. L'identifiabilite est binaire, le "
    "conditionnement est continu."
)

MENTION_FOURCHETTE = (
    "Les valeurs sont rapportees en fourchette. La largeur reflete "
    "l'incertitude analytique sur les teneurs fermes."
)

#: Destinataires possibles d'un rapport. Le systeme ne devine pas si un
#: document sort de la maison : il le demande.
DESTINATAIRE_TIERS = "tiers"
DESTINATAIRE_INTERNE = "interne"

REFUS_REDIFFUSION = (
    "Prix d'agence sans licence de rediffusion ({label}). Un abonnement "
    "d'agence couvre l'usage interne, pas l'affichage dans un document "
    "remis a un tiers. Trois issues : obtenir l'autorisation ecrite de "
    "l'agence et relancer la recuperation avec la licence, demander au "
    "client ses propres prix, ou emettre ce rapport en interne "
    "(destinataire='interne')."
)

#: Titre de la section de scenario. Le rendu HTML s'y reconnait, donc il est
#: nomme une fois et reutilise.
TITRE_SCENARIO = "Scenario : et si l'oxygene etait dose"

TITRE_DRX = "Quantification structurale (diffraction)"

MENTION_DRX = (
    "Une quantification par diffraction est une MESURE, avec son incertitude. "
    "Elle entre donc en encadrement et non en egalite : elle resserre les "
    "plages compatibles, elle ne rend aucune grandeur ferme. Le tableau donne "
    "la plage avant et apres."
)

MENTION_DRX_CONFLIT = (
    "Taux de conflit eleve entre la quantification et le bulletin : pour une "
    "part importante des tirages de bruit analytique, aucune repartition des "
    "phases ne satisfait les deux mesures. Ces tirages ont ete CONSERVES avec "
    "leurs bornes non contraintes - les ecarter aurait resserre l'incertitude "
    "du laboratoire au motif d'une mesure qui ne porte pas sur elle. Un taux "
    "eleve signale une analyse chimique, une quantification ou un modele de "
    "phases a reprendre."
)

#: Au-dela de cette part de tirages en conflit, le rapport avertit.
DRX_CONFLIT_ALERTE = 0.20

TITRE_CONSEIL = "Quelle quantification commander"

#: Libelles de statut par defaut : le statut repond alors a la question
#: "cette grandeur est-elle determinee ?".
LIBELLES_STATUT = {
    "ferme": "ferme",
    "ferme_large": "ferme mais **mal determine**",
    "ouvert": "**non identifiable**",
}

#: Sections ou le statut repond a une AUTRE question, parce que leurs valeurs
#: sont des largeurs et non des positions. Table unique, consommee par les
#: deux rendus : sans elle, le Markdown disait "ferme" la ou le HTML disait
#: "reductible", et les deux documents se contredisaient sur la meme ligne.
LIBELLES_STATUT_PAR_SECTION: dict[str, dict[str, str]] = {
    "Comment reduire l'incertitude": {
        "ferme": "reductible", "ferme_large": "reductible",
        "ouvert": "**irreductible**",
    },
    "Grandeurs sensibles a la qualite du bulletin": {
        "ferme": "reductible", "ferme_large": "reductible",
        "ouvert": "**irreductible**",
    },
    TITRE_SCENARIO: {
        "ferme": "deviendrait ferme", "ferme_large": "deviendrait ferme",
        "ouvert": "resterait ouverte",
    },
    TITRE_DRX: {
        "ferme": "resserree", "ferme_large": "resserree",
        "ouvert": "inchangee",
    },
    TITRE_CONSEIL: {
        "ferme": "gain acquis au pire cas",
        "ferme_large": "gain acquis au pire cas",
        "ouvert": "sans effet",
    },
}


def libelle_statut(section_title: str, status: str) -> str:
    """Libelle du statut, selon la question que pose la section."""
    table = LIBELLES_STATUT_PAR_SECTION.get(section_title, LIBELLES_STATUT)
    return table.get(status, "")

MENTION_CONSEIL = (
    "Une quantification par diffraction se paie, et toutes les phases ne la "
    "valent pas. Les gains annonces sont des PLANCHERS : ils sont pris au "
    "pire placement de la valeur mesuree dans la plage compatible, parce que "
    "cette valeur est inconnue avant la mesure."
)

MENTION_SCENARIO = (
    "Aucun chiffre de cette section n'est opposable. Ce sont des LARGEURS "
    "PROJETEES sous l'hypothese d'un dosage que vous ne possedez pas. Elles "
    "ne modifient en rien les resultats des sections precedentes, qui restent "
    "les seuls engages."
)

#: Base de mesure des largeurs du scenario. Sans cette mention, le client lit
#: deux largeurs differentes pour la meme grandeur dans deux sections, sans
#: comprendre qu'elles ne mesurent pas la meme chose.
MENTION_SCENARIO_BASE = (
    "Les largeurs de cette section sont les largeurs STRUCTURELLES du "
    "bulletin central : la part de l'incertitude qui vient de la "
    "degenerescence, et elle seule. Elles sont plus etroites que les "
    "fourchettes des sections precedentes, qui ajoutent l'incertitude "
    "analytique du laboratoire. Un dosage d'oxygene ne reduit que la part "
    "structurelle ; la part analytique, elle, demande un meilleur "
    "laboratoire ou des replicats."
)

#: Avertissement de fond, verrouille par un test. Il interdit la seule
#: facon simple - et fausse - de produire cette section.
MENTION_SCENARIO_PIEGE = (
    "Le scenario ne reinjecte jamais la teneur en oxygene predite par la "
    "reconstitution : elle sort de la solution elle-meme, donc elle "
    "n'apporterait aucune information et rendrait les grandeurs exactement "
    "determinees pour la seule raison que le solveur a choisi ce point. Les "
    "largeurs ci-dessus sont obtenues en balayant toute la plage compatible "
    "de l'oxygene."
)


class ReportRefused(RuntimeError):
    """Le rapport ne peut pas etre emis en l'etat."""


@dataclass
class ReportRow:
    """
    Une ligne du rapport.

    `value` est le texte deja formate, ce qui suffit au rendu Markdown. Les
    bornes NUMERIQUES sont conservees en plus, car le rendu HTML dessine des
    barres d'intervalle : c'est la seule maniere de montrer d'un coup d'oeil
    qu'une grandeur ferme est un trait fin et qu'un domaine compatible est
    une bande large. Un tableau de chiffres ne le fait pas voir.
    """

    label: str
    value: str
    status: str = ""   # "ferme" | "ferme_large" | "ouvert" | ""
    note: str = ""
    low: float | None = None       # borne basse, en fraction massique
    high: float | None = None      # borne haute
    point: float | None = None     # valeur centrale, si elle a un sens

    # Gravite du diagnostic porte par la ligne : "" | "ok" | "alerte" |
    # "rejet". C'est une DONNEE, pas une mise en forme. Elle existe parce
    # qu'un rendu ne doit jamais deduire la gravite en cherchant un mot dans
    # une phrase francaise : le message de bouclage degrade ne contient pas
    # le mot "alerte", et une telle heuristique affichait un lot en alerte
    # comme conforme.
    severity: str = ""

    @property
    def has_bar(self) -> bool:
        return self.low is not None and self.high is not None


@dataclass
class ReportSection:
    title: str
    intro: str = ""
    rows: list[ReportRow] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class LotReport:
    """Le livrable assemble."""

    lot_id: str
    client: str
    issued_on: _dt.date
    sections: list[ReportSection] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    traceability: list[str] = field(default_factory=list)
    is_demo: bool = False
    meta: dict = field(default_factory=dict)

    def section(self, title: str) -> ReportSection | None:
        return next((s for s in self.sections if s.title == title), None)

    # ------------------------------------------------------------------
    def to_markdown(self) -> str:
        L: list[str] = []
        titre = f"# Rapport de lot {self.lot_id}"
        L += [titre, ""]
        L += [f"**Client** : {self.client}  ",
              f"**Date d'emission** : {self.issued_on.isoformat()}", ""]

        if self.is_demo:
            L += ["> **DOCUMENT DE DEMONSTRATION — NON OPPOSABLE.** "
                  "Il repose sur des donnees ou des prix non destines a la "
                  "production.", ""]

        for s in self.sections:
            L += [f"## {s.title}", ""]
            if s.intro:
                L += [s.intro, ""]
            if s.rows:
                L += ["| Grandeur | Valeur | Statut |", "|---|---|---|"]
                for r in s.rows:
                    statut = libelle_statut(s.title, r.status)
                    L.append(f"| {r.label} | {r.value} | {statut} |")
                L.append("")
            for n in s.notes:
                L += [f"*{n}*", ""]

        if self.warnings:
            L += ["## Avertissements", ""]
            L += [f"- {w}" for w in self.warnings] + [""]

        if self.limitations:
            L += ["## Limites methodologiques declarees", ""]
            L += [f"- {m}" for m in self.limitations] + [""]

        if self.traceability:
            L += ["## Tracabilite", ""]
            L += [f"- {t}" for t in self.traceability] + [""]

        L += ["---", "",
              "*Rapport produit par KLASTOS21. Les engagements methodologiques "
              "figurent au protocole joint.*"]
        return "\n".join(L)


# ==========================================================================
# Assemblage
# ==========================================================================

def build_report(
    lot_id: str,
    client: str,
    uncertainty: UncertaintyReport,
    valuation: Valuation | None = None,
    provenance_journal: list[str] | None = None,
    lot=None,
    issued_on: _dt.date | None = None,
    allow_demo: bool = False,
    destinataire: str = DESTINATAIRE_TIERS,
    conseil=None,
) -> LotReport:
    """
    Assemble le rapport client.

    Parameters
    ----------
    lot : SyntheticLot eventuel. S'il provient du generateur de test, le
        rapport est refuse sauf `allow_demo=True`.
    allow_demo : autorise l'emission d'un document marque non opposable.
    destinataire : "tiers" (defaut) si le document sort de la maison,
        "interne" s'il reste chez vous. Le systeme ne peut pas le deviner,
        donc il le demande. Le defaut est le cas reel - un rapport se
        fabrique pour un client - et c'est aussi le plus contraignant.

    Raises
    ------
    ReportRefused si une donnee synthetique ou une source de prix de
    demonstration atteint un livrable sans autorisation explicite, si le
    bulletin est hors tolerance de bouclage, ou si des prix d'agence non
    couverts par une licence de rediffusion partiraient chez un tiers.
    """
    if destinataire not in (DESTINATAIRE_TIERS, DESTINATAIRE_INTERNE):
        raise ValueError(
            f"destinataire inconnu : {destinataire!r}. "
            f"Attendu {DESTINATAIRE_TIERS!r} ou {DESTINATAIRE_INTERNE!r}."
        )
    issued_on = issued_on or _dt.date.today()
    demo = False

    # --- verrous de sortie ------------------------------------------------
    if lot is not None:
        from .generator import DATA_CLASS, SYNTHETIC_WARNING

        if getattr(lot, "meta", {}).get("data_class") == DATA_CLASS:
            if not allow_demo:
                raise ReportRefused(SYNTHETIC_WARNING)
            demo = True

    if valuation is not None:
        label = valuation.meta.get("prices_label", "")
        if any("demonstration" in w.lower() for w in valuation.warnings):
            if not allow_demo:
                raise ReportRefused(
                    f"Jeu de prix non destine a la production ({label}). "
                    "Brancher un flux avant emission."
                )
            demo = True

        # Un abonnement d'agence couvre l'usage interne, pas la rediffusion.
        # Le refus ne porte donc pas sur le calcul - qui reste licite - mais
        # sur la SORTIE du document. Un rapport interne passe.
        if (not valuation.meta.get("redistribution_licensed", True)
                and destinataire == DESTINATAIRE_TIERS):
            raise ReportRefused(REFUS_REDIFFUSION.format(label=label))

    bouclage = uncertainty.meta.get("closure")
    if bouclage is not None and not bouclage.is_exploitable and not allow_demo:
        raise ReportRefused(
            f"Bouclage massique hors tolerance ({bouclage.total * 100:.2f} %). "
            "Une analyse complementaire est requise avant valorisation."
        )

    rapport = LotReport(
        lot_id=lot_id, client=client, issued_on=issued_on, is_demo=demo,
        meta={"degeneracy": uncertainty.degeneracy,
              "n_draws": uncertainty.n_draws},
    )

    def _statut(r) -> str:
        """
        Distingue identifiable et exploitable.

        Une grandeur peut etre mathematiquement determinee et rester
        inutilisable si le systeme est mal conditionne. L'afficher comme
        "ferme" sans reserve induirait le client en erreur.
        """
        if not r.identifiable:
            return "ouvert"
        return "ferme" if r.well_determined else "ferme_large"

    par_bloc = {"ferme_attendu": [], "phase": [], "ventilation": []}
    for r in uncertainty.results:
        par_bloc.setdefault(r.block, []).append(r)

    # --- 1. Diagnostic du bulletin ---------------------------------------
    diag = ReportSection(title="Diagnostic du bulletin")
    if bouclage is not None:
        diag.rows.append(ReportRow(
            label="Bouclage massique",
            value=f"{bouclage.total * 100:.2f} %",
            note=bouclage.message,
            severity=bouclage.status,
        ))
        if bouclage.status != "ok":
            rapport.warnings.append(bouclage.message)
    diag.rows.append(ReportRow(
        label="Degres de liberte non contraints",
        value=str(uncertainty.degeneracy),
        note=("Le systeme est bien pose." if uncertainty.degeneracy == 0
              else "Certaines grandeurs ne sont pas identifiables par analyse "
                   "elementaire seule."),
        # Une degenerescence non nulle n'est pas une anomalie : c'est la
        # realite du systeme Li-Ni-Mn-Co-O, et le rapport la rend visible
        # au lieu de la masquer. Donc "ok", jamais "alerte".
        severity="ok",
    ))
    diag.rows.append(ReportRow(
        label="Tirages de propagation",
        value=str(uncertainty.n_draws),
        severity="ok",
    ))
    rapport.sections.append(diag)

    # --- 2. Grandeurs fermes ---------------------------------------------
    fermes = ReportSection(
        title="Grandeurs fermes",
        intro=("Ces valeurs sont determinees par l'analyse elementaire, quelle "
               "que soit la ventilation retenue par le solveur. Ce sont les "
               "seules opposables."),
    )
    for r in sorted(par_bloc.get("ferme_attendu", []), key=lambda x: x.key):
        if not r.identifiable:
            continue
        fermes.rows.append(ReportRow(
            label=r.label, value=r.format_value(), status=_statut(r),
            low=r.total_lower, high=r.total_upper, point=r.median,
        ))
    for r in sorted(par_bloc.get("phase", []), key=lambda x: x.key):
        if not r.identifiable:
            continue
        fermes.rows.append(ReportRow(
            label=r.label, value=r.format_value(), status=_statut(r),
            note=r.note, low=r.total_lower, high=r.total_upper,
            point=r.median,
        ))
        if r.note:
            fermes.notes.append(f"{r.label} : {r.note}")

    mal_determinees = [row for row in fermes.rows if row.status == "ferme_large"]
    if mal_determinees:
        fermes.notes.append(MENTION_MAL_DETERMINE)
        rapport.warnings.append(
            f"{len(mal_determinees)} grandeur(s) identifiable(s) mais mal "
            "determinee(s) : "
            + ", ".join(row.label for row in mal_determinees)
            + f". Seuil d'exploitabilite retenu : "
              f"{WELL_DETERMINED_WIDTH * 100:.0f} points."
        )
    rapport.sections.append(fermes)

    # --- 3. Ventilation non identifiable ---------------------------------
    ouvertes = [r for r in uncertainty.results if not r.identifiable]
    if ouvertes:
        vent = ReportSection(
            title="Ventilation par grade",
            intro=("Les valeurs ci-dessous sont des DOMAINES COMPATIBLES, pas "
                   "des estimations. Toute valeur du domaine explique le "
                   "bulletin aussi bien qu'une autre."),
        )
        for r in sorted(ouvertes, key=lambda x: x.key):
            vent.rows.append(ReportRow(
                label=r.label, value=r.format_value(), status="ouvert",
                note=r.note, low=r.total_lower, high=r.total_upper,
            ))
        vent.notes.append(NOTE_NON_IDENTIFIABLE.capitalize() + ".")
        if any(r.apparent_uniqueness_risk for r in ouvertes):
            vent.notes.append(AVERTISSEMENT_SOMMET)
            rapport.warnings.append(AVERTISSEMENT_SOMMET)
        rapport.sections.append(vent)

    # --- 3 bis. Ce que la quantification structurale a resserre -----------
    structurale = uncertainty.meta.get("structural")
    if structurale is not None and len(structurale):
        mesures = " ; ".join(
            f"{q.label} {q.value * 100:.2f} +/- {q.uncertainty * 100:.2f} %"
            for q in structurale.quantifications)
        drx = ReportSection(
            title=TITRE_DRX,
            intro=(f"{MENTION_DRX}\n\nMesure(s) declaree(s), base "
                   f"{structurale.basis} : {mesures}."),
        )
        resserres = [r for r in uncertainty.results
                     if r.structural_gain is not None
                     and r.structural_gain > 0.01]
        resserres.sort(key=lambda r: -(r.structural_gain or 0.0))
        for r in resserres[:8]:
            apres = max(0.0, (r.struct_upper or 0.0) - (r.struct_lower or 0.0))
            drx.rows.append(ReportRow(
                label=r.label,
                value=(f"{r.open_width * 100:.2f} -> {apres * 100:.2f} points"),
                status="ferme",
                note=f"{(r.structural_gain or 0.0) * 100:.0f} % de largeur en moins",
                low=0.0, high=apres, point=r.open_width,
            ))
        if not resserres:
            drx.notes.append(
                "La quantification fournie ne resserre aucune plage de ce "
                "lot : les phases qu'elle designe etaient deja determinees, "
                "ou elle ne contraint pas les directions non identifiables."
            )
        if uncertainty.structural_conflict_rate > DRX_CONFLIT_ALERTE:
            drx.notes.append(
                f"{uncertainty.n_structural_conflicts} tirage(s) sur "
                f"{uncertainty.n_draws} en conflit "
                f"({uncertainty.structural_conflict_rate * 100:.0f} %). "
                + MENTION_DRX_CONFLIT
            )
        for ligne in structurale.journal:
            rapport.traceability.append(f"DRX : {ligne}")
        rapport.sections.append(drx)

    # --- 4. Levier d'amelioration ----------------------------------------
    goulots = uncertainty.structural_bottlenecks()
    if goulots:
        lev = ReportSection(
            title="Comment reduire l'incertitude",
            intro=("Toute incertitude n'a pas le meme remede. Le tableau "
                   "distingue ce qu'une meilleure analyse resoudrait de ce "
                   "qu'elle ne resoudra pas."),
        )
        for r in goulots[:6]:
            lev.rows.append(ReportRow(
                label=r.label,
                value=f"{r.total_width * 100:.2f} points",
                status="ouvert",
                note=r.advice(),
                low=0.0, high=r.total_width,
            ))
        lev.notes.append(
            "Une analyse plus fine ne reduira pas ces largeurs. Une donnee "
            "structurale (DRX) ou une attestation de provenance le ferait."
        )
        rapport.sections.append(lev)

    # --- 4 ter. Quelle quantification commander ---------------------------
    if conseil is not None and conseil.rows:
        cs = ReportSection(title=TITRE_CONSEIL, intro=MENTION_CONSEIL)
        utiles = [r for r in conseil.rows if r.useful]
        for r in utiles[:6]:
            cs.rows.append(ReportRow(
                label=r.label,
                value=f"au moins {r.gain * 100:.0f} % de largeur en moins",
                status="ferme",
                note=(f"plage actuelle {r.width_open * 100:.2f} points, "
                      f"pour une mesure a "
                      f"{conseil.uncertainty * 100:.1f} point(s)"),
                low=0.0, high=r.gain,
            ))
        inutiles = conseil.useless
        if inutiles:
            cs.notes.append(
                "Sans gain exploitable a cette incertitude : "
                + ", ".join(r.label for r in inutiles[:10])
                + ". Commander ces quantifications serait une depense sans "
                "effet sur les plages de ce lot."
            )
        if not utiles:
            cs.notes.append(
                "Aucune quantification ne resserrerait utilement ce lot a "
                f"{conseil.uncertainty * 100:.1f} point(s) d'incertitude. "
                "Un laboratoire plus precis changerait la conclusion."
            )
        cs.notes.append(
            f"Largeur cumulee actuelle des phases : "
            f"{conseil.total_before * 100:.2f} points."
        )
        rapport.sections.append(cs)

    analytiques = [r for r in uncertainty.analytic_bottlenecks()
                   if r.total_width > 0.01][:4]
    if analytiques:
        an = ReportSection(
            title="Grandeurs sensibles a la qualite du bulletin",
            intro=("Ces largeurs se reduiraient avec une analyse de meilleure "
                   "qualite ou des replicats."),
        )
        for r in analytiques:
            an.rows.append(ReportRow(
                label=r.label, value=f"{r.total_width * 100:.2f} points",
                status="ferme", low=0.0, high=r.total_width,
            ))
        rapport.sections.append(an)

    # --- 4 bis. Scenario : element non dose -------------------------------
    #
    # L'oxygene n'est presque jamais dose. Le calcul principal tourne donc
    # sans lui. Cette section ne corrige pas ce choix : elle chiffre ce que
    # le client gagnerait a commander le dosage, et - tout aussi utile - ce
    # qu'il n'y gagnerait pas.
    for sc in uncertainty.meta.get("scenarios", []):
        if not sc.rows:
            continue
        gagnantes = sc.firm_rows
        inutiles = sc.useless_rows
        sec = ReportSection(
            title=TITRE_SCENARIO,
            intro=(
                f"L'oxygene n'a pas ete dose. La reconstitution le contraint "
                f"neanmoins entre {sc.value_low * 100:.2f} % et "
                f"{sc.value_high * 100:.2f} %. Un dosage n'apporterait donc "
                f"quelque chose que s'il etait plus precis que cette plage : "
                f"son incertitude doit rester sous "
                f"{sc.max_useful_uncertainty * 100:.2f} point. Au-dela, il "
                f"confirmerait ce que le calcul donne deja."
            ),
        )
        for r in sc.rows:
            sec.rows.append(ReportRow(
                label=r.label,
                value=(f"{r.width_open * 100:.2f} → "
                       f"{r.width_conditional * 100:.2f} points"),
                status="ferme" if r.becomes_firm else "ouvert",
                note=("deviendrait ferme" if r.becomes_firm
                      else "resterait un domaine compatible"),
                low=0.0, high=r.width_conditional,
                point=r.width_open,
            ))
        sec.notes.append(MENTION_SCENARIO_BASE)
        if gagnantes:
            sec.notes.append(
                f"{len(gagnantes)} grandeur(s) deviendraient fermes : "
                + ", ".join(r.label for r in gagnantes) + "."
            )
        if inutiles:
            sec.notes.append(
                "Le dosage n'apporterait RIEN a ces grandeurs ("
                + ", ".join(r.label for r in inutiles)
                + "). Leur degenerescence vit dans le sous-systeme ferme "
                  "Li-Ni-Mn-Co-O, que l'oxygene ne contraint pas : seules une "
                  "donnee structurale (DRX) ou une attestation de provenance "
                  "la levent."
            )
        sec.notes.append(MENTION_SCENARIO)
        sec.notes.append(MENTION_SCENARIO_PIEGE)
        rapport.sections.append(sec)

    # --- 5. Valorisation --------------------------------------------------
    if valuation is not None:
        val = ReportSection(title="Valorisation", intro=MENTION_VALORISATION)
        for c in valuation.contributions:
            val.rows.append(ReportRow(
                label=f"{c.element} ({c.payable * 100:.2f} % payable)",
                value=(f"{c.value_low:,.0f} \u2013 {c.value_high:,.0f} "
                       f"{valuation.currency}/t"),
                status="ferme",
                note=c.reference_name,
            ))
        val.rows.append(ReportRow(
            label="Valeur brute",
            value=(f"{valuation.gross_low:,.0f} \u2013 "
                   f"{valuation.gross_high:,.0f} {valuation.currency}/t"),
            status="ferme",
        ))
        if valuation.processing_cost:
            val.rows.append(ReportRow(
                label="Cout de traitement retenu",
                value=f"{valuation.processing_cost:,.0f} {valuation.currency}/t",
            ))
        if valuation.margin_rate:
            val.rows.append(ReportRow(
                label="Marge visee",
                value=f"{valuation.margin_rate * 100:.1f} %",
            ))
        val.rows.append(ReportRow(
            label="PRIX MAXIMAL A PAYER",
            value=valuation.format_max_price(),
            status="ferme",
        ))
        val.notes.append(MENTION_FOURCHETTE)
        teneurs = {f"el_{c.element}" for c in valuation.contributions}
        fragiles = [
            r.label for r in uncertainty.results
            if r.key in teneurs and r.identifiable and not r.well_determined
        ]
        if fragiles:
            val.notes.append(
                "Teneurs mal determinees entrant dans le prix : "
                + ", ".join(fragiles)
                + ". La fourchette de valorisation s'en trouve elargie."
            )
        rapport.sections.append(val)

        if valuation.spec_deviations:
            conf = ReportSection(
                title="Conformite a la specification",
                intro="Ecarts constates par rapport a la specification retenue.",
            )
            for e in valuation.spec_deviations:
                conf.rows.append(ReportRow(label="Ecart", value=e))
            conf.notes.append(
                "Les decotes commerciales associees ne sont pas chiffrees "
                "dans cette version."
            )
            rapport.sections.append(conf)

        rapport.warnings.extend(valuation.warnings)
        rapport.traceability.extend(valuation.provenance)

    # --- 6. Tracabilite et limites ---------------------------------------
    if provenance_journal:
        rapport.traceability = list(provenance_journal) + rapport.traceability

    rapport.limitations = [
        NOTE_CARBONE.capitalize() + ".",
        NOTE_NON_IDENTIFIABLE.capitalize() + ".",
        MENTION_DETECTION,
    ]
    if demo:
        rapport.limitations.insert(
            0, "Document de demonstration. Aucune valeur opposable."
        )

    # deduplication en conservant l'ordre
    vus: set[str] = set()
    rapport.warnings = [
        w for w in rapport.warnings if not (w in vus or vus.add(w))
    ]
    return rapport