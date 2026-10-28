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
.nav { border-bottom: 1px solid var(--line); background: var(--bg); }
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
"""


def feuille() -> str:
    """La feuille de style complete du site."""
    return racine() + "\n" + CORPS
