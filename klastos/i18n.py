"""
KLASTOS21 - Catalogue de messages, francais et anglais.

Pourquoi un catalogue explicite
-------------------------------
Pas de gettext, pas de fichiers .po, aucune dependance. Le projet se relit
en entier dans la source : un `.mo` compile romprait cette propriete, et une
chaine traduite qui se lirait seulement dans un outil externe ne serait plus
verifiable par un test.

Le catalogue est donc un dictionnaire `{cle: {"fr": ..., "en": ...}}`. Il se
lit, il se teste, il se diffe.

Principe directeur
------------------
UNE CLE N'EST JAMAIS UN TEXTE AFFICHE. C'est la faute que ce module existe
pour empecher. `report.py` indexait ses libelles de statut par le TITRE
francais de la section - « Comment reduire l'incertitude » servait a la fois
d'en-tete imprime et de cle de dictionnaire. Traduire le titre cassait
silencieusement la recherche, et la colonne « statut » du rapport anglais se
serait videe sans qu'aucune exception ne soit levee.

Les cles sont donc des identifiants ASCII stables, hierarchises par couche :

    rapport.section.*     titres des sections du livrable
    rapport.intro.*       prose d'introduction de section
    rapport.statut.*      libelles de statut, par section
    ui.*                  interface Streamlit
    journal.*             journal de lecture et avertissements
    cli.*                 ligne de commande

Le protocole reste en francais
------------------------------
Arbitrage assume : `protocole.md` porte les engagements methodologiques et
n'est pas traduit. Un rapport anglais le cite donc en signalant sa langue,
plutot que de laisser croire a une version anglaise opposable qui n'existe
pas. Voir `rapport.protocole.renvoi`.
"""

from __future__ import annotations

#: Langues servies. L'ordre fixe celui des tests de completude.
LANGUES: tuple[str, ...] = ("fr", "en")

#: Langue de repli. Le francais, parce que c'est la langue de redaction du
#: protocole et celle dans laquelle les arbitrages ont ete pris.
DEFAUT = "fr"


class CleInconnue(KeyError):
    """Cle absente du catalogue. C'est un bug, pas un resultat."""


# ==========================================================================
# Catalogue
# ==========================================================================
# Regle de redaction : le francais porte ses accents. Une chaine affichee
# sans accent est un defaut, pas un choix - les commentaires et docstrings du
# projet sont en ASCII, les textes VISIBLES ne le sont pas.

CATALOGUE: dict[str, dict[str, str]] = {

    # ---------------------------------------------------------------- titres
    "rapport.section.diagnostic": {
        "fr": "Diagnostic du bulletin",
        "en": "Assay diagnostics",
    },
    "rapport.section.grandeurs_fermes": {
        "fr": "Grandeurs fermes",
        "en": "Determined quantities",
    },
    "rapport.section.ventilation": {
        "fr": "Ventilation par grade",
        "en": "Breakdown by grade",
    },
    "rapport.section.reduire": {
        "fr": "Comment réduire l'incertitude",
        "en": "How to reduce the uncertainty",
    },
    "rapport.section.sensibles": {
        "fr": "Grandeurs sensibles à la qualité du bulletin",
        "en": "Quantities sensitive to assay quality",
    },
    "rapport.section.scenario": {
        "fr": "Scénario : et si l'oxygène était dosé",
        "en": "Scenario: what if oxygen were assayed",
    },
    "rapport.section.drx": {
        "fr": "Quantification structurale (diffraction)",
        "en": "Structural quantification (diffraction)",
    },
    "rapport.section.conseil": {
        "fr": "Quelle quantification commander",
        "en": "Which quantification to order",
    },
    "rapport.section.valorisation": {
        "fr": "Valorisation",
        "en": "Valuation",
    },
    "rapport.section.specification": {
        "fr": "Conformité à la spécification",
        "en": "Compliance with the specification",
    },
    "rapport.section.avertissements": {
        "fr": "Avertissements",
        "en": "Warnings",
    },
    "rapport.section.limites": {
        "fr": "Limites méthodologiques déclarées",
        "en": "Declared methodological limits",
    },
    "rapport.section.tracabilite": {
        "fr": "Traçabilité",
        "en": "Traceability",
    },

    # ----------------------------------------------------------- introductions
    "rapport.intro.grandeurs_fermes": {
        "fr": "Ces valeurs sont déterminées par l'analyse élémentaire, quelle "
              "que soit la ventilation retenue par le solveur. Ce sont les "
              "seules opposables.",
        "en": "These values are determined by the elemental assay, whatever "
              "breakdown the solver settles on. They are the only ones that "
              "can be relied upon.",
    },
    "rapport.intro.ventilation": {
        "fr": "Les valeurs ci-dessous sont des DOMAINES COMPATIBLES, pas des "
              "estimations. Toute valeur du domaine explique le bulletin "
              "aussi bien qu'une autre.",
        "en": "The values below are COMPATIBLE RANGES, not estimates. Any "
              "value within a range explains the assay just as well as any "
              "other.",
    },
    "rapport.intro.reduire": {
        "fr": "Toute incertitude n'a pas le même remède. Le tableau distingue "
              "ce qu'une meilleure analyse résoudrait de ce qu'elle ne "
              "résoudra pas.",
        "en": "Not every uncertainty has the same remedy. The table "
              "separates what a better assay would resolve from what it "
              "will not.",
    },
    "rapport.intro.sensibles": {
        "fr": "Ces largeurs se réduiraient avec une analyse de meilleure "
              "qualité ou des réplicats.",
        "en": "These widths would narrow with a higher-quality assay or with "
              "replicates.",
    },
    "rapport.intro.specification": {
        "fr": "Écarts constatés par rapport à la spécification retenue.",
        "en": "Deviations observed against the selected specification.",
    },

    # --------------------------------------------------- libelles de statut
    # Question posee : « cette grandeur est-elle determinee ? »
    "rapport.statut.ferme": {"fr": "ferme", "en": "determined"},
    "rapport.statut.ferme_large": {
        "fr": "ferme mais **mal déterminé**",
        "en": "determined but **poorly constrained**",
    },
    "rapport.statut.ouvert": {
        "fr": "**non identifiable**",
        "en": "**not identifiable**",
    },

    # Question posee : « cette largeur se reduirait-elle ? »
    "rapport.statut.reductible": {"fr": "réductible", "en": "reducible"},
    "rapport.statut.irreductible": {
        "fr": "**irréductible**",
        "en": "**irreducible**",
    },

    # Question posee : « que deviendrait cette grandeur ? »
    "rapport.statut.deviendrait_ferme": {
        "fr": "deviendrait ferme",
        "en": "would become determined",
    },
    "rapport.statut.resterait_ouverte": {
        "fr": "resterait ouverte",
        "en": "would remain open",
    },

    # Question posee : « la diffraction a-t-elle resserre ? »
    "rapport.statut.resserree": {"fr": "resserrée", "en": "narrowed"},
    "rapport.statut.inchangee": {"fr": "inchangée", "en": "unchanged"},

    # Variantes du rendu HTML : meme vocabulaire, sans les marques d'emphase
    # Markdown. Les deux rendus doivent dire la meme chose - un test le
    # verifie - mais chacun garde ses conventions typographiques.
    "rapport.statut.html_ferme": {"fr": "ferme", "en": "determined"},
    "rapport.statut.html_ferme_large": {
        "fr": "ferme, mal déterminé",
        "en": "determined, poorly constrained",
    },
    "rapport.statut.html_ouvert": {
        "fr": "non identifiable",
        "en": "not identifiable",
    },
    "rapport.statut.html_reductible": {
        "fr": "réductible", "en": "reducible",
    },
    "rapport.statut.html_irreductible": {
        "fr": "irréductible", "en": "irreducible",
    },

    # Question posee : « que rapporterait la quantification a commander ? »
    "rapport.statut.gain_pire_cas": {
        "fr": "gain acquis au pire cas",
        "en": "gain secured in the worst case",
    },
    "rapport.statut.sans_effet": {"fr": "sans effet", "en": "no effect"},

    # ------------------------------------------- structure du document rendu
    "rapport.doc.titre": {
        "fr": "Rapport de lot {lot}",
        "en": "Lot report {lot}",
    },
    #: Variante sans l'identifiant : le rendu HTML le pose sur sa propre
    #: ligne, donc le titre doit pouvoir s'ecrire seul.
    "rapport.doc.titre_nu": {"fr": "Rapport de lot", "en": "Lot report"},
    "rapport.doc.soustitre": {
        "fr": "Analyse prédictive des matières premières secondaires",
        "en": "Predictive analysis of secondary raw materials",
    },
    "rapport.doc.degres": {
        "fr": "Degrés de liberté",
        "en": "Degrees of freedom",
    },
    "rapport.doc.client": {"fr": "Client", "en": "Client"},
    "rapport.doc.emis_le": {
        "fr": "Date d'émission",
        "en": "Issue date",
    },
    "rapport.doc.col_grandeur": {"fr": "Grandeur", "en": "Quantity"},
    "rapport.doc.col_valeur": {"fr": "Valeur", "en": "Value"},
    "rapport.doc.col_statut": {"fr": "Statut", "en": "Status"},
    "rapport.doc.col_domaine": {"fr": "Domaine", "en": "Range"},
    "rapport.doc.col_largeur": {
        "fr": "Largeur de la fourchette",
        "en": "Range width",
    },
    "rapport.doc.demo": {
        "fr": "**DOCUMENT DE DÉMONSTRATION — NON OPPOSABLE.** Il repose sur "
              "des données ou des prix non destinés à la production.",
        "en": "**DEMONSTRATION DOCUMENT — NOT BINDING.** It rests on data or "
              "prices not intended for production use.",
    },
    "rapport.doc.pied": {
        "fr": "Rapport produit par KLASTOS21. Les grandeurs marquées non "
              "identifiables sont des domaines compatibles : toute valeur du "
              "domaine explique le bulletin aussi bien qu'une autre.",
        "en": "Report produced by KLASTOS21. Quantities marked not "
              "identifiable are compatible ranges: any value within a range "
              "explains the assay just as well as any other.",
    },

    # ---------------------------------------------------- refus et messages
    "rapport.refus.prix_demo": {
        "fr": "Jeu de prix non destiné à la production ({label}). "
              "Brancher un flux avant émission.",
        "en": "Price set not intended for production use ({label}). "
              "Connect a live feed before issuing.",
    },
    "rapport.refus.bouclage": {
        "fr": "Bouclage massique hors tolérance ({ecart:.2f} %). Une analyse "
              "complémentaire est requise avant valorisation.",
        "en": "Mass closure out of tolerance ({ecart:.2f} %). A further "
              "assay is required before valuation.",
    },

    # ----------------------------------------------- lignes de diagnostic
    "rapport.ligne.degres": {
        "fr": "Degrés de liberté non contraints",
        "en": "Unconstrained degrees of freedom",
    },
    "rapport.note.bien_pose": {
        "fr": "Le système est bien posé.",
        "en": "The system is well posed.",
    },
    "rapport.note.degenere": {
        "fr": "Certaines grandeurs ne sont pas identifiables par analyse "
              "élémentaire seule.",
        "en": "Some quantities are not identifiable from the elemental assay "
              "alone.",
    },
    "rapport.note.mal_determinees": {
        "fr": "{n} grandeur(s) identifiable(s) mais mal déterminée(s) : "
              "{liste}. Seuil d'exploitabilité retenu : {seuil:.0f} points.",
        "en": "{n} quantity(ies) identifiable but poorly constrained: "
              "{liste}. Usability threshold applied: {seuil:.0f} points.",
    },
    "rapport.note.reduire_pied": {
        "fr": "Une analyse plus fine ne réduira pas ces largeurs. Une donnée "
              "structurale (DRX) ou une attestation de provenance le ferait.",
        "en": "A finer assay will not reduce these widths. Structural data "
              "(XRD) or a provenance attestation would.",
    },

    # ------------------------------------------- conseil de quantification
    "rapport.valeur.gain_largeur": {
        "fr": "au moins {gain:.0f} % de largeur en moins",
        "en": "at least {gain:.0f} % less width",
    },
    "rapport.note.plage_pour_mesure": {
        "fr": "plage actuelle {plage:.2f} points, pour une mesure à "
              "{u:.1f} point(s)",
        "en": "current range {plage:.2f} points, for a measurement at "
              "{u:.1f} point(s)",
    },
    "rapport.note.sans_gain": {
        "fr": "Sans gain exploitable à cette incertitude : {liste}. "
              "Commander ces quantifications serait une dépense sans effet "
              "sur les plages de ce lot.",
        "en": "No usable gain at this uncertainty: {liste}. Ordering these "
              "quantifications would be spending with no effect on this "
              "lot's ranges.",
    },
    "rapport.note.aucun_conseil": {
        "fr": "Aucune quantification ne resserrerait utilement ce lot à "
              "{u:.1f} point(s) d'incertitude. Un laboratoire plus précis "
              "changerait la conclusion.",
        "en": "No quantification would usefully narrow this lot at "
              "{u:.1f} point(s) of uncertainty. A more precise laboratory "
              "would change the conclusion.",
    },
    "rapport.note.largeur_cumulee": {
        "fr": "Largeur cumulée actuelle des phases : {total:.2f} points.",
        "en": "Current cumulative width of the phases: {total:.2f} points.",
    },
    "rapport.aide.drx_sans_effet": {
        "fr": "La quantification fournie ne resserre aucune plage de ce "
              "lot : les phases qu'elle désigne étaient déjà déterminées, ou "
              "elle ne contraint pas les directions non identifiables.",
        "en": "The quantification provided narrows no range for this lot: "
              "the phases it names were already determined, or it does not "
              "constrain the non-identifiable directions.",
    },
    "rapport.note.drx_conflit_compte": {
        "fr": "{n} tirage(s) sur {total} en conflit ({taux:.0f} %). ",
        "en": "{n} draw(s) out of {total} in conflict ({taux:.0f} %). ",
    },
    "rapport.valeur.drx_avant_apres": {
        "fr": "{avant:.2f} -> {apres:.2f} points",
        "en": "{avant:.2f} -> {apres:.2f} points",
    },
    "rapport.note.drx_gain": {
        "fr": "{gain:.0f} % de largeur en moins",
        "en": "{gain:.0f} % less width",
    },

    # ------------------------------------------------- scenario oxygene
    "rapport.intro.scenario": {
        "fr": "L'oxygène n'a pas été dosé. La reconstitution le contraint "
              "néanmoins entre {bas:.2f} % et {haut:.2f} %. Un dosage "
              "n'apporterait donc quelque chose que s'il était plus précis "
              "que cette plage : son incertitude doit rester sous "
              "{umax:.2f} point. Au-delà, il confirmerait ce que le calcul "
              "donne déjà.",
        "en": "Oxygen was not assayed. The reconstruction nonetheless "
              "constrains it between {bas:.2f} % and {haut:.2f} %. An assay "
              "would therefore add something only if it were more precise "
              "than that range: its uncertainty must stay below "
              "{umax:.2f} point. Beyond that, it would confirm what the "
              "calculation already gives.",
    },
    "rapport.note.resterait_domaine": {
        "fr": "resterait un domaine compatible",
        "en": "would remain a compatible range",
    },
    "rapport.note.deviendraient_fermes": {
        "fr": "{n} grandeur(s) deviendraient fermes : {liste}.",
        "en": "{n} quantity(ies) would become determined: {liste}.",
    },
    "rapport.note.dosage_sans_effet": {
        "fr": "Le dosage n'apporterait RIEN à ces grandeurs ({liste}). Leur "
              "dégénérescence vit dans le sous-système fermé Li-Ni-Mn-Co-O, "
              "que l'oxygène ne contraint pas : seules une donnée "
              "structurale (DRX) ou une attestation de provenance la lèvent.",
        "en": "The assay would add NOTHING to these quantities ({liste}). "
              "Their degeneracy lives in the closed Li-Ni-Mn-Co-O "
              "subsystem, which oxygen does not constrain: only structural "
              "data (XRD) or a provenance attestation lifts it.",
    },

    # ----------------------------------------------------- valorisation
    "rapport.ligne.ecart": {"fr": "Écart", "en": "Deviation"},
    "rapport.ligne.cout": {
        "fr": "Coût de traitement retenu",
        "en": "Processing cost applied",
    },
    "rapport.note.teneurs_mal_determinees": {
        "fr": "Teneurs mal déterminées entrant dans le prix : {liste}. La "
              "fourchette de valorisation s'en trouve élargie.",
        "en": "Poorly constrained grades entering the price: {liste}. The "
              "valuation range is widened accordingly.",
    },
    "rapport.note.decotes_non_chiffrees": {
        "fr": "Les décotes commerciales associées ne sont pas chiffrées "
              "dans cette version.",
        "en": "The associated commercial deductions are not quantified in "
              "this version.",
    },

    # ------------------------------------------- bloc de verdict, en tete
    "rapport.verdict.non_calculee": {
        "fr": "non calculée", "en": "not calculated",
    },
    "rapport.verdict.sans_prix": {
        "fr": "Aucun prix de référence n'a été fourni pour ce rapport. La "
              "reconstitution, les domaines compatibles et les diagnostics "
              "ci-dessous restent valides.",
        "en": "No reference price was supplied for this report. The "
              "reconstruction, the compatible ranges and the diagnostics "
              "below remain valid.",
    },
    "rapport.verdict.prix_maximal": {
        "fr": "Prix maximal à payer", "en": "Maximum price to pay",
    },
    "rapport.verdict.base_prix": {
        "fr": "Calculé sur les seules teneurs élémentaires, qui sont "
              "identifiables. Aucune ventilation par grade n'entre dans ce "
              "chiffre. La largeur de la fourchette reflète l'incertitude "
              "analytique.",
        "en": "Computed on the elemental grades alone, which are "
              "identifiable. No breakdown by grade enters this figure. The "
              "width of the range reflects the analytical uncertainty.",
    },

    # ------------------------------------- legendes des barres d'intervalle
    "rapport.doc.unite_points": {"fr": "points", "en": "points"},
    "rapport.legende.largeur_actuelle": {
        "fr": "largeur actuelle", "en": "current width",
    },
    "rapport.legende.ferme": {"fr": "ferme", "en": "determined"},
    "rapport.legende.mal_determine": {
        "fr": "mal déterminé", "en": "poorly constrained",
    },
    "rapport.legende.domaine": {
        "fr": "domaine compatible", "en": "compatible range",
    },

    # ------------- notes heritees des modules amont, rendues a la langue
    # Elles sont produites par identifiability.py, qui ne connait pas la
    # langue du livrable. Le rapport les traduit au moment ou il les pose :
    # c'est lui qui sait pour qui le document sort.
    "rapport.note.non_identifiable": {
        "fr": "Ventilation non identifiable par analyse élémentaire seule.",
        "en": "Breakdown not identifiable from the elemental assay alone.",
    },
    "rapport.note.carbone": {
        "fr": "La séparation graphite / noir de carbone nécessite des "
              "données texturales ou structurales, non prises en compte "
              "dans cette première version.",
        "en": "Separating graphite from carbon black requires textural or "
              "structural data, not accounted for in this first version.",
    },

    # ------------------------------------------------- mentions de fond
    "rapport.mention.detection": {
        "fr": "Le contrôle du résidu ne détecte pas une déclaration de "
              "provenance inexacte en dessous d'environ 5 % de phase non "
              "déclarée. Une absence d'alerte ne vaut pas certification de "
              "la déclaration.",
        "en": "The residual check does not detect an inaccurate provenance "
              "declaration below roughly 5 % of undeclared phase. The "
              "absence of a warning does not certify the declaration.",
    },
    "rapport.mention.valorisation": {
        "fr": "La valorisation ne repose que sur les teneurs élémentaires, "
              "qui sont identifiables. Aucune ventilation par grade n'entre "
              "dans le calcul du prix.",
        "en": "The valuation rests solely on the elemental grades, which are "
              "identifiable. No breakdown by grade enters the price "
              "calculation.",
    },
    "rapport.mention.mal_determine": {
        "fr": "Grandeur identifiable mais mal déterminée : le système la "
              "contraint en théorie, mais son conditionnement est tel que la "
              "fourchette reste trop large pour être exploitée en l'état. "
              "L'identifiabilité est binaire, le conditionnement est continu.",
        "en": "Quantity identifiable but poorly constrained: the system "
              "determines it in theory, but its conditioning is such that "
              "the range stays too wide to be used as it stands. "
              "Identifiability is binary, conditioning is continuous.",
    },
    "rapport.mention.fourchette": {
        "fr": "Les valeurs sont rapportées en fourchette. La largeur reflète "
              "l'incertitude analytique sur les teneurs fermes.",
        "en": "Values are reported as ranges. The width reflects the "
              "analytical uncertainty on the determined grades.",
    },
    "rapport.mention.drx": {
        "fr": "Une quantification par diffraction est une MESURE, avec son "
              "incertitude. Elle entre donc en encadrement et non en "
              "égalité : elle resserre les plages compatibles, elle ne rend "
              "aucune grandeur ferme. Le tableau donne la plage avant et "
              "après.",
        "en": "A diffraction quantification is a MEASUREMENT, with its own "
              "uncertainty. It therefore enters as a bound and not as an "
              "equality: it narrows the compatible ranges, it makes no "
              "quantity determined. The table gives the range before and "
              "after.",
    },
    "rapport.mention.drx_conflit": {
        "fr": "Taux de conflit élevé entre la quantification et le bulletin : "
              "pour une part importante des tirages de bruit analytique, "
              "aucune répartition des phases ne satisfait les deux mesures. "
              "Ces tirages ont été CONSERVÉS avec leurs bornes non "
              "contraintes — les écarter aurait resserré l'incertitude du "
              "laboratoire au motif d'une mesure qui ne porte pas sur elle. "
              "Un taux élevé signale une analyse chimique, une "
              "quantification ou un modèle de phases à reprendre.",
        "en": "High conflict rate between the quantification and the assay: "
              "for a sizeable share of the analytical-noise draws, no phase "
              "distribution satisfies both measurements. Those draws were "
              "KEPT with their bounds unconstrained — discarding them would "
              "have narrowed the laboratory's uncertainty on the strength of "
              "a measurement that does not bear on it. A high rate points to "
              "a chemical assay, a quantification or a phase model that "
              "needs revisiting.",
    },
    "rapport.mention.conseil": {
        "fr": "Une quantification par diffraction se paie, et toutes les "
              "phases ne la valent pas. Les gains annoncés sont des "
              "PLANCHERS : ils sont pris au pire placement de la valeur "
              "mesurée dans la plage compatible, parce que cette valeur est "
              "inconnue avant la mesure.",
        "en": "A diffraction quantification costs money, and not every phase "
              "is worth it. The stated gains are FLOORS: they are taken at "
              "the worst placement of the measured value within the "
              "compatible range, because that value is unknown before the "
              "measurement.",
    },
    "rapport.mention.scenario": {
        "fr": "Aucun chiffre de cette section n'est opposable. Ce sont des "
              "LARGEURS PROJETÉES sous l'hypothèse d'un dosage que vous ne "
              "possédez pas. Elles ne modifient en rien les résultats des "
              "sections précédentes, qui restent les seuls engagés.",
        "en": "No figure in this section is binding. These are PROJECTED "
              "WIDTHS under the assumption of an assay you do not have. They "
              "change nothing in the results of the preceding sections, "
              "which remain the only ones committed to.",
    },
    "rapport.mention.scenario_base": {
        "fr": "Les largeurs de cette section sont les largeurs STRUCTURELLES "
              "du bulletin central : la part de l'incertitude qui vient de "
              "la dégénérescence, et elle seule. Elles sont plus étroites "
              "que les fourchettes des sections précédentes, qui ajoutent "
              "l'incertitude analytique du laboratoire. Un dosage d'oxygène "
              "ne réduit que la part structurelle ; la part analytique, elle, "
              "demande un meilleur laboratoire ou des réplicats.",
        "en": "The widths in this section are the STRUCTURAL widths of the "
              "central assay: the share of the uncertainty that comes from "
              "the degeneracy, and that share alone. They are narrower than "
              "the ranges in the preceding sections, which add the "
              "laboratory's analytical uncertainty. An oxygen assay reduces "
              "only the structural share; the analytical share calls for a "
              "better laboratory or for replicates.",
    },
    "rapport.mention.scenario_piege": {
        "fr": "Le scénario ne réinjecte jamais la teneur en oxygène prédite "
              "par la reconstitution : elle sort de la solution elle-même, "
              "donc elle n'apporterait aucune information et rendrait les "
              "grandeurs exactement déterminées pour la seule raison que le "
              "solveur a choisi ce point. Les largeurs ci-dessus sont "
              "obtenues en balayant toute la plage compatible de l'oxygène.",
        "en": "The scenario never feeds back the oxygen grade predicted by "
              "the reconstruction: that grade comes out of the solution "
              "itself, so it would carry no information and would make the "
              "quantities exactly determined for the sole reason that the "
              "solver picked that point. The widths above are obtained by "
              "sweeping the whole compatible range of oxygen.",
    },
    "rapport.mention.refus_rediffusion": {
        "fr": "Prix d'agence sans licence de rediffusion ({label}). Un "
              "abonnement d'agence couvre l'usage interne, pas l'affichage "
              "dans un document remis à un tiers. Trois issues : obtenir "
              "l'autorisation écrite de l'agence et relancer la "
              "récupération avec la licence, demander au client ses propres "
              "prix, ou émettre ce rapport en interne "
              "(destinataire='interne').",
        "en": "Agency prices without a redistribution licence ({label}). An "
              "agency subscription covers internal use, not display in a "
              "document handed to a third party. Three ways out: obtain the "
              "agency's written authorisation and re-run the retrieval with "
              "the licence, ask the client for their own prices, or issue "
              "this report internally (destinataire='interne').",
    },

    # ------------------------------------------------------------- protocole
    "rapport.protocole.renvoi": {
        "fr": "Les engagements méthodologiques figurent au protocole joint.",
        "en": "The methodological commitments are set out in the "
              "accompanying protocol, which is available in French only "
              "(protocole.md). This report does not restate them in English, "
              "and no English version of the protocol is binding.",
    },
}


# ==========================================================================
# Acces
# ==========================================================================

def t(cle: str, langue: str = DEFAUT, **champs: object) -> str:
    """
    Rend le message `cle` dans `langue`, champs de format appliques.

    Une cle absente leve. Le silence serait pire : un rapport client avec un
    trou a la place d'un titre part quand meme, et personne ne le voit avant
    le destinataire.

    Une langue inconnue retombe sur le francais sans lever : mieux vaut un
    rapport lisible dans la mauvaise langue qu'un rapport qui n'existe pas.
    """
    try:
        entree = CATALOGUE[cle]
    except KeyError:
        raise CleInconnue(
            f"{cle!r} n'est pas au catalogue i18n. Ajoutez-la dans "
            f"klastos/i18n.py plutot que d'ecrire le texte en clair."
        ) from None

    texte = entree.get(langue) or entree[DEFAUT]
    return texte.format(**champs) if champs else texte


def langue_valide(langue: str | None) -> str:
    """Normalise une langue d'entree vers une langue servie."""
    if not langue:
        return DEFAUT
    court = str(langue).strip().lower()[:2]
    return court if court in LANGUES else DEFAUT


def cles_par_prefixe(prefixe: str) -> list[str]:
    """Les cles d'une couche, triees. Sert aux tests de completude."""
    return sorted(c for c in CATALOGUE if c.startswith(prefixe))
