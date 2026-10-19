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
    IDENTIQUES_ADMIS: set[str] = set()
    for cle, entree in i18n.CATALOGUE.items():
        if entree["fr"] == entree["en"]:
            assert cle in IDENTIQUES_ADMIS, cle


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
