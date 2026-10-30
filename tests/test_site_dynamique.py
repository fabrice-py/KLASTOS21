"""Tests du site vitrine : la console, le mouvement, et la cascade.

TROIS EXIGENCES, DANS CET ORDRE DE GRAVITE
-------------------------------------------
1. La console ne MENT pas. Ce qu'elle affiche sort du moteur qui produit
   les rapports clients, pas d'une maquette ecrite a la main. Un test
   compare les chiffres de la page a ce que le moteur repond aujourd'hui.

2. La page ne DISPARAIT pas. Le contenu est masque pour etre revele au
   defilement : si le script echoue, si le visiteur l'a desactive ou si un
   bloqueur s'en mele, tout doit rester lisible. Un site qui vend la
   prudence ne peut pas se vider en silence.

3. La cascade ne se MORD pas la queue. Une classe ajoutee qui porte le nom
   d'une classe existante en change le sens partout ailleurs. C'est arrive
   : `.mesure` est l'utilitaire de largeur de ligne du site, et la console
   l'a redefini en carte sombre. Tous les titres qui s'en servaient sont
   sortis en rectangle illisible.
"""

import json
import pathlib
import re
import sys

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "site"))

import charte          # noqa: E402
import contenu         # noqa: E402
import construire      # noqa: E402
import demo            # noqa: E402
import mouvement       # noqa: E402

PUBLIC = RACINE / "site" / "public"
PAGES = ("index", "methode", "rapport", "prix", "missions", "contact")


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    sortie = tmp_path_factory.mktemp("site_dyn")
    construire.construire(sortie)
    return sortie


def _page(site, nom="index", langue="fr") -> str:
    return (site / langue / f"{nom}.html").read_text(encoding="utf-8")


# ==========================================================================
# 1. La console dit ce que le moteur repond
# ==========================================================================

def test_les_donnees_de_la_console_sortent_du_moteur(site):
    """
    LE TEST QUI COMPTE. La page affirme que ses reponses viennent du
    moteur. On le verifie en rejouant le calcul : si quelqu'un fige un
    jour la table a la main, ou si le modele de phases change sans que la
    page suive, ce test tombe.
    """
    html = _page(site)
    brut = html[html.index('id="demo-donnees">') + len('id="demo-donnees">'):]
    brut = brut[:brut.index("</script>")]
    page = json.loads(brut)

    moteur = demo.balayage()
    assert page["elements"] == moteur["elements"]
    assert page["table"] == moteur["table"], (
        "la table de la console ne correspond plus a ce que le moteur "
        "repond : la page ment sur le produit")


def test_la_console_couvre_toutes_les_combinaisons():
    d = demo.balayage()
    assert len(d["table"]) == 2 ** len(d["elements"]) - 1


def test_chaque_dosage_ajoute_achete_exactement_un_rang():
    """
    L'affirmation centrale de la page d'accueil, et de la lecon sous la
    console. Elle est verifiee ici sur le vrai moteur, element par
    element, plutot que recopiee d'un document.
    """
    d = demo.balayage()
    els = d["elements"]
    courant: list[str] = []
    precedent = 0
    for e in els:
        courant.append(e)
        masque = "".join("1" if x in courant else "0" for x in els)
        rang = d["table"][masque]["r"]
        assert rang == precedent + 1, (
            f"ajouter {e} a fait passer le rang de {precedent} a {rang}")
        precedent = rang


def test_la_determination_arrive_tard_et_d_un_coup():
    """
    La lecon de la console : le rang monte regulierement, la
    DETERMINATION non. Si cela cessait d'etre vrai, le texte de la page
    deviendrait faux et il faudrait le reecrire.
    """
    d = demo.balayage()
    els = d["elements"]
    courant, fermes = [], []
    for e in els:
        courant.append(e)
        masque = "".join("1" if x in courant else "0" for x in els)
        fermes.append(bin(d["table"][masque]["f"]).count("1"))

    # Rien ne se determine pendant les six premiers dosages. C'est ce que
    # dit la lecon sous la console, et c'est verifie ici sur le moteur.
    assert fermes[:6] == [0] * 6, fermes
    # Puis cela arrive PAR SAUTS, et non proportionnellement.
    sauts = [b - a for a, b in zip(fermes, fermes[1:])]
    assert max(sauts) >= 3, (
        f"la determination progresse regulierement : la lecon de la page "
        f"ne tient plus. Sauts observes : {sauts}")
    assert fermes[-1] >= 8, fermes


def test_la_console_est_complete_sans_javascript(site):
    """
    Le balisage porte les douze phases et la selection de depart. Sans
    script, le visiteur perd l'interaction, pas l'information.
    """
    html = _page(site)
    for fiche in demo.balayage()["phases"]:
        assert f'data-phase="{fiche["cle"]}"' in html, fiche["cle"]
    for e in demo.ELEMENTS_DEMO:
        assert f'data-element="{e}"' in html
    actifs = re.findall(r'data-element="(\w+)" aria-pressed="true"', html)
    assert set(actifs) == set(demo.DEPART)


def test_la_console_ne_depend_d_aucun_reseau(site):
    """
    Les donnees sont EN LIGNE. `fetch` sur un fichier local est bloque par
    la politique d'origine : le site ouvert depuis un disque - ce que fait
    tout relecteur a qui on envoie l'archive - voyait une console morte.
    """
    html = _page(site)
    assert 'id="demo-donnees"' in html
    assert "fetch(" not in mouvement.SCRIPT


# ==========================================================================
# 2. La page ne disparait pas
# ==========================================================================

def test_le_masquage_est_conditionne_a_la_presence_du_script():
    """
    Sans le drapeau `.js`, le contenu a reveler reste a opacite nulle et
    rien ne vient le reveler : la page est VIDE. Le masquage ne doit donc
    s'appliquer que si le script a pu annoncer sa presence.
    """
    f = charte.feuille()
    for regle in re.findall(r"([^{}]*)\{[^{}]*opacity:\s*0[^{}]*\}", f):
        selecteur = regle.strip().splitlines()[-1].strip()
        if "data-reveler" in selecteur:
            assert selecteur.startswith(".js "), (
                f"« {selecteur} » masque du contenu sans attendre le script")


def test_l_entree_du_hero_ne_repose_pas_sur_un_etat_invisible():
    """
    LA MEME FAUTE, SOUS UNE AUTRE FORME.

    L'entree du hero posait `opacity: 0` au repos et comptait sur une
    animation en `forwards` pour la lever. L'animation n'est pas partie, et
    le premier ecran du site est reste NOIR - titre, chapeau, boutons et
    chiffres compris.

    L'etat de repos doit etre le contenu VISIBLE. L'animation part de
    l'invisible et n'y revient que pendant son propre delai, par
    `backwards`. Si elle ne tourne pas, on voit la page.
    """
    f = charte.feuille()
    for selecteur, corps in re.findall(r"([^{}]+)\{([^{}]*)\}", f):
        selecteur = selecteur.strip().splitlines()[-1].strip()
        if ".hero" not in selecteur:
            continue
        assert not re.search(r"opacity:\s*0\s*[;}]", corps), (
            f"« {selecteur} » rend le hero invisible au repos : si "
            f"l'animation ne part pas, le premier ecran reste noir")
    assert "backwards" in f, (
        "l'entree du hero n'utilise plus `backwards` : elle va soit "
        "clignoter, soit laisser le contenu invisible")


def test_le_bandeau_de_preuve_ne_porte_pas_deux_mecanismes(site):
    """
    Il cumulait la revelation au defilement et l'entree du hero. L'entree
    finissait a l'opacite 1, puis la regle de revelation la ramenait a 0
    faute de classe `.vu` : le bandeau disparaissait.
    """
    html = _page(site)
    i = html.index('class="preuves"')
    assert "data-reveler" not in html[i:i + 60], (
        "le bandeau de preuve est de nouveau soumis aux deux mecanismes")


def test_le_drapeau_js_est_pose_avant_tout_rendu(site):
    html = _page(site)
    i_drapeau = html.index('className+=" js"')
    i_corps = html.index("<body")
    assert i_drapeau < i_corps, (
        "le drapeau est pose apres le corps : le contenu clignote")


def test_le_mouvement_se_suspend_pour_qui_l_a_desactive():
    f = charte.feuille()
    assert "prefers-reduced-motion" in f
    # Le bloc va de la requete media a sa derniere accolade. On les compte
    # plutot que de chercher un motif de fin, qui dependrait de la mise en
    # forme du fichier.
    debut = f.index("@media (prefers-reduced-motion")
    profondeur, fin = 0, debut
    for j in range(f.index("{", debut), len(f)):
        if f[j] == "{":
            profondeur += 1
        elif f[j] == "}":
            profondeur -= 1
            if profondeur == 0:
                fin = j
                break
    bloc = f[debut:fin + 1]
    assert "opacity: 1" in bloc and "transform: none" in bloc, bloc
    assert "SOBRE" in mouvement.SCRIPT, (
        "le script ignore le reglage de mouvement reduit")


@pytest.mark.parametrize("page", PAGES)
def test_chaque_page_porte_le_mouvement(site, page):
    """
    Pose a la main sur la seule page d'accueil, l'attribut aurait manque
    partout ailleurs : le site serait reste immobile sur cinq pages sur
    six.
    """
    html = _page(site, page)
    assert "data-reveler" in html, page
    assert "IntersectionObserver" in html, page


# ==========================================================================
# 3. La cascade ne se mord pas la queue
# ==========================================================================

def test_aucune_classe_n_est_redefinie_avec_un_fond_different():
    """
    LE GARDE-FOU NE A D'UNE FAUTE REELLE.

    La console avait nomme ses cartes `.mesure`. Or `.mesure` est
    l'utilitaire de largeur de ligne du site, applique a une dizaine de
    titres. Tous sont sortis en rectangle sombre illisible, sans la
    moindre erreur : juste deux regles portant le meme nom.
    """
    f = charte.feuille()
    fonds: dict[str, list[str]] = {}
    for selecteur, corps in re.findall(r"([^{}]+)\{([^{}]*)\}", f):
        selecteur = selecteur.strip().splitlines()[-1].strip()
        # Les selecteurs simples a une seule classe sont les seuls
        # dangereux : les autres sont contextuels, donc volontaires.
        if not re.fullmatch(r"\.[a-z][a-z0-9-]*", selecteur):
            continue
        if "background" in corps:
            fonds.setdefault(selecteur, []).append(corps.strip()[:60])

    doubles = {k: v for k, v in fonds.items() if len(v) > 1}
    assert not doubles, (
        f"classes a fond declare deux fois, donc en conflit : "
        f"{sorted(doubles)}")


def test_l_utilitaire_de_largeur_de_ligne_reste_une_largeur():
    """Le cas precis qui a casse la page."""
    f = charte.feuille()
    bloc = re.search(r"\n\.mesure\s*\{([^{}]*)\}", f)
    assert bloc is not None, ".mesure a disparu de la charte"
    assert "max-width" in bloc[1]
    assert "background" not in bloc[1]


def test_la_console_nomme_ses_classes_dans_son_espace():
    f = charte.feuille()
    for nom in (".console-mesure", ".console-mesure-val",
                ".console-mesure-cle"):
        assert nom in f, nom


# ==========================================================================
# 4. Les textes de la console sont au catalogue, dans les deux langues
# ==========================================================================

@pytest.mark.parametrize("langue", ["fr", "en"])
def test_la_console_est_traduite(site, langue):
    # Le texte est ECHAPPE dans le document : une apostrophe y devient
    # « &#x27; ». Chercher la chaine brute echouerait sur toute phrase
    # francaise un peu naturelle, et le test passerait a cote de son sujet.
    import html as _html

    lisible = _html.unescape(_page(site, "index", langue))
    for cle in ("console.h2", "console.elements", "console.mesure.rang",
                "console.verdict.rien"):
        extrait = contenu.t(cle, langue).split(".")[0][:40]
        assert extrait in lisible, f"{langue} : {cle}"


def test_la_signature_du_logo_n_est_pas_traduite_dans_la_console(site):
    """Elle reste identique d'une langue a l'autre : c'est une marque."""
    from klastos import marque

    for langue in ("fr", "en"):
        assert marque.SIGNATURE in _page(site, "index", langue)
