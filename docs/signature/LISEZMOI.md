# Signature de courriel

Quatre fichiers : la signature HTML et sa version en texte brut, en
français et en anglais.

| fichier | usage |
|---|---|
| `signature-fr.html` | signature principale, français |
| `signature-en.html` | signature principale, anglais |
| `signature-fr.txt` | repli texte brut, français |
| `signature-en.txt` | repli texte brut, anglais |

---

## La méthode qui marche partout

**Aucun client de messagerie grand public n'accepte qu'on lui colle du
code HTML dans la case « signature ».** Il faut lui coller le résultat
*affiché*, pas le code.

1. Ouvrir `signature-fr.html` dans un navigateur — double-clic suffit.
2. Sélectionner tout le contenu affiché : `Ctrl+A`.
3. Copier : `Ctrl+C`.
4. Coller dans la case signature de votre messagerie : `Ctrl+V`.

Si vous collez le code et que vous voyez apparaître `<table
role="presentation"…`, c'est que vous avez copié le fichier au lieu de
son rendu.

---

## Par client

**Gmail** — Paramètres (roue dentée) → *Voir tous les paramètres* →
onglet *Général* → section *Signature* → *Créer*. Collez, puis
**descendez en bas de la page et cliquez sur *Enregistrer les
modifications*** : Gmail ne sauvegarde pas tout seul, et c'est l'oubli
le plus fréquent.

**Outlook sur le web** — Paramètres → *Courrier* → *Composer et
répondre* → *Signature électronique*.

**Outlook pour Windows** — *Fichier* → *Options* → *Courrier* →
*Signatures*.

**Thunderbird** — *Paramètres du compte* → cochez **Joindre la
signature à partir d'un fichier** et désignez directement
`signature-fr.html`. C'est le seul client qui accepte le fichier tel
quel.

**Apple Mail** — *Réglages* → *Signatures*. Décochez *Toujours utiliser
la police par défaut* avant de coller, sinon le style saute.

---

## Deux signatures, et quand changer

Créez-les toutes les deux et nommez-les clairement — `FR` et `EN`. La
plupart des clients permettent d'en choisir une à la rédaction.

Écrivez à un interlocuteur étranger avec la version anglaise : son lien
pointe vers `klastos21.fr/en/`, pas vers l'accueil français.

---

## Ce qu'il faut savoir avant d'envoyer

**Le logo est hébergé, pas joint.** Il est servi depuis
`klastos21.fr/marque/klastos21_logo.png`. C'est volontaire : une image
jointe se détache des réponses et des transferts, tandis qu'une image
hébergée survit à toute la chaîne. En contrepartie, elle disparaît si le
site tombe.

**Beaucoup de clients bloquent les images par défaut.** Votre
destinataire verra alors le texte de remplacement, « KLASTOS21 - what
the assay proves », à la place du logo. C'est pour cela que ce texte dit
quelque chose plutôt que « logo ».

**Le logo est servi en 1200 pixels pour un affichage à 190.** Il reste
net sur écran retina, où chaque pixel affiché en vaut deux.

**Testez avant de diffuser.** Envoyez-vous un message à vous-même, puis
répondez-y : c'est la réponse qui révèle les signatures mal construites,
pas le premier envoi.

---

## Si vous modifiez quelque chose

Les couleurs viennent de la charte de marque : `#12161C` pour l'encre,
`#B4632B` pour l'orange, `#5B6573` pour l'ardoise. Les mêmes que le
site et les rapports.

**Les accents sont écrits en entités** : `&eacute;` et non `é`. Les
deux fichiers HTML sont en ASCII pur. Un fragment sans `<head>` ne peut
pas porter de déclaration d'encodage utile, et un navigateur qui se
rabat sur la locale de la machine afficherait du charabia que vous
copieriez tel quel dans votre messagerie. Si vous ajoutez du texte
accentué, écrivez-le en entités aussi : un test du dépôt le vérifie.

Tout le style est **en ligne**, dans les attributs `style` de chaque
balise. Ce n'est pas de la négligence : Gmail supprime les blocs
`<style>` à l'affichage, et une signature qui compte dessus arrive en
texte nu. De même, la mise en page est un **tableau** parce qu'Outlook
rend le HTML avec le moteur de Word, qui ignore flexbox et grid.
