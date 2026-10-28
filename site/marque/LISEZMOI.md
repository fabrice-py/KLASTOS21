# Marque KLASTOS21

## Les fichiers

| Fichier | Usage |
|---|---|
| `klastos21_logo_source.png` | **Original fourni**, 2400 x 800, fond transparent. Ne pas modifier : c'est la référence. |
| `klastos21_logo.png` | Verrouillage complet, 1200 px de large. Signatures de courriel, plaquettes, partenaires. |
| `klastos21_logo@2x.png` | Le même en 2400 px, pour l'impression. |
| `klastos21_marque.png` | Le cube seul, 512 px de haut. |
| `favicon-32.png` | Onglet de navigateur. |
| `favicon-180.png` | Icône d'écran d'accueil, et onglet de l'interface Streamlit. |

## Le cube est vectoriel dans le produit

Les trois supports du logiciel — rapport, site, interface — ne consomment
**aucun** de ces fichiers pour afficher le cube. Il est redessiné en SVG
par `klastos/marque.py`.

La raison est le rapport : c'est un document **autonome**, destiné à
l'impression. Un PNG y partirait en base64, pèserait 4,8 Ko pour une seule
taille et sortirait flou à 300 dpi. Le SVG pèse un demi-kilo-octet et reste
net à toute résolution.

Les fichiers ci-dessus existent pour les supports qui ne savent pas lire un
SVG, et pour tout ce qui sort du logiciel.

## Les couleurs, et la règle à ne pas enfreindre

| | |
|---|---|
| Encre | `#12161C` |
| **Orange de la marque** | `#B4632B` |
| Ardoise de la signature | `#5B6573` |

**L'orange de la marque n'est le statut de rien.** La palette du produit est
sémantique : le cobalt signifie « grandeur déterminée », la rouille « non
identifiable », l'ambre « à élucider », le vert « bouclage conforme ». Un
client les décode comme des états.

Si l'orange se met à colorer une donnée, il devient un cinquième statut que
personne n'a défini, voisin de l'ambre et de la rouille. La faute a déjà été
commise une fois ici, dans l'autre sens : la tuile « bouclage conforme »
sortait en cobalt, c'est-à-dire dans la couleur qui veut dire « déterminé ».

`tests/test_marque.py` tient cette séparation.

## Le cube se renverse sur fond sombre

La barre latérale de l'interface est en `theme.NUIT`. Un cube à l'encre
d'origine y disparaîtrait. `marque.cube_svg()` prend donc ses trois faces en
paramètres : l'encre passe au blanc et la face droite prend la couleur du
fond, ce qui conserve la lecture en volume.
