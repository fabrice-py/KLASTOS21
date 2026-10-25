"""
KLASTOS21 - Rendu HTML du rapport, pensé pour l'impression.

Pourquoi un rendu dédié
-----------------------
Le Markdown suffit à un relecteur technique. Il ne suffit pas à un négociant
qui décide d'engager 80 000 € sur une cargaison : un tableau de chiffres ne
montre pas qu'une grandeur ferme est un trait fin et qu'un domaine compatible
est une bande large. C'est précisément la distinction que KLASTOS21 vend.

D'où les BARRES D'INTERVALLE. Elles portent l'argument du produit mieux que
n'importe quelle phrase : on voit, d'un coup d'œil, ce qui est déterminé et
ce qui ne l'est pas.

Ce module ne calcule rien et ne décide rien. Il met en forme un `LotReport`
déjà assemblé.

Impression
----------
Le fichier s'ouvre dans un navigateur et s'imprime en PDF. Le format A4, les
sauts de page et les couleurs d'impression sont réglés en CSS. Volontairement
en thème clair uniquement : un rapport client sur fond sombre déconcerte, et
l'impression se fait toujours sur blanc.

Aucune dépendance : les polices web sont chargées depuis Google Fonts avec
une pile de repli système, et le fichier reste lisible hors ligne.
"""

from __future__ import annotations

import html as _html
import re as _re

from . import i18n
from .report import (SECTION_CONSEIL, SECTION_DIAGNOSTIC, SECTION_DRX,
                     SECTION_REDUIRE, SECTION_SCENARIO, SECTION_SENSIBLES,
                     SECTION_VALORISATION, TITRE_CONSEIL, TITRE_DRX,
                     TITRE_SCENARIO, LotReport, ReportRow, ReportSection)

# Statuts tels que le client les lit. Les tables portent desormais une CLE
# i18n et non le texte : le libelle est resolu au rendu, dans la langue du
# document. Les classes CSS, elles, sont de la presentation et ne se
# traduisent pas.
STATUTS = {
    "ferme": ("rapport.statut.html_ferme", "st-ferme"),
    "ferme_large": ("rapport.statut.html_ferme_large", "st-large"),
    "ouvert": ("rapport.statut.html_ouvert", "st-ouvert"),
}

# Sections dont les valeurs sont des largeurs, pas des positions : la barre
# part alors de zéro et la légende change. Construit a partir du vocabulaire,
# plus bas, pour que les deux ne puissent pas diverger.

# Dans une section de largeurs, `status` ne dit plus si la grandeur est
# identifiable : il dit si la largeur est RÉDUCTIBLE. Le vocabulaire doit
# donc changer, sans quoi le document affiche « ferme » en regard d'une
# fourchette de 20 points — exactement l'inverse de ce qu'il faut lire.
#
#   status "ferme"  -> largeur d'origine analytique, donc réductible
#   status "ouvert" -> largeur d'origine structurale, donc irréductible
STATUTS_LARGEUR = {
    "ferme": ("rapport.statut.html_reductible", "st-ferme", "b-ferme"),
    "ferme_large": ("rapport.statut.html_reductible", "st-ferme", "b-ferme"),
    "ouvert": ("rapport.statut.html_irreductible", "st-ouvert", "b-irr"),
}

# La section de scénario rapporte elle aussi des largeurs, mais le statut y
# répond à une troisième question : le dosage déterminerait-il la grandeur ?
STATUTS_SCENARIO = {
    "ferme": ("rapport.statut.deviendrait_ferme", "st-ferme", "b-ferme"),
    "ferme_large": ("rapport.statut.deviendrait_ferme", "st-ferme", "b-ferme"),
    "ouvert": ("rapport.statut.resterait_ouverte", "st-ouvert", "b-irr"),
}

# La section de quantification structurale rapporte un resserrement DEJA
# acquis, pas un potentiel : le statut y repond a une quatrieme question.
STATUTS_DRX = {
    "ferme": ("rapport.statut.resserree", "st-ferme", "b-ferme"),
    "ferme_large": ("rapport.statut.resserree", "st-ferme", "b-ferme"),
    "ouvert": ("rapport.statut.inchangee", "st-ouvert", "b-irr"),
}

# La section de conseil rapporte un gain a venir, conditionne a une mesure
# que le client n'a pas encore commandee.
STATUTS_CONSEIL = {
    "ferme": ("rapport.statut.gain_pire_cas", "st-ferme", "b-ferme"),
    "ferme_large": ("rapport.statut.gain_pire_cas", "st-ferme", "b-ferme"),
    "ouvert": ("rapport.statut.sans_effet", "st-ouvert", "b-irr"),
}

#: Vocabulaire applique a chaque section de largeurs. Une section absente de
#: cette table est une section de positions, pas de largeurs.
# Indexe par CLE de section, jamais par titre : le titre est du texte
# affiche, donc traduit. Indexe par titre, cette table se vidait
# silencieusement des que le document changeait de langue.
VOCABULAIRE_LARGEUR = {
    SECTION_REDUIRE: STATUTS_LARGEUR,
    SECTION_SENSIBLES: STATUTS_LARGEUR,
    SECTION_SCENARIO: STATUTS_SCENARIO,
    SECTION_DRX: STATUTS_DRX,
    SECTION_CONSEIL: STATUTS_CONSEIL,
}

SECTIONS_LARGEUR = frozenset(VOCABULAIRE_LARGEUR)

CSS = """
/* Identité KLASTOS21. Thème clair uniquement : destiné à l'impression. */
:root {
  --bg: #FFFFFF;
  --paper: #F7F8FA;
  --ink: #13171E;
  --muted: #5A6472;
  --line: #DBE1E9;
  --line-strong: #BFC8D4;
  --accent: #1F45C8;
  --accent-soft: #E9EDFB;
  --amber: #8A5410;
  --amber-soft: #F8EFDF;
  --rust: #9D3A1C;
  --rust-soft: #F9E9E2;
  /* Vert de bouclage conforme. Il manquait, et son absence n'etait pas
     neutre : la tuile « ok » sortait en var(--accent), soit en COBALT - la
     couleur qui signifie « grandeur determinee » dans la charte. Elle
     portait donc deux sens sur le meme document, alors que l'ecran
     affichait bien du vert pour cet etat. */
  --green: #0E7A5F;
  /* TIMES NEW ROMAN pour tout le document. C'est la police des pieces
     contractuelles, et un rapport qui se discute en reunion gagne a en
     avoir l'allure. L'ecran, lui, reste en IBM Plex Sans : les deux
     supports partagent la PALETTE, qui porte le sens, et non la police,
     qui porte le registre. */
  --f-display: "Times New Roman", Times, Georgia, serif;
  --f-body: "Times New Roman", Times, Georgia, serif;
  /* Les COLONNES DE CHIFFRES restent en chasse fixe. Times New Roman n'a
     pas de chiffres tabulaires : un « 1 » y est plus etroit qu'un « 8 »,
     et les virgules decimales d'une colonne cessent de s'aligner. Sur un
     tableau de teneurs, cet alignement est ce qui permet de comparer deux
     lignes d'un coup d'oeil. */
  --f-mono: "IBM Plex Mono", ui-monospace, "SF Mono", Consolas, monospace;
}
* { box-sizing: border-box; }
html { background: var(--paper); }
body {
  margin: 0 auto; max-width: 196mm; padding: 14mm 12mm 18mm;
  background: var(--bg); color: var(--ink);
  font-family: var(--f-body); font-size: 11pt; line-height: 1.45;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3 { font-family: var(--f-display); font-weight: 700; margin: 0; }
h1 { font-size: 20pt; letter-spacing: -0.02em; line-height: 1.1; }
h2 {
  font-size: 12pt; letter-spacing: -0.01em; margin: 0 0 6pt;
  padding-bottom: 4pt; border-bottom: 1.5pt solid var(--ink);
}
p { margin: 0; }
.mono { font-family: var(--f-mono); font-variant-numeric: tabular-nums; }

/* ---------- En-tête ---------- */
header { margin-bottom: 10mm; }
.marque {
  font-family: var(--f-display); font-weight: 700; font-size: 13pt;
  letter-spacing: 0.02em;
}
.marque span { color: var(--accent); }
.soustitre {
  font-family: var(--f-mono); font-size: 7.5pt; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--muted); margin-top: 2pt;
}
.titre-bloc {
  display: flex; justify-content: space-between; align-items: flex-end;
  gap: 10mm; margin-top: 7mm; padding-bottom: 4mm;
  border-bottom: 2pt solid var(--ink);
}
.meta {
  font-family: var(--f-mono); font-size: 8.5pt; color: var(--muted);
  text-align: right; white-space: nowrap;
}
.meta b { color: var(--ink); font-weight: 500; }

.banniere {
  margin: 6mm 0; padding: 4mm 5mm;
  background: var(--amber-soft); border-left: 3pt solid var(--amber);
  font-size: 9.5pt;
}
.banniere b { font-family: var(--f-display); }

/* ---------- Chiffre de tête ---------- */
.verdict {
  margin: 8mm 0; padding: 6mm 7mm;
  background: var(--accent-soft); border: 1pt solid var(--accent);
}
.verdict-k {
  font-family: var(--f-mono); font-size: 8pt; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--accent);
}
.verdict-v {
  font-family: var(--f-mono); font-size: 22pt; font-weight: 500;
  letter-spacing: -0.02em; color: var(--accent); margin-top: 2mm;
  font-variant-numeric: tabular-nums;
}
.verdict-n { font-size: 9pt; color: var(--muted); margin-top: 3mm; }

/* ---------- Tuiles de diagnostic ---------- */
/* Le cadre est volontairement plus fonce que les separateurs : une hairline
   en gris clair, posee au bord de la zone imprimable, disparait au tirage. */
.tuiles {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 1pt; background: var(--line-strong);
  border: 0.75pt solid var(--line-strong);
  margin-bottom: 8mm;
}
.tuile { background: var(--bg); padding: 4mm; }
.tuile-k {
  font-family: var(--f-mono); font-size: 7pt; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--muted);
}
.tuile-v {
  font-family: var(--f-mono); font-size: 13pt; font-weight: 500;
  margin-top: 1.5mm; font-variant-numeric: tabular-nums;
}
.tuile.ok .tuile-v { color: var(--green); }
.tuile.alerte .tuile-v { color: var(--amber); }
.tuile.rejet .tuile-v { color: var(--rust); }

/* ---------- Sections ---------- */
section { margin-bottom: 9mm; }
.intro { font-size: 9.5pt; color: var(--muted); margin-bottom: 4mm; }

table { width: 100%; border-collapse: collapse; font-size: 9.5pt; }
th {
  font-family: var(--f-mono); font-size: 7pt; font-weight: 500;
  letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted);
  text-align: left; padding: 0 3mm 2mm 0; border-bottom: 1pt solid var(--line);
}
td { padding: 2.2mm 3mm 2.2mm 0; border-bottom: 0.5pt solid var(--line); vertical-align: middle; }
tr:last-child td { border-bottom: 0; }
.c-lab { width: 33%; }
.c-bar { width: 27%; }
.c-val { width: 20%; text-align: right; white-space: nowrap; }
/* La precision relative : « ± 10 % ». Elle repond a la seule question
   qu'un acheteur pose devant un tableau de teneurs, et elle se compare
   d'une ligne a l'autre sans calcul. */
.c-prec { width: 11%; text-align: right; white-space: nowrap; }
.c-st  { width: 9%;  text-align: right; white-space: nowrap; }
.prec {
  font-family: var(--f-mono); font-size: 8.5pt; color: var(--muted);
  font-variant-numeric: tabular-nums;
}
.val {
  font-family: var(--f-mono); font-size: 9pt;
  font-variant-numeric: tabular-nums;
}
.st {
  font-family: var(--f-mono); font-size: 7pt; letter-spacing: 0.06em;
  text-transform: uppercase;
}
.st-ferme  { color: var(--accent); }
.st-large  { color: var(--amber); }
.st-ouvert { color: var(--rust); }

/* ---------- Barres d'intervalle ----------
   CE QUE LA BARRE DOIT DIRE, et ce qu'elle ne disait pas.
   L'acheteur n'a qu'une question : de combien ce chiffre peut-il bouger ?
   Donc la LARGEUR de l'intervalle, pas sa position.

   L'echelle est commune a la section - 0 a 50 % sur les teneurs - alors
   que les valeurs valent 2 a 5 %. La bande occupait donc 4 % de la piste,
   tassee a gauche, et l'intervalle d'une grandeur ferme - 0,66 point sur
   un axe de 50 - faisait moins d'un pixel. La barre ne disait rien de la
   fermete, qui est pourtant sa seule raison d'etre.

   Trois corrections. La piste est plus haute, donc une bande fine reste
   visible. Des reperes au quart, a la moitie et aux trois quarts rendent
   la position lisible sans lire l'echelle. Et toute bande recoit une
   largeur minimale : une grandeur ferme se lit alors comme un TRAIT NET,
   ce qui est exactement ce qu'elle est. */
.piste {
  position: relative; height: 11pt; background: var(--paper);
  border: 0.5pt solid var(--line-strong);
  /* Reperes au quart. Ils situent la valeur sans qu'on ait a lire les
     bornes de l'echelle sous le tableau. */
  background-image: repeating-linear-gradient(
    to right, transparent 0 calc(25% - 0.25pt),
    var(--line) calc(25% - 0.25pt) 25%);
}
.bande {
  position: absolute; top: 1.5pt; bottom: 1.5pt;
  border-radius: 0.5pt;
}
/* Largeur avant dosage : un fantôme hachuré, sous la bande du « après ». */
.avant {
  position: absolute; left: 0; top: 0; bottom: 0;
  background: repeating-linear-gradient(
    -45deg, var(--line-strong) 0 1pt, transparent 1pt 3pt);
  border-right: 0.5pt solid var(--muted);
}
/* Une grandeur FERME est un trait net : largeur minimale genereuse, pour
   qu'elle se lise comme une certitude et non comme une bande ecrasee. */
.b-ferme  { background: var(--accent); min-width: 3pt; }
.b-large  { background: var(--amber); min-width: 3pt; }
/* Un DOMAINE COMPATIBLE est une bande pleine et translucide, pas un
   contour vide : « large et flou » doit se voir comme tel. Le contour
   seul se lisait comme une boite, donc comme une borne nette. */
.b-ouvert {
  background: var(--rust); opacity: 0.30;
  border: 0.5pt solid var(--rust); min-width: 3pt;
}
.b-irr    { background: var(--rust); min-width: 3pt; }
.echelle {
  display: flex; justify-content: space-between;
  font-family: var(--f-mono); font-size: 6.5pt; color: var(--muted);
  margin-top: 1.5mm;
}

.legende {
  display: flex; flex-wrap: wrap; gap: 5mm; margin-top: 4mm;
  font-family: var(--f-mono); font-size: 7pt; color: var(--muted);
}
.legende i {
  display: inline-block; width: 8pt; height: 6pt; margin-right: 1.5mm;
  vertical-align: -0.5pt;
}
.lg-ferme { background: var(--accent); }
.lg-large { background: var(--amber); }
.lg-ouvert { background: var(--rust); opacity: 0.30;
             border: 0.5pt solid var(--rust); }
.lg-irr { background: var(--rust); }
.lg-avant {
  background: repeating-linear-gradient(
    -45deg, var(--line-strong) 0 1pt, transparent 1pt 3pt);
  border-right: 0.5pt solid var(--muted);
}

/* ---------- Notes, listes, annexes ---------- */
.note {
  font-size: 8.5pt; color: var(--muted); font-style: italic;
  margin-top: 3mm; padding-left: 3mm; border-left: 1.5pt solid var(--line-strong);
}
ul { margin: 0; padding-left: 5mm; font-size: 9.5pt; }
li { margin-bottom: 1.5mm; }
.annexe { font-size: 8.5pt; }
.annexe li { color: var(--muted); }
.avert li { color: var(--amber); }

footer {
  margin-top: 10mm; padding-top: 4mm; border-top: 1pt solid var(--line);
  font-size: 8pt; color: var(--muted);
}

/* ---------- Impression ---------- */
@page { size: A4; margin: 14mm 12mm 16mm; }
@media print {
  html, body { background: #FFF; }
  /* Le filet lateral de 0,75 pt n'est pas de la coquetterie : sans lui, les
     blocs encadres affleurent la zone imprimable et le navigateur rogne leur
     bordure droite. Le decalage est invisible, la bordure revient. */
  body { max-width: none; padding: 0 0.75pt; font-size: 9.5pt; }

  /* Les blocs courts restent d'un seul tenant. Les sections, elles, doivent
     pouvoir se couper : une section plus longue qu'une page, declaree
     insecable, est repoussee en entier et laisse une demi-page blanche. */
  .verdict, .tuiles, .banniere { break-inside: avoid; }
  tr, h2, .legende, .note { break-inside: avoid; }
  h2 { break-after: avoid; }
  thead { display: table-header-group; }   /* en-tetes repris apres un saut */
  a { color: inherit; text-decoration: none; }
}
"""


def _sans_commentaires(css: str) -> str:
    """
    La feuille de style, debarrassee de ses commentaires.

    POURQUOI. Les commentaires de `CSS` sont ecrits en francais et
    expliquent des choix de rendu : ils s'adressent a qui maintient le
    module, pas au destinataire du rapport. Ils partaient pourtant dans
    CHAQUE document livre, y compris les rapports anglais - ou le test de
    fuite de vocabulaire les a trouves, sur le mot « largeur ».

    Les retirer regle trois choses d'un coup : plus de francais dans un
    document anglais, un fichier plus leger, et un client qui ouvre la
    source ne lit pas nos notes de travail.

    La constante `CSS` garde ses commentaires : c'est elle que lisent les
    tests de charte et les relecteurs.
    """
    return _re.sub(r"/\*.*?\*/", "", css, flags=_re.S)


#: Ce qui part reellement dans le document livre. Calcule une fois.
CSS_LIVRE = _sans_commentaires(CSS)


def _e(texte: object) -> str:
    """Échappe tout texte inséré dans le document."""
    return _html.escape(str(texte if texte is not None else ""))


def _echelle(section: ReportSection) -> float:
    """
    Échelle commune à une section, pour que les barres soient comparables
    entre elles. Arrondie au palier supérieur, jamais nulle.

    `point` entre dans le calcul : dans la section de scénario il porte la
    largeur AVANT dosage, qui est dessinée en fantôme derrière la largeur
    après. Sans lui, l'échelle serait réglée sur les seules largeurs
    restantes et le « avant » sortirait de la piste.
    """
    hauts = [r.high for r in section.rows if r.has_bar and r.high is not None]
    hauts += [r.point for r in section.rows if r.has_bar and r.point is not None]
    if not hauts:
        return 1.0
    pic = max(hauts)
    for palier in (0.05, 0.1, 0.25, 0.5, 0.75, 1.0):
        if pic <= palier:
            return palier
    return 1.0


def _barre(ligne: ReportRow, echelle: float, vocabulaire: dict | None = None) -> str:
    if not ligne.has_bar:
        return ""
    if vocabulaire is not None:
        classe = vocabulaire.get(ligne.status, ("", "", "b-irr"))[2]
    else:
        classe = {"ferme": "b-ferme", "ferme_large": "b-large"}.get(
            ligne.status, "b-ouvert"
        )
    gauche = max(0.0, min(100.0, (ligne.low / echelle) * 100.0))
    largeur = max(0.0, min(100.0 - gauche,
                           ((ligne.high - ligne.low) / echelle) * 100.0))

    # Fantôme du « avant ». Sans lui, une grandeur que le dosage détermine
    # s'affiche en barre vide : le lecteur voit ce qui reste, jamais ce qui
    # a disparu, c'est-à-dire exactement le gain que la section annonce.
    fantome = ""
    if ligne.point is not None and ligne.point > ligne.high:
        av = max(0.0, min(100.0, (ligne.point / echelle) * 100.0))
        fantome = f'<span class="avant" style="width:{av:.2f}%"></span>'

    return (f'<div class="piste">{fantome}<span class="bande {classe}" '
            f'style="left:{gauche:.2f}%;width:{largeur:.2f}%"></span></div>')


def _precision(ligne: ReportRow, lg: str) -> str:
    """
    La demi-largeur de l'intervalle, en pourcentage de la valeur centrale.

    POURQUOI CETTE COLONNE EXISTE. L'acheteur n'a qu'une question devant un
    tableau de teneurs : de combien ce chiffre peut-il bouger ? La reponse
    etait dans la colonne VALEUR - « 3,19 [2,86 - 3,52] % » - mais elle
    demandait un calcul mental, ligne par ligne, pour comparer deux
    elements.

    La barre ne la donnait pas davantage : l'echelle est commune a la
    section, 0 a 50 % sur les teneurs, et dix lignes sur quatorze valent
    moins de 5 %. Elles rendaient donc toutes la meme petite marque.

    « ± 10 % » se lit d'un coup d'oeil et se compare d'une ligne a l'autre.

    Rien n'est affiche quand la valeur centrale manque : un DOMAINE
    COMPATIBLE n'en a pas, et en inventer une - le milieu de la plage -
    serait exactement le representant arbitraire que ce rapport refuse de
    presenter comme une estimation.
    """
    if ligne.point is None or ligne.low is None or ligne.high is None:
        return ""
    if ligne.point <= 0:
        return ""
    relatif = (ligne.high - ligne.low) / 2.0 / ligne.point
    if relatif > 1.0:
        return i18n.t("rapport.doc.precision_large", lg)
    return f"± {relatif * 100:.0f} %"


def _tableau(section: ReportSection, lg: str = i18n.DEFAUT) -> str:
    echelle = _echelle(section)
    avec_barres = any(r.has_bar for r in section.rows)
    # Par la CLE, jamais par le titre : le titre est traduit.
    vocabulaire = VOCABULAIRE_LARGEUR.get(section.cle)
    largeur = vocabulaire is not None

    L: list[str] = ["<table>", "<thead><tr>",
                    f'<th class="c-lab">'
                    f'{_e(i18n.t("rapport.doc.col_grandeur", lg))}</th>']
    if avec_barres:
        entete = i18n.t("rapport.doc.col_largeur" if largeur
                        else "rapport.doc.col_domaine", lg)
        L.append(f'<th class="c-bar">{_e(entete)}</th>')
    # La colonne n'apparait que si la section porte de vraies VALEURS
    # CENTRALES. Deux cas l'excluent, et le second etait un piege.
    #
    # Une section de DOMAINES COMPATIBLES n'a pas de valeur centrale : une
    # colonne vide y suggererait qu'il manque quelque chose.
    #
    # Et dans les sections de LARGEUR - reduire, sensibles, scenario, drx,
    # conseil - le champ `point` ne porte PAS une valeur centrale mais la
    # largeur AVANT dosage, dessinee en fantome derriere la largeur apres.
    # La formule y rendait « ± 0 % », c'est-a-dire une precision parfaite,
    # sur des lignes qui mesurent une incertitude. Exactement l'inverse de
    # ce que le tableau dit.
    avec_precision = not largeur and any(
        r.point is not None and r.low is not None for r in section.rows)
    L.append(f'<th class="c-val">'
             f'{_e(i18n.t("rapport.doc.col_valeur", lg))}</th>')
    if avec_precision:
        L.append(f'<th class="c-prec">'
                 f'{_e(i18n.t("rapport.doc.col_precision", lg))}</th>')
    L += [f'<th class="c-st">{_e(i18n.t("rapport.doc.col_statut", lg))}</th>',
          "</tr></thead><tbody>"]

    for r in section.rows:
        if largeur:
            cle_st, classe, _ = vocabulaire.get(r.status, ("", "", ""))
        else:
            cle_st, classe = STATUTS.get(r.status, ("", ""))
        libelle = i18n.t(cle_st, lg) if cle_st else ""
        L.append("<tr>")
        L.append(f'<td class="c-lab">{_e(r.label)}</td>')
        if avec_barres:
            L.append(f'<td class="c-bar">{_barre(r, echelle, vocabulaire)}</td>')
        L.append(f'<td class="c-val val">{_e(r.value)}</td>')
        if avec_precision:
            L.append(f'<td class="c-prec prec">'
                     f'{_e(_precision(r, lg))}</td>')
        L.append(f'<td class="c-st"><span class="st {classe}">'
                 f'{_e(libelle)}</span></td>')
        L.append("</tr>")
    L.append("</tbody></table>")

    if avec_barres:
        unite = i18n.t("rapport.doc.unite_points", lg) if largeur else "%"
        L.append(f'<div class="echelle"><span>0 {_e(unite)}</span>'
                 f'<span>{echelle * 100:.0f} {_e(unite)}</span></div>')
        statuts = {r.status for r in section.rows if r.has_bar}
        items = []
        if largeur:
            # La legende est DERIVEE du vocabulaire de la section : les deux
            # ne peuvent donc pas se contredire, ce qui est arrive.
            if any(r.point is not None and r.high is not None
                   and r.point > r.high for r in section.rows):
                items.append(
                    f'<span><i class="lg-avant"></i>'
                    f'{_e(i18n.t("rapport.legende.largeur_actuelle", lg))}'
                    f"</span>")
            vus: set[str] = set()
            for statut in ("ferme", "ferme_large", "ouvert"):
                if statut not in statuts or statut not in vocabulaire:
                    continue
                cle_lib, _, classe_barre = vocabulaire[statut]
                libelle = i18n.t(cle_lib, lg)
                if libelle in vus:
                    continue
                vus.add(libelle)
                pastille = "lg-" + classe_barre.removeprefix("b-")
                items.append(f'<span><i class="{pastille}"></i>'
                             f'{_e(libelle)}</span>')
        else:
            for statut, classe, cle_lib in (
                ("ferme", "lg-ferme", "rapport.legende.ferme"),
                ("ferme_large", "lg-large", "rapport.legende.mal_determine"),
                ("ouvert", "lg-ouvert", "rapport.legende.domaine"),
            ):
                if statut in statuts:
                    items.append(f'<span><i class="{classe}"></i>'
                                 f'{_e(i18n.t(cle_lib, lg))}</span>')
        if items:
            L.append(f'<div class="legende">{"".join(items)}</div>')
    return "".join(L)


def _tuiles(rapport: LotReport) -> str:
    """
    Bandeau de diagnostic, extrait de la première section.

    La gravité est lue dans `ReportRow.severity`, qui est une donnée produite
    par `build_report`. Elle n'est jamais devinée en cherchant un mot dans le
    message : le message d'un bouclage dégradé ne contient pas le mot
    « alerte », et un lot en alerte s'affichait en bleu comme conforme.
    """
    diag = rapport.section(SECTION_DIAGNOSTIC)
    if diag is None or not diag.rows:
        return ""
    autorisees = {"ok", "alerte", "rejet"}
    colonnes = max(1, min(4, len(diag.rows)))
    L = [f'<div class="tuiles" style="grid-template-columns:'
         f'repeat({colonnes},1fr)">']
    for r in diag.rows:
        classe = r.severity if r.severity in autorisees else "ok"
        L.append(
            f'<div class="tuile {classe}">'
            f'<div class="tuile-k">{_e(r.label)}</div>'
            f'<div class="tuile-v">{_e(r.value)}</div></div>'
        )
    L.append("</div>")
    return "".join(L)


def _verdict(rapport: LotReport) -> str:
    """Le prix maximal à payer, en tête : c'est ce que le lecteur cherche."""
    lg = i18n.langue_valide(rapport.langue)
    val = rapport.section(SECTION_VALORISATION)
    if val is None:
        return (
            '<div class="verdict"><div class="verdict-k">'
            f'{_e(i18n.t("rapport.section.valorisation", lg))}</div>'
            '<div class="verdict-v" style="font-size:13pt">'
            f'{_e(i18n.t("rapport.verdict.non_calculee", lg))}</div>'
            '<div class="verdict-n">'
            f'{_e(i18n.t("rapport.verdict.sans_prix", lg))}</div></div>'
        )
    ligne = next((r for r in val.rows if "MAXIMAL" in r.label.upper()), None)
    if ligne is None:
        return ""
    return (
        '<div class="verdict">'
        '<div class="verdict-k">'
        f'{_e(i18n.t("rapport.verdict.prix_maximal", lg))}</div>'
        f'<div class="verdict-v">{_e(ligne.value)}</div>'
        '<div class="verdict-n">'
        f'{_e(i18n.t("rapport.verdict.base_prix", lg))}</div></div>'
    )


def to_html(rapport: LotReport) -> str:
    """Rend le rapport en un document HTML autonome, prêt à imprimer."""
    lg = i18n.langue_valide(rapport.langue)
    L: list[str] = [
        "<!doctype html>", f'<html lang="{lg}">', "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>KLASTOS21 : lot {_e(rapport.lot_id)}</title>",
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Archivo:wght@600;700&family=IBM+Plex+Mono:wght@400;500&'
        'family=IBM+Plex+Sans:wght@400;500&display=swap">',
        f"<style>{CSS_LIVRE}</style>", "</head>", "<body>",
    ]

    # --- en-tête ---------------------------------------------------------
    L += [
        "<header>",
        '<div class="marque">KLASTOS<span>21</span></div>',
        f'<div class="soustitre">'
        f'{_e(i18n.t("rapport.doc.soustitre", lg))}</div>',
        '<div class="titre-bloc">',
        f'<h1>{_e(i18n.t("rapport.doc.titre_nu", lg))}<br>'
        f"{_e(rapport.lot_id)}</h1>",
        '<div class="meta">'
        f'{_e(i18n.t("rapport.doc.client", lg))}&nbsp;: '
        f"<b>{_e(rapport.client)}</b><br>"
        f'{_e(i18n.t("rapport.doc.emis_le", lg))} '
        f"<b>{_e(rapport.issued_on.isoformat())}</b><br>"
        f'{_e(i18n.t("rapport.doc.degres", lg))}&nbsp;: <b>'
        f"{_e(rapport.meta.get('degeneracy', 'n.d.'))}</b>"
        "</div>",
        "</div>", "</header>",
    ]

    if rapport.is_demo:
        L.append(
            '<div class="banniere"><b>Document de démonstration, non '
            'opposable.</b> Il repose sur des données ou des prix non '
            'destinés à la production, et ne constitue ni une offre '
            'commerciale ni une évaluation opposable.</div>'
        )

    L.append(_verdict(rapport))
    L.append(_tuiles(rapport))

    # --- sections --------------------------------------------------------
    for s in rapport.sections:
        if s.cle == SECTION_DIAGNOSTIC:
            continue                      # déjà rendu en tuiles
        L.append("<section>")
        L.append(f"<h2>{_e(s.title)}</h2>")
        if s.intro:
            L.append(f'<p class="intro">{_e(s.intro)}</p>')
        if s.rows:
            L.append(_tableau(s, lg))
        for n in s.notes:
            L.append(f'<p class="note">{_e(n)}</p>')
        L.append("</section>")

    # --- annexes ---------------------------------------------------------
    for cle_titre, elements, classe in (
        ("rapport.section.avertissements", rapport.warnings, "annexe avert"),
        ("rapport.section.limites", rapport.limitations, "annexe"),
        ("rapport.section.tracabilite", rapport.traceability, "annexe"),
    ):
        titre = i18n.t(cle_titre, lg)
        if not elements:
            continue
        L.append("<section>")
        L.append(f"<h2>{_e(titre)}</h2>")
        L.append(f'<ul class="{classe}">')
        L += [f"<li>{_e(x)}</li>" for x in elements]
        L.append("</ul></section>")

    L += [
        f'<footer>{_e(i18n.t("rapport.doc.pied", lg))} '
        f'{_e(i18n.t("rapport.protocole.renvoi", lg))}</footer>',
        "</body>", "</html>",
    ]
    return "\n".join(L)