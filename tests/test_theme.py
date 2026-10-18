"""Tests de klastos/theme.py.

theme.py est le seul module qui ne calcule rien. Il n'en est pas moins
porteur d'un engagement, et c'est le meme que celui du reste de la chaine :

    UNE COULEUR NE DIT JAMAIS PLUS QUE CE QUE LA DONNEE PORTE.

Un lot mal determine qui ressort en bleu se lit comme un lot determine. La
faute est invisible au relecteur, elle ne leve aucune exception, et elle
survit a tous les tests numeriques du protocole : c'est precisement pour ca
qu'elle se teste ici. render_html.py garde la trace d'une occurrence reelle
(« un lot en alerte s'affichait en bleu comme conforme »).

Deux invariantes du module vivent deja dans test_charts.py, par voisinage de
sujet : l'absence de chiffre metier dans theme.py, et le partage de la
palette avec le rapport imprime. Elles ne sont pas reprises ici.
"""

import pathlib
import re
import tomllib

import pytest

from klastos import charts, theme

RACINE = pathlib.Path(__file__).resolve().parent.parent

#: Les trois gravites de bouclage que `render_html._tuiles` accepte. C'est le
#: vocabulaire de reference : l'ecran ne peut pas en teinter d'autres.
GRAVITES = {"ok", "alerte", "rejet"}

#: Seuil WCAG AA pour du texte courant.
AA = 4.5


def _sans_commentaires(css: str) -> str:
    """Le CSS prive de ses commentaires.

    Indispensable : les commentaires du module citent les selecteurs
    interdits, et une recherche naive les trouverait la.
    """
    return re.sub(r"/\*[\s\S]*?\*/", "", css)


def _luminance(hexa: str) -> float:
    """Luminance relative WCAG d'une couleur #RRGGBB."""
    brut = hexa.lstrip("#")
    canaux = [int(brut[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lineaire = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                for c in canaux]
    return 0.2126 * lineaire[0] + 0.7152 * lineaire[1] + 0.0722 * lineaire[2]


def _contraste(a: str, b: str) -> float:
    """Rapport de contraste WCAG entre deux couleurs, de 1 a 21."""
    haut, bas = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (haut + 0.05) / (bas + 0.05)


def _jetons() -> dict[str, str]:
    """Les jetons de couleur du module, par nom."""
    trouves = {}
    for nom in dir(theme):
        valeur = getattr(theme, nom)
        if nom.isupper() and isinstance(valeur, str) and valeur.startswith("#"):
            trouves[nom] = valeur
    return trouves


def _classe_de(statut) -> str:
    """La classe CSS que `chip` attribue a un statut."""
    trouve = re.search(r'class="chip (chip-\w+)"', theme.chip(statut, "x"))
    assert trouve is not None, theme.chip(statut, "x")
    return trouve[1]


# ==========================================================================
# 1. La pastille de statut ne surclasse jamais une phase
# ==========================================================================

def test_chaque_statut_connu_a_sa_pastille():
    assert _classe_de("ferme") == "chip-ferme"
    assert _classe_de("ferme_large") == "chip-large"
    assert _classe_de("ouvert") == "chip-ouvert"


@pytest.mark.parametrize("statut", ["", "inconnu", "FERME", "ferme "])
def test_un_statut_non_reconnu_retombe_sur_la_lecture_la_plus_prudente(statut):
    """
    LE VERROU DU MODULE. `chip` choisit par defaut, et son defaut doit etre
    « domaine compatible » - l'aveu d'ignorance. Un defaut sur « ferme »
    ferait passer une faute de frappe dans un statut pour une determination.
    Les variantes de casse et d'espace sont testees parce que c'est sous
    cette forme qu'une erreur arrive.
    """
    assert _classe_de(statut) == "chip-ouvert"


def test_les_trois_pastilles_sont_distinctes():
    """Trois etats de connaissance, trois rendus. Sinon l'ecran les fond."""
    classes = {_classe_de(s) for s in ("ferme", "ferme_large", "ouvert")}
    assert len(classes) == 3


def test_la_pastille_porte_le_libelle_transmis():
    assert ">determine<" in theme.chip("ferme", "determine")


def test_chaque_statut_de_phase_affiche_par_l_interface_est_stylable():
    """
    app.py appelle `theme.chip(s, charts.LIBELLE_STATUT[s])`. Toute classe
    que `chip` peut produire doit donc exister dans le CSS, sans quoi la
    pastille sort sans fond : un statut muet au lieu d'un statut lu.
    """
    for statut in charts.LIBELLE_STATUT:
        classe = _classe_de(statut)
        assert f".{classe} " in theme.CSS or f".{classe}{{" in theme.CSS


# ==========================================================================
# 2. La teinte de bouclage suit la gravite reelle
# ==========================================================================

def test_les_teintes_couvrent_exactement_les_gravites_du_rapport():
    """
    app.py lit `TEINTE_BOUCLAGE.get(statut, ...["ok"])`. Une gravite non
    prevue retomberait donc sur le vert du lot conforme : la table doit
    couvrir le vocabulaire en entier, pas s'en remettre au defaut.
    """
    assert set(theme.TEINTE_BOUCLAGE) == GRAVITES


def test_une_alerte_ne_se_confond_jamais_avec_un_lot_conforme():
    """
    LA REGRESSION DOCUMENTEE. Un lot en alerte s'est affiche en bleu comme
    conforme. Les trois gravites doivent se distinguer au texte comme au
    fond, independamment l'une de l'autre.
    """
    textes = {t for t, _ in theme.TEINTE_BOUCLAGE.values()}
    fonds = {f for _, f in theme.TEINTE_BOUCLAGE.values()}
    assert len(textes) == len(GRAVITES)
    assert len(fonds) == len(GRAVITES)


def test_chaque_teinte_est_un_jeton_de_la_palette():
    """Pas de couleur improvisee dans la table : charts.py relit la palette."""
    palette = set(_jetons().values())
    for gravite, (texte, fond) in theme.TEINTE_BOUCLAGE.items():
        assert texte in palette, gravite
        assert fond in palette, gravite


def test_le_texte_de_gravite_est_toujours_plus_sombre_que_son_fond():
    """
    Le couple est (texte, fond) et non (fond, texte). Inverse, le bandeau
    sort en texte pale sur fond sature : lisible nulle part, et l'erreur ne
    se voit pas dans la table.
    """
    for gravite, (texte, fond) in theme.TEINTE_BOUCLAGE.items():
        assert _luminance(texte) < _luminance(fond), gravite


# ==========================================================================
# 3. Lisibilite. Un rapport se lit a l'ecran d'un entrepot, pas en studio.
# ==========================================================================

def test_les_gravites_restent_lisibles_sur_leur_fond():
    for gravite, (texte, fond) in theme.TEINTE_BOUCLAGE.items():
        mesure = _contraste(texte, fond)
        assert mesure >= AA, f"{gravite} : {mesure:.2f}"


@pytest.mark.parametrize("encre,fond", [
    ("ENCRE", "PAPIER"), ("ENCRE", "CARTE"),
    ("ARDOISE", "CARTE"), ("ARDOISE", "PAPIER"),
    ("COBALT", "CARTE"), ("COBALT", "COBALT_PALE"),
    ("AMBRE", "AMBRE_PALE"), ("ROUILLE", "ROUILLE_PALE"),
])
def test_le_plan_de_travail_reste_lisible(encre, fond):
    """
    ARDOISE porte les notes de tuile et les sous-titres, du texte de 11,5
    px. C'est le couple le plus expose du theme : il ne peut pas descendre
    sous AA sous pretexte qu'il est secondaire.
    """
    mesure = _contraste(getattr(theme, encre), getattr(theme, fond))
    assert mesure >= AA, f"{encre}/{fond} : {mesure:.2f}"


@pytest.mark.parametrize("fond", ["NUIT", "NUIT_CLAIRE"])
def test_la_barre_laterale_reste_lisible(fond):
    """La barre est sombre par parti pris, pas au detriment du contraste."""
    mesure = _contraste("#D7DEEC", getattr(theme, fond))
    assert mesure >= AA, f"{fond} : {mesure:.2f}"


# ==========================================================================
# 4. Le CSS. Un selecteur trop large casse l'interface en silence.
# ==========================================================================

def test_le_css_est_un_bloc_style_complet():
    css = theme.CSS.strip()
    assert css.startswith("<style>")
    assert css.endswith("</style>")


def test_les_accolades_du_css_sont_equilibrees():
    """
    Une accolade perdue ne leve rien : le navigateur avale la regle suivante
    et une section entiere sort sans style.
    """
    css = _sans_commentaires(theme.CSS)
    assert css.count("{") == css.count("}")


def test_le_selecteur_de_classe_large_reste_interdit():
    """
    LA REGRESSION DOCUMENTEE PAR LE MODULE. Le selecteur sur les classes
    `st-` attrape aussi les spans d'icones de Streamlit et ecrase leur
    fonte : les ligatures Material ressortent en texte brut, « _arrow_right »
    a la place du chevron. Le commentaire du module le dit ; ce test
    l'empeche, commentaire retire pour ne pas se citer lui-meme.
    """
    assert '[class*="st-"]' not in _sans_commentaires(theme.CSS)


def test_les_icones_materiales_gardent_leur_fonte():
    """
    Le garde-fou complementaire : la regle qui reaffirme la fonte des icones
    doit etre presente et prioritaire, sinon la police generale la reprend.
    """
    css = _sans_commentaires(theme.CSS)
    bloc = re.search(r'\[data-testid="stIconMaterial"\][^}]*\}', css)
    assert bloc is not None
    assert "Material Symbols" in bloc[0]
    assert "!important" in bloc[0]


def test_le_theme_reste_clair():
    """
    Parti pris assume, inscrit dans config.toml : l'ecran et le rapport
    imprime partagent une palette, et un rapport s'imprime sur blanc. Une
    regle sombre conditionnelle desaccorderait les deux.
    """
    assert "prefers-color-scheme" not in theme.CSS


# ==========================================================================
# 5. Les polices. L'outil tourne sur un poste sans acces reseau.
# ==========================================================================

@pytest.mark.parametrize("pile", ["POLICE", "MONO"])
def test_chaque_pile_de_polices_finit_sur_une_famille_generique(pile):
    """
    Les IBM Plex viennent de Google Fonts. Si l'import echoue - poste hors
    ligne, reseau filtre - la pile doit retomber sur une famille que le
    systeme possede, pas sur la fonte par defaut du navigateur.
    """
    dernier = getattr(theme, pile).split(",")[-1].strip()
    assert dernier in {"sans-serif", "serif", "monospace"}


def test_les_polices_importees_sont_celles_que_le_css_utilise():
    """
    Un import qui ne sert pas est un aller-reseau pour rien ; une pile qui
    cite une fonte non importee tombe sur son recours sans qu'on le voie.
    """
    importees = {f.replace("+", " ")
                 for f in re.findall(r"family=([A-Za-z+]+)", theme.CSS)}
    assert importees
    piles = theme.POLICE + theme.MONO
    for fonte in importees:
        assert f'"{fonte}"' in piles, fonte


# ==========================================================================
# 6. Une seule palette. L'ecran et le graphique ne derivent pas.
# ==========================================================================

def test_tout_jeton_homonyme_de_charts_porte_la_meme_couleur():
    """
    theme.py se declare « une seule source, reprise par charts.py ». Rien ne
    le garantissait : TRAIT a vecu a deux valeurs, #DFE4EC a l'ecran et
    #DBE1E9 dans les axes de graphique et dans le rapport imprime. Deux gris
    a un pas l'un de l'autre ne se voient pas en relecture - ils se voient a
    l'ecran, ou le cadre d'une carte et l'axe du graphique qu'elle contient
    ne se repondent plus.

    Le test porte sur les homonymes : un jeton present des deux cotes sous le
    meme nom doit porter la meme couleur. Un jeton propre a un module reste
    libre (charts a ses gris de masse inexpliquee, theme ses tons de barre
    laterale).
    """
    communs = {n: v for n, v in _jetons().items() if hasattr(charts, n)}
    assert communs, "aucun jeton homonyme : la lecture du module a change"
    for nom, valeur in communs.items():
        assert valeur == getattr(charts, nom), (
            f"{nom} : theme {valeur} contre charts {getattr(charts, nom)}")


def test_le_trait_est_celui_du_rapport_imprime():
    """
    L'ancre de l'alignement ci-dessus. En cas de divergence, c'est le
    rapport imprime qui tranche - c'est lui qui sort de l'outil et qui se
    discute en reunion. `render_html` le nomme `--line`.
    """
    from klastos import render_html

    trouve = re.search(r"--line:\s*(#[0-9A-Fa-f]{6})", render_html.CSS)
    assert trouve is not None, "--line a disparu du rapport imprime"
    assert trouve[1].upper() == theme.TRAIT.upper(), (
        f"theme {theme.TRAIT} contre rapport imprime {trouve[1]}")


# ==========================================================================
# 7. Purete du module
# ==========================================================================

def test_le_theme_n_importe_rien():
    """
    theme.py est importe par app.py avant tout le reste. Une dependance ici
    - streamlit en tete - ferait du style un prealable au calcul, et le CLI
    trainerait l'interface derriere lui.
    """
    import ast

    src = (RACINE / "klastos" / "theme.py").read_text(encoding="utf-8")
    for noeud in ast.walk(ast.parse(src)):
        assert not isinstance(noeud, ast.Import)
        if isinstance(noeud, ast.ImportFrom):
            assert noeud.module == "__future__"


def test_aucun_jeton_n_est_orphelin():
    """
    Un jeton defini et jamais consomme est une couleur morte : le relecteur
    la croit en usage et l'ajuste sans effet visible. Un jeton compte comme
    consomme s'il teinte le CSS ou s'il passe par TEINTE_BOUCLAGE, que
    app.py pose en style en ligne.
    """
    for nom, valeur in _jetons().items():
        utilise = valeur in theme.CSS or any(
            valeur in couple for couple in theme.TEINTE_BOUCLAGE.values())
        assert utilise, nom


def test_le_theme_s_accorde_avec_la_configuration_streamlit():
    """
    config.toml teinte ce que le CSS ne peut pas atteindre : le chrome des
    widgets, le focus. Divergent, l'interface porte deux bleus.
    """
    conf = tomllib.loads(
        (RACINE / "config.toml").read_text(encoding="utf-8"))["theme"]
    assert conf["base"] == "light"
    assert conf["primaryColor"].upper() == theme.COBALT.upper()
    assert conf["textColor"].upper() == theme.ENCRE.upper()


def test_les_deux_config_toml_ne_divergent_pas():
    """
    Le depot en porte deux : la racine et .streamlit/. Streamlit lit celui
    de .streamlit/ ; le test precedent lit celui de la racine. S'ils
    divergent, le theme teste n'est pas le theme servi.
    """
    racine = (RACINE / "config.toml").read_text(encoding="utf-8")
    streamlit = (RACINE / ".streamlit" / "config.toml").read_text(
        encoding="utf-8")
    assert tomllib.loads(racine) == tomllib.loads(streamlit)
