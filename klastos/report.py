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

from . import i18n
from .identifiability import NOTE_CARBONE, NOTE_NON_IDENTIFIABLE
from .uncertainty import (AVERTISSEMENT_SOMMET, SOURCE_STRUCTURELLE,
                          WELL_DETERMINED_WIDTH, UncertaintyReport)
from .valuation import Valuation

# Mentions reprises telles quelles du protocole. Vue francaise du catalogue.
MENTION_DETECTION = i18n.t("rapport.mention.detection", "fr")

MENTION_VALORISATION = i18n.t("rapport.mention.valorisation", "fr")

MENTION_MAL_DETERMINE = i18n.t("rapport.mention.mal_determine", "fr")

MENTION_FOURCHETTE = i18n.t("rapport.mention.fourchette", "fr")

#: Destinataires possibles d'un rapport. Le systeme ne devine pas si un
#: document sort de la maison : il le demande.
DESTINATAIRE_TIERS = "tiers"
DESTINATAIRE_INTERNE = "interne"

#: Les textes du rapport vivent desormais au catalogue i18n. Les constantes
#: ci-dessous en sont la VUE FRANCAISE, conservee parce qu'une quinzaine
#: d'appelants et de tests les importent par leur nom. Le rendu, lui, ne les
#: utilise pas : il demande la langue du rapport au catalogue.
REFUS_REDIFFUSION = i18n.CATALOGUE["rapport.mention.refus_rediffusion"]["fr"]

#: Titre de la section de scenario. Le rendu HTML s'y reconnait, donc il est
#: nomme une fois et reutilise.
TITRE_SCENARIO = i18n.t("rapport.section.scenario", "fr")

TITRE_DRX = i18n.t("rapport.section.drx", "fr")

MENTION_DRX = i18n.t("rapport.mention.drx", "fr")

MENTION_DRX_CONFLIT = i18n.t("rapport.mention.drx_conflit", "fr")

#: Au-dela de cette part de tirages en conflit, le rapport avertit.
DRX_CONFLIT_ALERTE = 0.20

TITRE_CONSEIL = i18n.t("rapport.section.conseil", "fr")

#: Identifiants stables des sections. Ils remplacent le titre comme cle :
#: `LIBELLES_STATUT_PAR_SECTION` etait indexe par le TITRE francais, donc
#: traduire un titre vidait la colonne « statut » sans lever. Voir i18n.py.
SECTION_DIAGNOSTIC = "diagnostic"
SECTION_FERMES = "grandeurs_fermes"
SECTION_VENTILATION = "ventilation"
SECTION_REDUIRE = "reduire"
SECTION_SENSIBLES = "sensibles"
SECTION_SCENARIO = "scenario"
SECTION_DRX = "drx"
SECTION_CONSEIL = "conseil"
SECTION_VALORISATION = "valorisation"
SECTION_SPECIFICATION = "specification"

#: Statut -> cle i18n, par defaut : le statut repond alors a la question
#: "cette grandeur est-elle determinee ?".
STATUT_DEFAUT: dict[str, str] = {
    "ferme": "rapport.statut.ferme",
    "ferme_large": "rapport.statut.ferme_large",
    "ouvert": "rapport.statut.ouvert",
}

#: Sections ou le statut repond a une AUTRE question, parce que leurs valeurs
#: sont des largeurs et non des positions. Table unique, consommee par les
#: deux rendus : sans elle, le Markdown disait "ferme" la ou le HTML disait
#: "reductible", et les deux documents se contredisaient sur la meme ligne.
STATUT_PAR_SECTION: dict[str, dict[str, str]] = {
    SECTION_REDUIRE: {
        "ferme": "rapport.statut.reductible",
        "ferme_large": "rapport.statut.reductible",
        "ouvert": "rapport.statut.irreductible",
    },
    SECTION_SENSIBLES: {
        "ferme": "rapport.statut.reductible",
        "ferme_large": "rapport.statut.reductible",
        "ouvert": "rapport.statut.irreductible",
    },
    SECTION_SCENARIO: {
        "ferme": "rapport.statut.deviendrait_ferme",
        "ferme_large": "rapport.statut.deviendrait_ferme",
        "ouvert": "rapport.statut.resterait_ouverte",
    },
    SECTION_DRX: {
        "ferme": "rapport.statut.resserree",
        "ferme_large": "rapport.statut.resserree",
        "ouvert": "rapport.statut.inchangee",
    },
    SECTION_CONSEIL: {
        "ferme": "rapport.statut.gain_pire_cas",
        "ferme_large": "rapport.statut.gain_pire_cas",
        "ouvert": "rapport.statut.sans_effet",
    },
}

#: Titres -> cle de section. Transitoire : il existe pour que les appelants
#: qui designent encore une section par son titre francais continuent de
#: fonctionner le temps de la migration. Toute nouvelle ecriture passe par
#: les constantes SECTION_*.
_CLE_PAR_TITRE: dict[str, str] = {
    i18n.t(f"rapport.section.{c}", "fr"): c
    for c in (SECTION_DIAGNOSTIC, SECTION_FERMES, SECTION_VENTILATION,
              SECTION_REDUIRE, SECTION_SENSIBLES, SECTION_SCENARIO,
              SECTION_DRX, SECTION_CONSEIL, SECTION_VALORISATION,
              SECTION_SPECIFICATION)
}


def libelle_statut(section: str, status: str,
                   langue: str = i18n.DEFAUT) -> str:
    """
    Libelle du statut, selon la question que pose la section.

    `section` est une cle SECTION_*. Un titre francais est encore accepte,
    le temps de la migration, et traduit en cle.
    """
    cle_section = section if section in STATUT_PAR_SECTION else \
        _CLE_PAR_TITRE.get(section, section)
    table = STATUT_PAR_SECTION.get(cle_section, STATUT_DEFAUT)
    cle = table.get(status)
    return i18n.t(cle, langue) if cle else ""

MENTION_CONSEIL = i18n.t("rapport.mention.conseil", "fr")

MENTION_SCENARIO = i18n.t("rapport.mention.scenario", "fr")

#: Base de mesure des largeurs du scenario. Sans cette mention, le client lit
#: deux largeurs differentes pour la meme grandeur dans deux sections, sans
#: comprendre qu'elles ne mesurent pas la meme chose.
MENTION_SCENARIO_BASE = i18n.t("rapport.mention.scenario_base", "fr")

#: Avertissement de fond, verrouille par un test. Il interdit la seule
#: facon simple - et fausse - de produire cette section.
MENTION_SCENARIO_PIEGE = i18n.t("rapport.mention.scenario_piege", "fr")


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

    # Identifiant stable, independant de la langue. `title` est du TEXTE
    # AFFICHE : il change avec la langue du rapport, donc il ne peut pas
    # servir a reconnaitre une section. Les rendus s'appuient sur `cle`.
    cle: str = ""


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

    #: Langue du document. Le protocole n'etant pas traduit, un rapport
    #: anglais le cite en declarant sa langue : voir i18n.py.
    langue: str = i18n.DEFAUT

    def section(self, ref: str) -> ReportSection | None:
        """
        Rend une section par sa CLE, ou par son titre.

        La recherche par cle d'abord : c'est la seule qui survive a un
        changement de langue. La recherche par titre reste acceptee pour les
        appelants ecrits avant l'introduction des cles.
        """
        par_cle = next((s for s in self.sections if s.cle and s.cle == ref),
                       None)
        if par_cle is not None:
            return par_cle
        return next((s for s in self.sections if s.title == ref), None)

    # ------------------------------------------------------------------
    def to_markdown(self) -> str:
        lg = i18n.langue_valide(self.langue)

        def tr(cle: str, **champs: object) -> str:
            return i18n.t(cle, lg, **champs)

        L: list[str] = []
        L += [f"# {tr('rapport.doc.titre', lot=self.lot_id)}", ""]
        L += [f"**{tr('rapport.doc.client')}** : {self.client}  ",
              f"**{tr('rapport.doc.emis_le')}** : "
              f"{self.issued_on.isoformat()}", ""]

        if self.is_demo:
            L += [f"> {tr('rapport.doc.demo')}", ""]

        entete = (f"| {tr('rapport.doc.col_grandeur')} "
                  f"| {tr('rapport.doc.col_valeur')} "
                  f"| {tr('rapport.doc.col_statut')} |")
        for s in self.sections:
            L += [f"## {s.title}", ""]
            if s.intro:
                L += [s.intro, ""]
            if s.rows:
                L += [entete, "|---|---|---|"]
                for r in s.rows:
                    # Par la CLE, jamais par le titre : le titre est traduit.
                    statut = libelle_statut(s.cle or s.title, r.status, lg)
                    L.append(f"| {r.label} | {r.value} | {statut} |")
                L.append("")
            for n in s.notes:
                L += [f"*{n}*", ""]

        if self.warnings:
            L += [f"## {tr('rapport.section.avertissements')}", ""]
            L += [f"- {w}" for w in self.warnings] + [""]

        if self.limitations:
            L += [f"## {tr('rapport.section.limites')}", ""]
            L += [f"- {m}" for m in self.limitations] + [""]

        if self.traceability:
            L += [f"## {tr('rapport.section.tracabilite')}", ""]
            L += [f"- {t}" for t in self.traceability] + [""]

        L += ["---", "",
              f"*{tr('rapport.doc.pied')} {tr('rapport.protocole.renvoi')}*"]
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
    langue: str = i18n.DEFAUT,
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
    lg = i18n.langue_valide(langue)
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
                    i18n.t("rapport.refus.prix_demo", lg, label=label))
            demo = True

        # Un abonnement d'agence couvre l'usage interne, pas la rediffusion.
        # Le refus ne porte donc pas sur le calcul - qui reste licite - mais
        # sur la SORTIE du document. Un rapport interne passe.
        if (not valuation.meta.get("redistribution_licensed", True)
                and destinataire == DESTINATAIRE_TIERS):
            raise ReportRefused(
                i18n.t("rapport.mention.refus_rediffusion", lg,
                       label=label))

    bouclage = uncertainty.meta.get("closure")
    if bouclage is not None and not bouclage.is_exploitable and not allow_demo:
        raise ReportRefused(
            i18n.t("rapport.refus.bouclage", lg,
                   ecart=bouclage.total * 100))

    rapport = LotReport(
        lot_id=lot_id, client=client, issued_on=issued_on, is_demo=demo,
        langue=lg,
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
    diag = ReportSection(cle=SECTION_DIAGNOSTIC,
                         title=i18n.t("rapport.section.diagnostic", lg))
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
        label=i18n.t("rapport.ligne.degres", lg),
        value=str(uncertainty.degeneracy),
        note=i18n.t("rapport.note.bien_pose" if uncertainty.degeneracy == 0
                    else "rapport.note.degenere", lg),
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
        cle=SECTION_FERMES,
        title=i18n.t("rapport.section.grandeurs_fermes", lg),
        intro=i18n.t("rapport.intro.grandeurs_fermes", lg),
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
        fermes.notes.append(i18n.t("rapport.mention.mal_determine", lg))
        rapport.warnings.append(
            i18n.t("rapport.note.mal_determinees", lg,
                   n=len(mal_determinees),
                   liste=", ".join(row.label for row in mal_determinees),
                   seuil=WELL_DETERMINED_WIDTH * 100)
        )
    rapport.sections.append(fermes)

    # --- 3. Ventilation non identifiable ---------------------------------
    ouvertes = [r for r in uncertainty.results if not r.identifiable]
    if ouvertes:
        vent = ReportSection(
            cle=SECTION_VENTILATION,
            title=i18n.t("rapport.section.ventilation", lg),
            intro=i18n.t("rapport.intro.ventilation", lg),
        )
        for r in sorted(ouvertes, key=lambda x: x.key):
            vent.rows.append(ReportRow(
                label=r.label, value=r.format_value(), status="ouvert",
                note=r.note, low=r.total_lower, high=r.total_upper,
            ))
        vent.notes.append(i18n.t("rapport.note.non_identifiable", lg))
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
            cle=SECTION_DRX,
            title=i18n.t("rapport.section.drx", lg),
            intro=(f'{i18n.t("rapport.mention.drx", lg)}\n\n'
                   f"Mesure(s) declaree(s), base "
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
                value=i18n.t("rapport.valeur.drx_avant_apres", lg,
                             avant=r.open_width * 100, apres=apres * 100),
                status="ferme",
                note=i18n.t("rapport.note.drx_gain", lg,
                            gain=(r.structural_gain or 0.0) * 100),
                low=0.0, high=apres, point=r.open_width,
            ))
        if not resserres:
            drx.notes.append(i18n.t("rapport.aide.drx_sans_effet", lg))
        if uncertainty.structural_conflict_rate > DRX_CONFLIT_ALERTE:
            drx.notes.append(
                i18n.t("rapport.note.drx_conflit_compte", lg,
                       n=uncertainty.n_structural_conflicts,
                       total=uncertainty.n_draws,
                       taux=uncertainty.structural_conflict_rate * 100)
                + i18n.t("rapport.mention.drx_conflit", lg)
            )
        for ligne in structurale.journal:
            rapport.traceability.append(f"DRX : {ligne}")
        rapport.sections.append(drx)

    # --- 4. Levier d'amelioration ----------------------------------------
    goulots = uncertainty.structural_bottlenecks()
    if goulots:
        lev = ReportSection(
            cle=SECTION_REDUIRE,
            title=i18n.t("rapport.section.reduire", lg),
            intro=i18n.t("rapport.intro.reduire", lg),
        )
        for r in goulots[:6]:
            lev.rows.append(ReportRow(
                label=r.label,
                value=f"{r.total_width * 100:.2f} points",
                status="ouvert",
                note=r.advice(),
                low=0.0, high=r.total_width,
            ))
        lev.notes.append(i18n.t("rapport.note.reduire_pied", lg))
        rapport.sections.append(lev)

    # --- 4 ter. Quelle quantification commander ---------------------------
    if conseil is not None and conseil.rows:
        cs = ReportSection(
            cle=SECTION_CONSEIL,
            title=i18n.t("rapport.section.conseil", lg),
            intro=i18n.t("rapport.mention.conseil", lg))
        utiles = [r for r in conseil.rows if r.useful]
        for r in utiles[:6]:
            cs.rows.append(ReportRow(
                label=r.label,
                value=i18n.t("rapport.valeur.gain_largeur", lg,
                             gain=r.gain * 100),
                status="ferme",
                note=i18n.t("rapport.note.plage_pour_mesure", lg,
                            plage=r.width_open * 100,
                            u=conseil.uncertainty * 100),
                low=0.0, high=r.gain,
            ))
        inutiles = conseil.useless
        if inutiles:
            cs.notes.append(i18n.t(
                "rapport.note.sans_gain", lg,
                liste=", ".join(r.label for r in inutiles[:10])))
        if not utiles:
            cs.notes.append(i18n.t("rapport.note.aucun_conseil", lg,
                                   u=conseil.uncertainty * 100))
        cs.notes.append(i18n.t("rapport.note.largeur_cumulee", lg,
                               total=conseil.total_before * 100))
        rapport.sections.append(cs)

    analytiques = [r for r in uncertainty.analytic_bottlenecks()
                   if r.total_width > 0.01][:4]
    if analytiques:
        an = ReportSection(
            cle=SECTION_SENSIBLES,
            title=i18n.t("rapport.section.sensibles", lg),
            intro=i18n.t("rapport.intro.sensibles", lg),
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
            cle=SECTION_SCENARIO,
            title=i18n.t("rapport.section.scenario", lg),
            intro=i18n.t("rapport.intro.scenario", lg,
                         bas=sc.value_low * 100,
                         haut=sc.value_high * 100,
                         umax=sc.max_useful_uncertainty * 100),
        )
        for r in sc.rows:
            sec.rows.append(ReportRow(
                label=r.label,
                value=(f"{r.width_open * 100:.2f} → "
                       f"{r.width_conditional * 100:.2f} points"),
                status="ferme" if r.becomes_firm else "ouvert",
                note=i18n.t("rapport.statut.deviendrait_ferme"
                            if r.becomes_firm
                            else "rapport.note.resterait_domaine", lg),
                low=0.0, high=r.width_conditional,
                point=r.width_open,
            ))
        sec.notes.append(i18n.t("rapport.mention.scenario_base", lg))
        if gagnantes:
            sec.notes.append(i18n.t(
                "rapport.note.deviendraient_fermes", lg, n=len(gagnantes),
                liste=", ".join(r.label for r in gagnantes)))
        if inutiles:
            sec.notes.append(i18n.t(
                "rapport.note.dosage_sans_effet", lg,
                liste=", ".join(r.label for r in inutiles)))
        sec.notes.append(i18n.t("rapport.mention.scenario", lg))
        sec.notes.append(i18n.t("rapport.mention.scenario_piege", lg))
        rapport.sections.append(sec)

    # --- 5. Valorisation --------------------------------------------------
    if valuation is not None:
        val = ReportSection(
            cle=SECTION_VALORISATION,
            title=i18n.t("rapport.section.valorisation", lg),
            intro=i18n.t("rapport.mention.valorisation", lg))
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
                label=i18n.t("rapport.ligne.cout", lg),
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
        val.notes.append(i18n.t("rapport.mention.fourchette", lg))
        teneurs = {f"el_{c.element}" for c in valuation.contributions}
        fragiles = [
            r.label for r in uncertainty.results
            if r.key in teneurs and r.identifiable and not r.well_determined
        ]
        if fragiles:
            val.notes.append(i18n.t(
                "rapport.note.teneurs_mal_determinees", lg,
                liste=", ".join(fragiles)))
        rapport.sections.append(val)

        if valuation.spec_deviations:
            conf = ReportSection(
                cle=SECTION_SPECIFICATION,
                title=i18n.t("rapport.section.specification", lg),
                intro=i18n.t("rapport.intro.specification", lg),
            )
            for e in valuation.spec_deviations:
                conf.rows.append(ReportRow(
                    label=i18n.t("rapport.ligne.ecart", lg), value=e))
            conf.notes.append(
                i18n.t("rapport.note.decotes_non_chiffrees", lg))
            rapport.sections.append(conf)

        rapport.warnings.extend(valuation.warnings)
        rapport.traceability.extend(valuation.provenance)

    # --- 6. Tracabilite et limites ---------------------------------------
    if provenance_journal:
        rapport.traceability = list(provenance_journal) + rapport.traceability

    rapport.limitations = [
        i18n.t("rapport.note.carbone", lg),
        i18n.t("rapport.note.non_identifiable", lg),
        i18n.t("rapport.mention.detection", lg),
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