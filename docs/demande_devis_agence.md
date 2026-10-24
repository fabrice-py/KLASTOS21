# Demande de devis à une agence d'évaluation

Document prêt à envoyer. Il existe parce que **ni Fastmarkets ni Benchmark
ne publient de tarif** : les deux travaillent sur devis, et le prix dépend
de ce que vous demandez. Demander le bon périmètre change l'ordre de
grandeur.

---

## Pourquoi vous en avez besoin

L'étage gratuit du projet (`klastos usgs`) vous rend autonome pour
**cribler** un lot. Il ne vous rend pas autonome pour **contracter** :
`is_production_source` vaut `False` sur les moyennes USGS, et une
valorisation opposable est refusée.

Mesure de l'écart que la licence achète :

| Métal | Source gratuite | Marché | Écart |
|---|---|---|---|
| Lithium (Li₂CO₃) | 9 000 USD/t, moyenne 2025 | 19 750 USD/t, CIF Asie, sept. 2026 | **×2,2** |
| Cobalt (LME cash) | 15,00 USD/lb, moyenne 2025 | 25,05 USD/lb, janv. 2026 | **+67 %** |

La licence n'achète donc pas « des prix » : elle achète la **fraîcheur** et
le **droit de les reproduire** devant un client.

---

## La règle qui décide du montant

Une agence facture trois choses séparément, et la troisième est de loin la
plus chère :

1. **les séries** que vous lisez ;
2. **le nombre d'utilisateurs** qui les consultent ;
3. **le droit de rediffusion** — reproduire un chiffre dans un document
   remis à un tiers.

**Ne demandez pas le catalogue.** Demandez quatre séries nommées plus les
payables, avec le droit de reproduction. Un devis étroit n'a aucune commune
mesure avec un siège entreprise.

---

## Fastmarkets : la demande, prête à copier

À privilégier, et pour une raison technique et non commerciale : le
catalogue de symboles du projet est **déjà renseigné** pour Fastmarkets, y
compris la subtilité qui fausserait tout si on la manquait. Benchmark et SMM
ont des catalogues vides (voir plus bas).

> Bonjour,
>
> Nous développons un outil d'analyse prédictive de black mass et cherchons
> un abonnement **restreint** aux séries ci-dessous, avec **droit de
> reproduction dans un rapport remis à un client**.
>
> **Prix métal**
>
> | Symbole | Série |
> |---|---|
> | `MB-CO-0005` | Cobalt standard grade, in-whs Rotterdam, **point bas** |
>
> Plus, par votre canal usuel ou par le LME : nickel cash official, cuivre
> grade A cash, aluminium, et carbonate ou hydroxyde de lithium qualité
> batterie CIF Chine-Japon-Corée.
>
> **Payables black mass** — c'est le cœur de notre besoin
>
> | Symbole | Série |
> |---|---|
> | `MB-BMS-0004` | Black mass NCM, payable nickel, EXW Europe |
> | `MB-BMS-0005` | Black mass NCM, payable cobalt, EXW Europe |
> | `MB-BMS-0001` | Black mass NCM, payable nickel, CIF Corée du Sud |
> | `MB-BMS-0002` | Black mass NCM, payable cobalt, CIF Corée du Sud |
> | `MB-BMS-0003` | Black mass NCM, payable lithium, CIF Corée du Sud |
>
> **Questions auxquelles nous avons besoin d'une réponse chiffrée**
>
> 1. Coût annuel pour **un** utilisateur, ces séries seulement.
> 2. Surcoût du **droit de rediffusion** dans un document client, ligne
>    séparée.
> 3. L'accès API (`api.fastmarkets.com/physical/v2`) est-il inclus, ou
>    facturé à part ?
> 4. Quelle **latence** : la valeur du jour, ou décalée ?
> 5. Y a-t-il un palier *startup* ou *early stage* ?
>
> Nous n'avons pas besoin des prévisions, des analyses de marché, ni des
> autres familles de produits.

### La subtilité à ne pas manquer

Le catalogue du projet la porte déjà, en commentaire de
`data/symboles_pra.json` :

> « Les payables de black mass de Fastmarkets se réfèrent au **point bas**
> du cobalt standard grade, pas au point médian. Retenir le médian
> surestimerait la valeur du lot. »

D'où `"field": "low"` sur `MB-CO-0005`. Si l'agence vous propose une série
médiane, elle ne convient pas : le payable contractuel se calcule sur le
point bas.

---

## Benchmark Mineral Intelligence : l'alternative, et son surcoût caché

J'avais d'abord recommandé Benchmark, parce qu'ils publient directement des
payables black mass par région — 72 à 78 % Ni/Co en Europe au deuxième
trimestre 2026. **Je corrige : Fastmarkets est le choix de moindre
friction.**

La raison est dans le code. `klastos/feeds.py` porte bien un `BenchmarkFeed`
et attend `KLASTOS_BMI_API_KEY`, mais `data/symboles_pra.json` a **zéro
symbole** déclaré pour Benchmark, contre douze pour Fastmarkets. Souscrire
chez Benchmark impose donc de constituer ce catalogue à partir de leur
documentation, qui n'est accessible qu'après souscription. C'est un travail
d'intégration en plus, à faire à l'aveugle au moment de négocier.

Le palier gratuit de Benchmark ne compense pas : il n'affiche que des
**indices sans unité** — « Black Mass Index 37,11 », « Lithium Index
317,07 » — et le détail est derrière authentification. Un indice à 37,11 ne
se convertit pas en USD/t.

Si vous allez chez Benchmark malgré tout, demandez-leur **la liste des
identifiants de séries et leur documentation d'API avant signature**. C'est
une demande légitime et elle vous évite de payer pour une intégration que
vous ne pouvez pas chiffrer.

---

## Le seul repère public que j'ai trouvé

Aucune agence ne publie ses tarifs. Le seul chiffre vérifiable du marché
voisin est celui du **CME** : licence de distribution de données retardées à
**12 000 USD/an**. C'est de la donnée de *bourse*, structurellement moins
chère qu'une évaluation d'agence, et cela ne couvre que la rediffusion, pas
l'accès.

Traitez-le comme un plancher d'ordre de grandeur, pas comme une estimation.

---

## Le jour où vous signez

Rien à développer. Le flux existe et attend ses identifiants :

```powershell
$env:KLASTOS_FM_SERVICE_KEY  = "<votre cle>"
$env:KLASTOS_FM_SERVICE_NAME = "<votre nom de service>"

# confronte le catalogue du projet a vos droits REELS
klastos prix --catalogue
```

Cette dernière commande existe précisément pour ça : l'endpoint
*Instruments* de Fastmarkets ne renvoie que les symboles que votre
abonnement autorise, et elle compare ce que le projet déclare à ce que vous
avez effectivement acheté. Lancez-la avant de vous fier au catalogue.

---

## Ce que vous gardez même sans licence

L'étage gratuit ne disparaît pas. `klastos usgs` continue de donner cinq
métaux redistribuables pour le criblage, et `klastos usgs --mois` le cobalt
mensuel jusqu'à janvier 2026. La licence s'ajoute, elle ne remplace pas.
