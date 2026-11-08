"""
KLASTOS21 - Contenu du site vitrine, en deux langues.

Meme invariant que `klastos/i18n.py` : UNE CLE N'EST JAMAIS UN TEXTE
AFFICHE. Le generateur ne manipule que des cles ; les deux langues vivent
cote a cote dans la meme entree, ce qui rend une traduction manquante
visible a la lecture et non a l'execution.

Les chiffres cites dans le contenu ne sont pas inventes. Ils viennent du
lot XRF reel analyse pendant la mise au point : degenerescence 5, une phase
determinee sur douze, sept totaux elementaires fermes. Les seuils de
bouclage cites (6 % et 20 %) sont ceux que `klastos/solver.py` applique.
"""

from __future__ import annotations

LANGUES: tuple[str, ...] = ("fr", "en")
DEFAUT = "fr"

#: Les pages, dans l'ordre de la navigation. La cle est le nom de fichier
#: sans extension ; elle ne s'affiche jamais.
PAGES: tuple[str, ...] = (
    "index", "methode", "rapport", "prix", "missions", "contact",
)


class CleInconnue(KeyError):
    """Cle absente du catalogue. Le message reste lisible."""

    def __str__(self) -> str:
        if len(self.args) == 1 and isinstance(self.args[0], str):
            return self.args[0]
        return super().__str__()


TEXTES: dict[str, dict[str, str]] = {

    # ================================================================
    # Navigation, pied de page, mentions
    # ================================================================
    "nav.index": {
        "fr": "Accueil",
        "en": "Home"},
    "nav.methode": {
        "fr": "La méthode",
        "en": "Method"},
    "nav.rapport": {
        "fr": "Un rapport réel",
        "en": "A real report"},
    "nav.prix": {
        "fr": "Prix et sources",
        "en": "Prices and sources"},
    "nav.missions": {
        "fr": "Nos missions",
        "en": "Our mission"},
    "nav.contact": {
        "fr": "Contact",
        "en": "Contact"},

    "marque.nom": {
        "fr": "KLASTOS21",
        "en": "KLASTOS21"},
    "marque.sous": {
        "fr": "Matières premières secondaires",
        "en": "Secondary raw materials"},

    "pied.produit": {
        "fr": "Produit",
        "en": "Product"},
    "pied.maison": {
        "fr": "La maison",
        "en": "Company"},
    "pied.mention": {
        "fr": "KLASTOS21 est un outil d'aide à la décision. Un rapport "
              "produit sans attestation de provenance, ou marqué non "
              "opposable, ne constitue pas un document contractuel. Les "
              "cotations affichées proviennent des sources déclarées sur la "
              "page Prix et sources, avec leur date et leur licence de "
              "rediffusion.",
        "en": "KLASTOS21 is a decision-support tool. A report produced "
              "without a provenance attestation, or marked non-binding, is "
              "not a contractual document. Quoted prices come from the "
              "sources declared on the Prices and sources page, with their "
              "date and redistribution licence."},

    # ================================================================
    # Accueil
    # ================================================================
    "index.titre_onglet": {
        "fr": "KLASTOS21 | Analyse prédictive de black mass",
        "en": "KLASTOS21 | Predictive analysis of black mass"},
    "index.description": {
        "fr": "KLASTOS21 lit un bulletin d'analyse de black mass et "
              "distingue ce que la donnée détermine de ce qu'elle ne "
              "détermine pas.",
        "en": "KLASTOS21 reads a black mass assay bulletin and separates "
              "what the data determines from what it does not."},


    # ================================================================
    # Bandeau de preuve du hero. Les trois chiffres viennent du lot XRF
    # reel analyse pendant la mise au point, et du depot lui-meme.
    # ================================================================
    "index.preuve.phases.cle": {
        "fr": "phase déterminée sur douze, sur un lot réel",
        "en": "phase determined out of twelve, on a real lot"},
    "index.preuve.degen.cle": {
        "fr": "directions de composition que les mesures ne séparent pas",
        "en": "composition directions the measurements do not separate"},
    # Le troisieme chiffre etait le nombre de tests. Il parle au
    # developpeur, pas a l'acheteur : `docs/mails_prospection.md` interdit
    # deja de le citer dans un premier courriel. Le delai de rendu, lui,
    # est un engagement que le visiteur peut tenir contre nous.
    "index.preuve.delai.cle": {
        "fr": "heures ouvrées pour rendre le verdict d'un bulletin",
        # « 48 working hours » se lirait six jours de huit heures.
        "en": "hours, two working days, to return the verdict on a "
              "bulletin"},

    # ================================================================
    # Console d'identifiabilite. Le visiteur coche les elements doses et
    # lit ce que son bulletin determinerait. Les reponses sortent du
    # moteur, pre-calculees a la construction.
    # ================================================================
    "index.vers_console": {
        "fr": "Essayer la console d'identifiabilité",
        "en": "Try the identifiability console"},

    "console.surtitre": {
        "fr": "Essayez vous-même",
        "en": "Try it yourself"},
    "console.h2": {
        "fr": "Cochez ce que votre laboratoire dose. Lisez ce qui reste indéterminé.",
        "en": "Tick what your laboratory assays. Read what stays undetermined."},
    "console.chapeau": {
        "fr": "Les réponses ci-dessous ne sont pas une maquette : elles "
              "sortent du moteur qui produit les rapports clients, calculées "
              "pour les 2 047 combinaisons possibles. Provenance déclarée "
              "véhicule électrique, douze phases admissibles.",
        "en": "The answers below are not a mock-up: they come from the "
              "engine that produces client reports, computed for all 2,047 "
              "possible combinations. Declared provenance electric vehicle, "
              "twelve admissible phases."},
    "console.elements": {
        "fr": "Éléments dosés par le bulletin",
        "en": "Elements assayed by the bulletin"},
    "console.raz": {
        "fr": "Bulletin courant", "en": "Typical bulletin"},
    "console.tout": {
        "fr": "Tout doser", "en": "Assay everything"},
    "console.mesure.dosees": {
        "fr": "éléments dosés", "en": "elements assayed"},
    "console.mesure.rang": {
        "fr": "rang du système", "en": "system rank"},
    "console.mesure.deg": {
        "fr": "degrés de liberté", "en": "degrees of freedom"},
    "console.mesure.fermes": {
        "fr": "phases déterminées", "en": "phases determined"},
    "console.phases": {
        "fr": "Les douze phases admissibles",
        "en": "The twelve admissible phases"},
    "console.etat.ferme": {
        "fr": "déterminée", "en": "determined"},
    "console.etat.ouvert": {
        "fr": "domaine compatible", "en": "compatible range"},
    "console.indisponible": {
        "fr": "La démonstration interactive n'a pas pu se charger. Le "
              "raisonnement de la page reste valide sans elle.",
        "en": "The interactive demonstration could not load. The page's "
              "reasoning stands without it."},
    # Les trois verdicts. Ils ne commentent pas, ils CONCLUENT : c'est ce
    # que le rapport ferait.
    "console.verdict.rien": {
        "fr": "Aucune phase n'est déterminée. Toute ventilation par grade "
              "annoncée sur ce bulletin serait un choix arbitraire parmi "
              "une infinité de compositions également compatibles.",
        "en": "No phase is determined. Any breakdown by grade announced on "
              "this bulletin would be an arbitrary pick among infinitely "
              "many equally compatible compositions."},
    "console.verdict.partiel": {
        "fr": "Quelques phases sont déterminées, les autres restent des "
              "domaines compatibles. Le rapport les sépare, et ne valorise "
              "que les premières.",
        "en": "A few phases are determined, the rest stay compatible "
              "ranges. The report separates them, and values only the "
              "former."},
    "console.verdict.large": {
        "fr": "La plupart des phases sont déterminées. Remarquez le moment "
              "où cela bascule : le rang monte d'un cran à chaque dosage, "
              "mais la détermination, elle, arrive d'un coup.",
        "en": "Most phases are determined. Notice when it tips: rank rises "
              "by exactly one per assay, but determination arrives all at "
              "once."},
    "console.lecon.titre": {
        "fr": "Ce que la console vous a montré",
        "en": "What the console just showed you"},
    "console.lecon.texte": {
        "fr": "Chaque dosage ajouté achète exactement un rang : la "
              "progression est parfaitement régulière, et c'est ce qui "
              "trompe. La détermination, elle, ne l'est pas du tout. Elle "
              "reste à zéro pendant les six premiers dosages, puis arrive "
              "par sauts. Un acheteur qui commande une analyse de plus "
              "sans savoir laquelle paie souvent sans rien obtenir. C'est "
              "précisément ce que KLASTOS21 calcule : quelle mesure, et "
              "dans quel ordre.",
        "en": "Each added assay buys exactly one rank: the progression is "
              "perfectly regular, and that is what misleads. Determination "
              "is not regular at all. It stays at zero through the first "
              "six assays, then arrives in jumps. A buyer who orders one "
              "more analysis without knowing which one often pays and gets "
              "nothing. That is precisely what KLASTOS21 computes: which "
              "measurement, and in what order."},

    "index.surtitre": {
        "fr": "Analyse prédictive des matières premières secondaires",
        "en": "Predictive analysis of secondary raw materials"},
    "index.h1": {
        "fr": "Un chiffre que vous pouvez opposer, ou rien.",
        "en": "A figure you can stand behind, or nothing at all."},
    "index.chapeau": {
        "fr": "KLASTOS21 lit un bulletin d'analyse de black mass et dit ce "
              "que la donnée porte, puis ce qu'elle ne porte pas. Une "
              "grandeur déterminée sort en trait fin. Une grandeur que le "
              "bulletin ne contraint pas sort en bande. Et quand le "
              "bouclage de masse ne tient pas, l'outil refuse d'éditer le "
              "rapport.",
        "en": "KLASTOS21 reads a black mass assay bulletin and states what "
              "the data carries, then what it does not. A determined "
              "quantity comes out as a thin line. A quantity the bulletin "
              "fails to constrain comes out as a band. And when mass "
              "closure does not hold, the tool refuses to issue the report."},
    "index.bouton_methode": {
        "fr": "Comment ça marche",
        "en": "How it works"},
    "index.bouton_rapport": {
        "fr": "Voir un rapport réel",
        "en": "See a real report"},

    # --- la figure ---
    "index.figure.titre": {
        "fr": "Le même lot, lu honnêtement",
        "en": "The same lot, read honestly"},
    "index.figure.chapeau": {
        "fr": "Quatre grandeurs du même bulletin, à la même échelle. Les "
              "deux premières sont mesurées et fermes. Les deux suivantes "
              "ne sont pas déterminées par les données fournies : les "
              "afficher comme un nombre unique serait une invention.",
        "en": "Four quantities from the same bulletin, at the same scale. "
              "The first two are measured and firm. The next two are not "
              "determined by the data supplied: showing them as a single "
              "number would be an invention."},
    "index.figure.ni": {
        "fr": "Nickel total",
        "en": "Total nickel"},
    "index.figure.co": {
        "fr": "Cobalt total",
        "en": "Total cobalt"},
    "index.figure.nmc": {
        "fr": "Phase NMC 811",
        "en": "NMC 811 phase"},
    "index.figure.lfp": {
        "fr": "Phase LFP",
        "en": "LFP phase"},
    "index.figure.legende": {
        "fr": "Trait fin : grandeur déterminée. Bande : domaine compatible "
              "avec les mesures. Toute valeur de la bande explique le "
              "bulletin aussi bien qu'une autre.",
        "en": "Thin line: determined quantity. Band: domain compatible with "
              "the measurements. Every value in the band explains the "
              "bulletin just as well as any other."},

    # --- la trichotomie ---
    "index.tri.surtitre": {
        "fr": "Trois états, jamais deux",
        "en": "Three states, never two"},
    "index.tri.titre": {
        "fr": "Un résultat n'est pas vrai ou faux. Il est déterminé, mal "
              "déterminé, ou pas déterminé du tout.",
        "en": "A result is not true or false. It is determined, poorly "
              "determined, or not determined at all."},
    "index.tri.determine.nom": {
        "fr": "Déterminé",
        "en": "Determined"},
    "index.tri.determine.texte": {
        "fr": "Les données fixent la grandeur. Elle sort avec son "
              "incertitude analytique, et c'est elle que vous pouvez "
              "opposer à un fournisseur.",
        "en": "The data pins the quantity down. It comes out with its "
              "analytical uncertainty, and it is the figure you can put to "
              "a supplier."},
    "index.tri.mal.nom": {
        "fr": "Mal déterminé",
        "en": "Poorly determined"},
    "index.tri.mal.texte": {
        "fr": "Les données contraignent la grandeur, mais faiblement. "
              "L'intervalle est large, et KLASTOS21 vous dit laquelle de "
              "l'incertitude analytique ou de l'indétermination structurelle "
              "domine.",
        "en": "The data constrains the quantity, but weakly. The interval "
              "is wide, and KLASTOS21 tells you whether analytical "
              "uncertainty or structural indeterminacy dominates."},
    "index.tri.domaine.nom": {
        "fr": "Domaine compatible",
        "en": "Compatible domain"},
    "index.tri.domaine.texte": {
        "fr": "Les données ne distinguent pas. Plusieurs compositions très "
              "différentes expliquent le bulletin exactement aussi bien. "
              "Nous donnons le domaine, pas un représentant choisi dedans.",
        "en": "The data does not discriminate. Several very different "
              "compositions explain the bulletin exactly as well. We give "
              "the domain, not a representative picked from inside it."},

    # --- le refus ---
    "index.refus.surtitre": {
        "fr": "Le refus est une fonction, pas une panne",
        "en": "Refusal is a feature, not a failure"},
    "index.refus.titre": {
        "fr": "Au-delà de 20 % d'écart de bouclage, il n'y a pas de rapport.",
        "en": "Beyond a 20% closure gap, there is no report."},
    "index.refus.texte": {
        "fr": "Le bouclage de masse est le contrôle le plus simple et le "
              "plus dur : la somme de ce que vous avez dosé doit approcher "
              "la masse du lot. Au-dessus de 6 % d'écart, KLASTOS21 alerte. "
              "Au-dessus de 20 %, il refuse d'éditer le rapport et explique "
              "ce qui manque. Les deux seuils sont arbitrés contre le "
              "plancher de bruit analytique, pas choisis pour faire joli.",
        "en": "Mass closure is the simplest and harshest check: the sum of "
              "what you assayed must come close to the lot mass. Above a 6% "
              "gap, KLASTOS21 raises an alert. Above 20%, it refuses to "
              "issue the report and explains what is missing. Both "
              "thresholds are arbitrated against the analytical noise "
              "floor, not picked to look tidy."},
    "index.refus.citation": {
        "fr": "Un tableau de chiffres ne montre pas qu'une grandeur ferme "
              "est un trait fin et qu'un domaine compatible est une bande "
              "large. C'est précisément la distinction que KLASTOS21 vend.",
        "en": "A table of numbers does not show that a firm quantity is a "
              "thin line and a compatible domain is a wide band. That "
              "distinction is precisely what KLASTOS21 sells."},
    "index.refus.source": {
        "fr": "klastos/render_html.py, docstring du module",
        "en": "klastos/render_html.py, module docstring"},

    # --- ce qui reste opposable ---
    "index.ferme.surtitre": {
        "fr": "Ce qui reste, même quand presque tout manque",
        "en": "What remains, even when almost everything is missing"},
    "index.ferme.titre": {
        "fr": "Sur un lot réel, une phase sur douze était déterminée. Les "
              "sept totaux élémentaires, eux, étaient fermes.",
        "en": "On a real lot, one phase out of twelve was determined. The "
              "seven elemental totals, however, were firm."},
    "index.ferme.texte": {
        "fr": "C'est le genre de verdict qu'un outil complaisant ne donne "
              "jamais. Le bulletin examiné présentait une dégénérescence de "
              "5 : cinq directions de composition que les mesures ne "
              "séparent pas. KLASTOS21 les a nommées, a indiqué quel dosage "
              "manquant lèverait chacune, et a montré que le lithium seul "
              "rendait trois phases supplémentaires identifiables. Les sept "
              "totaux élémentaires restaient les seules grandeurs "
              "opposables, et elles suffisaient à négocier.",
        "en": "This is the kind of verdict an obliging tool never gives. "
              "The bulletin examined showed a degeneracy of 5: five "
              "composition directions the measurements do not separate. "
              "KLASTOS21 named them, said which missing assay would lift "
              "each one, and showed that lithium alone made three further "
              "phases identifiable. The seven elemental totals remained the "
              "only binding quantities, and they were enough to trade on."},
    "index.ferme.f1": {
        "fr": "<b>Dégénérescence 5</b> : cinq directions non séparées par "
              "les mesures, chacune nommée",
        "en": "<b>Degeneracy 5</b>: five directions not separated by the "
              "measurements, each one named"},
    "index.ferme.f2": {
        "fr": "<b>Chaque dosage ajouté achète exactement 1 rang</b>, donc "
              "l'outil vous dit lequel commander en premier",
        "en": "<b>Each added assay buys exactly 1 rank</b>, so the tool "
              "tells you which one to order first"},
    "index.ferme.f3": {
        "fr": "<b>Sept totaux élémentaires fermes</b> : les seules "
              "grandeurs opposables sur ce lot",
        "en": "<b>Seven firm elemental totals</b>: the only binding "
              "quantities on this lot"},

    # --- attestations ---
    "index.attest.surtitre": {
        "fr": "Deux attestations à la première personne",
        "en": "Two first-person attestations"},
    "index.attest.titre": {
        "fr": "Qui dit quoi, et qui en répond.",
        "en": "Who says what, and who answers for it."},
    "index.attest.texte": {
        "fr": "Un rapport KLASTOS21 porte deux déclarations distinctes. "
              "L'une est la nôtre : nous attestons de la méthode, des "
              "seuils appliqués et des sources de prix. L'autre est la "
              "vôtre : vous attestez de la provenance du lot. Les deux sont "
              "nécessaires pour qu'un rapport soit opposable, et le "
              "document dit clairement laquelle manque.",
        "en": "A KLASTOS21 report carries two distinct statements. One is "
              "ours: we attest to the method, the thresholds applied and "
              "the price sources. The other is yours: you attest to the "
              "lot's provenance. Both are required for a report to be "
              "binding, and the document states plainly which one is "
              "missing."},

    # ================================================================
    # La méthode
    # ================================================================
    "methode.titre_onglet": {
        "fr": "La méthode | KLASTOS21",
        "en": "Method | KLASTOS21"},
    "methode.description": {
        "fr": "Identifiabilité, bouclage de masse, dégénérescence : "
              "comment KLASTOS21 décide ce qu'il peut affirmer.",
        "en": "Identifiability, mass closure, degeneracy: how KLASTOS21 "
              "decides what it may assert."},
    "methode.surtitre": {
        "fr": "La méthode",
        "en": "Method"},
    "methode.h1": {
        "fr": "Trois questions, posées dans cet ordre.",
        "en": "Three questions, asked in this order."},
    "methode.chapeau": {
        "fr": "Aucune équation sur cette page. L'enchaînement, en revanche, "
              "est celui du code : si une étape échoue, les suivantes ne "
              "sont pas tentées.",
        "en": "No equations on this page. The sequence, however, is the "
              "one in the code: if a step fails, the later ones are not "
              "attempted."},

    "methode.un.titre": {
        "fr": "1. La masse boucle-t-elle ?",
        "en": "1. Does the mass close?"},
    "methode.un.texte": {
        "fr": "On additionne tout ce que le bulletin dose et on compare à "
              "la masse du lot. Un écart modéré est normal : aucun bulletin "
              "ne dose tout. Un écart de 35 % signifie qu'un tiers du lot "
              "n'est pas renseigné, et aucun calcul sur les deux tiers "
              "restants ne rattrapera ça. C'est pourquoi le seuil de rejet "
              "existe, et pourquoi il est haut : à 20 % d'écart, un rapport "
              "serait un bel objet appuyé sur rien.",
        "en": "We add up everything the bulletin assays and compare it with "
              "the lot mass. A moderate gap is normal: no bulletin assays "
              "everything. A 35% gap means a third of the lot is "
              "unaccounted for, and no calculation on the remaining "
              "two-thirds will make that good. That is why the rejection "
              "threshold exists, and why it is high: at a 20% gap, a report "
              "would be a handsome object resting on nothing."},

    "methode.deux.titre": {
        "fr": "2. Les données déterminent-elles la réponse ?",
        "en": "2. Does the data determine the answer?"},
    "methode.deux.texte": {
        "fr": "C'est la question d'identifiabilité, et c'est le cœur de "
              "l'outil. Un bulletin donne des totaux élémentaires ; vous "
              "voulez des proportions de phases. Plusieurs jeux de phases "
              "très différents peuvent produire exactement les mêmes "
              "totaux. KLASTOS21 calcule combien de directions restent "
              "libres (c'est la dégénérescence) et les nomme. Une "
              "direction libre du type « carbone total seul » vous dit "
              "immédiatement quel dosage commander.",
        "en": "This is the identifiability question, and it is the heart of "
              "the tool. A bulletin gives elemental totals; you want phase "
              "proportions. Several very different sets of phases can "
              "produce exactly the same totals. KLASTOS21 computes how many "
              "directions remain free (that is the degeneracy) and names "
              "them. A free direction of the form \"total carbon alone\" "
              "tells you at once which assay to order."},

    "methode.trois.titre": {
        "fr": "3. Qu'est-ce qui domine l'incertitude ?",
        "en": "3. What dominates the uncertainty?"},
    "methode.trois.texte": {
        "fr": "Un intervalle large n'a pas la même valeur selon sa cause. "
              "Si l'incertitude est analytique, un laboratoire plus précis "
              "la réduit. Si elle est structurelle, aucune précision "
              "supplémentaire sur les mêmes éléments n'y changera quoi que "
              "ce soit : il faut doser un élément de plus. KLASTOS21 "
              "propage les incertitudes par tirages et nomme la source "
              "dominante, parce que les deux cas appellent deux décisions "
              "opposées.",
        "en": "A wide interval does not mean the same thing depending on "
              "its cause. If the uncertainty is analytical, a more precise "
              "laboratory reduces it. If it is structural, no extra "
              "precision on the same elements will change anything: you "
              "need to assay one more element. KLASTOS21 propagates "
              "uncertainties by sampling and names the dominant source, "
              "because the two cases call for opposite decisions."},

    "methode.quatre.titre": {
        "fr": "Ce que la méthode interdit",
        "en": "What the method forbids"},
    "methode.quatre.f1": {
        "fr": "<b>Aucune valeur par défaut silencieuse.</b> Une cellule "
              "vide n'est pas un zéro. Si un élément n'est pas dosé, il est "
              "déclaré non dosé.",
        "en": "<b>No silent defaults.</b> An empty cell is not a zero. If "
              "an element is not assayed, it is declared not assayed."},
    "methode.quatre.f2": {
        "fr": "<b>Aucun représentant choisi dans un domaine.</b> Donner le "
              "milieu d'une bande large comme si c'était une mesure serait "
              "le défaut exact que l'outil existe pour éviter.",
        "en": "<b>No representative picked from a domain.</b> Giving the "
              "middle of a wide band as though it were a measurement is "
              "precisely the fault this tool exists to avoid."},
    "methode.quatre.f3": {
        "fr": "<b>Aucun prix sans source datée.</b> Une valorisation sans "
              "cotation identifiée n'est pas produite.",
        "en": "<b>No price without a dated source.</b> A valuation without "
              "an identified quotation is not produced."},
    "methode.quatre.f4": {
        "fr": "<b>Aucun rapport opposable sans attestation de provenance.</b> "
              "Le document le dit sur sa première page.",
        "en": "<b>No binding report without a provenance attestation.</b> "
              "The document says so on its first page."},

    # ================================================================
    # Un rapport réel
    # ================================================================
    "rapport.titre_onglet": {
        "fr": "Un rapport réel | KLASTOS21",
        "en": "A real report | KLASTOS21"},
    "rapport.description": {
        "fr": "Le rapport produit sur un lot de black mass réel, avec son "
              "verdict d'identifiabilité et ses refus.",
        "en": "The report produced on a real black mass lot, with its "
              "identifiability verdict and its refusals."},
    "rapport.surtitre": {
        "fr": "Un rapport réel",
        "en": "A real report"},
    "rapport.h1": {
        "fr": "Le document, tel qu'il sort.",
        "en": "The document, exactly as it comes out."},
    "rapport.chapeau": {
        "fr": "Ce lot est authentique, anonymisé. Il a été choisi parce "
              "qu'il se passe mal : le bulletin ne dosait ni le fluor, ni "
              "le lithium, ni le carbone. C'est le cas qui montre ce que "
              "l'outil fait quand la donnée ne suffit pas.",
        "en": "This lot is genuine, anonymised. It was chosen because it "
              "goes badly: the bulletin assayed neither fluorine, nor "
              "lithium, nor carbon. It is the case that shows what the tool "
              "does when the data is not enough."},

    "rapport.verdict.titre": {
        "fr": "Le verdict, en cinq lignes",
        "en": "The verdict, in five lines"},
    "rapport.verdict.col_grandeur": {
        "fr": "Grandeur",
        "en": "Quantity"},
    "rapport.verdict.col_etat": {
        "fr": "État",
        "en": "State"},
    "rapport.verdict.col_valeur": {
        "fr": "Valeur",
        "en": "Value"},
    "rapport.verdict.l1": {
        "fr": "Totaux élémentaires dosés",
        "en": "Elemental totals assayed"},
    "rapport.verdict.l2": {
        "fr": "Phases quantifiables",
        "en": "Quantifiable phases"},
    "rapport.verdict.l3": {
        "fr": "Dégénérescence",
        "en": "Degeneracy"},
    "rapport.verdict.l4": {
        "fr": "Écart de bouclage",
        "en": "Closure gap"},
    "rapport.verdict.l5": {
        "fr": "Rapport opposable",
        "en": "Binding report"},
    "rapport.verdict.v5": {
        "fr": "Oui, sur les totaux seuls",
        "en": "Yes, on the totals alone"},

    "rapport.manque.titre": {
        "fr": "Ce que l'outil a répondu à « que dois-je commander ? »",
        "en": "What the tool answered to \"what should I order?\""},
    "rapport.manque.texte": {
        "fr": "Les cinq directions libres portaient des noms exploitables. "
              "Deux désignaient un seul élément chacune : le carbone total "
              "et le PVDF. Les trois autres mélangeaient NMC et NCA, ce qui "
              "veut dire qu'aucune mesure du bulletin ne les distingue. "
              "Chaque dosage ajouté levait exactement une direction, et le "
              "lithium seul rendait trois phases supplémentaires "
              "identifiables. L'ordre de commande en découlait sans "
              "discussion : lithium d'abord.",
        "en": "The five free directions had usable names. Two pointed at a "
              "single element each: total carbon and PVDF. The other three "
              "mixed NMC and NCA, which means no measurement in the "
              "bulletin separates them. Each added assay lifted exactly one "
              "direction, and lithium alone made three further phases "
              "identifiable. The ordering priority followed without "
              "argument: lithium first."},

    "rapport.piege.titre": {
        "fr": "Un piège qui a coûté deux analyses",
        "en": "A trap that cost two analyses"},
    "rapport.piege.texte": {
        "fr": "Sur ce même lot, deux tentatives ont échoué avant d'aboutir, "
              "et les deux pour des raisons de forme. La première : le "
              "fichier était séparé par des points-virgules et lu comme une "
              "colonne unique. La seconde : des cellules laissées vides "
              "pour les éléments non dosés ont été comprises comme des "
              "zéros mesurés, ce qui a fait passer l'écart de bouclage de "
              "10,35 % à 16,75 %. Les deux cas sont maintenant détectés et "
              "expliqués par un message, pas par un échec muet.",
        "en": "On that same lot, two attempts failed before one succeeded, "
              "and both for reasons of form. First: the file was "
              "semicolon-separated and read as a single column. Second: "
              "cells left blank for unassayed elements were understood as "
              "measured zeros, which pushed the closure gap from 10.35% to "
              "16.75%. Both cases are now detected and explained by a "
              "message, not by a silent failure."},

    # ================================================================
    # Prix et sources
    # ================================================================
    "prix.titre_onglet": {
        "fr": "Prix et sources | KLASTOS21",
        "en": "Prices and sources | KLASTOS21"},
    "prix.description": {
        "fr": "D'où viennent les cotations, à quelle date, et ce que leur "
              "licence autorise.",
        "en": "Where the quotations come from, at what date, and what their "
              "licence permits."},
    "prix.surtitre": {
        "fr": "Prix et sources",
        "en": "Prices and sources"},
    "prix.h1": {
        "fr": "Une valorisation vaut sa source.",
        "en": "A valuation is worth its source."},
    "prix.chapeau": {
        "fr": "Chaque prix affiché par KLASTOS21 porte sa source, sa date "
              "et sa licence de rediffusion. Un prix dont nous ne pouvons "
              "pas dire d'où il vient n'est pas affiché.",
        "en": "Every price KLASTOS21 displays carries its source, its date "
              "and its redistribution licence. A price whose origin we "
              "cannot state is not displayed."},

    "prix.devise.titre": {
        "fr": "Le dollar comme pivot, et pourquoi",
        "en": "The dollar as pivot, and why"},
    "prix.devise.texte": {
        "fr": "Les bandes de plausibilité de l'outil sont libellées en "
              "dollars. Convertir une valorisation vers une autre devise "
              "est donc possible, mais passe par un pivot explicite, avec "
              "un taux daté que vous fournissez. KLASTOS21 n'intègre aucune "
              "source de taux, et c'est une décision : un taux récupéré "
              "silencieusement sur un réseau est un chiffre dont personne "
              "ne répond. Un taux trop vieux est signalé.",
        "en": "The tool's plausibility bands are denominated in dollars. "
              "Converting a valuation into another currency is therefore "
              "possible, but goes through an explicit pivot, with a dated "
              "rate that you supply. KLASTOS21 integrates no rate source, "
              "and that is a decision: a rate silently fetched over a "
              "network is a figure nobody answers for. A rate that is too "
              "old is flagged."},

    "prix.licence.titre": {
        "fr": "Ce que la licence change",
        "en": "What the licence changes"},
    "prix.licence.texte": {
        "fr": "Toutes les sources de cotation ne se rediffusent pas. "
              "Certaines autorisent la reproduction d'un chiffre dans un "
              "rapport remis à un tiers, d'autres le réservent à un usage "
              "interne. KLASTOS21 distingue les deux et marque le rapport "
              "en conséquence, pour que vous ne découvriez pas la "
              "contrainte après avoir envoyé le document.",
        "en": "Not every quotation source may be redistributed. Some permit "
              "reproducing a figure in a report handed to a third party; "
              "others restrict it to internal use. KLASTOS21 distinguishes "
              "the two and marks the report accordingly, so you do not "
              "discover the constraint after sending the document."},
    "prix.licence.col_source": {
        "fr": "Source",
        "en": "Source"},
    "prix.licence.col_couv": {
        "fr": "Couverture",
        "en": "Coverage"},
    "prix.licence.col_lic": {
        "fr": "Rediffusion",
        "en": "Redistribution"},
    "prix.licence.pink_couv": {
        "fr": "Aluminium, cuivre, nickel",
        "en": "Aluminium, copper, nickel"},
    "prix.licence.pink_lic": {
        "fr": "Autorisée",
        "en": "Permitted"},
    "prix.licence.releve_nom": {
        "fr": "Relevé interne",
        "en": "Internal record"},
    "prix.licence.releve_couv": {
        "fr": "Selon le relevé fourni",
        "en": "As supplied"},
    "prix.licence.releve_lic": {
        "fr": "À déclarer",
        "en": "To be declared"},

    "prix.histo.titre": {
        "fr": "L'historique est conservé",
        "en": "History is kept"},
    "prix.histo.texte": {
        "fr": "Les cotations et les taux utilisés sont enregistrés avec "
              "leur date. Un rapport émis il y a six mois peut donc être "
              "relu avec les prix de l'époque, et non avec ceux "
              "d'aujourd'hui, ce qui est la seule façon honnête de "
              "réexaminer une décision passée.",
        "en": "The quotations and rates used are recorded with their date. "
              "A report issued six months ago can therefore be re-read with "
              "the prices of the time, not today's, which is the only "
              "honest way to revisit a past decision."},

    # ================================================================
    # Nos missions
    # ================================================================
    "missions.titre_onglet": {
        "fr": "Nos missions | KLASTOS21",
        "en": "Our mission | KLASTOS21"},
    "missions.description": {
        "fr": "Pourquoi un outil qui refuse de répondre vaut mieux qu'un "
              "outil qui répond toujours.",
        "en": "Why a tool that refuses to answer is worth more than a tool "
              "that always answers."},
    "missions.surtitre": {
        "fr": "Nos missions",
        "en": "Our mission"},
    "missions.h1": {
        "fr": "Rendre le doute lisible.",
        "en": "Make doubt legible."},
    "missions.chapeau": {
        "fr": "La filière des matières premières secondaires se négocie sur "
              "des bulletins d'analyse incomplets. Ce n'est pas un défaut "
              "passager : doser tout coûte plus que la marge. La question "
              "n'est donc pas d'obtenir des données parfaites, mais de "
              "savoir exactement ce que les données imparfaites permettent "
              "d'affirmer.",
        "en": "Secondary raw materials are traded on incomplete assay "
              "bulletins. This is not a passing defect: assaying everything "
              "costs more than the margin. The question is therefore not "
              "how to obtain perfect data, but how to know exactly what "
              "imperfect data allows you to assert."},

    "missions.un.titre": {
        "fr": "Ne jamais afficher ce que la donnée ne porte pas",
        "en": "Never display what the data does not carry"},
    "missions.un.texte": {
        "fr": "C'est la règle fondatrice, et toutes les autres en "
              "découlent. Un outil qui donne toujours un nombre est "
              "agréable jusqu'au jour où le nombre était inventé. Nous "
              "préférons la phrase qui dérange : cette grandeur n'est pas "
              "déterminée par votre bulletin.",
        "en": "This is the founding rule, and all the others follow from "
              "it. A tool that always gives a number is pleasant until the "
              "day the number was invented. We prefer the sentence that "
              "makes people uncomfortable: this quantity is not determined "
              "by your bulletin."},

    "missions.deux.titre": {
        "fr": "Dire quoi faire ensuite",
        "en": "Say what to do next"},
    "missions.deux.texte": {
        "fr": "Un refus sans suite serait un mur. Quand KLASTOS21 ne peut "
              "pas conclure, il nomme la mesure qui débloquerait l'analyse "
              "et chiffre ce qu'elle apporterait. Sur le lot présenté, "
              "doser le lithium rendait trois phases identifiables : c'est "
              "une décision d'achat, pas un message d'erreur.",
        "en": "A refusal with no sequel would be a wall. When KLASTOS21 "
              "cannot conclude, it names the measurement that would unblock "
              "the analysis and quantifies what it would buy. On the lot "
              "shown here, assaying lithium made three phases identifiable: "
              "that is a purchasing decision, not an error message."},

    "missions.trois.titre": {
        "fr": "Tenir l'écran et le document ensemble",
        "en": "Keep the screen and the document together"},
    "missions.trois.texte": {
        "fr": "Un négociant lit l'écran, puis imprime et discute le "
              "document en réunion. Si les deux ne se ressemblent pas, la "
              "confiance tombe. La palette, le vocabulaire des statuts et "
              "les seuils sont donc tenus par des tests de concordance "
              "entre l'interface, le rapport et ce site. Trois dérives "
              "avaient déjà été attrapées de cette façon.",
        "en": "A trader reads the screen, then prints the document and "
              "discusses it in a meeting. If the two do not resemble each "
              "other, trust collapses. The palette, the status vocabulary "
              "and the thresholds are therefore held by concordance tests "
              "across the interface, the report and this site. Three drifts "
              "had already been caught that way."},

    # ================================================================
    # Contact
    # ================================================================
    "contact.titre_onglet": {
        "fr": "Contact | KLASTOS21",
        "en": "Contact | KLASTOS21"},
    "contact.description": {
        "fr": "Faire analyser un bulletin, ou poser une question sur la "
              "méthode.",
        "en": "Have a bulletin analysed, or ask a question about the "
              "method."},
    "contact.surtitre": {
        "fr": "Contact",
        "en": "Contact"},
    "contact.h1": {
        "fr": "Envoyez un bulletin, recevez un verdict.",
        "en": "Send a bulletin, get a verdict."},
    "contact.chapeau": {
        "fr": "La façon la plus rapide de juger l'outil est de lui donner "
              "un de vos lots. Vous recevrez le rapport complet, y compris "
              "s'il conclut que vos données ne suffisent pas. C'est "
              "d'ailleurs le cas le plus instructif.",
        "en": "The fastest way to judge the tool is to give it one of your "
              "own lots. You will get the full report, including if it "
              "concludes that your data is not enough, which is in fact "
              "the most instructive case."},

    "contact.quoi.titre": {
        "fr": "Ce qu'il faut envoyer",
        "en": "What to send"},
    "contact.quoi.f1": {
        "fr": "<b>Le bulletin d'analyse</b>, en CSV ou en Excel. Les "
              "intitulés de colonnes n'ont pas besoin d'être normalisés.",
        "en": "<b>The assay bulletin</b>, as CSV or Excel. Column headings "
              "do not need to be normalised."},
    "contact.quoi.f2": {
        "fr": "<b>L'unité des dosages</b>, si elle n'est pas dans le "
              "fichier : pourcentage, ppm ou g/t.",
        "en": "<b>The assay unit</b>, if it is not in the file: percent, "
              "ppm or g/t."},
    "contact.quoi.f3": {
        "fr": "<b>La provenance du lot</b>, si vous souhaitez un rapport "
              "opposable. Sans elle, le document est produit mais marqué "
              "non opposable.",
        "en": "<b>The lot's provenance</b>, if you want a binding report. "
              "Without it, the document is produced but marked non-binding."},
    "contact.quoi.f4": {
        "fr": "<b>Une quantification DRX</b>, si vous en avez une. Elle "
              "n'est pas obligatoire et change beaucoup de choses.",
        "en": "<b>An XRD quantification</b>, if you have one. It is not "
              "required and changes a great deal."},

    "contact.courriel.titre": {
        "fr": "Par courriel",
        "en": "By email"},
    "contact.courriel.texte": {
        "fr": "Écrivez-nous en joignant le bulletin. Nous répondons avec le "
              "rapport et, le cas échéant, la liste des dosages qui "
              "lèveraient l'indétermination.",
        "en": "Write to us with the bulletin attached. We reply with the "
              "report and, where relevant, the list of assays that would "
              "lift the indeterminacy."},
    # Objet pre-rempli du lien mailto. Il rappelle au visiteur ce qu'il
    # doit joindre, et fait arriver le courriel deja qualifie.
    "contact.courriel.objet": {
        "fr": "Bulletin de black mass a analyser",
        "en": "Black mass bulletin for analysis"},

    # Corps pre-rempli du lien. Il rappelle les trois choses que la page
    # de contact enumere, au moment ou le visiteur ecrit - et non trois
    # ecrans plus tot. Un bulletin arrive ainsi avec son unite et sa
    # provenance, ce qui evite un aller-retour.
    "contact.courriel.corps": {
        "fr": "Bonjour,\n\n"
              "Je vous joins le bulletin d'analyse du lot.\n\n"
              "Unité des dosages : \n"
              "Provenance du lot : \n"
              "Quantification DRX jointe : oui / non\n\n"
              "Cordialement,\n",
        "en": "Hello,\n\n"
              "Please find the lot's assay bulletin attached.\n\n"
              "Assay unit: \n"
              "Lot provenance: \n"
              "XRD quantification attached: yes / no\n\n"
              "Best regards,\n"},

    "contact.courriel.copier": {
        "fr": "Copier l'adresse", "en": "Copy the address"},
    "contact.courriel.copie": {
        "fr": "Adresse copiee", "en": "Address copied"},

    "contact.courriel.bouton": {
        "fr": "Ouvrir un message", "en": "Compose a message"},

# ================================================================
    # Formulaire. Il existe parce qu'un lien `mailto:` ne mene nulle part
    # chez une part notable des visiteurs : sur Windows 11, le
    # gestionnaire pointe souvent sur l'application Courrier, retiree du
    # systeme, et le clic n'ouvre rien.
    # ================================================================
    # ------------------------------------------------------------------
    # Le graphique des cotations. Il n'illustre pas, il DEMONTRE : le
    # verrou de sept jours paraît sévère tant qu'on n'a pas vu le
    # lithium faire 5,4 fois son prix puis redescendre sous son point
    # de départ.
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Le schéma du procédé. Il répond à la question que pose tout
    # interlocuteur au bout de deux minutes : « vous faites quoi,
    # exactement, dans cette chaîne ? » La réponse est une frontière —
    # KLASTOS21 ne voit jamais le lot, il entre sur le bulletin.
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Les illustrations techniques. Elles sont DESSINÉES, et elles ne
    # s'en cachent pas : cinq banques libres ont été fouillées, et les
    # seules images gratuites montraient des piles alcalines ou des
    # batteries au plomb — le mauvais matériau.
    # ------------------------------------------------------------------
    "ill.titre": {
        "fr": "Ce que vous nous envoyez",
        "en": "What you send us"},
    "ill.chapeau": {
        "fr": "Une poudre, et le bulletin qui la décrit. Les deux "
              "illustrations ci-dessous sont dessinées, pas "
              "photographiées : nous préférons un schéma juste à une "
              "photographie approximative.",
        "en": "A powder, and the bulletin that describes it. Both "
              "illustrations below are drawn, not photographed: we "
              "prefer an accurate diagram to an approximate "
              "photograph."},

    "ech.titre": {"fr": "BLACK MASS", "en": "BLACK MASS"},
    "ech.lot": {"fr": "Lot", "en": "Lot"},
    "ech.lot.valeur": {"fr": "2026-RA-04871", "en": "2026-RA-04871"},
    "ech.granulo": {"fr": "Granulométrie", "en": "Particle size"},
    "ech.granulo.valeur": {"fr": "< 1 mm", "en": "< 1 mm"},
    "ech.humidite": {"fr": "Humidité", "en": "Moisture"},
    "ech.humidite.valeur": {"fr": "déclarée", "en": "declared"},
    "ech.alt": {
        "fr": "Illustration d'un échantillon de black mass : une poudre "
              "noire à grains fins, sous une étiquette portant le numéro "
              "de lot, la granulométrie et l'humidité.",
        "en": "Illustration of a black mass sample: a fine-grained black "
              "powder, under a label carrying the lot number, particle "
              "size and moisture."},

    "mod.titre": {
        "fr": "MODULE, VUE ÉCLATÉE",
        "en": "MODULE, EXPLODED VIEW"},
    "mod.boitier": {"fr": "Boîtier", "en": "Casing"},
    "mod.boitier2": {"fr": "Boîtier", "en": "Casing"},
    "mod.collecteur": {"fr": "Collecteur Al", "en": "Al collector"},
    "mod.collecteur2": {"fr": "Collecteur Cu", "en": "Cu collector"},
    "mod.cellules": {"fr": "Cellules", "en": "Cells"},
    "mod.alt": {
        "fr": "Illustration d'un module de batterie en vue éclatée : "
              "boîtier, collecteur d'aluminium, empilement de cellules "
              "souples, collecteur de cuivre, boîtier.",
        "en": "Illustration of a battery module in exploded view: "
              "casing, aluminium collector, stack of pouch cells, "
              "copper collector, casing."},
    "ill.lecon": {
        "fr": "Les collecteurs partent avec la poudre, en fines de "
              "cuivre et d'aluminium. C'est pourquoi le modèle les porte "
              "comme phases à part entière, et pourquoi leur teneur "
              "figure dans le rapport.",
        "en": "The collectors leave with the powder, as copper and "
              "aluminium fines. That is why the model carries them as "
              "phases in their own right, and why their grade appears in "
              "the report."},
    "proc.titre": {
        "fr": "Où nous entrons dans la chaîne",
        "en": "Where we enter the chain"},
    "proc.chapeau": {
        "fr": "KLASTOS21 ne broie pas, ne dose pas, ne raffine pas. Sa "
              "matière première est un tableau de chiffres : le bulletin "
              "que votre laboratoire a rendu.",
        "en": "KLASTOS21 does not shred, assay or refine. Its raw material "
              "is a table of figures: the bulletin your laboratory "
              "produced."},
    "proc.lecon": {
        "fr": "Cette frontière explique tout le reste. L'outil ne peut pas "
              "regarder la poudre pour savoir d'où elle vient, d'où "
              "l'attestation de provenance. Un bulletin donne des "
              "éléments quand un acheteur paie des phases, et plusieurs "
              "mélanges de phases donnent le même bulletin : d'où "
              "l'indétermination, et d'où une fourchette là où vous "
              "attendiez un prix.",
        "en": "This boundary explains everything else. The tool cannot "
              "look at the powder to learn where it came from, hence the "
              "provenance attestation. A bulletin gives elements where a "
              "buyer pays for phases, and several phase mixtures produce "
              "the same bulletin: hence the indeterminacy, and hence a "
              "range where you expected a price."},
    "proc.alt": {
        "fr": "Schéma du procédé en six étapes : batteries en fin de vie, "
              "broyage, black mass, bulletin d'analyse, déconvolution, "
              "valeur payable. Les trois premières relèvent du lot, la "
              "quatrième du laboratoire, les deux dernières de KLASTOS21.",
        "en": "Six-step process diagram: end-of-life batteries, shredding, "
              "black mass, assay bulletin, deconvolution, payable value. "
              "The first three belong to the lot, the fourth to the "
              "laboratory, the last two to KLASTOS21."},

    "proc.zone.lot": {"fr": "LE LOT", "en": "THE LOT"},
    "proc.zone.labo": {"fr": "LE LABORATOIRE", "en": "THE LABORATORY"},
    "proc.zone.nous": {"fr": "KLASTOS21", "en": "KLASTOS21"},

    "proc.batterie.nom": {"fr": "Batteries", "en": "Batteries"},
    "proc.batterie.detail": {
        "fr": "Fin de vie, chutes de production",
        "en": "End of life, production scrap"},
    "proc.broyage.nom": {"fr": "Broyage", "en": "Shredding"},
    "proc.broyage.detail": {
        "fr": "Décharge, démantèlement, séparation",
        "en": "Discharge, dismantling, separation"},
    "proc.blackmass.nom": {"fr": "Black mass", "en": "Black mass"},
    "proc.blackmass.detail": {
        "fr": "La poudre que vous achetez ou vendez",
        "en": "The powder you buy or sell"},
    "proc.bulletin.nom": {"fr": "Bulletin", "en": "Bulletin"},
    "proc.bulletin.detail": {
        "fr": "Des éléments dosés, pas des phases",
        "en": "Assayed elements, not phases"},
    "proc.deconvolution.nom": {"fr": "Déconvolution", "en": "Deconvolution"},
    "proc.deconvolution.detail": {
        "fr": "Ce que la donnée porte, et ce qu'elle ne porte pas",
        "en": "What the data carries, and what it does not"},
    "proc.valeur.nom": {"fr": "Valeur payable", "en": "Payable value"},
    "proc.valeur.detail": {
        "fr": "Une fourchette opposable, jamais un point",
        "en": "A defensible range, never a point"},
    "cot.titre": {
        "fr": "Ce que vaut un prix d'il y a un mois",
        "en": "What a month-old price is worth"},
    "cot.chapeau": {
        "fr": "Quatre métaux payables, ramenés à une base 100 en 2021. "
              "Le carbonate de lithium de qualité batterie est passé de "
              "11 700 à 63 700 dollars la tonne en un an, puis à 9 000 "
              "quatre ans plus tard. Pendant ce temps le cuivre bougeait "
              "de 9 %.",
        "en": "Four payable metals, rebased to 100 in 2021. Battery-grade "
              "lithium carbonate went from 11,700 to 63,700 dollars per "
              "tonne in a year, then down to 9,000 four years later. Over "
              "the same period copper moved by 9 %."},
    "cot.lecon": {
        "fr": "C'est pourquoi KLASTOS21 refuse de valoriser sur une "
              "cotation de plus de sept jours. Le refus n'est pas une "
              "prudence d'affichage : sur ce marché, un prix périmé n'est "
              "pas un prix approximatif, c'est un autre prix.",
        "en": "This is why KLASTOS21 refuses to value a lot on a quotation "
              "older than seven days. The refusal is not for show: on this "
              "market a stale price is not an approximate price, it is a "
              "different price."},
    "cot.echelle": {
        "fr": "Échelle logarithmique : un doublement et une division par "
              "deux occupent la même hauteur.",
        "en": "Logarithmic scale: a doubling and a halving take the same "
              "height."},
    "cot.source": {
        "fr": "Source : USGS, Mineral Commodity Summaries 2026, moyennes "
              "annuelles. Cotations London Metal Exchange, sauf lithium "
              "(prix réel, qualité batterie). Les quatre métaux sont "
              "classés minerais critiques 2025.",
        "en": "Source: USGS, Mineral Commodity Summaries 2026, annual "
              "averages. London Metal Exchange quotations, except lithium "
              "(real price, battery grade). All four are listed 2025 "
              "critical minerals."},
    "cot.alt": {
        "fr": "Évolution indexée du lithium, du cobalt, du nickel et du "
              "cuivre de 2021 à 2025, en base 100.",
        "en": "Indexed evolution of lithium, cobalt, nickel and copper "
              "from 2021 to 2025, base 100."},
    "cot.lithium": {"fr": "Lithium", "en": "Lithium"},
    "cot.cobalt": {"fr": "Cobalt", "en": "Cobalt"},
    "cot.nickel": {"fr": "Nickel", "en": "Nickel"},
    "cot.copper": {"fr": "Cuivre", "en": "Copper"},
    "form.titre": {
        "fr": "Ou envoyez-le depuis cette page",
        "en": "Or send it from this page"},
    "form.chapeau": {
        "fr": "Si vous n'avez pas de logiciel de messagerie sous la main. "
              "Le bulletin se joint directement, en CSV ou en Excel.",
        "en": "If you have no mail application at hand. The bulletin "
              "attaches directly, as CSV or Excel."},
    "form.nom": {"fr": "Votre nom", "en": "Your name"},
    "form.organisation": {"fr": "Organisation", "en": "Organisation"},
    "form.courriel": {"fr": "Votre adresse de courriel",
                      "en": "Your email address"},
    "form.message": {"fr": "Message", "en": "Message"},
    "form.message.indice": {
        "fr": "Unité des dosages, provenance du lot, et tout ce qui vous "
              "paraît utile.",
        "en": "Assay unit, lot provenance, and anything else you find "
              "relevant."},
    "form.fichier": {"fr": "Le bulletin d'analyse", "en": "The assay bulletin"},
    "form.fichier.indice": {
        "fr": "CSV ou Excel, 10 Mo au plus. Facultatif : vous pouvez aussi "
              "l'envoyer ensuite par courriel.",
        "en": "CSV or Excel, 10 MB maximum. Optional: you may also send it "
              "afterwards by email."},
    "form.envoyer": {"fr": "Envoyer", "en": "Send"},
    "form.obligatoire": {"fr": "obligatoire", "en": "required"},

    # Accuse de reception. Il redit le delai de 48 h ouvrees, engagement
    # pris sur l'accueil et la page Contact, et rappelle ce qui manque le
    # plus souvent.
    # ------------------------------------------------------------------
    # La page d'erreur. Elle est BILINGUE sur un seul document, parce
    # qu'elle est servie pour n'importe quelle adresse : impossible de
    # savoir dans quelle langue était le visiteur.
    #
    # Elle traite d'abord le cas qui coûte un client : un envoi de
    # formulaire qui n'aboutit pas. Netlify répond alors 404, et sa page
    # générique ne dit ni ce qui s'est passé ni quoi faire.
    # ------------------------------------------------------------------
    "err.titre_onglet": {
        "fr": "Page introuvable | KLASTOS21",
        "en": "Page not found | KLASTOS21"},
    "err.description": {
        "fr": "Cette adresse n'existe pas sur klastos21.fr.",
        "en": "This address does not exist on klastos21.fr."},
    "err.h1": {
        "fr": "Cette adresse n'existe pas.",
        "en": "This address does not exist."},
    "err.chapeau": {
        "fr": "Un lien périmé, une adresse mal recopiée, ou un envoi "
              "qui n'a pas abouti.",
        "en": "A stale link, a mistyped address, or a submission that "
              "did not go through."},
    "err.envoi.titre": {
        "fr": "Vous nous envoyiez un bulletin ?",
        "en": "Were you sending us a bulletin?"},
    "err.envoi.texte": {
        "fr": "Votre message n'est pas parti, et nous ne l'avons pas "
              "reçu. Écrivez-nous directement à l'adresse ci-dessous en "
              "joignant votre fichier : c'est la voie la plus sûre, et "
              "elle ne dépend d'aucun formulaire.",
        "en": "Your message did not leave, and we did not receive it. "
              "Write to us directly at the address below with your file "
              "attached: it is the surest route, and it depends on no "
              "form."},
    "err.retour": {
        "fr": "Revenir à l'accueil",
        "en": "Back to home"},
    "merci.titre_onglet": {
        "fr": "Message reçu | KLASTOS21",
        "en": "Message received | KLASTOS21"},
    "merci.description": {
        "fr": "Votre message a bien été transmis à KLASTOS21.",
        "en": "Your message has reached KLASTOS21."},
    "merci.surtitre": {"fr": "Message reçu", "en": "Message received"},
    "merci.h1": {
        "fr": "C'est bien arrivé.",
        "en": "It got through."},
    "merci.chapeau": {
        "fr": "Nous revenons vers vous sous 48 h ouvrées avec le rapport, "
              "et le cas échéant avec la liste des dosages qui lèveraient "
              "l'indétermination.",
        "en": "We will come back within two working days with the report "
              "and, where relevant, the list of assays that would lift the "
              "indeterminacy."},
    "merci.oubli.titre": {
        "fr": "Si vous avez oublié le bulletin",
        "en": "If you forgot the bulletin"},
    "merci.oubli.texte": {
        "fr": "Envoyez-le à cette adresse en répondant simplement. Sans "
              "lui, nous ne pouvons rien conclure.",
        "en": "Send it to this address, simply by replying. Without it we "
              "can conclude nothing."},
    "merci.retour": {"fr": "Revenir à l'accueil", "en": "Back to home"},

    "contact.modele.titre": {
        "fr": "Un modèle de bulletin",
        "en": "A bulletin template"},
    "contact.modele.texte": {
        "fr": "Si vous préférez partir d'un format sûr, un modèle CSV "
              "accepté par l'outil est fourni avec le projet, sous "
              "data/exemples/bulletin_modele.csv. Il évite les deux pièges "
              "de forme les plus courants.",
        "en": "If you would rather start from a format known to work, a CSV "
              "template accepted by the tool ships with the project, at "
              "data/exemples/bulletin_modele.csv. It avoids the two "
              "commonest formatting traps."},

    # ================================================================
    # Pour qui. Les sites de la filiere (cylib, tozero, Primobius)
    # orientent le visiteur par profil des l'accueil ; le notre parlait
    # de methode sans dire a qui elle sert. Chaque carte reprend
    # l'argument du segment dans `docs/mails_prospection.md`.
    # ================================================================
    "index.pourqui.surtitre": {
        "fr": "Pour qui",
        "en": "Who it is for"},
    "index.pourqui.titre": {
        "fr": "Le même bulletin ne pose pas la même question à tout le "
              "monde.",
        "en": "The same bulletin does not ask everyone the same "
              "question."},
    "index.pourqui.vendeur.titre": {
        "fr": "Vous vendez de la black mass",
        "en": "You sell black mass"},
    "index.pourqui.vendeur.texte": {
        "fr": "Sachez avant l'acheteur quelles teneurs sont inattaquables, "
              "et quel dosage commander pour clore le débat sur les autres.",
        "en": "Know before the buyer does which grades cannot be "
              "challenged, and which assay to order to settle the rest."},
    "index.pourqui.acheteur.titre": {
        "fr": "Vous en achetez",
        "en": "You buy it"},
    "index.pourqui.acheteur.texte": {
        "fr": "Séparez ce que le bulletin du vendeur détermine de ce qu'il "
              "laisse ouvert. Sur vos volumes, un écart de lecture se "
              "compte à l'année, pas au lot.",
        "en": "Separate what the seller's bulletin determines from what it "
              "leaves open. On your volumes, a reading error adds up over "
              "the year, not per lot."},
    "index.pourqui.negociant.titre": {
        "fr": "Vous la négociez",
        "en": "You trade it"},
    "index.pourqui.negociant.texte": {
        "fr": "Votre marge tient dans l'écart entre le prix payé et le "
              "contenu réel. KLASTOS21 mesure la part de cet écart qui "
              "vient de l'incertitude analytique.",
        "en": "Your margin lies in the gap between the price paid and the "
              "real content. KLASTOS21 measures the share of that gap that "
              "comes from analytical uncertainty."},
    "index.pourqui.labo.titre": {
        "fr": "Vous l'analysez",
        "en": "You analyse it"},
    "index.pourqui.labo.texte": {
        "fr": "Vos clients tirent de vos bulletins des conclusions que la "
              "mesure ne porte pas toujours. L'outil désigne, chiffres à "
              "l'appui, le dosage complémentaire qui les justifierait.",
        "en": "Your clients draw conclusions from your bulletins that the "
              "measurement does not always support. The tool names, with "
              "figures, the extra assay that would justify them."},
    "index.pourqui.lien": {
        "fr": "Envoyer un bulletin",
        "en": "Send a bulletin"},

    # ================================================================
    # L'offre, en bandeau de fin d'accueil. La page se terminait sur les
    # attestations, sans rien proposer de faire. Les trois engagements
    # (gratuite, 48 h ouvrees, confidentialite) sont repris a l'identique
    # sur la page Contact et dans l'accuse de reception.
    # ================================================================
    "index.offre.surtitre": {
        "fr": "Première analyse offerte",
        "en": "First analysis free"},
    "index.offre.titre": {
        "fr": "Envoyez un bulletin. Le verdict revient sous 48 h ouvrées.",
        "en": "Send a bulletin. The verdict comes back within two working "
              "days."},
    "index.offre.texte": {
        "fr": "Un bulletin anonymisé suffit. Vous recevez le rapport "
              "complet, y compris s'il conclut que vos données ne suffisent "
              "pas, et vous en faites ce que vous voulez.",
        "en": "An anonymised bulletin is enough. You receive the full "
              "report, including when it concludes that your data fall "
              "short, and you do what you like with it."},
    "index.offre.f1": {
        "fr": "<b>Gratuit</b> pour le premier bulletin, sans engagement",
        "en": "<b>Free</b> for the first bulletin, no commitment"},
    "index.offre.f2": {
        "fr": "<b>48 h ouvrées</b> pour rendre le rapport",
        "en": "<b>Two working days</b> to return the report"},
    "index.offre.f3": {
        "fr": "<b>Confidentiel</b> : accord de confidentialité sur demande, "
              "données supprimées 30 jours après le rendu",
        "en": "<b>Confidential</b>: non-disclosure agreement on request, "
              "data deleted 30 days after delivery"},
    "index.offre.bouton": {
        "fr": "Envoyer un bulletin",
        "en": "Send a bulletin"},

    # Apercu dessine de la premiere page du rapport. C'est la « photo
    # produit » du site : les concurrents montrent leurs usines, nous
    # montrons le document, et la legende dit qu'il est dessine.
    "apercu.alt": {
        "fr": "Aperçu dessiné de la première page d'un rapport KLASTOS21 : "
              "un verdict, puis quatre grandeurs sur la même échelle, deux "
              "en trait fin parce que déterminées, deux en bande parce que "
              "seulement compatibles.",
        "en": "Drawn preview of the first page of a KLASTOS21 report: a "
              "verdict, then four quantities on the same scale, two as thin "
              "lines because they are determined, two as bands because they "
              "are only compatible."},
    "apercu.titre": {
        "fr": "Rapport d'analyse",
        "en": "Analysis report"},
    "apercu.verdict": {
        "fr": "Verdict",
        "en": "Verdict"},
    "apercu.verdict.texte": {
        "fr": "Bouclage conforme",
        "en": "Mass balance accepted"},
    "apercu.legende": {
        "fr": "Dessin de la première page. Le document réel est sur la "
              "page Rapport.",
        "en": "Drawing of the first page. The real document is on the "
              "Report page."},

    # ================================================================
    # Ce que nous garantissons, page Contact. Le frein principal a
    # l'envoi d'un bulletin est la confidentialite : un concurrent qui
    # ACHETE de la matiere n'a pas besoin d'en parler, nous qui DEMANDONS
    # une donnee sensible, si.
    #
    # La cinquieme ligne n'est pas une precaution oratoire : le
    # formulaire transite par l'hebergeur du site. Promettre un
    # traitement local tout en recevant le fichier par un tiers serait
    # faux, on le dit donc.
    # ================================================================
    "contact.confiance.titre": {
        "fr": "Ce que nous vous garantissons",
        "en": "What we guarantee"},
    "contact.confiance.f1": {
        "fr": "<b>La première analyse est gratuite</b>, sans engagement.",
        "en": "<b>The first analysis is free</b>, with no commitment."},
    "contact.confiance.f2": {
        "fr": "<b>Le rapport revient sous 48 h ouvrées</b> après réception "
              "d'un bulletin complet.",
        "en": "<b>The report comes back within two working days</b> of "
              "receiving a complete bulletin."},
    "contact.confiance.f3": {
        "fr": "<b>Un accord de confidentialité</b> est signé sur simple "
              "demande, avant tout envoi.",
        "en": "<b>A non-disclosure agreement</b> is signed on request, "
              "before anything is sent."},
    "contact.confiance.f4": {
        "fr": "<b>L'analyse tourne sur notre machine</b>, jamais sur un "
              "service en ligne, et le bulletin est <b>supprimé 30 jours</b> "
              "après le rendu du rapport.",
        "en": "<b>The analysis runs on our own machine</b>, never on an "
              "online service, and the bulletin is <b>deleted 30 days</b> "
              "after the report is delivered."},
    "contact.confiance.f5": {
        "fr": "<b>Pour un lot sensible</b>, ne joignez rien au formulaire : "
              "demandez d'abord l'accord de confidentialité, le bulletin "
              "suivra.",
        "en": "<b>For a sensitive lot</b>, attach nothing to the form: ask "
              "for the non-disclosure agreement first, the bulletin can "
              "follow."},

    # Image de partage (Open Graph). Son texte est dessine dans le PNG par
    # `site/partage.py` a partir de `index.h1` et `partage.sous_titre` ;
    # la description ci-dessous le redit pour qui ne voit pas l'image.
    "partage.sous_titre": {
        "fr": "Analyse prédictive de bulletins de black mass",
        "en": "Predictive analysis of black mass assay bulletins"},
    "partage.alt": {
        "fr": "KLASTOS21. Un chiffre que vous pouvez opposer, ou rien. "
              "Quatre grandeurs d'un bulletin de black mass : deux traits "
              "fins déterminés, deux bandes larges seulement compatibles.",
        "en": "KLASTOS21. A figure you can stand behind, or nothing at all. "
              "Four "
              "quantities from a black mass bulletin: two thin determined "
              "lines, two wide bands that are only compatible."},

    # Le profil du visiteur, dans le formulaire. Il trie les demandes
    # comme le fait le menu « You are » de cylib, et il n'est pas
    # obligatoire : mieux vaut un envoi sans profil qu'aucun envoi.
    "form.profil": {"fr": "Vous êtes", "en": "You are"},
    "form.profil.choisir": {"fr": "Choisir", "en": "Choose"},
    "form.profil.vendeur": {
        "fr": "Vendeur de black mass (prétraiteur, recycleur)",
        "en": "Black mass seller (pre-processor, recycler)"},
    "form.profil.acheteur": {
        "fr": "Acheteur (affineur, recycleur)",
        "en": "Buyer (refiner, recycler)"},
    "form.profil.negociant": {"fr": "Négociant", "en": "Trader"},
    "form.profil.labo": {"fr": "Laboratoire", "en": "Laboratory"},
    "form.profil.autre": {"fr": "Autre", "en": "Other"},
}


def t(cle: str, langue: str = DEFAUT) -> str:
    """Le texte de `cle` dans `langue`. Leve CleInconnue si elle manque."""
    entree = TEXTES.get(cle)
    if entree is None:
        raise CleInconnue(f"cle absente du contenu du site : {cle!r}")
    texte = entree.get(langue)
    if texte is None:
        raise CleInconnue(
            f"cle {cle!r} non traduite en {langue!r}")
    return texte


def langue_valide(langue: str | None) -> str:
    """`langue` si elle est connue, sinon la langue par defaut."""
    return langue if langue in LANGUES else DEFAUT
