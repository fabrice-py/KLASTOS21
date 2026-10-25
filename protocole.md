# PROTOCOLE MÉTHODOLOGIQUE KLASTOS21 v0

Ce document engage KLASTOS21 sur ce que l'outil sait, ce qu'il ne sait pas,
et ce qu'il s'interdit d'affirmer. Il est destiné à accompagner tout rapport
client. Il est versionné avec le code.

---

## 1. Statut des données

### 1.1 Données synthétiques

Le module `klastos/generator.py` est un **outil de test interne**. Il n'est
pas un oracle du réel.

- Il sert exclusivement à valider la mécanique du solveur en l'absence de
  données réelles.
- Il ne décrit pas la population réelle des lots de black mass.
- Ses bornes de composition sont des **hypothèses métier**, non sourcées et
  non statistiques.
- Aucune de ses sorties ne figure dans un livrable client.

**Verrous techniques.** Tout lot produit porte le marqueur
`meta["data_class"] == "synthetique"`. La fonction `assert_client_grade()`
lève une exception si une telle donnée atteint un contexte client. Ces
verrous sont couverts par des tests de non-régression.

### 1.2 Engagement de révision

> **Les bornes de composition seront révisées à partir de données de lots
> réels. La version 1.1 intégrera les statistiques de composition observées,
> en remplacement des bornes actuelles.**

Jusque-là, tout profil non arbitré porte `validated=False` et la fonction
`unvalidated_profiles()` en donne la liste à jour.

### 1.3 Paramètres analytiques

Le modèle de bruit par défaut porte **trois paramètres de statuts
différents**, et cette section disait le contraire jusqu'au 22 octobre 2026 :
elle annonçait `validated=False` pour l'ensemble, alors que le code porte
`validated=True` depuis que l'erreur relative a été sourcée.

| Paramètre | Valeur | Statut |
|---|---|---|
| `rel_sigma` | 6 % | **sourcé** : LNE-LiB01, certifié ISO 33405 |
| `abs_sigma` | 0,02 % massique | à valider : dépend du laboratoire |
| `lod` | 0,005 % massique | à valider : dépend de la méthode |

Les deux derniers seront remplacés par les valeurs réelles des bulletins dès
le premier lot client. Le premier est discuté ci-dessous : il est sourcé,
mais sa source est contredite par une autre.

### 1.3 bis. Deux certificats qui ne disent pas la même chose

**La contradiction.** `rel_sigma` vaut 6 % uniformes, calibré sur le matériau
de référence LNE-LiB01 : son certificat donne des incertitudes **élargies**
de 10 à 15 %, soit 5 à 7,5 % d'incertitude type à k = 2, dont on retient le
milieu. Le matériau de référence OREAS, lui, donne des écarts-types relatifs
**par élément** :

| Élément | RSD | | Élément | RSD |
|---|---|---|---|---|
| Ni | 0,51 % | | Al | 2,86 % |
| Li | 0,99 % | | Fe | 3,60 % |
| Co | 1,05 % | | Cu | 3,68 % |
| Mn | 1,08 % | | F | 5,70 % |
| C | 2,30 % | | P | 18,57 % |

L'écart est d'un **ordre de grandeur** sur le nickel (0,51 % contre 6 %) et
il est **inversé** sur le phosphore (18,57 % contre 6 %). Cela ne se tranche
pas en choisissant un certificat.

**Trois statistiques distinctes.** L'hypothèse à vérifier était que les deux
documents ne mesurent pas la même chose. Elle tient, et il y a au moins trois
grandeurs en jeu :

1. l'**incertitude d'une valeur certifiée** : à quel point la valeur de
   référence est connue. Elle décroît avec le nombre de laboratoires
   participants, approximativement en 1/√n ;
2. l'**homogénéité** du matériau : ce qu'on risque en prélevant une autre
   prise d'essai. Indépendante du nombre de laboratoires ;
3. la **reproductibilité interlaboratoires** : la dispersion des résultats
   entre laboratoires sur le même matériau. Ne décroît pas avec n.

Un facteur k = 2 sépare par ailleurs une incertitude élargie d'une
incertitude type, ce qui ajoute un facteur deux à toute comparaison faite
sans précaution.

**Ce que je n'ai pas pu établir, et je le dis plutôt que de le supposer.**
Aucun des deux certificats n'était disponible pour cette séance. Je dispose
de la description de LNE-LiB01 déjà portée par `generator.py`, et d'un
**extrait de données** OREAS, pas du certificat. L'extrait ne permet pas
d'identifier ce que ses propres colonnes rapportent, et c'est mesurable : si
`Expanded uncertainty Low/High` était une incertitude élargie à k = 2, sa
demi-largeur vaudrait environ deux fois `1SD`, soit un rapport
`1SD / demi-intervalle` proche de 0,5. Mesure sur les 34 éléments
quantifiés :

| Statistique du rapport | Valeur |
|---|---|
| médiane | 1,02 |
| minimum | 0,28 (dysprosium) |
| maximum | 2,34 (nickel) |

La médiane proche de 1 exclut k = 2 ; la dispersion de 0,28 à 2,34 exclut
**tout** facteur k unique entre les deux colonnes. Les deux grandeurs ne sont
donc pas liées par un élargissement, et lire les intitulés de colonnes comme
s'ils se suffisaient serait une erreur.

**Pourquoi le modèle reste à 6 % uniformes.** Trois raisons, dans cet ordre.

D'abord, la grandeur dont l'outil a besoin n'est **rapportée par aucun des
deux certificats**. `rel_sigma` doit modéliser l'erreur d'**un** bulletin,
produit par **un** laboratoire, sur un lot client **hétérogène** : c'est de
la reproductibilité *plus* de l'hétérogénéité d'échantillonnage. Un
certificat de matériau de référence décrit un matériau finement broyé et
homogénéisé, analysé par des laboratoires compétents. C'est un **meilleur
cas**, donc un plancher, pas une estimation.

Ensuite, la conséquence d'une erreur est mesurée, et elle est grande. Sur le
lot OREAS, avec les prix d'exemple du dépôt :

| Modèle de bruit | Intervalle de prix maximal | Largeur |
|---|---|---|
| 6 % uniformes | 3 693 – 4 454 USD/t | 761 USD/t, soit 18,69 % |
| RSD par élément (OREAS) | 4 026 – 4 147 USD/t | 121 USD/t, soit 2,96 % |

L'intervalle se resserrerait de **84 %**. Passer de ±9 % à ±1,5 % sur un prix
d'achat n'est pas un ajustement de détail : c'est un changement de ce que
l'outil prétend savoir.

Enfin, la direction est la dangereuse. Un bruit plus étroit resserre tous les
intervalles, donc le prix annoncé. Une fausse précision sur un prix d'achat
se paie comptant, et elle contredit la thèse du produit : ne jamais afficher
ce que la donnée ne porte pas.

**Ce qui a néanmoins changé.** `NoiseModel` sait désormais porter un bruit
**par élément** (`rel_sigma_par_element`), et les trois consommateurs du
bruit (la pondération du solveur, le rééchantillonnage d'incertitude, le
bruitage du générateur) passent par une méthode unique,
`NoiseModel.sigmas`.
La valeur par défaut est **inchangée**, et vérifiée bit pour bit. Un modèle
par élément est donc un **choix explicite de l'appelant**, jamais un défaut.

**Et pourquoi la table OREAS ne doit pas être ce choix.** La capacité existe ;
l'employer avec les RSD de ce certificat serait une erreur, et deux mesures
supplémentaires le montrent.

*Le modèle actuel n'est pas uniformément prudent.* Il est trop pessimiste sur
neuf éléments et trop optimiste sur le phosphore, le seul dont le RSD dépasse
6 %. L'effet dépend donc de la chimie du lot, et il change de signe :

| Lot | Effet du passage aux RSD par élément |
|---|---|
| OREAS, type NMC | intervalle de prix **resserré de 84 %** |
| lot riche en LFP, P à 8,86 % | intervalle de la phase LFP **élargi de 125 %** |

*Et la table extrapole une précision de trace vers une concentration
majeure.* Le RSD de 18,57 % sur le phosphore a été mesuré **à 0,350 %**, près
de la limite de détection, où un tel écart est normal. L'appliquer à un lot
LFP où le phosphore vaut 8,86 % n'a aucune justification : la précision
relative s'améliore avec la concentration, et la corrélation le confirme,
`log(RSD)` contre `log(concentration)` donne **r = −0,59** sur les 34 éléments
quantifiés du certificat.

Dernier indice, et il est indépendant : ajuster la forme même du modèle,
`sigma = rel_sigma·b + abs_sigma`, aux couples (valeur, 1SD) du certificat
donne des paramètres qui **varient de deux ordres de grandeur** selon la
fenêtre de concentration retenue.

| Fenêtre ajustée | `rel_sigma` | `abs_sigma` |
|---|---|---|
| tous les éléments | 1,34 % | 214 ppm |
| traces seules, < 0,1 % | 17,54 % | 3,6 ppm |
| majeurs seuls, ≥ 1 % | 0,98 % | 748 ppm |

L'accord apparent de 214 ppm avec les 200 ppm du modèle est une
**coïncidence** : l'estimateur direct sur les traces donne 1,9 ppm, soit cent
fois moins. Le `1SD` du certificat n'est donc pas descriptible par la forme
du modèle, ce qui est une raison de plus de ne pas l'y injecter, et
`abs_sigma` reste à valider, contrairement à ce que cet ajustement aurait pu
laisser croire.

**Conclusion opérationnelle.** Garder 6 % uniformes. Ne pas adopter la table
OREAS, même dans une variante qui n'élargirait que le phosphore. La capacité
par élément attend une source dont la définition et le domaine de
concentration soient connus.

### 1.3 ter. Engagement : l'analyse en double qui tranchera le bruit

> **Le modèle de bruit sera recalibré sur une ANALYSE EN DOUBLE d'un lot
> réel. Tant qu'elle n'a pas eu lieu, ou qu'une analyse en double publiée
> n'a pas été trouvée et reprise, `rel_sigma` reste à 6 % uniformes et
> aucun resserrement n'est appliqué.**

C'est le seul engagement de ce protocole qui porte sur une **mesure à
acquérir** plutôt que sur une règle de calcul. Il existe parce que la
grandeur dont l'outil a besoin n'est publiée par personne.

**Ce qu'il faut mesurer, exactement.** `rel_sigma` doit modéliser l'erreur
d'**un** bulletin, produit par **un** laboratoire, sur un lot client
**hétérogène**. Les deux certificats disponibles décrivent un matériau
finement broyé et homogénéisé, analysé par des laboratoires compétents :
c'est un meilleur cas, donc un plancher, et jamais une estimation.

**Le protocole de la mesure.** Deux précautions, et elles ne sont pas des
détails :

1. **Même prise d'essai divisée en deux**, puis envoyée à deux laboratoires.
   Prélever deux fois dans le lot mesurerait l'hétérogénéité
   d'échantillonnage, qui est une autre grandeur.
2. **Sur le lot le plus hétérogène disponible**, pas le plus propre. C'est le
   pire cas qui doit calibrer le modèle, sans quoi on recommence l'erreur
   des certificats.

**Chemin de repli, également admis.** Une analyse en double **publiée** sur
une black mass réelle — comparaison interlaboratoires, étude de
reproductibilité, essai circulaire d'un organisme de normalisation — vaut
autant, à condition qu'elle porte sur une matière réelle et non sur un
matériau de référence, et que sa provenance soit citée comme l'est celle du
bulletin OREAS au § 1.3 bis. Si une telle donnée est trouvée, elle doit être
versée au dépôt avec sa note de provenance et le modèle recalibré.

**Ce que l'attente coûte, et ce qu'elle protège.** Le resserrement en jeu
vaut **84 %** de la largeur de l'intervalle de prix sur un lot NMC, et un
**élargissement de 125 %** sur un lot LFP. L'enjeu est donc considérable
dans les deux sens. Mais resserrer sans la mesure produirait une fausse
précision sur un prix d'achat, qui se paie comptant — d'où le refus
d'avancer sans elle.

**À défaut.** Les deux certificats complets permettraient au moins de lire
la définition exacte de chaque colonne, et donc de savoir laquelle des trois
statistiques du § 1.3 bis chacun rapporte. Ils ne mesureraient toujours pas
la grandeur dont l'outil a besoin.

---

## 2. Ce que l'outil affirme, et avec quelle force

KLASTOS21 distingue deux natures de résultat et ne les mélange jamais.

### 2.1 Grandeurs fermes

Une grandeur est **ferme** lorsqu'elle est mathématiquement déterminée par
l'analyse élémentaire, quelle que soit la solution retenue par le solveur.
Le caractère ferme est **calculé**, jamais supposé.

Sont fermes en toute configuration :

- les teneurs élémentaires (Li, Ni, Co, Mn, Fe, Cu, Al, P, F, C) ;
- la masse totale de cathodes ;
- le bloc « NMC + LCO » ;
- les phases hors famille dégénérée (LFP, NCA, LMO, carbone total,
  collecteurs, liant, sel d'électrolyte, fer métallique).

**La valorisation du lot et le prix maximal à payer reposent exclusivement
sur des grandeurs fermes.**

### 2.2 Domaines compatibles

Une grandeur non identifiable n'est jamais affichée comme un chiffre unique.
Elle est rapportée sous forme de **domaine compatible**, accompagné de la
mention normalisée :

> *ventilation non identifiable par analyse élémentaire seule*

**Garantie, et sa portée exacte.** Le domaine compatible contient toujours la
valeur vraie. Cette garantie porte sur les grandeurs **non identifiables** :
un domaine compatible est un ensemble mathématique borné, toute valeur qu'il
contient explique le bulletin, et la valeur vraie en fait nécessairement
partie. Vérifié sans aucun dépassement sur douze lots.

Une grandeur **ferme** reçoit en revanche un **intervalle de confiance**, pas
une garantie : son incertitude est purement statistique. L'intervalle 5–95
couvre la valeur vraie dans environ 90 % des cas, mesuré à 90,2 % sur 315
observations. Exiger 100 % de couverture imposerait l'enveloppe min/max des
tirages, qui n'est pas un estimateur stable puisqu'elle s'élargit
mécaniquement avec le nombre de tirages.

L'intervalle **affiché** est toujours celui qui sert au **classement**.
Montrer une fourchette étroite puis qualifier la grandeur de mal déterminée
sur la base d'un intervalle plus large et invisible serait trompeur.

### 2.3 Les deux incertitudes

KLASTOS21 sépare deux incertitudes de nature différente, parce qu'elles
n'appellent pas la même décision.

| | Origine | Réductible par | Rapportée comme |
|---|---|---|---|
| **Analytique** | bruit du bulletin | une analyse de meilleure qualité | intervalle à 5–95 % |
| **Structurelle** | rang déficient de la matrice | DRX, Raman, ou attestation de provenance | domaine compatible |

**Règle de prudence.** Pour toute grandeur non identifiable, l'incertitude est
déclarée structurelle, même lorsque la dispersion mesurée paraît d'origine
analytique. KLASTOS21 ne recommande jamais une analyse plus fine pour résoudre
un problème d'identifiabilité : ce serait vendre au client une dépense inutile.

### 2.4 Le piège du sommet

La contrainte de non-négativité peut restaurer l'unicité apparente d'un
système pourtant dégénéré. Lorsque plusieurs phases ressortent à exactement
zéro, aucun déplacement n'est possible sans rendre une fraction négative, et
le solveur produit une solution unique.

**Cette unicité est un artefact.** Elle dépend du bulletin exact. Un bruit
analytique de 3 % suffit à déplacer ce sommet, et une grandeur affichée à
0,00 % peut en réalité balayer 0 à 40 %.

KLASTOS21 signale ces cas par un avertissement explicite et rapporte
systématiquement l'enveloppe sur l'ensemble des tirages, jamais le domaine du
seul bulletin central. Un outil qui ne ferait pas cette distinction afficherait
des chiffres faussement précis.

### 2.5 Identifiable n'est pas exploitable

L'identifiabilité est binaire, le conditionnement est continu. Une grandeur
peut être mathématiquement déterminée et rester inexploitable si le système est
mal conditionné. Le rapport distingue donc trois statuts :

| Statut | Signification |
|---|---|
| **ferme** | déterminée et exploitable |
| **ferme mais mal déterminée** | déterminée en théorie, fourchette trop large en pratique |
| **non identifiable** | domaine compatible, jamais un chiffre |

Le critère d'exploitabilité est **relatif**, pas absolu. Un critère absolu
serait faux dans les deux sens : il condamnerait une teneur en nickel de 19 %
connue à ±1 point (soit 5 %, très bon) et absoudrait une phase mineure à 0,9 %
connue à ±1 point (soit 100 %, inutilisable). Un plancher absolu complète le
critère pour les grandeurs proches de zéro.

### 2.6 Le rendu montre ce que les chiffres ne disent pas

Le rapport est émis sous deux formes, issues du **même objet** : aucune des
deux ne calcule quoi que ce soit, aucune ne peut donc dire autre chose que
l'autre.

| Forme | Usage |
|---|---|
| Markdown | relecture technique, archivage, intégration |
| HTML | document client, imprimable en PDF depuis le navigateur |

La forme HTML porte en plus des **barres d'intervalle**. Elles existent pour
une raison de fond : un tableau de chiffres ne fait pas voir qu'une grandeur
ferme est un trait fin et qu'un domaine compatible est une bande large. C'est
la distinction centrale du protocole, et elle doit être visible avant d'être
lue.

Deux engagements de rendu en découlent.

- **La gravité d'un diagnostic est une donnée**, portée par la ligne du
  rapport, jamais déduite de la présence d'un mot dans une phrase. Un message
  de bouclage dégradé ne contient pas le mot « alerte » : une telle heuristique
  affichait un lot en alerte comme conforme.
- **Une largeur de fourchette n'est jamais étiquetée « ferme »**. Dans les
  sections qui rapportent des largeurs, le statut ne dit pas si la grandeur est
  identifiable mais si la largeur est **réductible** par une meilleure analyse
  ou **irréductible** sans donnée structurale. Le vocabulaire change avec le
  sens.

### 2.7 Un seul chemin, deux portes

La chaîne complète (lire le bulletin, résoudre la provenance, propager
l'incertitude, valoriser, assembler le rapport) vit dans un module unique.
La ligne de commande et l'interface graphique n'en sont que des
**adaptateurs** : elles traduisent des arguments ou des widgets en demande,
puis une analyse en affichage.

Ce n'est pas une élégance d'architecture, c'est une garantie pour le client.
Deux chemins parallèles divergent toujours : l'un reçoit un correctif, l'autre
non ; l'un pose un verrou, l'autre l'oublie. Le jour où le rapport issu de
l'interface ne dit plus la même chose que celui issu de la ligne de commande
pour le même lot, le client a raison et nous avons tort.

Un test interdit à un adaptateur d'appeler lui-même les étapes réservées, et
vérifie que les deux routes d'entrée (un chemin de fichier, un fichier
téléversé) produisent un rapport identique au caractère près.

La même règle vaut pour la lecture des bulletins : **une seule reconnaissance
de format dans le projet**. L'interface l'avait réimplémentée et la ratait.
un bulletin large à deux colonnes se lisait comme un format long.

### 2.7 bis. Ce qu'un graphique a le droit de montrer

> **Un graphique ne montre jamais ce que la donnée ne porte pas.**

Le camembert de phases minérales à valeur unique, sommant à 100 %, est le
visuel que tout le monde attend d'un outil de reconstitution. Il est faux sur
une black mass, et il est faux de la pire manière : il a l'air juste.

Démonstration, sur le bulletin d'exemple. Deux assemblages minéralogiques
construits dans l'espace nul :

| Phase | Lot A | Lot B | Écart |
|---|---|---|---|
| PVDF | 2,86 % | 0,00 % | 2,86 pt |
| LiPF₆ | 0,00 % | 2,27 % | 2,27 pt |
| LFP | 9,62 % | 7,27 % | 2,35 pt |

Les bulletins d'analyse que ces deux lots produiraient sont identiques à
**2,8 × 10⁻¹⁵ point de masse** près, soit la précision machine. Aucun laboratoire
ne peut les distinguer, et le solveur retient l'un plutôt que l'autre pour
une raison numérique, pas physique. Dessiner sa part revient à présenter un
arbitrage d'algorithme comme un résultat de mesure.

Deux règles en découlent, vérifiées par les tests du rendu.

**Le camembert porte la composition élémentaire**, qui est ferme, augmentée
de l'oxygène prédit et de la masse non expliquée. Il est construit sur la
composition **reconstituée** (A·x) et non sur les teneurs lues : la somme
fait alors exactement la masse expliquée, et le total exactement 100 %.
Mélanger les deux donnait 100,01 % et aurait obligé à tricher sur la part
grise.

**Le camembert bascule automatiquement sur les phases** le jour où toutes
deviennent fermes. L'interdiction n'est donc pas un refus de principe :
c'est une condition sur la donnée d'entrée.

**Correction apportée par la séance 17.** Ce paragraphe affirmait qu'une
quantification par diffraction de deux phases ramenait la dégénérescence à
zéro et rendait toutes les phases déterminées. C'est vrai dans le cas limite
d'une mesure d'incertitude **nulle**, et ce cas n'existe pas : une
quantification Rietveld porte 1 à 3 points d'incertitude absolue. Elle entre
donc en encadrement, et une inégalité **borne** une direction nulle sans la
supprimer. Mesuré sur le lot d'exemple en provenance VE attestée, à deux
points d'incertitude : la dégénérescence reste à 2, aucune grandeur ne
devient ferme, et la largeur cumulée des phases passe de 61,35 à 17,39
points, 72 % de resserrement. Le camembert ne basculera donc pas sur les
phases du fait d'une DRX.

Nombre de phases à quantifier pour annuler la dégénérescence, dans le cas
limite u → 0, et coût de la base cristalline :

| Provenance | Dégénérescence | Base absolue | Base cristalline |
|---|---|---|---|
| Non déclarée | 4 | 4 phases | 5 phases |
| VE attestée | 2 | 2 phases | 3 phases |
| Chutes gigafactory, grades déclarés | 1 | 1 phase | 2 phases |

La base cristalline coûte exactement une phase, dans les trois cas : *n*
phases quantifiées ne donnent que *n* − 1 rapports indépendants.

### 2.8 Ce que le rapport refuse de faire

Le rapport n'est pas émis lorsqu'un engagement du protocole n'est pas tenu :

- donnée provenant du générateur de test ;
- jeu de prix non destiné à la production ;
- bulletin dont le bouclage massique est hors tolérance.

Un document de démonstration peut être produit explicitement, mais il porte
alors la mention **non opposable** en tête.

### 2.6 L'oxygène n'est jamais dosé

Aucun laboratoire de routine ne dose l'oxygène : il n'existe pas de méthode
économique pour une telle matrice. Un bulletin de black mass somme donc autour
de 71 %, le reste étant l'oxygène lié dans les oxydes de cathode.

**KLASTOS21 ne l'invente pas.** Il résout sur les éléments effectivement dosés,
et l'oxygène devient une grandeur **prédite** à partir des phases reconstituées.
L'oxygène par différence est écarté : testé sur un lot connu, il donne 27,9 %
au lieu de 18,9 %, et il détruit le diagnostic de bouclage en le rendant exact
par construction.

Deux conséquences, toutes deux rapportées.

**Le bouclage se mesure sur les phases, jamais sur le bulletin.** Les colonnes
de la matrice de stœchiométrie sommant à 1, la somme des fractions de phases
couvre toute la masse, oxygène compris. Un lot reconstitué à 92 % signale donc
8 % de masse que le modèle n'explique pas : humidité, phase absente du modèle,
ou déclaration inexacte. Mesurer le bouclage sur le bulletin rejetterait tous
les lots réels.

**La dégénérescence augmente d'un degré.** Sans l'oxygène, « Cathodes
totales » et le bloc « NMC + LCO » cessent d'être identifiables sur liste
large. Une attestation de provenance restaure le bloc « NMC + LCO ». Elle ne
restaure PAS « Cathodes totales ».

Mesure, sur la liste complète et sur la liste restreinte aux véhicules
électriques :

| Liste de phases | Oxygène | Degrés de liberté | Cathodes totales | NMC + LCO |
|---|---|---|---|---|
| complète | dosé | 2 | ferme | ferme |
| complète | non dosé | 4 | **non identifiable** | **non identifiable** |
| provenance attestée | dosé | 1 | ferme | ferme |
| provenance attestée | non dosé | 2 | **non identifiable** | ferme |

Conséquence, écrite sans détour : **« Cathodes totales » n'est ferme que si
l'oxygène est dosé.** Sur un bulletin de routine, qui ne le dose pas, cette
grandeur est rapportée en domaine compatible comme n'importe quelle autre
grandeur ouverte. L'annoncer ferme serait une promesse que la donnée d'entrée
ne permet pas de tenir.

### 2.6 quater. Ce qu'un dosage d'oxygène apporterait

Le client peut commander un dosage d'oxygène. Le rapport chiffre ce qu'il y
gagnerait, **et ce qu'il n'y gagnerait pas**, au lieu de le laisser deviner.

**Le critère de décision est une demi-plage.** La reconstitution, sans avoir
dosé l'oxygène, le contraint déjà à un intervalle. Une grandeur que le dosage
rendrait ferme est fonction affine de la teneur dosée : sa largeur ouverte
vaut |levier| × plage, et un dosage d'incertitude type u la ramène à
|levier| × 2u. Il y a donc gain si et seulement si u < plage / 2. Le
levier disparaît de l'inégalité : **le critère est le même pour toutes les
grandeurs concernées et ne dépend que de la plage compatible de l'oxygène.**

**Le dosage n'apporte rien à la ventilation par grade.** Mesuré : les largeurs
des grades NMC sont strictement inchangées par le conditionnement. Cette
dégénérescence vit dans le sous-système fermé Li-Ni-Mn-Co-O, que l'oxygène ne
contraint pas. Seules une donnée structurale (DRX) ou une attestation de
provenance la lèvent. Le rapport le dit explicitement, pour que personne ne
paie un essai qui ne répondra pas à sa question.

**Le scénario balaie, il ne se pose jamais sur un point.** Y réinjecter la
teneur en oxygène prédite par la reconstitution produirait des grandeurs
exactement déterminées, d'une précision qui n'est qu'un artefact du point
retenu par le solveur, puisque cette valeur sort de la solution elle-même.
C'est le piège du sommet dans sa forme la plus pure, et c'est la manière
simple et fausse de produire cette section. Les largeurs rapportées sont donc
obtenues en balayant toute la plage compatible, et la plus défavorable est
retenue.

**Le balayage est raffiné, parce que trois points ne suffisent pas.** Notons
w(v) la largeur conditionnelle à une teneur supposée v. C'est un maximum de
forme linéaire moins un minimum de forme linéaire sur un polytope paramétré
par son second membre : le premier est concave, le second convexe, donc
**w(v) est concave**. Or le maximum d'une fonction concave est génériquement
**intérieur**. Un balayage limité aux bornes et au milieu le manque, et le
manque toujours par en dessous, il annonce donc un gain plus grand que le
gain réel, c'est-à-dire exactement le biais qu'un rapport commercial ne doit
pas avoir. Mesure sur un lot de provenance non déclarée, grade NMC 811 :
trois points donnent 26,18 points quand le maximum réel vaut 27,21 points,
atteint à 42 % de la plage. La concavité fournit aussi la parade, sur une
grille, le maximum réel est encadré par les deux voisins du maximum de grille
et le balayage procède par passes de resserrement successives.

**Les largeurs de cette section sont structurelles.** Ce sont les largeurs
structurelles du bulletin central : la part d'incertitude due à la
dégénérescence, et elle seule. Elles sont plus étroites que les fourchettes
des autres sections, qui ajoutent l'incertitude analytique du laboratoire. Un
dosage d'oxygène ne réduit que la part structurelle. La mention figure dans
la section, faute de quoi le lecteur verrait deux largeurs différentes pour
la même grandeur sans comprendre pourquoi.

**Une grandeur déjà épinglée à largeur nulle n'entre pas dans le scénario.**
La non-négativité suffit parfois à déterminer une grandeur non identifiable,
c'est le piège du sommet. Elle n'a rien à gagner à un dosage, et l'y faire
figurer la déclarait « deviendrait ferme » dans la section même qui la
listait parmi celles auxquelles le dosage n'apporte rien.

**Aucun chiffre de cette section n'est opposable** : ce sont des largeurs
projetées sous l'hypothèse d'un dosage que le client ne possède pas. Elles ne
modifient aucun résultat des autres sections.

**Périmètre, non arbitré.** Seul l'oxygène fait l'objet d'un scénario.
L'hydrogène lève formellement un degré de liberté lui aussi, mais il est
écarté : dans le modèle il n'existe que dans le PVDF, alors que dans une black
mass réelle l'hydrogène total est dominé par l'humidité résiduelle et les
solvants d'électrolyte, que le modèle ne porte pas. Un dosage d'hydrogène
total mesurerait donc surtout ce que le modèle ignore. Ce choix est une
hypothèse de modélisation, pas une mesure, et sera revu si un client dispose
d'un dosage d'hydrogène corrigé de l'humidité.

### 2.6 bis. Deux diagnostics indépendants

| Diagnostic | Ce qu'il mesure | Ce qu'il détecte |
|---|---|---|
| **Résidu d'ajustement** | cohérence interne du bulletin | une analyse physiquement impossible |
| **Masse non expliquée** | couverture du modèle | humidité, phase absente, fausse déclaration |

Les deux sont indépendants. À titre d'illustration mesurée, un bulletin
annonçant 2,09 % de phosphore sans fer ni fluor est impossible, le phosphore
ne peut venir que du LFP, qui apporte du fer, ou du LiPF₆, qui apporte du
fluor. Son résidu ressort à 1,79 point contre 0,007 point pour un bulletin
cohérent présentant la même masse non expliquée.

### 2.6 ter. Seuils de bouclage

Le bouclage a **deux directions**, et elles ne se jugent pas de la même
façon. Le seuil de rejet est donc asymétrique.

| Écart au bouclage | Statut | Conséquence |
|---|---|---|
| sous 6 %, dans les deux sens | conforme | aucune |
| 6 % à 20 % de masse non expliquée | alerte | lot exploitable, cause à élucider |
| au-delà de 20 % de masse non expliquée | rejet | analyse complémentaire requise |
| 6 % à 12 % de masse en excès | alerte | lot exploitable, cause à élucider |
| au-delà de 12 % de masse en excès | rejet | analyse complémentaire requise |

Ces valeurs sont **arbitrées**, et elles le sont contre une mesure.

**Sous-bouclage, 6 % et 20 %.** Sur des lots entièrement décrits par le
modèle, le seul bruit analytique de 6 % produit une masse apparemment
inexpliquée de 1,8 % en médiane, 5,7 % au 95ᵉ centile et jusqu'à 10,3 % au
pire. Les premiers seuils envisagés (3 % et 8 %) étaient donc **sous le
plancher de bruit** : ils refusaient des lots sains. Le réglage retenu se
cale sur la réalité métallurgique des black masses (séparateur, solvants
d'électrolyte, liants aqueux, traces non dosées) plutôt que sur un
échantillon idéalement caractérisé.

**Sur-bouclage, 12 %.** Un lot peut légitimement porter de la masse que le
modèle n'explique pas. L'inverse n'a aucun équivalent physique : les phases
du modèle ne peuvent pas peser plus que le lot. Au-delà du bruit, un
sur-bouclage est une erreur et non une lacune, et il se rejette donc plus
tôt.

Mesure, sur 2 500 lots sains (bouclage exactement 1, seul le bruit
analytique de 6 %) répartis sur les cinq profils de composition :

| Centile du sur-bouclage observé | Écart |
|---|---|
| 95ᵉ | +5,55 pt |
| 99ᵉ | +7,35 pt |
| 99,9ᵉ | +9,44 pt |
| pire observé | +10,10 pt |

Le bruit seul atteint donc **+10 points**. Un seuil en dessous refuserait des
lots sains. C'est exactement l'erreur écartée plus haut pour le sous-bouclage.
12 % est le premier palier strictement au-dessus du plancher mesuré.

**Conséquence assumée.** Les deux lots réels qui ont révélé le défaut restent
en alerte : BM1 à +10,45 pt et BM2 à +7,63 pt ne sont pas séparables du bruit
par leur bouclage. Ce qui les attrape est ailleurs (la prédiction de fluor à
17,79 % contre 2,44 % sur matériau certifié, soit un facteur 7) et relève
des bandes de plausibilité de composition (§ 2.6 quinquies).

Il serait tentant d'abaisser le seuil pour « attraper » ces deux lots. Ce
serait troquer un diagnostic juste contre un diagnostic qui tombe au bon
endroit par hasard, au prix d'environ un faux rejet sur cent lots sains.

**Direction et message.** Le statut porte la sévérité, le sens porte la
direction, et les causes annoncées diffèrent. Jusqu'au 22 octobre 2026,
`check_closure` calculait `abs(total - 1)` et perdait le signe : un lot à
110,45 % s'entendait dire qu'une part de sa masse était inexpliquée, et
partait enquêter sur une humidité résiduelle qui n'existait pas.

### 2.6 quinquies. Bandes de plausibilité sur les compositions prédites

Le solveur attribue une teneur à des éléments que le bulletin **ne dose
pas** : c'est son travail. Rien ne vérifiait que ces teneurs prédites
restent dans l'ordre de grandeur d'un matériau réel.

Le 22 octobre 2026, sur un lot réel où ni le phosphore ni le fluor
n'étaient dosés, l'outil a prédit **17,79 % de fluor**, en retenant 14,3 %
de LiPF6 et 11,8 % de PVDF. Le matériau de référence certifié OREAS donne un
fluor à **2,44 %** : la prédiction valait sept fois la valeur d'un matériau
réel. Aucun signal n'a été émis, `is_exploitable` valait `True`, et le lot
serait parti en valorisation avec 110 % de masse, donc à un prix surestimé.

Le générateur synthétique ne pouvait pas révéler ce trou : il produit des
lots cohérents par construction, et `make_lot` refuse même un bouclage
supérieur à 1.

**Ce que le contrôle fait.** Pour chaque élément non dosé qui possède un
ancrage certifié, la teneur prédite est comparée à une borne haute, et un
dépassement nomme l'élément **et la phase porteuse responsable**, sans quoi
l'utilisateur saurait qu'un chiffre est faux sans savoir où agir.

| Élément | Ancrage certifié | Borne à facteur 3 | Statut |
|---|---|---|---|
| F | 2,44 % | 7,32 % | `validated=False` |

**Le phosphore n'est pas ancré, bien que le certificat le donne.** Une
première version en avait fait un ancrage à 0,350 %. Mesure du taux de faux
positifs, sur 1 200 lots que les profils du projet déclarent plausibles,
l'élément n'étant pas dosé :

| Élément | Faux positifs | Plafond des profils | Borne à facteur 3 |
|---|---|---|---|
| F | **0,0 %** | 5,17 %, soit 2,1× l'ancrage | 7,32 % |
| P | **45,8 %**, et 100 % sur les lots riches en LFP | 11,70 %, soit **33×** | 1,05 % |

La cause est chimique. LFP est LiFePO₄ : le phosphore y est un élément
**majeur**, pas une trace. Le matériau OREAS ne contient quasiment pas de
LFP, donc son phosphore n'est pas un ancrage, c'est un cas particulier, et
s'en servir revient à supposer qu'aucun lot ne contient de LFP.

Le phosphore ressort donc en **non contrôlé**, déclaré comme tel. L'ancrer
exigerait une teneur certifiée sur une black mass de chimie LFP.

Le fluor, lui, a de la marge des deux côtés : plafond plausible à 2,1× contre
une borne à 3×, et la prédiction fautive du lot réel à 7,3×.

**Ce que le contrôle ne fait pas.** Un élément **dosé** n'est jamais
contrôlé : sa valeur est une mesure, et la refuser reviendrait à contester
le laboratoire. C'est pourquoi le lot OREAS lui-même ne déclenche rien, son
fluor est dosé.

Aucune borne n'est inventée pour un élément sans ancrage. L'hydrogène,
l'oxygène et le phosphore sortent donc comme **non contrôlés**, et jamais
comme conformes : l'absence de contrôle est déclarée, elle n'est pas un
satisfecit.

**Ce que cette borne vaut.** Un point n'est pas une bande. Le seul
ancrage retenu vient d'un **seul certificat**, sur un **seul matériau**. Une
valeur ne décrit pas une population : elle dit seulement qu'un matériau réel
existe à ce niveau-là. Les bornes portent donc
`validated=False`, et le facteur qui les écarte est **exposé en paramètre**
(`--facteur-plausibilite` n'existe pas encore en ligne de commande ;
`Demande.facteur_plausibilite` l'expose au code appelant), comme les seuils
de bouclage, parce qu'un réglage non arbitré doit pouvoir se discuter.

**Où le facteur 3 tombe, et pourquoi là.** Le fluor d'une black mass ne vient
que de deux phases : **PVDF à 59,34 % de F** et **LiPF6 à 75,04 %**. Le
plafond chimique de n'importe quel scénario se calcule donc exactement. La
borne au facteur 3 vaut **7,32 %** de fluor.

| Scénario | PVDF | LiPF6 | F total | × ancrage | Verdict |
|---|---|---|---|---|---|
| Matériau certifié OREAS | — | — | 2,44 % | 1,00 | passe |
| Plafond des profils du générateur | 5 % | 2 % | 4,47 % | 1,83 | passe |
| Lot **mal séché**, électrolyte 5 % | 5 % | 5 % | 6,72 % | 2,75 | **passe de justesse** |
| Liant **doublé**, PVDF 10 % | 10 % | 2 % | 7,43 % | 3,05 | **signalé de justesse** |
| Séchage très défaillant, 8 % | 5 % | 8 % | 8,97 % | 3,68 | signalé |
| Prédiction fautive du lot réel | 12 % | 14 % | 17,73 % | 7,27 | signalé |

Le facteur 3 tombe **entre les deux cas limites**. Il tolère un lot dont
l'électrolyte a été mal retiré, et refuse un liant doublé ou un séchage très
défaillant. Ce n'est donc pas un chiffre arbitraire : c'est la frontière
entre ce qu'un procédé médiocre explique et ce qu'il n'explique plus.

**Pourquoi il reste néanmoins `validated=False`.** Le plafond de 4,47 %
dérive des bornes de composition du générateur, que le § 1.1 qualifie
lui-même d'**hypothèses métier, non sourcées et non statistiques**. Arbitrer
un seuil contre des hypothèses non sourcées serait le faire passer pour
mesuré alors qu'il est seulement cohérent. Le drapeau reste donc à `False`.

**Les deux questions qui l'arbitreraient.** Elles sont volontairement
fermées, pour qu'un géométallurgiste les tranche sans ouvrir un chantier :

1. Une black mass avec **5 % d'électrolyte résiduel** est-elle plausible ?
   Si oui, le facteur ne peut pas descendre sous **2,75**.
2. Une black mass avec **8 % d'électrolyte résiduel**, ou **10 % de liant**,
   est-elle implausible ? Si oui, le facteur ne peut pas dépasser **3,68**.

Deux oui enferment le facteur dans **[2,75 ; 3,68]**, et 3 s'y trouve. Le
drapeau passerait alors à `True`, arbitré contre une mesure comme les seuils
de bouclage du § 2.6 ter.

Mesure complémentaire déjà acquise : sur **1 200 lots** que les profils du
générateur déclarent plausibles, fluor non dosé, le taux de faux positifs au
facteur 3 est de **0,0 %**.

### 2.7 Origine de la dégénérescence

Le sous-système Li–Ni–Mn–Co–O est fermé : six phases (NMC 111, 532, 622,
811, LCO, LMO) y coexistent pour seulement quatre directions mesurables. Il
en résulte deux degrés de liberté non contraints par l'analyse élémentaire.

À titre d'illustration, 0,75 mole de NMC 111 additionnée de 1,00 mole de
NMC 811 est **rigoureusement indiscernable** de 1,75 mole de NMC 622. Aucun
gain de précision analytique ne lève cette ambiguïté.

---

## 2 bis. Valorisation

### Assise de la valeur

La valorisation ne s'appuie que sur des grandeurs fermes : les teneurs
élémentaires. Aucune ventilation par grade n'entre dans le calcul d'un prix.
Un lot dégénéré reste donc valorisable, avec la même fiabilité qu'un lot bien
posé.

### Convention retenue

Conformément à l'usage du marché, un payable s'exprime en pourcentage d'un
prix de référence publié, et non en valeur absolue :

| Élément | Référence usuelle |
|---|---|
| Nickel | LME Nickel cash official price |
| Cobalt | Cobalt standard grade, in-whs Rotterdam, point bas |
| Lithium | Carbonate de lithium qualité batterie, spot |

Le manganèse, le cuivre et l'aluminium ne sont pas payables : ce sont des
impuretés soumises à des teneurs maximales. Sur certains marchés, la valeur du
lithium est intégrée aux payables nickel et cobalt plutôt que payée
séparément ; le rapport le signale lorsque c'est le cas.

### Aucun prix ne vit dans le code

> **Le module de valorisation ne contient aucune valeur de prix.**

Le marché varie trop pour qu'un prix survive dans du code source : un littéral
part dans le dépôt, se livre avec le paquet, et se retrouve encore là trois ans
plus tard. Le carbonate de lithium a varié de plus de 100 % sur douze mois et le
cobalt de plus de 300 % en 2025.

Trois règles en découlent, chacune verrouillée par un test :

1. Les instantanés de prix vivent dans `data/`, au format JSON, chacun avec sa
   source, sa date et sa base de cotation. Un champ manquant est une erreur, pas
   une valeur par défaut.
2. La fonction de valorisation n'a **aucun jeu de prix par défaut**. L'appelant
   déclare explicitement d'où viennent ses chiffres.
3. Un jeu non déclaré comme source de production est refusé, et un instantané de
   plus de 7 jours (60 jours pour des conditions commerciales) interrompt le
   calcul.

Un flux de production se branche par `PriceProvider` : toute fonction rendant un
jeu de prix daté convient, qu'il s'agisse d'une API, d'un export quotidien ou
d'une saisie manuelle.

### Conversion de devises

> **Aucune source de taux de change n'est intégrée, et c'est une décision.**

Le taux est **fourni par l'utilisateur**, exactement comme ses prix : c'est le
taux de sa banque qui vaut pour sa transaction, et le logiciel n'a pas à en
inventer un. Le module de conversion ne contient donc ni appel réseau, ni taux
littéral, ni valeur de repli, le même raisonnement que pour les prix,
appliqué mot pour mot.

La conversion est un **acte explicite** de l'appelant. Un jeu de prix
multi-devises reste refusé tant que personne n'a demandé la conversion :
convertir d'office reviendrait à choisir à la place du négociant quel taux
engage sa transaction.

Six règles en découlent, chacune verrouillée par un test :

1. Un **taux sans source déclarée est refusé**, exactement comme un prix sans
   source. Un chiffre sans origine n'est opposable à personne.
2. Un **taux périmé est refusé**. Le seuil de fraîcheur est **non arbitré**,
   donc exposé à l'appelant, un négociant au comptant voudra un jour, un
   contrat mensuel s'accommode de trente.
3. Chaque prix converti **conserve son origine** : valeur et devise d'origine,
   taux appliqué, source du taux, date du taux.
4. Une **paire croisée exige deux taux** déclarés, et les deux figurent dans la
   provenance. Un taux croisé ne se déduit jamais d'un seul.
5. La **bande de plausibilité est re-vérifiée** après conversion, sur la valeur
   en dollars que la chaîne produit. Les bandes étant libellées en USD, c'est le
   seul endroit où elles signifient quelque chose : appliquées telles quelles à
   un prix converti en wons, elles rejetteraient une conversion juste d'un
   facteur 1 350. Mesure à l'appui, un taux EUR/USD saisi 108 au lieu de 1,08
   porte un nickel de 14 000 EUR/t à 1 512 000 USD/t au pivot, hors bande
   [5 000 ; 100 000] : refusé.
6. **Le rapport porte la mention.** Une valorisation convertie indique la devise
   d'origine, le taux appliqué, sa source et sa date, telles que déclarées par
   celui qui les a fournies. Sans cette mention, l'acheteur ne pourrait pas
   distinguer un prix bas d'un taux faux.

Quand la chaîne ne produit aucune valeur en dollars (une conversion GBP vers
EUR par taux direct), aucune vérification de plausibilité n'est possible, et la
provenance le **dit** plutôt que de laisser croire à un contrôle qui n'a pas eu
lieu.

### Connexion aux agences d'évaluation

KLASTOS21 se branche sur les flux réels de trois agences. Les spécifications
viennent de leur documentation publique, et le catalogue de symboles vit dans
`data/symboles_pra.json` : donnée, pas code.

| Agence | Accès | Couverture utile |
|---|---|---|
| **Fastmarkets** | Physical Prices API v2, clé de service, jeton porteur | cobalt standard grade Rotterdam, payables black mass par marché |
| **Benchmark** | Prices API v3, en-tête `x-api-key` | lithium, cobalt, nickel, et un marché `recycling` dédié |
| **SMM** | API de données, jeton | marché chinois, séries à renseigner |

**Trois précautions codées en dur.**

Les **identifiants** sont lus dans l'environnement, jamais passés en argument :
un argument reste dans l'historique du shell. Les variables attendues sont
`KLASTOS_FM_SERVICE_KEY`, `KLASTOS_FM_SERVICE_NAME`, `KLASTOS_BMI_API_KEY`,
`KLASTOS_SMM_USER` et `KLASTOS_SMM_PASSWORD_MD5`.

La **borne retenue** est déclarée symbole par symbole. Les payables de black
mass se réfèrent au **point bas** du cobalt standard grade, pas à la médiane :
retenir la médiane surestimerait un lot de 7 %. Le catalogue le spécifie, et un
test le verrouille.

Les **unités ne sont jamais devinées**. Un libellé d'unité inconnu provoque une
erreur plutôt qu'une hypothèse, et la bande de plausibilité rattrape toute
conversion aberrante.

### L'autorisation de rediffusion est portée, pas supposée

> **Un abonnement d'agence couvre l'usage interne. Rien de plus.**

Afficher un prix d'agence dans un rapport facturé à un tiers exige une
autorisation écrite distincte. Les conditions standard de Fastmarkets
l'interdisent explicitement à défaut : l'article 4.3(b) prohibe la distribution
du contenu à des tiers ou à leur bénéfice sans contrat propre ou accord écrit,
et l'article 4.3(c) interdit d'en tirer un service concurrent.

KLASTOS21 ne tranche pas cette question : chaque instantané de prix porte son
niveau d'autorisation déclaré. Sans le drapeau explicite
`--licence-rediffusion`, l'instantané est marqué **USAGE INTERNE** et la
commande le rappelle à l'écran. Déclarer une autorisation que l'on ne détient
pas engage l'utilisateur, pas le code.

**L'autorisation vit dans la donnée, pas dans un message.** Elle était
d'abord écrite dans le fichier d'instantané puis perdue à la relecture :
`PriceSet` ne la portait pas, et plus rien dans le système ne savait si des
prix pouvaient partir chez un client. Il n'en restait qu'un libellé, du texte
que personne ne vérifie. Le droit de rediffusion est désormais un champ du
jeu de prix, transporté jusqu'au rapport.

**Le refus porte sur la sortie du document, pas sur le calcul.** Calculer avec
des prix d'agence est licite ; les afficher à un tiers ne l'est pas sans
licence. Le rapport déclare donc son destinataire :

| Destinataire | Prix d'agence sans licence |
|---|---|
| `tiers` (défaut) | **rapport refusé** |
| `interne` | rapport émis |

Le défaut est le cas réel (un rapport se fabrique pour un client), et c'est
aussi le plus contraignant. Le système ne devine pas où va un document : il le
demande, exactement comme il demande une attestation de provenance au lieu de
supposer une origine. Un fichier de prix fourni par le client n'est pas
concerné : ce sont ses propres données, aucune licence d'agence ne s'y
applique.

### Approvisionnement en prix

Trois routes, une seule interface, empilées par ordre de préférence.

1. **Prix apportés par le client** (CSV, JSON, saisie datée). Route
   prioritaire : sans licence à rediffuser, et plus juste puisqu'elle reflète
   les conditions contractuelles réelles plutôt qu'un indice public.
2. **Sources publiques et dérivées** (flux différés, règlements de contrats à
   terme). Route de secours pour les métaux de bourse.
3. **Évaluation propre**, construite sur les transactions observées. Route de
   long terme.

KLASTOS21 n'extrait aucune donnée de site soumis à licence. Le droit *sui
generis* des bases de données protège les recueils d'évaluations, et une
valorisation fondée sur une source illicite n'est pas défendable devant un
client.

#### L'étage gratuit, et ce qu'il ne peut pas faire

Recherche du 24 octobre 2026. L'outil devait pouvoir chiffrer un lot **sans
attendre le fichier de prix du client**. Constat : **gratuit, quotidien et
redistribuable n'existe pas** pour le cobalt et le lithium. C'est une
propriété du marché, pas un manque d'outillage.

| Source | Couvre | Fréquence | Coût | Redistribuable |
|---|---|---|---|---|
| Pink Sheet, Banque mondiale | Al, Cu, Ni | mensuel | gratuit | **oui**, avec attribution |
| **USGS** Mineral Commodity Summaries | **Co, Li**, Ni, Cu, Al | annuel | gratuit | **oui**, CC0 1.0 |
| Règlements CME | Co Rotterdam, Li CIF CJK | quotidien | gratuit à consulter | **non** |
| Fastmarkets, Benchmark, SMM | tout, plus les payables | quotidien | payant | oui, sous licence |

**L'USGS est la source retenue.** Œuvre du gouvernement fédéral américain,
donc domaine public : cinq métaux dans un CSV lisible par machine, DOI
10.5066/P1WKQ63T, téléchargé par `klastos usgs --rafraichir`. C'est le
premier flux du projet qui cote le cobalt et le lithium sans abonnement.

Ironie à déclarer : les prix de l'USGS sont eux-mêmes repris d'agences,
S&P Global Platts pour le cobalt et l'aluminium, Benchmark Mineral
Intelligence pour le lithium. L'USGS en publie la moyenne annuelle dans le
domaine public. On obtient donc légalement la référence d'agence, **au prix
de sa fraîcheur**.

**Ce que cet étage ne peut pas faire, mesuré.** Moyenne annuelle USGS 2025
du carbonate de lithium : 9 000 USD/t. Cotation Benchmark CIF Asie du
2 septembre 2026 : 19 750 USD/t. **Un facteur 2,2**, trois causes cumulées —
l'année, la base géographique, et un marché qui a pris plus de 100 % début
2026. Le même fichier montre le lithium à 63 700 USD/t en 2022 contre 9 000
en 2025, soit **un facteur 7 en trois ans**.

En conséquence `UsgsProvider.is_production_source` vaut `False`, et une
valorisation **opposable est refusée** sur ces prix. Le refus est le
comportement voulu : l'étage gratuit sert au **criblage** d'un lot, jamais au
contrat. Le mode démonstration donne la valeur indicative, et le document
porte la mention.

**Le cobalt mensuel, et pourquoi il s'arrête.** La moyenne annuelle
sous-estime le cobalt de **67 %** face à janvier 2026 (15,00 contre
25,05 USD/lb, série LME cash). Le prix mensuel est donc lu quand il existe,
par `klastos usgs --mois`. Mais il ne vit dans aucune table : il est dans un
document Word embarqué dans le classeur, et **l'USGS a cessé de l'embarquer
en février 2026**. Le dernier mois lisible par machine est janvier 2026 ;
au-delà, seul le PDF le porte, et extraire un prix d'une prose serait la
devinette que ce protocole interdit. Le lecteur échoue alors bruyamment et
renvoie vers la moyenne annuelle.

**Deux séries présentes et volontairement écartées.** Le manganèse est coté
en dollars par tonne-unité de minerai (dmtu), pas par tonne de métal :
4,50 USD en 2025, que la bande de plausibilité refuserait d'ailleurs.
Convertir exigerait la teneur du minerai, que l'USGS ne donne pas. Le
graphite naturel est coté en trois qualités de 470 à 2 600 USD/t, et aucune
bande de plausibilité n'existe pour le carbone. Les deux sont déclarés avec
leur raison dans `USGS_ECARTEES`, jamais devinés.

**Une correction de fait.** Le message d'orientation du Pink Sheet affirmait
que le cobalt et le lithium étaient « des marchés de gré à gré, sans
cotation de bourse ». C'était vrai à l'écriture et ne l'est plus : le CME,
le LME et le GFEX listent des contrats sur ces deux métaux depuis 2023. Le
texte corrigé renvoie vers les trois voies, avec leur licence.

### L'unité de cotation n'est jamais devinée

> **Une cotation sans unité déclarée est refusée.**

Certaines interfaces cotent les métaux par once troy : la conversion en tonne
exige un facteur 32 150. Une omission silencieuse fausserait une valorisation
d'un facteur trente mille sans aucun signe extérieur.

Deux protections cumulatives :

1. L'unité est obligatoire à la configuration ou à la lecture. Elle n'est
   jamais déduite du nom du métal ni de l'ordre de grandeur.
2. Une **bande de plausibilité** par métal rejette tout prix converti
   aberrant. Ces bandes sont volontairement très larges : ce sont des filets
   anti-erreur, jamais une opinion de marché, et elles ne bornent aucune
   valorisation.

### Continuité de service

Une panne de source n'interrompt pas un rapport en cours. Les fournisseurs
s'empilent avec repli automatique, et un cache disque prend le relais. Le
contenu servi depuis le cache conserve sa date d'origine : les verrous
d'ancienneté s'y appliquent normalement, et sa provenance est signalée.

L'instantané livré avec le code est marqué comme non destiné à la production. Le
mode démonstration lève les verrous mais marque le résultat comme non opposable.

### Résultat

La valeur et le prix maximal à payer sont rapportés en **fourchette**, jamais
en chiffre unique. La largeur de cette fourchette reflète l'incertitude
analytique sur les teneurs fermes.

---

## 3. Provenance déclarée

### 3.1 Principe

La provenance déclarée par le client est une information qui réduit la
dégénérescence du système et améliore l'identifiabilité.

| Provenance déclarée | Phases exclues | Degrés de liberté restants |
|---|---|---|
| Non déclarée | aucune | 2 |
| Véhicule électrique | LCO, LMO | 1 |
| Stationnaire | LCO, LMO | 1 |
| Chutes de production | grades non déclarés | 0 |

### 3.2 Règle non négociable

> **Aucune phase n'est exclue sans attestation écrite du client.**

Une déclaration de provenance non attestée laisse la liste de phases
complète et la dégénérescence assumée. Cette règle est verrouillée par le
test `test_sans_attestation_aucune_exclusion` et ne doit jamais être
assouplie.

Le texte exact de l'attestation figure dans le journal de traçabilité joint
à chaque rapport.

### 3.3 Responsabilité

Une attestation inexacte fausse le résultat de manière quantifiable. À titre
d'exemple mesuré, un lot déclaré « véhicule électrique » contenant en
réalité 7,4 % de LCO voit sa teneur en cobalt sous-estimée de 44 %.

**Détection.** Le signal n'est pas le bouclage massique. Le bulletin d'un
lot mal déclaré boucle normalement, puisqu'il décrit une réalité physique
cohérente. Le signal est le **résidu d'ajustement** : le solveur ne parvient
plus à expliquer le bulletin avec la liste de phases restreinte.

Pouvoir de détection mesuré sur données synthétiques, avec un bruit
analytique de 3 % relatif et un seuil placé au 95ᵉ centile des lots
conformes :

| Contamination réelle | Taux de détection |
|---|---|
| 1 à 2 % | non détectable, confondu avec le bruit |
| 5 % | environ 50 % des lots |
| 8 % | environ 98 % des lots |

**Ce que KLASTOS21 s'interdit d'affirmer.** L'outil ne détecte pas une
attestation inexacte en dessous d'environ 5 % de phase non déclarée. Une
absence d'alerte ne vaut donc pas certification de la déclaration. Le
contrôle du résidu est un filet, pas une garantie.

---

## 4. Limites méthodologiques déclarées

### 4.1 Carbone

> *La séparation graphite / noir de carbone nécessite des données texturales
> ou structurales, non prises en compte dans cette première version.*

Le carbone est rapporté sous forme agrégée « carbone total ».

### 4.2 Grades de cathode

La ventilation fine par grade NMC n'est pas accessible par analyse
élémentaire. Elle nécessite soit une donnée structurale (DRX, éventuellement
Raman), soit une traçabilité de procédé, soit une déclaration de provenance
attestée.

### 4.3 Dette technique ouverte

| Élément | Statut | Résolution prévue |
|---|---|---|
| Profils de composition (4) | `validated=False` | v1.1, sur lots réels |
| Modèle de bruit, erreur relative **non sourcée** | **soldée** | 6 %, calibré sur LNE-LiB01 |
| Modèle de bruit, **contradiction entre les deux certificats** | ouverte | § 1.3 ter, analyse en double sur lot réel |
| Modèle de bruit, bruit de fond et limite de détection | `validated=False` | premier lot client |
| **Bandes de plausibilité, facteur appliqué à l'ancrage** | `validated=False` | § 2.6 quinquies, deux questions fermées |
| Profil de provenance `deee` | `validated=False` | arbitrage métier en attente |

Deux lignes de ce tableau ont changé le 25 octobre 2026, et la nuance
importe. La dette d'origine sur l'erreur relative — **elle n'était pas
sourcée** — est bien soldée : `rel_sigma` vaut 6 %, calibré sur LNE-LiB01.
Mais une dette **nouvelle** s'est ouverte en confrontant ce certificat à
celui d'OREAS : les deux se contredisent d'un ordre de grandeur sur le
nickel. Solder la première ne solde pas la seconde, et le tableau aurait
menti en ne portant que la première.

---

## 4 bis. Architecture

La chaîne de dépendances est linéaire et vérifiée par un test :

```
units  →  market  →  providers
                  →  valuation
```

`market.py` ne contient que des structures et des chargeurs : aucune logique de
valorisation, aucune valeur de prix. Un fournisseur de prix ne dépend pas du
calcul de valorisation, et réciproquement.

Cette séparation n'est pas cosmétique : elle permet d'exploiter et de
commercialiser le service d'approvisionnement en prix indépendamment du service
de valorisation.

---

## 5. Principes de développement

1. **Aucune valeur chimique ou économique numérique n'entre dans le code
   sans référence vérifiable.** À défaut, elle est marquée `A VALIDER` et
   soumise à arbitrage.
2. **L'identifiabilité est calculée, jamais supposée.** Ajouter une phase
   qui casserait le caractère ferme d'un agrégat est détecté automatiquement.
3. **Les hypothèses métier sont des données, pas du code.** Les corriger ne
   demande aucune modification de logique.
4. **Tout invariant qui protège le client est verrouillé par un test.** Ces
   tests ne sont jamais assouplis pour faire passer autre chose.

---

*Document versionné avec le code. Toute modification d'un engagement de ce
protocole doit s'accompagner de la mise à jour des tests correspondants.*