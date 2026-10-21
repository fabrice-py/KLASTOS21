# Site vitrine KLASTOS21

Site statique, six pages, deux langues. Aucune dépendance : trois modules
Python génèrent du HTML et une feuille de style, comme `render_html.py`
génère le rapport.

## Construire

```
python site/construire.py
```

Écrit quatorze fichiers dans `site/public/`. Pour voir le résultat, ouvrir
`site/public/index.html` — la racine redirige vers la langue par défaut.

Un autre dossier de sortie :

```
python site/construire.py --sortie chemin/vers/dossier
```

## Les trois modules

| Module | Rôle |
|---|---|
| `charte.py` | Le style, et rien d'autre. La palette vient de `klastos/theme.py` ; aucun hex n'est écrit ici. |
| `contenu.py` | Les 128 textes, en français et en anglais côte à côte. Une clé n'est jamais un texte affiché. |
| `construire.py` | Les gabarits des six pages et la génération. |

## Le parti pris visuel

**Le site est achromatique partout.** Texte, navigation, cartes, boutons :
tout est en encre, gris et filets de 1 px. Les quatre couleurs de KLASTOS21
n'apparaissent que là où elles mesurent quelque chose — cobalt pour une
grandeur déterminée, ambre pour une grandeur mal déterminée, rouille pour un
domaine compatible, vert pour un bouclage accepté.

Conséquence qui surprend : **le bouton principal est encre, pas cobalt.** Un
bouton cobalt serait la seule tache de cobalt du site qui ne signifie rien,
et il apprendrait au visiteur que la couleur est un ornement. Or la thèse du
produit est que la couleur est la mesure.

Quatre interdits, relevés comme unanimes sur cinq systèmes de design de
produits techniques (Vercel, Linear, OpenAI, Ramp, teenage engineering) et
vérifiés par test : aucun dégradé, aucune ombre portée, aucun texte centré,
aucune icône décorative. La structure vient des filets et du blanc.

## La chaîne de la charte

```
site/charte.py  ←  klastos/theme.py  ←  klastos/render_html.py
   (tests/test_site.py)              (tests/test_theme.py)
```

En cas de divergence, **c'est le rapport imprimé qui tranche** : c'est lui
qui sort de l'outil et qui se discute en réunion. Les deux maillons sont
tenus par test. Cinq jetons sur douze avaient déjà dérivé entre l'écran et
le papier avant que la table complète ne soit vérifiée.

## Tests

```
python -m pytest tests/test_site.py -q
```

Le test qui mord le plus est
`test_aucun_texte_francais_ne_fuit_dans_les_pages_anglaises` : pour chaque
clé dont les deux langues diffèrent, le texte français ne doit apparaître
dans aucune page anglaise, ni l'inverse. Il attrape le défaut réel —
un appel à `t()` qui oublie son argument de langue et retombe sur le
français par défaut.

## Ajouter une page

1. Ajouter son nom à `contenu.PAGES`.
2. Ajouter ses quatre clés d'en-tête : `titre_onglet`, `description`,
   `surtitre`, `h1`, plus `nav.<page>`.
3. Ajouter sa fonction de corps à `construire.CORPS_DE_PAGE`.

Les trois étapes sont chacune exigées par un test : en oublier une fait
échouer la suite plutôt que de produire une page muette.
