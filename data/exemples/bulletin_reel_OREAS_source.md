# Provenance — `bulletin_reel_OREAS_brut.csv`

## Ce que ce fichier est

Extrait de données d'un **matériau de référence certifié OREAS**, black mass
de batteries lithium-ion. Fourni tel quel, sans retouche : l'empreinte
SHA-256 du fichier versé est identique à celle de la source remise.

```
sha256  fb7fab6f2d106e8d6a5b78518c56f02e3617d51a37791c0c19921fa4506e9364
```

C'est le fichier **brut**, et c'est tout son intérêt : il porte les six
formes qui faisaient refuser le bulletin avant le 22 octobre 2026.

| Forme | Exemple dans le fichier |
|---|---|
| symbole suivi du nom complet | `Al, Aluminium (wt.%)` |
| unité `wt.%` au lieu de `%` | `C, Carbon (wt.%)` |
| unité `ppm` | `Ba, Barium (ppm)` |
| valeur censurée | `< 0.050` (thulium) |
| incertitude indéterminée | `IND` (thulium) |
| séparateur point-virgule | toutes les lignes |

## Ce que je ne sais pas, et que je n'invente pas

Les éléments suivants **ne figurent pas** dans le fichier remis et ne sont
donc pas documentés ici : la référence produit OREAS, le numéro de
certificat, la date d'émission, le lot, la méthode de préparation, le nombre
de laboratoires participants. Cette note ne les devine pas.

Conséquence pratique : le fichier sert de **cas de non-régression
d'ingestion** et de source des deux ancrages de plausibilité (F et P). Il ne
peut pas servir de référence métrologique opposable tant que le certificat
lui-même n'est pas joint.

## Structure des colonnes

```
Element ; Value ; 1SD ; Expanded uncertainty Low ; Expanded uncertainty High ; Methods
```

KLASTOS21 ne lit que les **deux premières** colonnes — l'intitulé et la
valeur. Les trois colonnes d'incertitude et la colonne de méthode sont
ignorées par le lecteur de format long.

### Ce que les deux colonnes d'incertitude rapportent

**Indéterminé, et c'est mesuré.** Si `Expanded uncertainty Low/High` était
une incertitude élargie à k = 2, sa demi-largeur vaudrait environ deux fois
`1SD`, soit un rapport `1SD / demi-intervalle` proche de 0,5. Mesure sur les
34 éléments quantifiés :

| Statistique du rapport `1SD / demi-intervalle` | Valeur |
|---|---|
| médiane | 1,02 |
| minimum | 0,28 (dysprosium) |
| maximum | 2,34 (nickel) |

La médiane proche de 1 exclut un facteur k = 2 ; la dispersion de 0,28 à
2,34 exclut **tout** facteur k unique entre les deux colonnes. Les deux
grandeurs ne sont donc pas liées par un élargissement, et le fichier seul ne
permet pas de dire laquelle est quoi. Voir PROTOCOLE.md § 1.3 bis.

## Les dix éléments retenus

Sur 35 lignes, dix correspondent à un élément du modèle KLASTOS21 ; les
vingt-cinq autres sont **refusées et listées**, conformément à la règle du
module d'ingestion — un intitulé non reconnu n'est jamais deviné.

| Élément | Teneur certifiée | 1SD | RSD |
|---|---|---|---|
| Ni | 23,11 % | 0,117 | 0,51 % |
| C | 21,39 % | 0,493 | 2,30 % |
| Al | 7,46 % | 0,213 | 2,86 % |
| Co | 6,09 % | 0,064 | 1,05 % |
| Mn | 5,35 % | 0,058 | 1,08 % |
| Li | 4,13 % | 0,041 | 0,99 % |
| F | 2,44 % | 0,139 | 5,70 % |
| Cu | 2,34 % | 0,086 | 3,68 % |
| Fe | 1,11 % | 0,040 | 3,60 % |
| P | 0,350 % | 0,065 | 18,57 % |

Somme des dix : **73,77 %**. L'oxygène n'est pas dosé, comme sur tout
bulletin de routine (PROTOCOLE.md § 2.6).

## Bouclage mesuré

| Configuration | Somme des phases |
|---|---|
| sans attestation de provenance | 93,95 % |
| provenance véhicule électrique, attestée | 93,42 % |
| provenance DEEE, attestée | 94,19 % |

Le bouclage dépend de la liste de phases retenue, donc de l'attestation. La
valeur de référence citée au protocole, **93,95 %**, est celle du cas non
attesté — liste de phases complète.

## Usages dans le dépôt

- `tests/test_ingestion_reelle.py` — cas de non-régression des six formes.
- `klastos/plausibility.py` — `ANCRAGES_CERTIFIES`, qui ne retient que le
  **fluor**. **Un point n'est pas une bande** : la borne qui en découle porte
  `validated=False`.

  Le phosphore de ce certificat, 0,350 %, n'est **pas** utilisé comme
  ancrage. LFP est LiFePO₄, le phosphore y est un élément majeur, et ce
  matériau ne contient quasiment pas de LFP : l'ancrer refusait 45,8 % des
  lots que le projet déclare plausibles, et 100 % des lots riches en LFP.
  Voir PROTOCOLE.md § 2.6 quinquies.
