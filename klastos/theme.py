"""
KLASTOS21 - Habillage de l'interface.

Ce module ne contient que du style. Aucune valeur, aucun calcul, aucune
decision : si un chiffre apparait ici, c'est une erreur.

Parti pris
----------
L'ecran et le rapport imprime partagent la meme palette - cobalt pour ce qui
est determine, ambre pour ce qui est mal determine, rouille pour un domaine
compatible. Un negociant qui lit l'ecran puis le PDF ne doit pas avoir
l'impression de changer d'outil.

La barre laterale est sombre, le plan de travail clair. C'est la disposition
des consoles d'exploitation : la navigation recule, la donnee avance.
"""

from __future__ import annotations

# ==========================================================================
# Jetons de couleur. Une seule source, reprise par charts.py.
# ==========================================================================

NUIT = "#0E1526"          # barre laterale
NUIT_CLAIRE = "#17203A"   # element actif de la barre
BORD_NUIT = "#223052"

PAPIER = "#F4F6FA"        # fond du plan de travail
CARTE = "#FFFFFF"
TRAIT = "#DBE1E9"
TRAIT_FORT = "#C3CBD8"

ENCRE = "#13171E"
ARDOISE = "#5A6472"

COBALT = "#1F45C8"
COBALT_PALE = "#EAEFFC"
AMBRE = "#8A5410"
AMBRE_PALE = "#FBF2E2"
ROUILLE = "#9D3A1C"
ROUILLE_PALE = "#FAEAE4"
VERT = "#0E7A5F"
VERT_PALE = "#E6F4EF"

POLICE = '"IBM Plex Sans", -apple-system, "Segoe UI", Roboto, sans-serif'
MONO = '"IBM Plex Mono", ui-monospace, Consolas, monospace'

#: Couleur de fond et de texte par statut de bouclage.
TEINTE_BOUCLAGE = {
    "ok": (VERT, VERT_PALE),
    "alerte": (AMBRE, AMBRE_PALE),
    "rejet": (ROUILLE, ROUILLE_PALE),
}


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

/* NE PAS elargir ce selecteur. `[class*="st-"]` attrape aussi les spans
   d'icones de Streamlit et ecrase leur fonte : les ligatures Material
   ressortent alors en texte brut, « _arrow_right » a la place du chevron. */
.stApp, .stApp p, .stApp label, .stApp span, .stApp div,
.stApp h1, .stApp h2, .stApp h3, .stApp button, .stApp input {{
  font-family: {POLICE};
}}
[data-testid="stIconMaterial"], .material-symbols-rounded,
[class*="material-symbols"] {{
  font-family: "Material Symbols Rounded", "Material Symbols Outlined" !important;
}}
.stApp {{ background: {PAPIER}; }}

/* Streamlit laisse un bandeau vide en haut : on le recupere. */
header[data-testid="stHeader"] {{ background: transparent; height: 0; }}
.block-container {{ padding: 1.4rem 2rem 3rem; max-width: 1560px; }}

/* ---------- Barre laterale ---------- */
section[data-testid="stSidebar"] {{
  background: {NUIT};
  border-right: 1px solid {BORD_NUIT};
}}
section[data-testid="stSidebar"] * {{ color: #D7DEEC; }}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{ color: #FFFFFF; }}
section[data-testid="stSidebar"] .stRadio > div {{ gap: 2px; }}
section[data-testid="stSidebar"] label {{
  font-size: 0.92rem; padding: 2px 0;
}}
section[data-testid="stSidebar"] [data-testid="stExpander"] {{
  background: {NUIT_CLAIRE}; border: 1px solid {BORD_NUIT};
  border-radius: 10px;
}}
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] [data-baseweb="select"] > div {{
  background: {NUIT_CLAIRE} !important; border-color: {BORD_NUIT} !important;
  color: #EEF2F9 !important;
}}

.marque {{
  display: flex; align-items: center; gap: 10px;
  padding: 4px 0 18px; border-bottom: 1px solid {BORD_NUIT};
  margin-bottom: 16px;
}}
.marque-cube {{
  width: 38px; height: 38px; border-radius: 10px; flex: 0 0 38px;
  background: linear-gradient(135deg, #2E5BE8 0%, #1B3BA8 100%);
  display: flex; align-items: center; justify-content: center;
  color: #FFF; font-weight: 700; font-size: 15px;
  box-shadow: 0 4px 14px rgba(31,69,200,.35);
}}
.marque-nom {{
  font-size: 19px; font-weight: 700; letter-spacing: .01em; color: #FFF;
  line-height: 1.1;
}}
.marque-nom span {{ color: #7FA0FF; }}
.marque-sous {{
  font-family: {MONO}; font-size: 8.5px; letter-spacing: .1em;
  text-transform: uppercase; color: #7A88A8; margin-top: 3px;
}}

.etat-systeme {{
  margin-top: 18px; padding: 11px 13px; border-radius: 10px;
  background: {NUIT_CLAIRE}; border: 1px solid {BORD_NUIT};
  font-size: 12px;
}}
.etat-systeme b {{ color: #FFF; font-weight: 600; }}
.pastille-verte {{
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: #35C48E; margin-right: 7px; vertical-align: 1px;
}}

/* ---------- En-tete du plan de travail ---------- */
.fil {{
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 14px;
}}
.fil-gauche {{ font-size: 13px; color: {ARDOISE}; }}
.fil-gauche b {{ color: {ENCRE}; font-weight: 600; }}
.fil-sep {{ margin: 0 9px; color: {TRAIT_FORT}; }}

.heros {{
  background: linear-gradient(100deg, #FFFFFF 0%, #FFFFFF 58%, {COBALT_PALE} 100%);
  border: 1px solid {TRAIT}; border-radius: 14px;
  padding: 20px 24px; margin-bottom: 16px;
  display: flex; align-items: center; justify-content: space-between; gap: 22px;
}}
.heros h1 {{
  font-size: 23px; font-weight: 700; color: {ENCRE}; margin: 0 0 5px;
  letter-spacing: -.015em;
}}
.heros p {{ font-size: 13.5px; color: {ARDOISE}; margin: 0; max-width: 640px; }}
.heros-note {{
  border-left: 2px solid {COBALT}; padding-left: 14px; min-width: 215px;
}}
.heros-note b {{ font-size: 13px; color: {ENCRE}; }}
.heros-note span {{ font-size: 12px; color: {ARDOISE}; display: block;
                    margin-top: 3px; line-height: 1.45; }}

/* ---------- Cartes ----------
   Les cartes sont des st.container(border=True). Envelopper des widgets
   Streamlit dans un <div> injecte ne marche pas : le <div> se ferme seul et
   laisse une boite blanche vide au-dessus du contenu. */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background: {CARTE}; border: 1px solid {TRAIT} !important;
  border-radius: 14px; padding: 15px 18px;
}}
section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {{
  background: {NUIT_CLAIRE}; border-color: {BORD_NUIT} !important;
}}
.carte {{
  background: {CARTE}; border: 1px solid {TRAIT}; border-radius: 14px;
  padding: 17px 19px; margin-bottom: 14px;
}}
.carte-titre {{
  display: flex; align-items: center; gap: 9px;
  font-size: 14.5px; font-weight: 600; color: {ENCRE}; margin-bottom: 12px;
}}
.puce {{
  width: 21px; height: 21px; border-radius: 50%; flex: 0 0 21px;
  background: {COBALT}; color: #FFF; font-size: 11px; font-weight: 600;
  display: inline-flex; align-items: center; justify-content: center;
}}

/* ---------- Bandeau de resultat ---------- */
.bandeau {{
  display: flex; align-items: center; justify-content: space-between;
  border-radius: 12px; padding: 13px 18px; margin-bottom: 14px;
  border: 1px solid; gap: 16px;
}}
.bandeau-titre {{ font-size: 14.5px; font-weight: 600; }}
.bandeau-sous {{ font-size: 12.5px; opacity: .85; margin-top: 2px; }}
.bandeau-droite {{
  font-family: {MONO}; font-size: 11.5px; text-align: right;
  white-space: nowrap; opacity: .9;
}}

/* ---------- Tuiles de mesure ---------- */
.tuile {{
  background: {CARTE}; border: 1px solid {TRAIT}; border-radius: 12px;
  padding: 14px 16px; height: 100%;
}}
.tuile-k {{
  font-family: {MONO}; font-size: 9.5px; letter-spacing: .09em;
  text-transform: uppercase; color: {ARDOISE};
}}
.tuile-v {{
  font-family: {MONO}; font-size: 25px; font-weight: 500; color: {ENCRE};
  margin-top: 5px; letter-spacing: -.02em; line-height: 1.15;
}}
.tuile-n {{ font-size: 11.5px; color: {ARDOISE}; margin-top: 4px; }}
.tuile.ok .tuile-v {{ color: {VERT}; }}
.tuile.alerte .tuile-v {{ color: {AMBRE}; }}
.tuile.rejet .tuile-v {{ color: {ROUILLE}; }}
.tuile.prix .tuile-v {{ color: {COBALT}; font-size: 22px; }}

/* ---------- Pastilles de statut ---------- */
.chip {{
  display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-family: {MONO}; font-size: 10px; letter-spacing: .03em;
  white-space: nowrap;
}}
.chip-ferme {{ background: {COBALT_PALE}; color: {COBALT}; }}
.chip-large {{ background: {AMBRE_PALE}; color: {AMBRE}; }}
.chip-ouvert {{ background: {ROUILLE_PALE}; color: {ROUILLE}; }}

/* ---------- Tableau de phases ---------- */
table.phases {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
table.phases th {{
  font-family: {MONO}; font-size: 9.5px; letter-spacing: .08em;
  text-transform: uppercase; color: {ARDOISE}; text-align: left;
  padding: 0 10px 7px 0; border-bottom: 1px solid {TRAIT}; font-weight: 500;
}}
table.phases td {{
  padding: 8px 10px 8px 0; border-bottom: 1px solid #EFF2F6;
  color: {ENCRE}; vertical-align: middle;
}}
table.phases tr:last-child td {{ border-bottom: 0; }}
table.phases td.num {{
  font-family: {MONO}; font-size: 11.5px; text-align: right;
  white-space: nowrap; width: 1%;
}}
table.phases td:first-child {{ line-height: 1.35; }}
.point {{
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  margin-right: 8px; vertical-align: 0;
}}

/* ---------- Encart methode ---------- */
.methode {{
  background: {COBALT_PALE}; border-left: 3px solid {COBALT};
  border-radius: 0 10px 10px 0; padding: 12px 15px; margin-top: 12px;
  font-size: 12.5px; color: #1B2A52; line-height: 1.55;
}}
.methode b {{ color: {COBALT}; }}

/* ---------- Boutons et onglets ---------- */
.stButton > button[kind="primary"] {{
  background: linear-gradient(135deg, #2E5BE8 0%, {COBALT} 100%);
  border: 0; border-radius: 10px; font-weight: 600; padding: .6rem 1rem;
  box-shadow: 0 4px 14px rgba(31,69,200,.28);
}}
.stButton > button[kind="secondary"] {{
  border-radius: 10px; border-color: {TRAIT};
}}
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 1px solid {TRAIT}; }}
.stTabs [data-baseweb="tab"] {{
  font-size: 13.5px; font-weight: 500; padding: 9px 15px;
}}
[data-testid="stFileUploaderDropzone"] {{
  background: #FAFBFD; border: 1.5px dashed {TRAIT_FORT}; border-radius: 12px;
}}
[data-testid="stExpander"] {{
  border: 1px solid {TRAIT}; border-radius: 12px; background: {CARTE};
}}
div[data-testid="stVegaLiteChart"] {{ overflow: visible; }}
</style>
"""


def chip(statut: str, libelle: str) -> str:
    """Pastille de statut, en HTML. `statut` vaut ferme, ferme_large, ouvert."""
    classe = {"ferme": "chip-ferme", "ferme_large": "chip-large"}.get(
        statut, "chip-ouvert")
    return f'<span class="chip {classe}">{libelle}</span>'