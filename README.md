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