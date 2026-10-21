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
    """
    Cle absente du catalogue. C'est un bug, pas un resultat.

    Meme correction que `market.MissingPriceError`, et pour la meme raison :
    la base reste `KeyError` - une cle absente du catalogue est bien une cle
    absente - mais `KeyError.__str__` entourerait le message de guillemets,
    alors que ce message est une phrase destinee a celui qui releve le code.
    """

    def __str__(self) -> str:
        if len(self.args) == 1 and isinstance(self.args[0], str):
            return self.args[0]
        return super().__str__()


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
    "rapport.mention.fx_fournie": {
        "fr": "Le taux de change ci-dessus a été FOURNI avec le jeu de prix. "
              "KLASTOS21 n'intègre aucune source de taux : la valeur, sa "
              "source et sa date sont celles déclarées par le fournisseur, "
              "et c'est son taux qui engage la transaction.",
        "en": "The exchange rate above was SUPPLIED with the price set. "
              "KLASTOS21 integrates no rate source: the value, its source "
              "and its date are those declared by the supplier, and it is "
              "their rate that binds the transaction.",
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

    # ======================================================================
    # Interface
    # ======================================================================

    # ------------------------------------------------- choix de la langue
    "ui.langue.libelle": {"fr": "Langue", "en": "Language"},
    "ui.langue.aide": {
        "fr": "Langue de l'interface et du rapport produit. Le protocole "
              "méthodologique reste en français.",
        "en": "Language of the interface and of the report produced. The "
              "methodological protocol remains in French.",
    },
    "ui.langue.nom.fr": {"fr": "Français", "en": "French"},
    "ui.langue.nom.en": {"fr": "Anglais", "en": "English"},

    # --------------------------------------------- en-tete page d'analyse
    "ui.analyse.titre": {
        "fr": "Analyse minéralogique de black mass",
        "en": "Mineralogical analysis of black mass",
    },
    "ui.analyse.chapeau": {
        "fr": "Importez votre bulletin d'analyse et obtenez la "
              "reconstitution minéralogique de votre échantillon, avec ce "
              "qui est déterminé et ce qui ne peut pas l'être.",
        "en": "Import your assay certificate and obtain the mineralogical "
              "reconstruction of your sample, together with what is "
              "determined and what cannot be.",
    },
    "ui.analyse.garantie_titre": {
        "fr": "Ce que l'outil garantit", "en": "What the tool guarantees",
    },
    "ui.analyse.garantie": {
        "fr": "Aucun chiffre que la donnée ne porte. Une grandeur non "
              "identifiable sort en domaine, jamais en valeur unique.",
        "en": "No figure the data does not carry. A non-identifiable "
              "quantity comes out as a range, never as a single value.",
    },

    # ----------------------------------------------------------------- DRX
    "ui.drx.titre": {
        "fr": "Quantification par diffraction",
        "en": "Diffraction quantification",
    },
    "ui.drx.facultatif": {
        "fr": "Facultatif. C'est le levier le plus puissant du lot.",
        "en": "Optional. It is the most powerful lever available.",
    },
    "ui.drx.fichier": {
        "fr": "Fichier de quantification DRX",
        "en": "XRD quantification file",
    },
    "ui.drx.aide": {
        "fr": "Une phase par ligne : phase, valeur, incertitude. La colonne "
              "d'incertitude est OBLIGATOIRE — une mesure Rietveld est "
              "précise à 1 ou 3 points, et sans son incertitude elle "
              "passerait pour exacte.",
        "en": "One phase per row: phase, value, uncertainty. The "
              "uncertainty column is MANDATORY — a Rietveld measurement is "
              "precise to 1 or 3 points, and without its uncertainty it "
              "would pass for exact.",
    },
    "ui.drx.base": {
        "fr": "Base de normalisation", "en": "Normalisation basis",
    },
    "ui.drx.base_aide": {
        "fr": "Un diffractogramme ne voit que le cristallin. Sur base "
              "cristalline, les niveaux ne sont pas contraints : seuls les "
              "rapports entre phases le sont, et il faut donc une phase de "
              "plus.",
        "en": "A diffractogram sees only the crystalline fraction. On a "
              "crystalline basis the levels are not constrained: only the "
              "ratios between phases are, so one more phase is needed.",
    },
    "ui.drx.conseil": {
        "fr": "Calculer quelle phase faire quantifier",
        "en": "Compute which phase to have quantified",
    },
    "ui.drx.conseil_aide": {
        "fr": "Classe les phases par le resserrement qu'une mesure "
              "apporterait, au pire placement. Quelques secondes.",
        "en": "Ranks the phases by the narrowing a measurement would bring, "
              "at its worst placement. A few seconds.",
    },
    "ui.drx.incertitude": {
        "fr": "Incertitude supposée du laboratoire (points)",
        "en": "Assumed laboratory uncertainty (points)",
    },

    # ------------------------------------------------- lancement et verdict
    "ui.prix.absent": {
        "fr": "Aucun prix chargé : le rapport sortira sans valorisation. "
              "Onglet **Prix** pour en fournir.",
        "en": "No prices loaded: the report will come out without a "
              "valuation. Use the **Prices** tab to supply some.",
    },
    "ui.prix.charge": {"fr": "Prix : {label}", "en": "Prices: {label}"},
    "ui.analyse.lancer": {
        "fr": "Lancer l'analyse", "en": "Run the analysis",
    },
    "ui.analyse.aucune": {
        "fr": "Aucune analyse en cours", "en": "No analysis in progress",
    },
    "ui.analyse.aucune_detail": {
        "fr": "Importez un bulletin à gauche, puis lancez l'analyse.",
        "en": "Import an assay on the left, then run the analysis.",
    },
    "ui.analyse.en_cours": {
        "fr": "Reconstitution et propagation d'incertitude…",
        "en": "Reconstruction and uncertainty propagation…",
    },
    "ui.verdict.ok": {"fr": "Analyse terminée", "en": "Analysis complete"},
    "ui.verdict.alerte": {
        "fr": "Analyse terminée — à vérifier",
        "en": "Analysis complete — needs checking",
    },
    "ui.verdict.rejet": {
        "fr": "Lot inexploitable en l'état",
        "en": "Lot unusable as it stands",
    },
    "ui.verdict.ok_sous": {
        "fr": "Votre rapport est prêt.", "en": "Your report is ready.",
    },
    "ui.verdict.alerte_sous": {
        "fr": "Le rapport est disponible, mais le bouclage massique demande "
              "une explication.",
        "en": "The report is available, but the mass closure calls for an "
              "explanation.",
    },
    "ui.verdict.rejet_sous": {
        "fr": "Le bouclage est hors tolérance.",
        "en": "The closure is out of tolerance.",
    },
    "ui.demo.avert": {
        "fr": "Document de démonstration — non opposable.",
        "en": "Demonstration document — not binding.",
    },

    # -------------------------------------------------------------- onglets
    "ui.onglet.ensemble": {"fr": "Vue d'ensemble", "en": "Overview"},
    "ui.onglet.composition": {
        "fr": "Composition minéralogique", "en": "Mineralogical composition",
    },
    "ui.onglet.reduire": {
        "fr": "Réduire l'incertitude", "en": "Reduce the uncertainty",
    },
    "ui.onglet.rapport": {"fr": "Rapport", "en": "Report"},

    # --------------------------------------------- onglet « rapport »
    "ui.rapport.telecharger": {
        "fr": "Télécharger le rapport (HTML)",
        "en": "Download the report (HTML)",
    },
    "ui.rapport.telecharger_aide": {
        "fr": "Ouvrez-le dans un navigateur, puis Ctrl+P pour un PDF.",
        "en": "Open it in a browser, then Ctrl+P for a PDF.",
    },
    "ui.rapport.enregistre": {
        "fr": "Enregistré dans l'historique (#{i})",
        "en": "Recorded in the history (#{i})",
    },
    "ui.rapport.limites_courtes": {
        "fr": "Limites déclarées", "en": "Declared limits",
    },
    "ui.rapport.apercu": {
        "fr": "Aperçu du rapport imprimable",
        "en": "Preview of the printable report",
    },

    # ------------------------------------------------------- page « prix »
    "ui.prix.titre": {"fr": "Prix de référence", "en": "Reference prices"},
    "ui.prix.chapeau": {
        "fr": "Sans prix, pas de valorisation : le rapport reste complet "
              "mais ne porte aucun chiffre commercial. Il n'existe nulle "
              "part dans KLASTOS21 de jeu de prix par défaut.",
        "en": "Without prices there is no valuation: the report stays "
              "complete but carries no commercial figure. Nowhere in "
              "KLASTOS21 is there a default price set.",
    },
    "ui.prix.route_titre": {
        "fr": "Route prioritaire", "en": "Preferred route",
    },
    "ui.prix.route": {
        "fr": "Les prix fournis par le client. Ce sont ses données : aucune "
              "licence d'agence ne les restreint.",
        "en": "Prices supplied by the client. They are the client's own "
              "data: no agency licence restricts them.",
    },
    "ui.prix.source": {"fr": "Source", "en": "Source"},
    "ui.prix.mode_fichier": {"fr": "Fichier de prix", "en": "Price file"},
    "ui.prix.mode_agence": {"fr": "Flux d'agence", "en": "Agency feed"},
    "ui.prix.aucun_titre": {
        "fr": "Aucun prix chargé", "en": "No prices loaded",
    },
    "ui.prix.aucun_detail": {
        "fr": "Le rapport sortira sans valorisation.",
        "en": "The report will come out without a valuation.",
    },
    "ui.prix.col_metal": {"fr": "Métal", "en": "Metal"},
    "ui.prix.col_prix": {
        "fr": "Prix ({devise}/t)", "en": "Price ({devise}/t)",
    },
    "ui.prix.col_date": {"fr": "Date", "en": "Date"},
    "ui.prix.col_reference": {"fr": "Référence", "en": "Reference"},
    "ui.prix.col_source": {"fr": "Source", "en": "Source"},
    "ui.prix.usage_interne": {
        "fr": "**USAGE INTERNE.** Ces prix ne peuvent pas figurer dans un "
              "document remis à un tiers. Un rapport avec destinataire "
              "« tiers » sera refusé — et c'est voulu.",
        "en": "**INTERNAL USE.** These prices cannot appear in a document "
              "handed to a third party. A report addressed to a third party "
              "will be refused — and that is deliberate.",
    },
    "ui.prix.carte_fichier": {"fr": "Fichier", "en": "File"},
    "ui.prix.fichier": {
        "fr": "Prix au format CSV ou JSON", "en": "Prices as CSV or JSON",
    },
    "ui.prix.payables": {
        "fr": "Conditions commerciales (JSON)",
        "en": "Commercial terms (JSON)",
    },
    "ui.prix.marche": {"fr": "Marché", "en": "Market"},
    "ui.prix.charger": {"fr": "Charger ces prix", "en": "Load these prices"},
    "ui.prix.carte_agence": {"fr": "Agence", "en": "Agency"},
    "ui.prix.agence": {"fr": "Agence", "en": "Agency"},
    "ui.prix.identifiants": {
        "fr": "Les identifiants sont lus dans les variables "
              "d'environnement, jamais saisis ici ni stockés.",
        "en": "Credentials are read from environment variables, never typed "
              "here and never stored.",
    },
    "ui.prix.licence": {
        "fr": "J'atteste détenir l'autorisation écrite de rediffuser ces "
              "prix à un tiers.",
        "en": "I certify that I hold written authorisation to redistribute "
              "these prices to a third party.",
    },
    "ui.prix.licence_aide": {
        "fr": "Un abonnement d'agence couvre l'usage interne, pas la "
              "rediffusion. Sans cette autorisation, un rapport destiné à "
              "un client sera refusé — et c'est voulu.",
        "en": "An agency subscription covers internal use, not "
              "redistribution. Without this authorisation, a report intended "
              "for a client will be refused — and that is deliberate.",
    },
    "ui.prix.marche_payables": {
        "fr": "Marché pour les payables", "en": "Market for payables",
    },
    "ui.prix.recuperer": {
        "fr": "Récupérer les prix du jour", "en": "Fetch today's prices",
    },
    "ui.prix.licence_ok": {
        "fr": "rediffusion autorisée", "en": "redistribution authorised",
    },
    "ui.prix.licence_non": {
        "fr": "USAGE INTERNE uniquement", "en": "INTERNAL USE only",
    },
    "ui.prix.releve_auto": {
        "fr": "{source}, relevé automatique",
        "en": "{source}, automatic retrieval",
    },
    "ui.prix.identifiants_absents": {
        "fr": "Identifiants absents", "en": "Credentials missing",
    },

    # ------------------------------------------------- page « historique »
    "ui.histo.titre": {"fr": "Lots analysés", "en": "Lots analysed"},
    "ui.histo.chapeau": {
        "fr": "Retrouver un lot, ressortir le rapport tel qu'il a été émis, "
              "rejouer une reconstitution contestée.",
        "en": "Find a lot again, reissue the report exactly as it was "
              "issued, replay a contested reconstruction.",
    },
    "ui.histo.locale_titre": {"fr": "Donnée locale", "en": "Local data"},
    "ui.histo.locale": {
        "fr": "L'historique reste sur cette machine. Un carnet de lots est "
              "une donnée commerciale.",
        "en": "The history stays on this machine. A book of lots is "
              "commercial data.",
    },
    "ui.histo.vide": {
        "fr": "Aucune analyse enregistrée", "en": "No analysis recorded",
    },
    "ui.histo.col_lot": {"fr": "Lot", "en": "Lot"},
    "ui.histo.col_client": {"fr": "Client", "en": "Client"},
    "ui.histo.col_analyse_le": {"fr": "Analysé le", "en": "Analysed on"},
    "ui.histo.col_bouclage": {"fr": "Bouclage", "en": "Closure"},
    "ui.histo.col_prix_max": {"fr": "Prix maximal", "en": "Maximum price"},
    "ui.histo.col_destinataire": {"fr": "Destinataire", "en": "Recipient"},
    "ui.histo.col_demo": {"fr": "Démo", "en": "Demo"},
    "ui.histo.oui": {"fr": "oui", "en": "yes"},
    "ui.histo.ressortir": {
        "fr": "Ressortir une analyse", "en": "Reissue an analysis",
    },
    "ui.histo.afficher": {
        "fr": "Afficher le rapport émis", "en": "Show the issued report",
    },
    "ui.histo.rejouer": {
        "fr": "Rejouer la reconstitution", "en": "Replay the reconstruction",
    },
    "ui.histo.rejouer_aide": {
        "fr": "Mêmes teneurs, même provenance, même graine. Les prix ne sont "
              "pas restitués : ceux de l'époque seraient périmés.",
        "en": "Same grades, same provenance, same seed. Prices are not "
              "restored: those of the time would be stale.",
    },
    "ui.histo.rejoue": {
        "fr": "Reconstitution rejouée. Voir la page Analyse.",
        "en": "Reconstruction replayed. See the Analysis page.",
    },

    # ------------------------------------------------------- page « aide »
    "ui.aide.titre": {
        "fr": "Comment lire un rapport KLASTOS21",
        "en": "How to read a KLASTOS21 report",
    },
    "ui.aide.chapeau": {
        "fr": "Trois notions suffisent à exploiter l'outil sans se tromper.",
        "en": "Three notions are enough to use the tool without going wrong.",
    },
    "ui.aide.engagement_titre": {"fr": "Engagement", "en": "Commitment"},
    "ui.aide.engagement": {
        "fr": "Le protocole méthodologique complet accompagne chaque "
              "rapport.",
        "en": "The complete methodological protocol accompanies every "
              "report.",
    },
    "ui.aide.determinee_titre": {
        "fr": "Grandeur déterminée", "en": "Determined quantity",
    },
    "ui.aide.determinee": {
        "fr": "L'analyse élémentaire la contraint à une valeur unique, "
              "quelle que soit la ventilation retenue par le solveur. Ce "
              "sont les seules grandeurs opposables, et les seules qui "
              "entrent dans le prix.",
        "en": "The elemental assay pins it to a single value, whatever "
              "breakdown the solver settles on. These are the only "
              "quantities that can be relied upon, and the only ones that "
              "enter the price.",
    },
    "ui.aide.mal_determinee_titre": {
        "fr": "Grandeur mal déterminée",
        "en": "Poorly constrained quantity",
    },
    "ui.aide.mal_determinee": {
        "fr": "Déterminée en théorie, mais le conditionnement du système "
              "rend la fourchette trop large pour être exploitée. "
              "L'identifiabilité est binaire, le conditionnement est "
              "continu.",
        "en": "Determined in theory, but the conditioning of the system "
              "makes the range too wide to be used. Identifiability is "
              "binary, conditioning is continuous.",
    },
    "ui.aide.domaine_titre": {
        "fr": "Domaine compatible", "en": "Compatible range",
    },
    "ui.aide.domaine": {
        "fr": "Toute valeur du domaine explique le bulletin aussi bien "
              "qu'une autre. Ce n'est pas une imprécision de mesure : c'est "
              "une propriété du système. Une meilleure analyse chimique ne "
              "la réduit pas ; une donnée structurale ou une attestation de "
              "provenance, si.",
        "en": "Any value in the range explains the assay just as well as any "
              "other. This is not measurement imprecision: it is a property "
              "of the system. A better chemical assay does not reduce it; "
              "structural data or a provenance attestation does.",
    },
    "ui.aide.bouclage_titre": {
        "fr": "Bouclage massique", "en": "Mass closure",
    },
    "ui.aide.bouclage": {
        "fr": "La somme des phases reconstituées. Ce qui manque pour "
              "atteindre 100 % n'est pas une erreur de calcul : c'est de "
              "l'humidité, une phase absente du modèle, ou une provenance "
              "mal déclarée.",
        "en": "The sum of the reconstructed phases. What is missing to "
              "reach 100 % is not a calculation error: it is moisture, a "
              "phase absent from the model, or a misdeclared provenance.",
    },

    # ---------------------------------------------- titres de refus
    "ui.refus.rapport": {"fr": "Rapport refusé", "en": "Report refused"},
    "ui.refus.source_prix": {
        "fr": "Source de prix non destinée à la production",
        "en": "Price source not intended for production use",
    },
    "ui.refus.prix_perimes": {"fr": "Prix périmés", "en": "Stale prices"},
    "ui.refus.prix_manquant": {
        "fr": "Prix manquant", "en": "Missing price",
    },
    "ui.refus.prix_invraisemblable": {
        "fr": "Prix invraisemblable", "en": "Implausible price",
    },
    "ui.refus.bulletin": {
        "fr": "Bulletin illisible", "en": "Assay unreadable",
    },
    "ui.refus.analyse": {
        "fr": "Analyse impossible", "en": "Analysis not possible",
    },

    # ------------------------------- onglet « reduire l'incertitude »
    "ui.carte.scenario": {
        "fr": "Ce qu'un dosage d'oxygène apporterait",
        "en": "What an oxygen assay would bring",
    },
    "ui.scenario.deja_dose": {
        "fr": "L'oxygène est dosé dans ce bulletin : il n'y a plus rien à "
              "projeter.",
        "en": "Oxygen is assayed in this certificate: there is nothing left "
              "to project.",
    },
    "ui.methode.scenario": {
        "fr": "La reconstitution contraint déjà l'oxygène entre "
              "<b>{bas:.2f} %</b> et <b>{haut:.2f} %</b>. Un dosage "
              "n'apporte donc quelque chose que si son incertitude reste "
              "sous <b>{umax:.2f} point</b>. Au-delà, il confirme ce que le "
              "calcul donne déjà. Ces largeurs sont des projections : aucune "
              "n'est opposable.",
        "en": "The reconstruction already constrains oxygen between "
              "<b>{bas:.2f} %</b> and <b>{haut:.2f} %</b>. An assay "
              "therefore adds something only if its uncertainty stays below "
              "<b>{umax:.2f} point</b>. Beyond that, it confirms what the "
              "calculation already gives. These widths are projections: none "
              "is binding.",
    },
    "ui.carte.drx": {
        "fr": "Quantification par diffraction (DRX)",
        "en": "Diffraction quantification (XRD)",
    },
    "ui.methode.drx_posee": {
        "fr": "{n} phase(s) quantifiée(s), base <b>{base}</b>. Une mesure "
              "entre en <b>encadrement</b> et non en égalité : elle resserre "
              "les plages, elle ne rend aucune grandeur ferme — une "
              "inégalité borne une direction nulle, elle ne la supprime pas.",
        "en": "{n} phase(s) quantified, {base} basis. A measurement enters "
              "as a <b>bound</b> and not as an equality: it narrows the "
              "ranges, it makes no quantity determined — an inequality "
              "bounds a null direction, it does not remove it.",
    },
    "ui.drx.sans_effet": {
        "fr": "Cette quantification ne resserre aucune plage de ce lot : les "
              "phases qu'elle désigne étaient déjà déterminées, ou elle ne "
              "contraint pas les directions non identifiables.",
        "en": "This quantification narrows no range for this lot: the phases "
              "it names were already determined, or it does not constrain "
              "the non-identifiable directions.",
    },
    "ui.drx.conflit": {
        "fr": "**{n} tirage(s) sur {total} en conflit ({taux:.0f} %).** Pour "
              "cette part des tirages de bruit analytique, aucune "
              "répartition des phases ne satisfait à la fois le bulletin et "
              "la quantification. Ces tirages sont **conservés** avec leurs "
              "bornes non contraintes : les écarter aurait resserré "
              "l'incertitude du laboratoire au motif d'une mesure qui ne "
              "porte pas sur elle. Un taux élevé signale une analyse, une "
              "quantification ou un modèle de phases à reprendre.",
        "en": "**{n} draw(s) out of {total} in conflict ({taux:.0f} %).** "
              "For that share of the analytical-noise draws, no phase "
              "distribution satisfies both the assay and the "
              "quantification. Those draws are **kept** with their bounds "
              "unconstrained: discarding them would have narrowed the "
              "laboratory's uncertainty on the strength of a measurement "
              "that does not bear on it. A high rate points to an assay, a "
              "quantification or a phase model that needs revisiting.",
    },
    "ui.methode.drx_absente": {
        "fr": "Aucune quantification fournie. Déposez-en une dans la colonne "
              "de gauche. Mesuré sur un lot en provenance VE attestée : une "
              "seule phase quantifiée à <b>±2 points</b> retire <b>72 %</b> "
              "de la largeur cumulée. Mais toutes les phases ne se valent "
              "pas — cochez le calcul du conseil pour savoir laquelle "
              "commander.",
        "en": "No quantification supplied. Drop one in the left-hand column. "
              "Measured on a lot with attested EV provenance: a single phase "
              "quantified to <b>±2 points</b> removes <b>72 %</b> of the "
              "cumulative width. But not every phase is worth the same — "
              "tick the advice calculation to find out which one to order.",
    },
    "ui.carte.conseil": {
        "fr": "Quelle phase faire quantifier",
        "en": "Which phase to have quantified",
    },
    "ui.methode.conseil": {
        "fr": "{resume} Les gains sont des <b>planchers</b> : ils sont pris "
              "au pire placement de la valeur mesurée dans la plage "
              "compatible, puisque cette valeur est inconnue avant la "
              "mesure.",
        "en": "{resume} The gains are <b>floors</b>: they are taken at the "
              "worst placement of the measured value within the compatible "
              "range, since that value is unknown before the measurement.",
    },
    "ui.conseil.col_phase": {"fr": "Phase", "en": "Phase"},
    "ui.conseil.col_plage": {
        "fr": "Plage actuelle", "en": "Current range",
    },
    "ui.conseil.col_gain": {
        "fr": "Gain au pire cas", "en": "Worst-case gain",
    },
    "ui.conseil.col_verdict": {"fr": "Verdict", "en": "Verdict"},
    "ui.conseil.a_commander": {"fr": "à commander", "en": "worth ordering"},
    "ui.conseil.sans_effet": {"fr": "sans effet", "en": "no effect"},

    # ------------------------------------------- onglet « vue d'ensemble »
    "ui.tuile.prix_max": {
        "fr": "Prix maximal à payer", "en": "Maximum price to pay",
    },
    "ui.tuile.par_tonne": {
        "fr": "{devise} par tonne", "en": "{devise} per tonne",
    },
    "ui.tuile.sans_prix": {
        "fr": "aucun prix fourni", "en": "no prices supplied",
    },
    "ui.tuile.degres": {
        "fr": "Degrés de liberté", "en": "Degrees of freedom",
    },
    "ui.tuile.degres_note": {
        "fr": "non contraints par l'analyse élémentaire",
        "en": "unconstrained by the elemental assay",
    },
    "ui.tuile.non_expliques": {
        "fr": "{part:.2f} % non expliqués",
        "en": "{part:.2f} % unexplained",
    },
    "ui.tuile.determinees": {
        "fr": "Grandeurs déterminées", "en": "Determined quantities",
    },
    "ui.tuile.en_domaine": {
        "fr": "{n} en domaine compatible",
        "en": "{n} as a compatible range",
    },
    "ui.carte.composition": {
        "fr": "Composition reconstituée", "en": "Reconstructed composition",
    },
    "ui.carte.teneurs": {
        "fr": "Teneurs élémentaires du bulletin",
        "en": "Elemental grades from the assay",
    },
    "ui.carte.bouclage": {"fr": "Bouclage massique", "en": "Mass closure"},
    "ui.methode.camembert_elements": {
        "fr": "Ce camembert porte la composition <b>élémentaire</b>, qui est "
              "déterminée, et non les phases minérales, qui ne le sont pas. "
              "Le gris est la masse que le modèle n'explique pas : humidité, "
              "phase absente du modèle, ou provenance mal déclarée. Il "
              "bascule automatiquement sur les phases le jour où celles-ci "
              "deviennent fermes.",
        "en": "This pie chart carries the <b>elemental</b> composition, "
              "which is determined, and not the mineral phases, which are "
              "not. The grey is the mass the model does not explain: "
              "moisture, a phase absent from the model, or a misdeclared "
              "provenance. It switches to phases automatically the day those "
              "become determined.",
    },
    "ui.methode.camembert_phases": {
        "fr": "Toutes les phases sont déterminées sur ce lot : le camembert "
              "porte donc directement la <b>minéralogie</b>.",
        "en": "Every phase is determined on this lot, so the pie chart "
              "carries the <b>mineralogy</b> directly.",
    },

    # ------------------------------------------- onglet « composition »
    "ui.carte.domaines": {
        "fr": "Domaines compatibles par phase",
        "en": "Compatible ranges by phase",
    },
    "ui.carte.detail_phases": {
        "fr": "Détail des phases", "en": "Phase detail",
    },
    "ui.methode.domaines": {
        "fr": "Un <b>trait fin</b> se lit « déterminé ». Une <b>bande "
              "large</b> se lit « toute valeur de cette bande explique le "
              "bulletin aussi bien qu'une autre ». Une quantification par "
              "diffraction (DRX) de deux phases suffirait à ramener toutes "
              "ces bandes à des traits.",
        "en": "A <b>thin line</b> reads as \"determined\". A <b>wide band</b> "
              "reads as \"any value in this band explains the assay just as "
              "well as any other\". An XRD quantification of two phases "
              "would be enough to bring every band back to a line.",
    },

    # ------------------------------------------- import du bulletin
    "ui.import.titre": {
        "fr": "Importer votre bulletin", "en": "Import your assay",
    },
    "ui.import.depot": {
        "fr": "Glissez-déposez votre fichier",
        "en": "Drag and drop your file",
    },
    "ui.import.aide": {
        "fr": "Format large (intitulés puis valeurs) ou long (élément, "
              "valeur). Les unités se déclarent dans l'intitulé : "
              "« Ni (%) », « Fe (mg/kg) ». L'oxygène n'est pas attendu, il "
              "est prédit.",
        "en": "Wide format (headers then values) or long format (element, "
              "value). Units are declared in the header: \"Ni (%)\", "
              "\"Fe (mg/kg)\". Oxygen is not expected, it is predicted.",
    },
    "ui.import.invite": {
        "fr": "Déposez un bulletin pour lancer une analyse. Un exemple est "
              "fourni dans <b>data/exemples/</b>.",
        "en": "Drop an assay to start an analysis. An example is provided in "
              "<b>data/exemples/</b>.",
    },
    "ui.import.lu": {
        "fr": "Ce que KLASTOS21 a lu dans votre fichier",
        "en": "What KLASTOS21 read in your file",
    },
    "ui.import.col_colonne": {"fr": "Colonne", "en": "Column"},
    "ui.import.col_valeur": {"fr": "Valeur lue", "en": "Value read"},

    # ------------------------------------------------- identification du lot
    "ui.lot.titre": {"fr": "Identifier le lot", "en": "Identify the lot"},
    "ui.lot.identifiant": {"fr": "Identifiant du lot", "en": "Lot reference"},
    "ui.lot.client": {"fr": "Client", "en": "Client"},
    "ui.lot.echantillon": {"fr": "Échantillon", "en": "Sample"},

    # -------------------------------------------------------- navigation
    "ui.nav.libelle": {"fr": "Navigation", "en": "Navigation"},
    "ui.page.analyse": {"fr": "Analyse", "en": "Analysis"},
    "ui.page.prix": {"fr": "Prix", "en": "Prices"},
    "ui.page.historique": {"fr": "Historique", "en": "History"},
    "ui.page.aide": {"fr": "Aide", "en": "Help"},

    # --------------------------------------------------------- provenance
    "ui.provenance.libelle": {
        "fr": "Provenance déclarée", "en": "Declared provenance",
    },
    "ui.provenance.non_arbitre": {
        "fr": "  (non arbitré)", "en": "  (not arbitrated)",
    },
    "ui.provenance.avert_non_arbitre": {
        "fr": "Ce profil d'exclusion n'a pas été arbitré métier. Les phases "
              "qu'il écarte relèvent d'une hypothèse, pas d'une décision.",
        "en": "This exclusion profile has not been arbitrated by the "
              "business. The phases it rules out rest on an assumption, not "
              "on a decision.",
    },
    "ui.attestation.libelle": {
        "fr": "Le client a signé l'attestation de provenance.",
        "en": "The client has signed the provenance attestation.",
    },
    "ui.attestation.aide": {
        "fr": "SANS CETTE ATTESTATION, AUCUNE PHASE N'EST EXCLUE, quelle que "
              "soit la provenance choisie. Exclure une phase sur une simple "
              "déclaration orale reviendrait à sous-estimer un lot sans "
              "trace.",
        "en": "WITHOUT THIS ATTESTATION, NO PHASE IS EXCLUDED, whatever "
              "provenance is chosen. Ruling out a phase on a spoken "
              "declaration alone would mean undervaluing a lot with no "
              "record of why.",
    },
    "ui.attestation.sans": {
        "fr": "Provenance renseignée sans attestation : aucune phase ne sera "
              "exclue. Le rapport le dira.",
        "en": "Provenance given without attestation: no phase will be "
              "excluded. The report will say so.",
    },
    "ui.grades.libelle": {
        "fr": "Grades produits sur le site",
        "en": "Grades produced on site",
    },

    # -------------------------------------------------------- destinataire
    "ui.destinataire.libelle": {
        "fr": "Destinataire du rapport", "en": "Report recipient",
    },
    "ui.destinataire.tiers": {
        "fr": "Un tiers (client)", "en": "A third party (client)",
    },
    "ui.destinataire.interne": {
        "fr": "Usage interne", "en": "Internal use",
    },
    "ui.destinataire.aide": {
        "fr": "Des prix d'agence sans licence de rediffusion font refuser un "
              "document destiné à un tiers.",
        "en": "Agency prices without a redistribution licence cause a "
              "document intended for a third party to be refused.",
    },

    # ------------------------------------------------- volets de reglages
    "ui.volet.valorisation": {"fr": "Valorisation", "en": "Valuation"},
    "ui.spec.libelle": {
        "fr": "Spécification à contrôler",
        "en": "Specification to check against",
    },
    "ui.spec.aucune": {"fr": "(aucune)", "en": "(none)"},
    "ui.cout.libelle": {
        "fr": "Coût de traitement (par tonne)",
        "en": "Processing cost (per tonne)",
    },
    "ui.marge.libelle": {"fr": "Marge visée", "en": "Target margin"},

    "ui.volet.seuils": {
        "fr": "Seuils et calcul", "en": "Thresholds and computation",
    },
    "ui.seuils.arbitres": {
        "fr": "Seuils arbitrés : alerte {alerte:.0%}, rejet {rejet:.0%}.",
        "en": "Arbitrated thresholds: alert {alerte:.0%}, "
              "rejection {rejet:.0%}.",
    },
    "ui.seuil.alerte": {"fr": "Seuil d'alerte", "en": "Alert threshold"},
    "ui.seuil.rejet": {
        "fr": "Seuil de rejet", "en": "Rejection threshold",
    },
    "ui.tirages.libelle": {
        "fr": "Tirages de propagation", "en": "Propagation draws",
    },
    "ui.graine.libelle": {"fr": "Graine aléatoire", "en": "Random seed"},
    "ui.graine.aide": {
        "fr": "Même graine, même résultat.", "en": "Same seed, same result.",
    },
    "ui.separateur.libelle": {
        "fr": "Séparateur du CSV", "en": "CSV separator",
    },
    "ui.separateur.aide": {
        "fr": "Virgule par défaut. Mettez « ; » si votre fichier vient d'un "
              "Excel en locale française, qui écrit nativement des "
              "points-virgules.",
        "en": "Comma by default. Set it to \";\" if your file comes from a "
              "French-locale Excel, which natively writes semicolons.",
    },

    "ui.volet.historique": {"fr": "Historique", "en": "History"},
    "ui.historique.enregistrer": {
        "fr": "Enregistrer les analyses", "en": "Record analyses",
    },
    "ui.historique.fichier": {
        "fr": "Fichier d'historique", "en": "History file",
    },

    # ------------------------------------------------------ etat du systeme
    "ui.etat.pret": {"fr": "Système prêt", "en": "System ready"},
    "ui.etat.pret_detail": {
        "fr": "Prêt à traiter un nouveau bulletin.",
        "en": "Ready to process a new assay.",
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
