# Barème client — mode d'emploi

KLASTOS21 n'impose aucune source de prix. Trois routes coexistent, et
celle-ci est la seule qui soit **gratuite, opposable et immédiate**.

---

## Pourquoi cette route existe

Le moteur refuse de valoriser sur un prix de plus de sept jours
(`MAX_PRICE_AGE_DAYS`). Les deux sources publiques câblées ne passent pas
ce verrou, et ce n'est pas un défaut de l'outil :

| source | métaux | périodicité | passe le verrou |
|---|---|---|---|
| World Bank Pink Sheet | Al, Cu, Ni | mensuelle | non — 30 j > 7 j |
| USGS (MCS / MIS) | Co, Li, Ni, Cu, Al | annuelle | non — 365 j > 7 j |

Les deux métaux qui portent l'essentiel de la valeur d'une black mass —
cobalt et lithium — ne sont couverts que par l'USGS, en moyenne annuelle.

L'architecture **refuse plutôt que de mentir**. La conséquence est nette :
sans abonnement d'agence, le seul chiffre opposable est celui que
**l'acheteur fournit lui-même**. C'est aussi le plus défendable, puisque
c'est le prix sur lequel il traitera réellement.

---

## Le fichier

Un CSV, encodé en UTF-8, une ligne par métal. Sept colonnes sont
obligatoires, trois sont facultatives.

| colonne | obligatoire | contenu |
|---|---|---|
| `metal` | oui | symbole : `Ni`, `Co`, `Li`, `Cu`, `Mn` |
| `value` | oui | la valeur numérique, sans séparateur de milliers |
| `unit` | oui | `USD/t`, `USD/kg`, `USD/lb`, `USD cent/lb` ou `USD/oz t` |
| `currency` | oui | `USD`, `EUR`… — une seule devise par fichier |
| `as_of` | oui | date de la cotation, au format `AAAA-MM-JJ` |
| `source` | oui | d'où vient le chiffre, en clair |
| `reference_name` | oui | l'intitulé exact de la cotation |
| `basis` | non | `Li2CO3` si le lithium est coté en carbonate ; vide vaut `metal`, c'est-à-dire une cotation du métal lui-même |
| `note` | non | tout commentaire utile |

**L'unité n'est jamais déduite.** Un libellé inconnu fait échouer le
chargement avec la liste des valeurs admises. C'est voulu : une erreur
d'unité sur le lithium déplace la valeur d'un lot d'un facteur 5.

**`basis` n'est pas cosmétique.** Une cotation de carbonate de lithium
porte sur le Li₂CO₃, pas sur le lithium contenu. Sans cette colonne, le
lot serait valorisé environ cinq fois trop cher. KLASTOS21 ne le devine
pas depuis l'intitulé : il le lit dans cette colonne.

---

## L'utiliser

```bash
python -m klastos rapport --bulletin mon_lot.csv --prix bareme_client.csv
```

Un fichier chargé par cette route est marqué **source de production** :
le rapport est opposable, et aucune licence de rediffusion ne le
restreint — ce sont vos prix.

---

## Les deux autres routes

**Abonnement d'agence.** Les adaptateurs existent déjà
(`klastos/feeds.py` : Fastmarkets, Benchmark Mineral Intelligence, SMM).
Il ne leur manque que des identifiants, lus dans l'environnement. Une
évaluation d'agence ne peut jamais être rediffusée à un tiers : le
rapport le sait et refuse la sortie externe en conséquence.

**Mode indicatif.** Sans barème ni abonnement, l'outil accepte de
travailler sur des prix périmés, mais le document porte alors la mention
« Document de démonstration. Aucune valeur opposable. » et le refus doit
être levé explicitement. C'est une aide à la réflexion, jamais une base
de négociation.
