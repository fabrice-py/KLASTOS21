# KLASTOS21

Analyse predictive des matieres premieres secondaires.
v0 : black mass lithium-ion.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## Tests

```bash
pytest -q
```

## Decisions structurantes (v0)

| # | Decision | Statut |
|---|----------|--------|
| 1 | Les 4 grades NMC sont conserves separement | validee |
| 2 | Graphite et noir de carbone fusionnes en "carbone total" | validee |
| 3 | Grandeurs fermes du rapport : "NMC + LCO" sur provenance attestee. "Cathodes totales" seulement si l'oxygene est dose | corrigee, mesuree |
| 4 | Ventilation par grade affichee comme domaine compatible, marquee non identifiable | validee |
| 5 | Restriction de phases par provenance declaree | validee |
| 6 | Aucune exclusion de phase sans attestation ecrite du client | validee, verrouillee par test |

## Dette technique connue

- Profil de provenance `deee` : liste d'exclusion non arbitree metier (`validated=False`).
- Parametres de bruit du generateur synthetique : ordres de grandeur non sources.
- Perimetre du scenario de dosage (`SCENARIO_ELEMENTS`) : l'oxygene seul.
  L'hydrogene est ecarte sur un argument physique, pas sur une mesure
  (`SCENARIO_ELEMENTS_VALIDATED = False`).
- Taux de conflit DRX / bulletin : sur le lot d'exemple, un tiers des
  tirages de bruit analytique sont incompatibles avec la quantification,
  parce que la non-negativite y epingle la phase a zero. Les tirages sont
  conserves avec leurs bornes non contraintes, et le taux est rapporte,
  mais le seuil d'alerte de 20 % (`DRX_CONFLIT_ALERTE`) n'est PAS arbitre
  sur lots reels.

## Etat des seances

| Seance | Module | Tests |
|--------|--------|-------|
| 1 | `elements.py`, `phases.py` | 12 |
| 2 | `provenance.py` | 10 |
| 3 | `identifiability.py` | 46 |
| 4 | `generator.py` | 45 |
| 4b | `PROTOCOLE.md` (tests d'engagement) | 19 |
| 5 | `solver.py` | 30 |
| 6 | `uncertainty.py` | 18 |
| 7 | `market.py`, `valuation.py` | 39 |
| 8 | `units.py`, `providers.py` | 47 |
| 9 | `report.py` | 29 |
| 10 | `ingestion.py` | 76 |
| 11 | `cli.py` | 41 |
| 12 | `feeds.py` | 47 |
| 13 | seuils arbitres | 3 |
| 13 | `render_html.py` | 26 |
| 14 | scenario de dosage (`identifiability.py`, `test_scenario.py`) | 37 |
| 15 | `service.py` (chemin unique) | 26 |
| 15 | `store.py` (historique SQLite) | 28 |
| 15 | `app.py` (interface Streamlit) | 35 |
| 16 | `theme.py`, `charts.py` (tableau de bord) | 18 |
| 17 | `structural.py` (ingestion DRX) | 46 |
| 17 | integration DRX, conseil de quantification | 30 |
| 17 | `app.py` (onglet DRX actif) | 4 |
| | **total** | **783** |

## Connexion aux agences de prix

```powershell
# une seule fois, dans votre profil PowerShell
$env:KLASTOS_FM_SERVICE_KEY  = "..."
$env:KLASTOS_FM_SERVICE_NAME = "..."
$env:KLASTOS_BMI_API_KEY     = "..."

# ce que votre abonnement autorise reellement
klastos prix --source fastmarkets --catalogue

# instantane du jour, plus les payables EXW Europe
klastos prix --source fastmarkets --marche exw_europe --sortie data/prix_du_jour.json

# puis le rapport
klastos rapport bulletin.csv --prix data/prix_du_jour.json --payables data/prix_du_jour_payables.json --marche exw_europe
```

Les identifiants ne sont **jamais** passes en argument : l'historique du shell
les conserverait. Sans `--licence-rediffusion`, l'instantane est marque USAGE
INTERNE : un abonnement d'agence n'autorise pas d'afficher ses prix dans un
rapport facture a un tiers.

## Utilisation en ligne de commande

```powershell
klastos diag bulletin.csv
klastos rapport bulletin.csv --provenance vehicule_electrique --atteste --prix mes_prix.csv --sortie rapport.md
```

Sans l'option `--prix`, aucune valorisation : il n'existe aucun jeu de prix par
defaut. Les seuils de bouclage sont exposes par `--seuil-alerte` et
`--seuil-rejet` parce qu'ils ne sont pas arbitres.

### Le document que vous envoyez au client

```powershell
klastos rapport bulletin.csv --provenance vehicule_electrique --atteste --prix mes_prix.csv --sortie rapport.html
```

L'extension `.html` suffit : le rapport sort alors en document autonome, a
ouvrir dans un navigateur et a imprimer en PDF par `Ctrl+P`. Aucune dependance
supplementaire, aucun serveur.

Ce rendu porte des **barres d'intervalle**, et c'est leur seule raison d'etre :
un tableau de chiffres ne fait pas voir qu'une grandeur ferme est un trait fin
et qu'un domaine compatible est une bande large. C'est la distinction que
KLASTOS21 vend, et elle doit se voir avant de se lire.

`--format markdown` ou `--format html` force le rendu quelle que soit
l'extension. Le Markdown reste le defaut a l'ecran.

`python -m klastos` fonctionne aussi, sans reinstaller le paquet.

## Quantification par diffraction

```powershell
klastos rapport bulletin.csv --provenance vehicule_electrique --atteste `
        --drx quantification.csv --base absolue
```

Format attendu, une phase par ligne. **La colonne d'incertitude est
obligatoire** : sans elle, une mesure precise a 1 ou 3 points passerait pour
exacte, et le logiciel sortirait des phases fermes que le client n'a pas
mesurees.

```csv
Phase,Valeur (%),Incertitude (%)
NMC 811,18.00,3.00
LFP,12.40,1.50
```

Les intitules sont tolerants (`Phase`/`Mineral`, `Valeur`/`Teneur`,
`Incertitude`/`Sigma`/`ESD`) et la phase se reconnait a sa cle, son libelle
ou sa formule : `NMC 622`, `nmc-622` et `LiNi0.6Mn0.2Co0.2O2` tombent sur la
meme colonne.

`--base` declare la normalisation du laboratoire, et la confondre coute
plusieurs points :

- `absolue` : fraction de la masse totale. Exige un standard interne ou une
  mesure de l'amorphe. La contrainte porte sur le **niveau** de la phase.
- `cristalline` : fraction du seul cristallin, renormalisee a 100 %. La
  fraction cristalline du lot etant inconnue, le niveau n'est **pas**
  contraint ; seuls les **rapports** entre phases le sont, et il faut donc
  une phase de plus.

Une somme superieure a 100 % en base absolue est refusee, avec le diagnostic
probable : le laboratoire a rendu des pourcentages cristallins renormalises.

### Quelle phase faire quantifier

```powershell
klastos rapport bulletin.csv --provenance vehicule_electrique --atteste --conseil-drx
```

Une quantification se paie, et toutes les phases ne la valent pas. Mesure
sur le lot d'exemple en VE attestee, a deux points d'incertitude : le NMC622
retire 43 % de la largeur cumulee, le fer metallique **rien**. Cinq phases
sur douze n'achetent aucun resserrement.

Les gains annonces sont des **planchers** : le placement de la valeur mesuree
est balaye dans la plage compatible et le pire cas est retenu, parce que
cette valeur est inconnue avant la mesure. Se poser au milieu donnerait un
gain flatteur, et flatteur dans le sens ou le client paie : sur la provenance
non declaree, le milieu annoncait 49 % pour le NCA la ou le pire cas en
donne 31 %, et changeait le classement.

Le calcul prend quelques secondes, il est donc hors du chemin par defaut.

### Le conflit entre les deux mesures

Un bulletin bruite peut etre incompatible avec la quantification : sur
certains tirages, la non-negativite des autres phases epingle la phase
quantifiee a zero. Ces tirages sont **conserves**, avec leurs bornes non
contraintes, donc plus larges. Les ecarter aurait resserre l'incertitude du
LABORATOIRE au motif d'une mesure qui ne porte pas sur elle - une premiere
version en supprimait 42 sur 60. Le taux est rapporte dans le rapport et
dans l'interface, et un taux eleve signale une analyse, une quantification
ou un modele de phases a reprendre.

## Interface

```powershell
pip install streamlit      # une seule fois, ce n'est pas une dependance du coeur
klastos ui
```

Depot d'un bulletin, prix du jour, rapport telechargeable en HTML, historique
des lots. L'interface ne calcule rien : elle appelle la meme chaine que la
ligne de commande. Un test l'empeche d'en reconstruire une seconde.

Deux cases a cocher y engagent l'utilisateur, jamais le code : l'attestation
de provenance, sans laquelle aucune phase n'est exclue, et la licence de
rediffusion des prix d'agence, sans laquelle un rapport destine a un tiers
est refuse.

### Ce que les graphiques montrent

Le camembert porte la composition ELEMENTAIRE - qui est ferme - plus
l'oxygene predit et la masse non expliquee. Jamais les phases a valeur
unique : deux assemblages differant de 2,86 points sur le PVDF produisent le
meme bulletin a 3e-15 point pres. Il bascule automatiquement sur les phases
le jour ou toutes deviennent fermes.

Ce jour-la n'arrivera PAS par une quantification par diffraction, et la
seance 17 l'a mesure. Une mesure Rietveld porte 1 a 3 points d'incertitude,
elle entre donc en encadrement, et une inegalite BORNE une direction nulle
sans la supprimer : la degenerescence est inchangee, les plages se
resserrent. Mesure sur un lot VE atteste, une phase quantifiee a +/- 2
points retire 72 % de la largeur cumulee, et rien ne devient ferme. Seule
une mesure d'incertitude nulle, qui n'existe pas, fermerait les phases.

`charts.py` n'importe pas Streamlit : les graphiques servent aussi hors
interface. `theme.py` ne contient que du style, et un test interdit qu'un
chiffre metier s'y glisse.

## Architecture

```
units  ->  market  ->  providers
                   ->  valuation

ingestion  ->  solver  ->  uncertainty  ->  report  ->  render_html
                                   \
                                    service  <-  cli.py
                                       |     <-  app.py
                                     store
```

`market.py` : structures et chargeurs, aucune logique, aucun prix.
`providers.py` : approvisionnement, trois routes, une interface.
`valuation.py` : prix maximal a payer, consomme des prix sans en produire.
`report.py` : assemblage du livrable client, et verrous de sortie.
`service.py` : LE CHEMIN UNIQUE d'une analyse. `cli.py` et `app.py` n'en sont
que des adaptateurs, et un test leur interdit de refaire la chaine.
`store.py` : historique local SQLite. Il reste sur la machine.
`render_html.py` : mise en forme seule. Il ne calcule rien et ne decide rien,
il consomme un `LotReport` deja assemble. Les deux rendus, Markdown et HTML,
partent du meme objet : ils ne peuvent pas dire deux choses differentes.

La linearite de cette chaine est verifiee par un test.

## Prix : aucune valeur dans le code

`klastos/pricing.py` ne contient aucun prix. Les instantanes vivent dans `data/`
au format JSON, avec source, date et base de cotation. `value_lot()` n'a aucun
jeu de prix par defaut : l'appelant declare sa source. Un flux de production se
branche par `PriceProvider`.

## Historique des prix et des taux

`store.py` est en **schema 2**. Aux tables `meta` et `lots` s'ajoutent
`cotations` et `taux` : chaque ligne porte sa source, sa **date de cotation**
et sa **date de collecte**, avec une contrainte d'unicite sur
`(source, reference, date de cotation)`.

Les deux dates ne se confondent pas : une moyenne mensuelle d'octobre relevee
le 15 novembre est cotee au 1er octobre et collectee le 15 novembre. Les
confondre ferait passer un releve tardif pour une donnee fraiche.

```python
from klastos import store

cx = store.ouvrir("data/historique.sqlite")
store.enregistrer_cotations(cx, jeu_de_prix, collecte_le=date.today())
store.enregistrer_taux(cx, mes_taux)

# le prix d'un metal a une date
store.prix_a_la_date(cx, "Ni", "2026-10-15")        # -> Cotation | None
# la serie sur une periode, bornes incluses
store.serie_prix(cx, "Ni", "2026-08-01", "2026-10-31")
store.serie_taux(cx, "EUR/USD", "2026-08-01", "2026-10-31")
```

`prix_a_la_date` rend la cotation la plus recente **a cette date ou avant** :
« que valait le nickel le 15 octobre » doit avoir une reponse meme quand la
source ne cote qu'une fois par mois.

### Trois regles

| Regle | Comportement |
|---|---|
| **Migration sans perte** | Une base v1 s'ouvre, se complete et passe en 2. Aucune ligne existante n'est touchee : un historique de lots est une donnee commerciale, sur un fichier que personne ne sauvegarde. `ouvrir` continue de **refuser** une base plus recente que le code. |
| **`refaire` ne restitue ni prix, ni taux** | Ce n'est pas un oubli. Des prix d'il y a six mois rejoues aujourd'hui donneraient une valorisation fausse, et la parite euro-dollar a varie de 0,95 a 1,17 sur vingt-quatre mois. `devise_cible` et `taux` restent a `None` : l'appelant fournit les prix **et** les taux du jour. La reconstitution, elle, ne depend d'aucun prix. |
| **Aucune valeur monetaire en flottant** | Les montants et les taux sont ranges en **TEXT decimal exact** et relus en `Decimal`. Un REAL SQLite est un double IEEE 754 : 15432.10 n'y est pas representable, et une relecture peut rendre 15432.099999999999, et l'ecart se voit des qu'on multiplie par une masse. |

Un meme `(source, reference, date)` portant **deux metaux differents leve**, au
lieu d'en perdre un en silence. En pratique un libelle de reference est propre
a un metal (« LME Nickel cash »), mais rien ne l'impose a un fournisseur, et
une cotation manquante dans une serie serait invisible.

## Pink Sheet : demontrable sans abonnement

Le classeur mensuel de la Banque mondiale est la **premiere** des deux
sources de prix gratuites et rediffusables du projet. La seconde est l'USGS,
decrite plus bas, et c'est elle qui apporte le cobalt et le lithium.

```powershell
# telecharge le classeur, puis affiche les trois metaux
klastos pink-sheet --rafraichir

# ensuite, lecture locale seule
klastos pink-sheet
```

**Le fournisseur lit un fichier LOCAL**, et c'est une decision : l'URL du
classeur porte un identifiant de document qui a **deja change entre les
editions 2025 et 2026**. Telecharger a chaque analyse ferait dependre une
valorisation d'un lien susceptible de mourir sans preavis. L'URL est donc
configurable (`--url`) et l'echec est **bruyant** : fichier absent, onglet
renomme, serie renommee ou unite inattendue produisent une erreur nommee,
jamais un zero.

### Deux limites a ne jamais oublier

| | |
|---|---|
| **Trois metaux, et trois seulement** | Aluminium, cuivre, nickel. Verifie sur l'edition d'octobre 2026. |
| **Le cobalt et le lithium n'y sont pas** | Ni le manganese, ni le graphite. Les demander leve `MissingPriceError` **avec l'adresse ou les trouver**, jamais un zero, qui traverserait toute la chaine sans qu'aucun controle le refuse. Pour le cobalt et le lithium, l'adresse est desormais `klastos usgs`. |
| **Moyennes mensuelles, pas du spot** | `is_production_source = False`. Le mois retenu figure dans la reference, dans la note et dans le libelle du jeu : une moyenne d'octobre ne s'oppose pas a une cargaison du 21 octobre. |
| **Rediffusable** | `redistribution_licensed = True`, l'un des deux flux du projet dans ce cas, avec l'USGS. Un abonnement d'agence couvre l'usage interne, pas l'affichage dans un document remis a un tiers ; une donnee publique, si. Contrepartie : l'attribution « Banque mondiale, Commodity Price Data (Pink Sheet) » est portee dans la provenance et dans le rapport. |

C'est cette derniere ligne qui fait la difference pratique : la ou un prix
d'agence fait **refuser** un rapport destine a un tiers, le Pink Sheet le
laisse passer.

## USGS : le cobalt et le lithium sans abonnement

Le trou que l'outil portait depuis le debut : sans le fichier de prix du
client, il ne pouvait pas chiffrer un lot, parce que les deux metaux qui
font l'essentiel de la valeur d'une black mass n'etaient dans aucune source
gratuite.

L'USGS les publie tous les deux. Son travail est une **oeuvre du
gouvernement federal americain**, donc domaine public, CC0 1.0 : aucune
contrepartie, pas meme une attribution juridiquement exigible.

```powershell
# telecharge le CSV (3,2 Mo), puis affiche les cinq metaux
klastos usgs --rafraichir

# ensuite, lecture locale seule
klastos usgs

# une annee anterieure, pour relire une decision passee
klastos usgs --annee 2022
```

| Metal | Serie retenue | 2025 | Converti |
|---|---|---|---|
| Co | LME cash | 15,00 USD/lb | 33 069 USD/t |
| Li | carbonate qualite batterie | 9 000 USD/t | 9 000 USD/t |
| Ni | LME cash | 15 000 USD/t | 15 000 USD/t |
| Cu | LME grade A cash | 440 cents/lb | 9 700 USD/t |
| Al | lingot marche americain | 180 cents/lb | 3 968 USD/t |

Le lien du CSV porte un condensat qui change a chaque republication : le
fournisseur **interroge l'API de l'item** pour l'obtenir, au lieu de coder
une adresse qui mourra. C'est l'erreur deja faite avec l'URL du Pink Sheet.

### Trois pieges, tous verifies par test

| | |
|---|---|
| **Le fichier n'est pas en UTF-8** | Il porte des octets cp1252, dont un cadratin a l'octet 170. Le lire en UTF-8 leve `UnicodeDecodeError` des la premiere ligne. L'extrait de test reproduit le piege, sinon le test passerait sur une fixture plus propre que la realite. |
| **Le cuivre et l'aluminium sont en CENTS par livre** | D'ou `PriceUnit.PER_POUND_CENT`. Les confondre avec des dollars par livre fausse d'un facteur **cent**, et dans le sens qui echappe a la bande de plausibilite : 4,40 USD/lb donne 9 700 USD/t, parfaitement dans la bande. |
| **Le lithium est cote en CARBONATE** | `basis="Li2CO3"`, et `valuation.py` ramene au lithium contenu. Sans cette base, 9 000 USD/t de carbonate se liraient comme 9 000 USD/t de lithium metal : un facteur 5,3 par omission. |

### Ce que cet etage ne peut pas faire

Ce sont des **moyennes annuelles**. `is_production_source = False`, et une
valorisation **opposable est refusee** sur ces prix.

Mesure de l'ecart : la moyenne 2025 du carbonate de lithium vaut
**9 000 USD/t**, quand la cotation Benchmark CIF Asie du 2 septembre 2026
vaut **19 750 USD/t**. Un facteur 2,2. Le meme fichier donne 63 700 USD/t en
2022, soit **un facteur 7 en trois ans**.

L'etage gratuit sert donc au **criblage** d'un lot, jamais au contrat. Le
mode demonstration donne la valeur indicative, et le document porte la
mention.

Ironie a declarer : les prix de l'USGS sont eux-memes repris d'agences,
S&P Global Platts pour le cobalt, Benchmark pour le lithium. L'USGS en
publie la moyenne annuelle dans le domaine public. On obtient donc
legalement la reference d'agence, **au prix de sa fraicheur**.

### Le cobalt au mois, et son plafond

La moyenne annuelle sous-estime lourdement le cobalt recent. Serie LME cash :

| Source | Cobalt | Ecart |
|---|---|---|
| moyenne annuelle 2025 | 15,00 USD/lb | reference |
| decembre 2025 | 23,31 USD/lb | +55 % |
| **janvier 2026** | **25,05 USD/lb** | **+67 %** |

```powershell
klastos usgs --mois 202601 --rafraichir
```

**Le plafond est deja atteint, et il faut le savoir.** Le prix ne vit dans
aucune table : il est dans un document Word EMBARQUE dans le classeur, et la
lecture traverse cinq couches - xlsx, zip, docx, zip, XML. A partir de
**fevrier 2026**, l'USGS a cesse d'embarquer ce document : les classeurs
recents annoncent « includes 5 tables » au lieu de « includes an embedded
Word document and 5 tables », et aucune de ces tables ne porte de prix.

Le dernier mois lisible par machine est donc **janvier 2026**. Au-dela, seul
le PDF porte le prix, et l'extraire d'une prose serait la devinette que ce
projet refuse. Le lecteur echoue alors **bruyamment**, nomme la cause, et
renvoie vers la moyenne annuelle.

La periode est **lue dans le document**, jamais deduite du nom de fichier :
un fichier renomme ne doit pas pouvoir dater une cotation de travers. Un
test le verifie en renommant la fixture en « mis-209912 ».

### Deux series ecartees, avec leur raison

Le **manganese** est cote en dollars par tonne-unite de minerai (dmtu), pas
par tonne de metal : 4,50 USD en 2025. Convertir exigerait la teneur du
minerai, que l'USGS ne donne pas, et la bande de plausibilite refuserait la
valeur brute. Le **graphite** est cote en trois qualites de 470 a
2 600 USD/t, et `units.py` n'a aucune bande pour le carbone. Les deux sont
declares dans `USGS_ECARTEES` avec leur motif, jamais devines.

## Conversion de devises

`PriceSet.check_currency()` **refuse** un jeu multi-devises, et continue de le
faire : convertir sans qu'on l'ait demande reviendrait a decider a la place du
negociant quel taux engage sa transaction. La conversion est donc un **acte
explicite** de l'appelant.

**Aucune source de taux n'est integree, et c'est une decision.** Le taux est
fourni par l'utilisateur, exactement comme ses prix : c'est le taux de sa
banque qui vaut pour sa transaction. Il n'y a dans `klastos/fx.py` ni appel
reseau, ni taux litteral, ni valeur de repli, pas plus que `market.py` ne
contient de prix.

```powershell
klastos rapport bulletin.csv --provenance vehicule_electrique --atteste `
  --prix mes_prix.csv --payables data/payable_terms.json `
  --devise EUR --taux data/taux_exemple.json
```

### Format du fichier de taux

Deux formats, reconnus a l'extension. Chaque taux porte sa valeur, sa date, sa
source et son libelle de reference : **un champ manquant est une erreur**,
jamais une valeur par defaut.

Convention de paire : `BASE/COTATION`, et le taux donne le nombre d'unites de
COTATION pour **une** unite de BASE. `EUR/USD` a 1,0842 signifie 1 EUR =
1,0842 USD.

**JSON** : `as_of` et `source` peuvent etre declares une fois pour le fichier,
et surcharges taux par taux. Exemple complet : `data/taux_exemple.json`.

```json
{
  "as_of": "2026-10-20",
  "source": "Releve bancaire du client",
  "rates": {
    "EUR/USD": {"rate": 1.0842, "reference_name": "spot EUR/USD, fixing 16h00 CET"}
  }
}
```

**CSV** : en-tetes tolerants : `paire`/`pair`, `taux`/`rate`/`cours`,
`date`/`as_of`, `source`/`banque`, `reference`/`libelle`. Exemple :
`data/taux_exemple.csv`.

```csv
paire,taux,date,source,reference
EUR/USD,1.0842,2026-10-20,Releve bancaire du client,spot EUR/USD fixing 16h00 CET
```

### Ce que la conversion garantit

| Regle | Comportement |
|---|---|
| Taux sans source | **Refuse.** Meme exigence que pour un prix. |
| Taux perime | **Refuse.** Seuil `--taux-age-max`, expose car **non arbitre**. |
| Origine conservee | Valeur et devise d'origine, taux applique, sa source et sa date, portes jusqu'au rapport. |
| Paire croisee | Exige **deux** taux declares, tous deux cites. Un taux croise ne se deduit jamais d'un seul. |
| Bande de plausibilite | Re-verifiee **sur la valeur en USD** que la chaine produit. |

Le dernier point meritait une mesure. Les bandes de `units.py` sont libellees
en USD : les appliquer telles quelles a un prix converti en wons rejetterait
une conversion juste d'un facteur 1 350. La conversion passe donc par un pivot,
et la bande est verifiee sur la valeur en dollars, le seul endroit ou elle
signifie quelque chose. Resultat mesure :

- un taux EUR/USD saisi **108** au lieu de 1,08 porte un nickel de 14 000 EUR/t
  a **1 512 000 USD/t** au pivot, hors bande [5 000 ; 100 000] : **refuse** ;
- un `USD -> KRW` correct a 1 350 donne 20 412 000 KRW/t : **aucun faux rejet**.

Quand la chaine ne produit aucune valeur en USD (un `GBP -> EUR` par taux
direct), aucune verification n'est possible, et la provenance le **dit** plutot
que de laisser croire a un controle qui n'a pas eu lieu.

## Statut du generateur

`klastos/generator.py` est un **outil de test interne**, pas un oracle du reel.
Ses bornes de composition sont des hypotheses metier non sourcees. Tout lot
produit porte `meta["data_class"] == "synthetique"` et ne peut atteindre un
livrable client : `assert_client_grade()` leve une exception.

**Engagement : la v1.1 integrera les statistiques de composition observees sur
lots reels, en remplacement des bornes actuelles.**

Voir `PROTOCOLE.md` pour les engagements complets, qui sont eux-memes couverts
par `tests/test_protocole.py`.

## Approvisionnement en prix

Trois routes empilees par ordre de preference, une seule interface :

```python
from klastos.providers import (AggregatingProvider, CachingProvider,
                               CSVProvider, HTTPProvider, build_price_set)
from klastos.units import PriceUnit

chaine = AggregatingProvider(
    providers=[
        CSVProvider("data/prix_client.csv"),          # 1. prix du client
        CachingProvider(                              # 2. flux public
            HTTPProvider(
                url="https://api.exemple/latest",
                mapping={"Ni": {"path": ["rates", "LME-NI"],
                                "unit": PriceUnit.PER_TROY_OUNCE,
                                "reference_name": "LME Nickel"}},
                fetcher=mon_client_http,
                source_label="agregateur public",
            ),
            cache_path=".cache/prix.json",
        ),
    ],
    required=("Ni", "Co"),
)
prix = build_price_set(chaine.quotes(), label="production",
                       is_production_source=True)
print(chaine.ledger.lines())   # provenance de chaque metal
```

L'unite de cotation est **obligatoire** et n'est jamais deduite. Une bande de
plausibilite par metal rejette toute erreur de conversion.
Voir `data/prix_client_exemple.csv` pour le format attendu du client.