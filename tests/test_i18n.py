"""Tests de klastos/i18n.py.

Un catalogue de traduction echoue toujours de la meme facon : une entree
oubliee, et le document part dans la mauvaise langue sans que rien ne leve.
L'engagement de ce module est donc :

    AUCUNE CHAINE AFFICHEE N'EST MUETTE DANS UNE LANGUE SERVIE.

Et son corollaire, qui est la faute reelle que le module a corrigee :

    UNE CLE N'EST JAMAIS UN TEXTE AFFICHE.

`report.py` indexait ses libelles de statut par le titre francais de la
section. Traduire le titre vidait la colonne « statut » du rapport anglais,
sans exception, sans trace.
"""

import re

import pytest

from klastos import i18n

#: Les lettres accentuees du francais. Une chaine francaise affichee qui n'en
#: porte aucune alors qu'elle contient un mot a accentuer est un defaut.
ACCENTS = set("éèêëàâäîïôöûüùçœÉÈÊËÀÂÄÎÏÔÖÛÜÙÇŒ")

#: Mots francais dont l'orthographe EXIGE un accent. Liste volontairement
#: courte et sure : on n'y met que ce qui ne souffre aucune exception.
EXIGENT_ACCENT = re.compile(
    r"\b(determin\w*|reduct\w*|irreduct\w*|reduire|elementaire|degener\w*|"
    r"identifiabilite|tracabilite|methodologique\w*|oxygene|qualite|"
    r"scenario|ecart\w*|resserree?|inchangee?|specification)\b",
    re.IGNORECASE,
)


# ==========================================================================
# 1. Completude. Le verrou du module.
# ==========================================================================

def test_chaque_cle_porte_toutes_les_langues():
    """
    LE VERROU. Une entree sans anglais ne leve pas : `t` retombe sur le
    francais. Le rapport anglais sortirait donc avec des titres francais
    melanges, et seul le destinataire le verrait.
    """
    manquantes = {
        cle: [lg for lg in i18n.LANGUES if not entree.get(lg)]
        for cle, entree in i18n.CATALOGUE.items()
        if any(not entree.get(lg) for lg in i18n.LANGUES)
    }
    assert not manquantes, manquantes


def test_aucune_entree_ne_porte_de_langue_non_servie():
    """Une langue en trop est du texte mort, jamais relu ni corrige."""
    for cle, entree in i18n.CATALOGUE.items():
        assert set(entree) <= set(i18n.LANGUES), (cle, set(entree))


def test_le_catalogue_couvre_chaque_famille_du_rapport():
    """
    Garde-fou : un catalogue vide ferait passer tous les tests ci-dessus,
    qui sont tous des quantificateurs universels. On verifie donc qu'il
    porte effectivement chaque famille de la couche rapport, plutot qu'un
    nombre total d'entrees - un seuil chiffre deviendrait faux a chaque
    ajout et finirait releve sans etre relu.
    """
    for famille in ("rapport.section.", "rapport.intro.", "rapport.statut.",
                    "rapport.protocole."):
        assert i18n.cles_par_prefixe(famille), famille


# ==========================================================================
# 2. Une cle n'est jamais un texte affiche
# ==========================================================================

def test_les_cles_sont_des_identifiants_ascii_stables():
    """
    Une cle doit survivre a une traduction, donc ne contenir ni accent, ni
    espace, ni majuscule. C'est ce qui la distingue d'un titre.
    """
    forme = re.compile(r"^[a-z0-9]+(\.[a-z0-9_]+)+$")
    for cle in i18n.CATALOGUE:
        assert forme.match(cle), cle
        assert not any(c in ACCENTS for c in cle), cle


def test_aucune_cle_ne_repete_un_texte_du_catalogue():
    """
    Si une cle egalait l'un des textes servis, c'est qu'on indexe par le
    libelle - la faute exacte que ce module corrige.
    """
    textes = {v for entree in i18n.CATALOGUE.values() for v in entree.values()}
    for cle in i18n.CATALOGUE:
        assert cle not in textes, cle


def test_les_cles_sont_hierarchisees_par_couche():
    """Chaque cle appartient a une couche connue, pour que `cles_par_prefixe`
    reste exhaustif et qu'aucune entree ne vive hors classement."""
    couches = ("rapport.", "ui.", "journal.", "cli.")
    for cle in i18n.CATALOGUE:
        assert cle.startswith(couches), cle


# ==========================================================================
# 3. Le francais affiche porte ses accents
# ==========================================================================

def test_le_francais_affiche_est_accentue():
    """
    LE DEFAUT D'ORIGINE. Le rapport client disait « Grandeurs fermes »,
    « Ces valeurs sont determinees », « Comment reduire l'incertitude » et
    « tracabilite », a cote de « Limites methodologiques declarees » et
    « irreductible » correctement accentues. L'incoherence saute aux yeux
    sur un document commercial.

    Les commentaires et docstrings du projet restent en ASCII ; les textes
    VISIBLES, non.
    """
    fautifs = []
    for cle, entree in i18n.CATALOGUE.items():
        fr = entree["fr"]
        if EXIGENT_ACCENT.search(fr) and not any(c in ACCENTS for c in fr):
            fautifs.append((cle, fr))
    assert not fautifs, fautifs


def test_l_anglais_ne_porte_pas_d_accent_francais():
    """Un accent dans l'anglais signale une traduction oubliee, recopiee."""
    for cle, entree in i18n.CATALOGUE.items():
        en = entree["en"]
        assert not any(c in ACCENTS for c in en), (cle, en)


def test_les_deux_langues_disent_des_choses_differentes():
    """
    Une entree dont le francais et l'anglais sont identiques est presque
    toujours une traduction non faite. Les exceptions legitimes - un sigle,
    une formule - doivent etre declarees ici explicitement.
    """
    #: Mots dont la forme est la meme en francais et en anglais. Chaque
    #: entree est une decision, pas un oubli - d'ou la liste explicite.
    IDENTIQUES_ADMIS = {
        "rapport.doc.client",            # « Client » / "Client"
        "rapport.doc.unite_points",      # « points » / "points"
        "rapport.valeur.drx_avant_apres",  # purement numerique
    }
    for cle, entree in i18n.CATALOGUE.items():
        if entree["fr"] == entree["en"]:
            assert cle in IDENTIQUES_ADMIS, cle
    # Et l'inverse : une exception devenue inutile doit etre retiree.
    for cle in IDENTIQUES_ADMIS:
        assert i18n.CATALOGUE[cle]["fr"] == i18n.CATALOGUE[cle]["en"], cle


# ==========================================================================
# 4. Comportement de `t`
# ==========================================================================

def test_t_rend_la_langue_demandee():
    assert i18n.t("rapport.section.grandeurs_fermes", "fr") == "Grandeurs fermes"
    assert i18n.t("rapport.section.grandeurs_fermes", "en") == "Determined quantities"


def test_t_leve_sur_une_cle_inconnue():
    """
    Le silence serait pire : un rapport avec un trou a la place d'un titre
    part quand meme, et personne ne le voit avant le destinataire.
    """
    with pytest.raises(i18n.CleInconnue):
        i18n.t("rapport.section.inexistante")


def test_t_retombe_sur_le_francais_pour_une_langue_inconnue():
    """Mieux vaut un rapport dans la mauvaise langue qu'aucun rapport."""
    assert i18n.t("rapport.section.valorisation", "de") == \
        i18n.t("rapport.section.valorisation", "fr")


def test_t_applique_les_champs_de_format():
    i18n.CATALOGUE["cli.essai.format"] = {"fr": "lot {x}", "en": "lot {x}"}
    try:
        assert i18n.t("cli.essai.format", "fr", x="A1") == "lot A1"
    finally:
        del i18n.CATALOGUE["cli.essai.format"]


def test_la_langue_par_defaut_est_le_francais():
    """Le protocole est redige en francais, et les arbitrages y sont pris."""
    assert i18n.DEFAUT == "fr"
    assert i18n.t("rapport.section.tracabilite") == "Traçabilité"


# ==========================================================================
# 5. Normalisation de la langue d'entree
# ==========================================================================

@pytest.mark.parametrize("entree,attendu", [
    ("fr", "fr"), ("en", "en"), ("FR", "fr"), ("EN", "en"),
    ("fr-FR", "fr"), ("en_US", "en"), ("  en  ", "en"),
    (None, "fr"), ("", "fr"), ("de", "fr"), ("zz", "fr"),
])
def test_langue_valide_normalise(entree, attendu):
    """
    L'interface et la ligne de commande recoivent ce que l'utilisateur tape.
    Une langue mal formee ne doit jamais interrompre une analyse.
    """
    assert i18n.langue_valide(entree) == attendu


# ==========================================================================
# 6. Le protocole reste en francais, et le rapport anglais le dit
# ==========================================================================

def test_le_renvoi_au_protocole_declare_sa_langue_en_anglais():
    """
    Arbitrage assume : `protocole.md` n'est pas traduit. Le rapport anglais
    doit donc signaler la langue du document qu'il cite, plutot que de
    laisser croire a une version anglaise opposable qui n'existe pas.
    """
    en = i18n.t("rapport.protocole.renvoi", "en")
    assert "French" in en
    assert "protocole.md" in en


# ==========================================================================
# 7. Le rapport sort reellement dans les deux langues
# ==========================================================================

@pytest.fixture(scope="module")
def rapports():
    """Le meme lot, rendu en francais puis en anglais."""
    import datetime as dt
    import pathlib

    from klastos.render_html import to_html
    from klastos.service import Demande, analyser

    racine = pathlib.Path(__file__).resolve().parent.parent
    bulletin = racine / "data" / "exemples" / "bulletin_coherent.csv"
    if not bulletin.exists():
        pytest.skip("bulletin d'exemple absent")

    out = {}
    for langue in i18n.LANGUES:
        a = analyser(Demande(bulletin=bulletin, langue=langue,
                             provenance="vehicule_electrique", attestee=True,
                             tirages=20, graine=0, emis_le=dt.date(2026, 9, 7)))
        out[langue] = (a.rapport, a.rapport.to_markdown(), to_html(a.rapport))
    return out


def test_le_rapport_porte_la_langue_demandee(rapports):
    for langue, (rapport, _, html) in rapports.items():
        assert rapport.langue == langue
        assert f'<html lang="{langue}">' in html


def test_les_titres_de_sections_sont_traduits(rapports):
    """
    LE VERROU DE LA TRANCHE. Les titres etaient du texte en dur ; un rapport
    anglais sortait integralement en francais.
    """
    fr = {s.title for s in rapports["fr"][0].sections}
    en = {s.title for s in rapports["en"][0].sections}
    assert fr and en
    assert not (fr & en), f"titres non traduits : {fr & en}"


def test_les_cles_de_sections_ne_changent_pas_avec_la_langue(rapports):
    """
    Le corollaire : ce que le titre perd en stabilite, la cle le garde. Sans
    cela les deux rendus ne pourraient plus reconnaitre leurs sections.
    """
    fr = [s.cle for s in rapports["fr"][0].sections]
    en = [s.cle for s in rapports["en"][0].sections]
    assert fr == en
    assert all(fr), "une section sans cle : elle redevient introuvable"


def test_le_rapport_anglais_ne_laisse_pas_fuir_le_vocabulaire_francais(rapports):
    """
    Un mot francais oublie dans le document anglais est invisible en
    relecture francaise, et saute aux yeux du destinataire.

    On ne teste que des mots sans ambiguite : « déterminé » ou « largeur »
    n'ont aucune raison d'apparaitre dans un rapport anglais, alors que des
    noms propres ou des formules chimiques peuvent legitimement y figurer.
    """
    _, md, html = rapports["en"]
    INTERDITS = ("déterminé", "déterminées", "Grandeur", "Statut",
                 "Traçabilité", "Avertissements", "largeur", "incertitude",
                 "non identifiable", "réductible", "Valorisation",
                 "calculée", "référence", "Prix maximal",
                 "Ventilation", "élémentaire")
    # « teneurs » n'y figure pas : il n'apparait plus que dans le journal
    # de provenance, dont la dette est declaree et testee separement.
    for mot in INTERDITS:
        assert mot not in md, f"Markdown anglais : « {mot} »"
        assert mot not in html, f"HTML anglais : « {mot} »"


#: Ce qui reste en francais dans un rapport anglais, et pourquoi.
#:
#: Le journal de lecture et le journal de provenance sont produits par
#: `ingestion.py` et `provenance.py`, en amont du rapport et avant que la
#: langue du livrable soit consultee. Les traduire demande de porter la
#: langue jusqu'a la lecture du bulletin : c'est l'etape suivante du
#: chantier, pas un oubli. Le test ci-dessous CONSTATE la dette plutot que
#: de la laisser passer en silence.
DETTE_JOURNAL = ("Provenance declaree", "Somme des teneurs lues")


def test_la_dette_de_traduction_restante_est_circonscrite(rapports):
    """
    Les seules fuites francaises admises sont celles des journaux amont.

    Si ce test echoue en signalant une entree de MOINS, c'est une bonne
    nouvelle : la dette a ete payee, et il faut retirer la ligne de
    DETTE_JOURNAL. S'il en signale une de PLUS, une regression a introduit
    du francais en dur dans le chemin du rapport.
    """
    rapport = rapports["en"][0]
    journaux = rapport.traceability + rapport.warnings
    presentes = {d for d in DETTE_JOURNAL
                 if any(d in x for x in journaux)}
    assert presentes == set(DETTE_JOURNAL), (
        f"dette attendue {set(DETTE_JOURNAL)}, constatee {presentes}")


def test_le_rapport_anglais_renvoie_au_protocole_francais(rapports):
    """L'arbitrage retenu : le protocole n'est pas traduit, et le document
    anglais doit le dire au lieu de laisser le lecteur le supposer."""
    _, md, html = rapports["en"]
    for doc in (md, html):
        assert "French" in doc
        assert "protocole.md" in doc


def test_les_deux_rapports_portent_les_memes_chiffres(rapports):
    """
    Traduire ne recalcule rien. Les valeurs doivent etre identiques aux deux
    langues, sans quoi la traduction serait devenue un chemin de calcul.
    """
    valeurs = {}
    for langue, (rapport, _, _) in rapports.items():
        valeurs[langue] = [r.value for s in rapport.sections for r in s.rows]
    assert valeurs["fr"] == valeurs["en"]
