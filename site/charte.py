"""
KLASTOS21 - Charte du site vitrine.

Ce module ne contient que du style, comme `klastos/theme.py` dont il tire
sa palette. Aucune couleur n'est ecrite ici en litteral : tout hex vient de
`theme`, qui est lui-meme tenu par test contre le rapport imprime. La chaine
est donc : site <- theme <- rapport. Aucun troisieme endroit ou deriver.

Parti pris, et il est deliberement contraire a l'habitude
---------------------------------------------------------
Le site est achromatique partout - texte, navigation, cartes, boutons. Les
quatre couleurs de KLASTOS21 n'apparaissent que la ou elles veulent dire
quelque chose : cobalt pour une grandeur determinee, ambre pour une grandeur
mal determinee, rouille pour un domaine compatible, vert pour un bouclage
accepte.

Consequence qui surprend : le bouton principal est encre, pas cobalt. Un
bouton cobalt serait la seule tache de cobalt qui ne signifie rien, et il
apprendrait au visiteur que la couleur est un ornement. Or la these du
produit est que la couleur est la mesure. On ne peut pas vendre ca sur une
page qui se contredit elle-meme.

Interdits, releves comme unanimes sur cinq systemes de design de produits
techniques (Vercel, Linear, OpenAI, Ramp, teenage engineering) : aucun
degrade, aucune ombre portee, aucun texte centre, aucune icone decorative.
La structure vient de filets de 1px et du blanc.
"""

from __future__ import annotations

from klastos import marque, theme

#: Jetons exposes au CSS. La cle est le nom de la variable CSS, la valeur
#: vient de `theme` - jamais d'un litteral.
JETONS: dict[str, str] = {
    "bg": theme.CARTE,
    "paper": theme.PAPIER,
    "ink": theme.ENCRE,
    "muted": theme.ARDOISE,
    "line": theme.TRAIT,
    "line-strong": theme.TRAIT_FORT,
    "cobalt": theme.COBALT,
    "cobalt-soft": theme.COBALT_PALE,
    "amber": theme.AMBRE,
    "amber-soft": theme.AMBRE_PALE,
    # ORANGE DE LA MARQUE. Il vient du logo, pas de la palette
    # semantique : il n'est le statut de rien.
    "marque": marque.ORANGE_MARQUE,
    "rust": theme.ROUILLE,
    "rust-soft": theme.ROUILLE_PALE,
    "green": theme.VERT,
    "green-soft": theme.VERT_PALE,
    # Fonds SOMBRES. Le site alternait pages blanches et pages blanches
    # lavees : tout y avait le meme poids. L'encre sert desormais aux
    # sections qui MONTRENT - la console, le hero - et le blanc a celles
    # qui expliquent. Repris de la barre laterale de l'interface, pour que
    # les deux surfaces du produit se ressemblent.
    "nuit": theme.NUIT,
    "nuit-claire": theme.NUIT_CLAIRE,
    "bord-nuit": theme.BORD_NUIT,
    # Textes posés sur les surfaces sombres. Ils sont nommés par leur
    # rôle, comme le reste de la palette : un hex écrit dans le corps de
    # la feuille serait une source de vérité de plus.
    "nuit-texte": "#E4EAF4",
    "nuit-muet": "#97A6C4",
    "nuit-faible": "#73839F",
    "nuit-filet": "#39496E",
    "nuit-fort": "#FFFFFF",
    "cobalt-clair": "#8FA8FF",
    "cobalt-fonce": "#16214A",
    "voile": "rgba(255, 255, 255, .92)",
    "voile-survol": "rgba(255, 255, 255, .06)",
}

#: Les trois polices. Archivo n'existait qu'a l'impression ; le site la fait
#: passer a l'ecran, ce qui reduit l'ecart entre le document et la page.
POLICES: dict[str, str] = {
    "display": '"Archivo", "Helvetica Neue", Arial, sans-serif',
    "body": '"IBM Plex Sans", -apple-system, "Segoe UI", Roboto, sans-serif',
    "mono": '"IBM Plex Mono", ui-monospace, "SF Mono", Consolas, monospace',
}

LIEN_POLICES = (
    "https://fonts.googleapis.com/css2?"
    "family=Archivo:wght@500;600;700"
    "&family=IBM+Plex+Mono:wght@400;500"
    "&family=IBM+Plex+Sans:wght@400;500;600"
    "&display=swap"
)


def racine() -> str:
    """Le bloc `:root`, seul endroit du CSS ou une couleur est nommee."""
    lignes = [f"  --{nom}: {valeur};" for nom, valeur in JETONS.items()]
    lignes += [f"  --f-{nom}: {valeur};" for nom, valeur in POLICES.items()]
    return ":root {\n" + "\n".join(lignes) + "\n}"


#: Le corps de la feuille. Il n'y a aucun hex ici : tout passe par var().
#: Un hex ecrit dans ce bloc serait une quatrieme source de verite, et
#: `tests/test_site.py` le refuse.
CORPS = """
*, *::before, *::after { box-sizing: border-box; }

html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--f-body);
  font-size: 17px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

/* Jamais de texte centre : la lecture technique se fait au fil de gauche. */
h1, h2, h3, h4, p, ul, ol, li, dl { text-align: left; }
h1, h2, h3, h4 {
  font-family: var(--f-display);
  font-weight: 600;
  margin: 0;
  letter-spacing: -0.02em;
  line-height: 1.15;
}
h1 { font-size: 46px; letter-spacing: -0.03em; }
h2 { font-size: 30px; }
h3 { font-size: 20px; letter-spacing: -0.01em; }
h4 { font-size: 17px; letter-spacing: 0; }
p { margin: 0 0 1em; }
p:last-child { margin-bottom: 0; }
a { color: var(--ink); text-decoration: underline;
    text-underline-offset: 3px; text-decoration-thickness: 1px; }
a:hover { text-decoration-color: var(--line-strong); }
strong { font-weight: 600; }
code, .mono {
  font-family: var(--f-mono);
  font-variant-numeric: tabular-nums;
}

/* ---------- Trame ---------- */
.enveloppe { max-width: 1200px; margin: 0 auto; padding: 0 28px; }
.bande { border-bottom: 1px solid var(--line); }
.bande-lavee { background: var(--paper); }
.section { padding: 76px 0; }
.section-serree { padding: 46px 0; }

/* ---------- Navigation ---------- */
.nav {
  border-bottom: 1px solid var(--line);
  background: var(--voile);
  position: sticky; top: 0; z-index: 40;
  -webkit-backdrop-filter: saturate(180%) blur(12px);
  backdrop-filter: saturate(180%) blur(12px);
  transition: border-color .25s;
}
.nav-interieur {
  display: flex; align-items: center; gap: 30px;
  min-height: 66px; flex-wrap: wrap;
}
.marque {
  display: inline-flex; align-items: center; gap: 9px;
  font-family: var(--f-display); font-weight: 700; font-size: 18px;
  letter-spacing: -0.01em; text-decoration: none; white-space: nowrap;
}
.marque svg { display: block; flex: none; }
/* Les deux chiffres passent a l'ORANGE DE LA MARQUE. Ils etaient gris,
   donc muets ; le logo les porte en couleur. L'orange n'appartient pas a
   la palette semantique du site : il ne signifie que la marque. */
.marque .mot span { color: var(--marque); font-weight: 700; }
/* Le mot au-dessus de la signature, alignes entre eux et non sous le
   cube : c'est la disposition du logo. */
.marque-texte { display: flex; flex-direction: column; gap: 1px; }
.marque .mot { line-height: 1.05; }
.marque-signature {
  font-family: var(--f-mono); font-size: 7px; font-weight: 400;
  letter-spacing: .2em; color: var(--muted); line-height: 1;
}
/* Dans le pied, la signature precede le descriptif : l'une est la
   marque, l'autre dit le metier. */
.pied-signature {
  font-family: var(--f-mono); font-size: 9px; letter-spacing: .18em;
  color: var(--muted); margin-bottom: 6px;
}
.nav-liens { display: flex; gap: 24px; flex-wrap: wrap; margin-left: auto; }
.nav-liens a {
  font-size: 15px; text-decoration: none; color: var(--muted);
  padding: 4px 0; border-bottom: 1px solid transparent;
}
.nav-liens a:hover { color: var(--ink); }
.nav-liens a[aria-current="page"] {
  color: var(--ink); border-bottom-color: var(--ink);
}
.langues { display: flex; gap: 0; border: 1px solid var(--line);
           border-radius: 4px; overflow: hidden; }
.langues a {
  font-family: var(--f-mono); font-size: 11px; letter-spacing: 0.08em;
  text-transform: uppercase; text-decoration: none; color: var(--muted);
  padding: 5px 10px;
}
.langues a[aria-current="true"] { background: var(--ink); color: var(--bg); }

/* ---------- Titrage ---------- */
.surtitre {
  font-family: var(--f-mono); font-size: 11px; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--muted); margin-bottom: 14px;
}
.chapeau {
  font-size: 20px; line-height: 1.5; color: var(--muted);
  max-width: 62ch; margin-top: 20px;
}
.mesure { max-width: 68ch; }

/* ---------- Boutons ----------
   Encre, pas cobalt. Voir le parti pris en tete de module : un bouton
   cobalt serait du cobalt qui ne mesure rien. */
.bouton {
  display: inline-block; font-size: 15px; font-weight: 500;
  text-decoration: none; padding: 10px 20px; border-radius: 6px;
  border: 1px solid var(--ink); background: var(--ink); color: var(--bg);
}
.bouton:hover { background: var(--muted); border-color: var(--muted); }
.bouton-creux { background: transparent; color: var(--ink); }
.bouton-creux:hover { background: var(--paper); color: var(--ink);
                      border-color: var(--ink); }
.boutons { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 30px; }

/* ---------- Cartes ----------
   Aucune ombre : un filet de 1px et du blanc suffisent. Rayon 6px, pas 16 -
   au-dela la page glisse vers le SaaS aimable, et nous vendons une mesure. */
.grille { display: grid; gap: 18px; }
.grille-2 { grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); }
.grille-3 { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.carte {
  background: var(--bg); border: 1px solid var(--line);
  border-radius: 6px; padding: 22px 24px;
}
.carte h3 { margin-bottom: 10px; }
.carte p { font-size: 15.5px; color: var(--muted); }
.carte-titre-mono {
  font-family: var(--f-mono); font-size: 11px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--muted); margin-bottom: 12px;
}

/* ---------- Statut : le seul endroit chromatique du site ---------- */
.statut { border-left: 3px solid var(--line); padding-left: 18px; }
.statut-determine { border-left-color: var(--cobalt); }
.statut-mal { border-left-color: var(--amber); }
.statut-domaine { border-left-color: var(--rust); }
.statut-ok { border-left-color: var(--green); }

.pastille {
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-family: var(--f-mono); font-size: 11px; letter-spacing: 0.04em;
  white-space: nowrap;
}
.pastille-determine { background: var(--cobalt-soft); color: var(--cobalt); }
.pastille-mal { background: var(--amber-soft); color: var(--amber); }
.pastille-domaine { background: var(--rust-soft); color: var(--rust); }
.pastille-ok { background: var(--green-soft); color: var(--green); }

/* ---------- La figure qui porte la these ----------
   Un trait fin contre une bande large, a la meme echelle. C'est la seule
   chose que le visiteur doit comprendre avant de lire une ligne. */
.regle { margin: 0; }
.regle-ligne {
  display: grid; grid-template-columns: 150px 1fr 116px;
  align-items: center; gap: 16px;
  padding: 13px 0; border-top: 1px solid var(--line);
}
.regle-ligne:last-child { border-bottom: 1px solid var(--line); }
.regle-nom { font-size: 15px; }
.regle-piste { position: relative; height: 15px; }
.regle-piste::before {
  content: ""; position: absolute; left: 0; right: 0; top: 7px;
  height: 1px; background: var(--line);
}
.regle-trait, .regle-bande {
  position: absolute; top: 3px; height: 9px; border-radius: 1px;
}
.regle-trait { width: 2px; }
.regle-bande { opacity: 0.32; }
.regle-trait.determine { background: var(--cobalt); }
.regle-trait.mal { background: var(--amber); }
.regle-bande.mal { background: var(--amber); }
.regle-bande.domaine { background: var(--rust); }
.regle-valeur {
  font-family: var(--f-mono); font-variant-numeric: tabular-nums;
  font-size: 13px; text-align: right; white-space: nowrap;
}
.regle-legende {
  font-family: var(--f-mono); font-size: 11px; color: var(--muted);
  margin-top: 14px; letter-spacing: 0.02em;
}

/* ---------- Citation du code ---------- */
.citation {
  border-left: 2px solid var(--line-strong); padding: 2px 0 2px 20px;
  margin: 0; font-size: 17px; color: var(--ink);
}
.citation footer {
  font-family: var(--f-mono); font-size: 11.5px; color: var(--muted);
  margin-top: 10px; letter-spacing: 0.02em;
}

/* ---------- Encart ---------- */
.encart {
  background: var(--paper); border: 1px solid var(--line);
  border-radius: 6px; padding: 24px 26px;
}
.encart .mono { font-size: 14px; }

/* ---------- Tableau ---------- */
.tableau { width: 100%; border-collapse: collapse; font-size: 15px; }
.tableau th {
  font-family: var(--f-mono); font-size: 10.5px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--muted); font-weight: 500;
  text-align: left; padding: 0 14px 9px 0;
  border-bottom: 1px solid var(--line-strong);
}
.tableau td {
  padding: 11px 14px 11px 0; border-bottom: 1px solid var(--line);
  vertical-align: top;
}
.tableau td.num {
  font-family: var(--f-mono); font-variant-numeric: tabular-nums;
  text-align: right; white-space: nowrap;
}
.defilant { overflow-x: auto; }

/* ---------- Liste de faits ---------- */
.faits { list-style: none; padding: 0; margin: 0; }
.faits li {
  padding: 13px 0; border-top: 1px solid var(--line); font-size: 16px;
}
.faits li:last-child { border-bottom: 1px solid var(--line); }
.faits b { font-weight: 600; }

/* ---------- Pied ---------- */
.pied { border-top: 1px solid var(--line); background: var(--paper); }
.pied-interieur {
  display: flex; gap: 40px; flex-wrap: wrap;
  padding: 40px 0; font-size: 14.5px; color: var(--muted);
}
.pied a { color: var(--muted); }
.pied-bloc h4 {
  font-family: var(--f-mono); font-size: 10.5px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--muted); margin-bottom: 12px;
}
.pied-bloc ul { list-style: none; padding: 0; margin: 0; }
.pied-bloc li { margin-bottom: 7px; }
.pied-mention {
  padding-bottom: 36px; font-size: 13px; color: var(--muted);
  max-width: 70ch;
}

@media (max-width: 720px) {
  h1 { font-size: 34px; }
  h2 { font-size: 25px; }
  .section { padding: 52px 0; }
  .chapeau { font-size: 18px; }
  .regle-ligne { grid-template-columns: 112px 1fr; }
  .regle-valeur { grid-column: 1 / -1; text-align: left; }
  .nav-liens { gap: 16px; }
}


/* ======================================================================
   SECTIONS SOMBRES
   ----------------------------------------------------------------------
   Le site n'avait que du blanc et du blanc lave : tout y pesait pareil.
   L'encre sert aux sections qui MONTRENT - le hero, la console - et le
   blanc a celles qui expliquent. Les jetons sont repris de la barre
   laterale de l'interface, pour que les deux surfaces se ressemblent.
   ====================================================================== */
.bande-nuit {
  background: var(--nuit); color: var(--nuit-texte);
  border-top: 1px solid var(--bord-nuit);
  border-bottom: 1px solid var(--bord-nuit);
}
.bande-nuit h1, .bande-nuit h2, .bande-nuit h3 { color: var(--nuit-fort); }
.bande-nuit .chapeau { color: var(--nuit-muet); }
.bande-nuit .surtitre { color: var(--nuit-faible); }
.bande-nuit a { color: var(--cobalt-clair); }

/* ======================================================================
   HERO
   ----------------------------------------------------------------------
   Pas de photographie. Les banques d'images libres n'ont rien d'utilisable
   sur la black mass, et une photo de batterie generique est ce que tous
   les concurrents affichent : elle ne dit rien d'une competence.
   Le fond est donc une TRAME calculee - la grille d'un instrument - et la
   seule image de la page est la figure, qui sort du moteur.
   ====================================================================== */
.hero {
  position: relative; overflow: hidden;
  background: var(--nuit); color: var(--nuit-texte);
  padding: 92px 0 84px;
}
/* Pas de trame en fond. Elle reposait sur deux degrades, interdits par
   la charte, et le hero ne perd rien a l'austerite : une encre pleine et
   un titre de 78 pixels suffisent amplement. */
.hero > * { position: relative; }
.hero h1 {
  color: var(--nuit-fort); font-size: clamp(38px, 6.2vw, 78px); line-height: 1.02;
  letter-spacing: -0.03em; max-width: 17ch;
}
.hero .chapeau { color: var(--nuit-muet); max-width: 54ch; }
.hero .surtitre { color: var(--marque); }

/* Le bandeau de preuve, sous le hero : trois chiffres du lot reel. */
.preuves {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 1px; background: var(--bord-nuit);
  border: 1px solid var(--bord-nuit); border-radius: 10px;
  overflow: hidden; margin-top: 46px;
}
.preuve { background: var(--nuit-claire); padding: 20px 22px; }
.preuve-val {
  font-family: var(--f-mono); font-size: 30px; font-weight: 500;
  color: var(--nuit-fort); font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
.preuve-cle {
  font-family: var(--f-mono); font-size: 10px; letter-spacing: .13em;
  text-transform: uppercase; color: var(--nuit-faible); margin-top: 8px;
  line-height: 1.5;
}

/* Le bouton creux est dessine pour le blanc : pose sur l'encre du hero,
   il disparaissait purement et simplement. */
.bouton-nuit {
  color: var(--nuit-texte); border-color: var(--nuit-filet);
  background: transparent;
}
.bouton-nuit:hover {
  color: var(--nuit-fort); border-color: var(--cobalt-clair);
  background: var(--voile-survol);
}

/* ======================================================================
   MOUVEMENT
   ----------------------------------------------------------------------
   Trois usages, et rien d'autre : reveler, compter, repondre. Tout est
   suspendu sous prefers-reduced-motion - la page s'affiche alors
   complete et immediate, et la console reste utilisable.
   ====================================================================== */
/* Le masquage est conditionne a `.js`, pose par un script en tete de
   document. Sans cette precaution, une erreur de script, un navigateur
   sans JavaScript ou un bloqueur laissaient une page VIDE : le contenu
   etait a opacite nulle et plus rien ne venait le reveler. Un site qui
   vend la prudence ne peut pas disparaitre en silence. */
.js [data-reveler] {
  opacity: 0; transform: translateY(16px);
  transition: opacity .62s cubic-bezier(.16,.84,.44,1),
              transform .62s cubic-bezier(.16,.84,.44,1);
  will-change: opacity, transform;
}
.js [data-reveler].vu { opacity: 1; transform: none; }

@media (prefers-reduced-motion: reduce) {
  .js [data-reveler] { opacity: 1; transform: none; transition: none; }
  * { animation: none !important; transition: none !important; }
}

/* ======================================================================
   CONSOLE D'IDENTIFIABILITE
   ----------------------------------------------------------------------
   Le visiteur coche les elements que son bulletin dose et lit, en direct,
   ce que ce bulletin determinerait. Les reponses sortent du moteur,
   pre-calculees a la construction : voir site/demo.py.
   ====================================================================== */
.console { margin-top: 38px; }
/* Le corps de la console ne disparait que si le script a DECLARE qu'il
   ne pouvait pas l'alimenter. Sans script du tout, le visiteur voit les
   douze phases et la selection de depart : il perd l'interaction, pas
   l'information. */
.console-indisponible .console-corps { display: none; }
.console-secours {
  display: none; color: var(--nuit-muet); font-size: 15px;
}
.console-indisponible .console-secours { display: block; }

/* Les COMMANDES et les MESURES n'ont aucun sens sans le script : les
   boutons ne repondraient pas, et les compteurs afficheraient quatre
   zeros, c'est-a-dire quatre chiffres faux. Elles n'apparaissent donc
   que si le script a annonce sa presence. La liste des douze phases,
   elle, reste : c'est de l'information, pas de l'interaction. */
.console-elements, .console-actions,
.console-mesures, .jauge-piste { display: none; }
.js .console-elements, .js .console-actions { display: flex; }
.js .console-mesures { display: grid; }
.js .jauge-piste { display: block; }

.console-elements {
  display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 26px;
}
.el {
  font-family: var(--f-mono); font-size: 15px; font-weight: 500;
  padding: 9px 15px; border-radius: 8px; cursor: pointer;
  background: transparent; color: var(--nuit-muet);
  border: 1px solid var(--bord-nuit);
  transition: background .18s, color .18s, border-color .18s;
}
.el:hover { color: var(--nuit-fort); border-color: var(--nuit-filet); }
.el[aria-pressed="true"] {
  background: var(--cobalt); border-color: var(--cobalt);
  color: var(--nuit-fort);
}
.el:focus-visible { outline: 2px solid var(--marque); outline-offset: 3px; }
.el-note {
  font-family: var(--f-mono); font-size: 10px; letter-spacing: .1em;
  text-transform: uppercase; color: var(--nuit-faible);
  margin-bottom: 10px;
}

.console-actions { display: flex; gap: 10px; margin-bottom: 30px; }
.console-actions button {
  font-family: var(--f-mono); font-size: 11px; letter-spacing: .1em;
  text-transform: uppercase; cursor: pointer; padding: 8px 14px;
  background: transparent; color: var(--nuit-muet);
  border: 1px solid var(--bord-nuit); border-radius: 7px;
  transition: color .18s, border-color .18s;
}
.console-actions button:hover {
  color: var(--nuit-fort); border-color: var(--nuit-filet);
}
.console-actions button:focus-visible {
  outline: 2px solid var(--marque); outline-offset: 3px;
}

.console-mesures {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
  gap: 1px; background: var(--bord-nuit);
  border: 1px solid var(--bord-nuit); border-radius: 10px;
  overflow: hidden; margin-bottom: 26px;
}
/* NOMMEES `console-*`. Appelees `.mesure`, elles ecrasaient l'utilitaire
   de largeur de ligne du meme nom, deja present dans la charte : tous les
   titres qui s'en servaient sortaient en rectangle sombre illisible. Une
   classe ajoutee ne doit jamais s'appeler comme une classe existante. */
.console-mesure { background: var(--nuit-claire); padding: 16px 18px; }
.console-mesure-val {
  font-family: var(--f-mono); font-size: 27px; font-weight: 500;
  color: var(--nuit-fort);
  font-variant-numeric: tabular-nums; line-height: 1;
}
.console-mesure-cle {
  font-family: var(--f-mono); font-size: 9.5px; letter-spacing: .12em;
  text-transform: uppercase; color: var(--nuit-faible);
  margin-top: 9px; line-height: 1.5;
}

.jauge-piste {
  height: 5px; border-radius: 3px; background: var(--bord-nuit);
  overflow: hidden; margin-bottom: 26px;
}
.jauge-part {
  height: 100%; background: var(--cobalt); border-radius: 3px;
  transition: width .45s cubic-bezier(.16,.84,.44,1);
}

.phases {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
  gap: 8px;
}
.phase {
  border: 1px solid var(--bord-nuit); border-radius: 9px;
  padding: 12px 13px; background: var(--nuit-claire);
  transition: border-color .25s, background .25s;
}
/* Une phase DETERMINEE passe au cobalt - la couleur qui, dans tout le
   produit, veut dire exactement cela. La console ne cree pas son propre
   vocabulaire de couleur. */
/* Un FILET epais a gauche, pas une ombre portee : la charte les
   interdit, et un filet dit la meme chose plus sechement. */
.phase-ferme {
  border-color: var(--cobalt); background: var(--cobalt-fonce);
  border-left-width: 3px;
}
.phase-nom {
  font-size: 13.5px; font-weight: 600; color: var(--nuit-texte);
  line-height: 1.25;
}
.phase-ferme .phase-nom { color: var(--nuit-fort); }
.phase-formule {
  font-family: var(--f-mono); font-size: 10px;
  color: var(--nuit-faible); margin-top: 5px; word-break: break-all;
}
.phase-etat {
  font-family: var(--f-mono); font-size: 9px; letter-spacing: .11em;
  text-transform: uppercase; margin-top: 9px;
  color: var(--nuit-faible);
}
.phase-ferme .phase-etat { color: var(--cobalt-clair); }
.phase-etat::after { content: attr(data-ouvert); }
.phase-ferme .phase-etat::after { content: attr(data-ferme); }

.verdict-console {
  margin-top: 26px; padding: 16px 20px; border-radius: 9px;
  border-left: 3px solid var(--marque); background: var(--nuit-claire);
  font-size: 15.5px; line-height: 1.55; color: var(--nuit-texte);
}
.verdict-console[data-etat="large"] { border-left-color: var(--cobalt); }

/* ======================================================================
   CARTES, AU SURVOL
   ====================================================================== */
/* Au survol, la carte se leve d'un cheveu et son filet se fonce. Pas
   d'ombre portee : la charte l'interdit. */
.carte { transition: transform .22s, border-color .22s; }
.carte:hover { transform: translateY(-2px); border-color: var(--line-strong); }

/* ======================================================================
   NAVIGATION COLLANTE
   ----------------------------------------------------------------------
   Les proprietes collantes sont posees sur la regle `.nav` D'ORIGINE, plus
   haut, et non dans une seconde regle du meme nom : deux declarations de
   fond sur un meme selecteur simple sont le debut d'une derive, et un
   test les interdit desormais.
   ====================================================================== */
.nav-compacte { border-bottom-color: var(--line-strong); }
.nav-compacte .nav-interieur { min-height: 54px; }
.nav-interieur { transition: min-height .25s; }

@media (max-width: 640px) {
  .hero { padding: 62px 0 56px; }
  .phases { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
}
"""


def feuille() -> str:
    """La feuille de style complete du site."""
    return racine() + "\n" + CORPS
