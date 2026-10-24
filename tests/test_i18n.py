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
    # `provenance.` porte des etiquettes de DOMAINE - les libelles des
    # profils - et non du texte de rapport ou d'interface : les deux les
    # consomment. D'ou sa propre couche.
    couches = ("rapport.", "ui.", "journal.", "provenance.", "cli.")
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
    #: Chaque entree est une decision, pas un oubli - d'ou la liste
    #: explicite, et le controle inverse plus bas qui retire celles qui
    #: n'ont plus lieu d'etre.
    IDENTIQUES_ADMIS = {
        # Mots de forme identique dans les deux langues.
        "rapport.doc.client",
        "ui.lot.client",
        "ui.histo.col_client",
        "rapport.doc.unite_points",
        "ui.nav.libelle",
        "ui.prix.source",
        "ui.prix.col_source",
        "ui.prix.col_date",
        "ui.histo.col_lot",
        "ui.conseil.col_phase",
        "ui.conseil.col_verdict",
        # Gabarit purement numerique : il n'y a rien a traduire.
        "rapport.valeur.drx_avant_apres",
        # Le traitement « zero » d'une valeur censuree s'ecrit « 0 » dans
        # les deux langues : c'est un chiffre, pas un mot.
        "journal.censure.zero",
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
                 "Ventilation", "élémentaire", "teneurs")
    # « teneurs » y est revenu : il ne fuyait que par « Somme des teneurs
    # lues », produite par `ingestion.py` - dette desormais soldee. La
    # liste se resserre a mesure que les journaux passent au catalogue.
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
#: LA DETTE EST SOLDEE. Ces fragments fuyaient en francais dans le rapport
#: anglais ; les trois journaux amont passent desormais par le catalogue.
#:
#: Le test qui suit a remplace le test de dette, et il est plus fort : au
#: lieu de constater une liste de fuites admises, il verifie qu'aucune n'est
#: revenue. L'ancien test avait rendu son service en signalant de lui-meme,
#: par un echec, que « Somme des teneurs lues » venait d'etre payee.
FUITES_SOLDEES = (
    "Provenance declaree",        # provenance.py
    "Attestation client fournie", # provenance.py
    "Phases exclues",             # provenance.py
    "Somme des teneurs lues",     # ingestion.py
    "Oxygene non dose",           # ingestion.py
    "Bouclage massique degrade",  # solver.py, rendu depuis le statut
)


def test_aucune_fuite_soldee_n_est_revenue(rapports):
    """
    Les six fragments qui fuyaient en francais ont disparu du rapport
    anglais, et doivent y rester.

    Chacun nomme son module d'origine dans FUITES_SOLDEES : si l'un revient,
    le message d'echec dit immediatement ou regarder.
    """
    rapport, md, html = rapports["en"]
    journaux = " ".join(rapport.traceability + rapport.warnings
                        + rapport.limitations)
    for fragment in FUITES_SOLDEES:
        assert fragment not in journaux, fragment
        assert fragment not in md, fragment
        assert fragment not in html, fragment


def test_le_texte_d_attestation_EST_traduit(rapports):
    """
    CE TEST A ETE INVERSE, et c'est le point interessant.

    Sa premiere version verrouillait le contraire : l'attestation n'etait
    pas traduite, au motif que c'etait l'enonce que le client avait SIGNE.
    Verification faite, la premisse etait fausse. `attestation_text`
    n'apparait QU'A la ligne de journal, n'est jamais presente au client, et
    vit dans `provenance.py` : c'est une formulation que KLASTOS21 ecrit
    pour DECRIRE l'engagement, pas la citation d'un document signe.

    Notre texte, donc notre traduction. Laisser un acheteur anglophone
    devant une phrase francaise ne protegeait rien - il n'avait pas
    davantage le document sous les yeux.
    """
    from klastos.provenance import texte_attestation

    fr = texte_attestation("vehicule_electrique", "fr")
    en = texte_attestation("vehicule_electrique", "en")
    assert fr != en
    assert "I certify" in en

    journaux = " ".join(rapports["en"][0].traceability)
    assert en in journaux, journaux
    assert fr not in journaux, (
        "l'attestation francaise fuit dans le rapport anglais")


def test_un_profil_sans_attestation_rend_une_chaine_vide():
    """« Provenance non declaree » n'a rien a attester."""
    from klastos.provenance import texte_attestation

    for langue in i18n.LANGUES:
        assert texte_attestation("non_declaree", langue) == ""


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


def test_une_cle_inconnue_s_affiche_sans_guillemets_parasites():
    """
    Meme correction que `market.MissingPriceError` : la base reste
    `KeyError`, mais le message est une phrase destinee a celui qui releve
    le code, pas une cle a mettre entre guillemets.
    """
    with pytest.raises(i18n.CleInconnue) as exc:
        i18n.t("rapport.section.inexistante")

    # L'assertion precise : le message affiche est EXACTEMENT celui qui a
    # ete pose, sans enrobage. Une premiere version de ce test exigeait que
    # le message ne commence par aucun guillemet - c'etait faux : il
    # commence legitimement par la cle entre guillemets, puisqu'elle est
    # posee avec `{cle!r}`, et c'est utile. Ce qu'il faut interdire, c'est
    # que `KeyError.__str__` enrobe la PHRASE ENTIERE.
    assert str(exc.value) == exc.value.args[0]
    assert "n'est pas au catalogue" in str(exc.value)
    # Et la preuve directe : sans la surcharge, on lirait ceci.
    assert str(exc.value) != repr(exc.value.args[0])


def test_cle_inconnue_reste_un_keyerror():
    """`t` peut etre appelee dans un contexte qui attrape KeyError."""
    assert issubclass(i18n.CleInconnue, KeyError)
    try:
        i18n.t("ui.absente.totalement")
    except KeyError:
        pass
    else:
        raise AssertionError("CleInconnue n'est plus un KeyError")


def test_le_journal_de_lecture_sort_dans_la_langue_du_document():
    """
    LE VERROU DE LA TRANCHE. Le journal de `ingestion.py` part dans la
    TRACABILITE du rapport client : c'est la section qui explique les
    decisions de lecture - oxyde converti, valeur sous le seuil, unite
    appliquee par defaut. Un rapport anglais qui la porterait en francais
    serait traduit a moitie, et c'est la moitie qui justifie les chiffres.

    La langue descend de `Demande.langue` jusqu'a `read_bulletin`, parce que
    la lecture est faite une fois par analyse, pour un document donne : il
    n'existe pas de journal partage entre deux langues.
    """
    from klastos.ingestion import read_bulletin

    # Un bulletin qui declenche plusieurs lignes de journal a la fois :
    # oxyde a convertir, valeur censuree, unite non declaree.
    lignes = {"Li2O (%)": "8.44", "Ni": "18.24", "F (%)": "<0.05"}

    rendus = {}
    for langue in i18n.LANGUES:
        lu = read_bulletin(rows=lignes, langue=langue)
        rendus[langue] = " ".join(lu.journal + lu.warnings)
        assert rendus[langue], langue

    assert rendus["fr"] != rendus["en"], (
        "le journal sort a l'identique dans les deux langues : la langue "
        "n'est pas transmise jusqu'a la lecture"
    )
    # Chacun porte le vocabulaire de sa langue, pas celui de l'autre.
    assert "converti en" in rendus["fr"]
    assert "converted to" in rendus["en"]
    assert "converti en" not in rendus["en"]


def test_une_langue_inconnue_ne_fait_pas_echouer_la_lecture():
    """Mieux vaut un journal dans la mauvaise langue qu'une analyse perdue."""
    from klastos.ingestion import read_bulletin

    lu = read_bulletin(rows={"Ni (%)": "18.24"}, langue="zz")
    assert lu.values["Ni"]


def test_le_journal_d_ingestion_ne_porte_plus_de_texte_francais_en_dur():
    """
    GARDE AU PRODUCTEUR, et non au document produit.

    `test_le_rapport_anglais_ne_laisse_pas_fuir_le_vocabulaire_francais`
    cherche des mots francais ACCENTUES dans le document final. Une mutation
    l'a mis en defaut : une phrase francaise sans accent - « Oxygene non
    dose, il sera PREDIT a partir des phases » - lui echappe entierement, et
    le projet ecrit justement son ASCII sans accents.

    Le garde fiable est donc a la source : aucune chaine de prose passee a
    `journal.append` ou `warnings.append` dans `ingestion.py`. Toutes
    passent par `i18n.t`, dont la cle n'est pas de la prose.
    """
    import ast
    import pathlib as _p
    import re

    racine = _p.Path(__file__).resolve().parent.parent
    arbre = ast.parse(
        (racine / "klastos" / "ingestion.py").read_text(encoding="utf-8"))

    #: Trois mots de suite : de la prose, pas un identifiant ni une unite.
    PROSE = re.compile(r"[A-Za-zÀ-ÿ]{3,}\s+[a-zà-ÿ']{2,}\s+[A-Za-zÀ-ÿ']{2,}")

    fautes = []
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Call):
            continue
        if not (isinstance(n.func, ast.Attribute)
                and n.func.attr == "append"
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id in ("journal", "warnings")):
            continue
        for a in n.args:
            texte = None
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                texte = a.value
            elif isinstance(a, ast.JoinedStr):
                texte = "".join(v.value for v in a.values
                                if isinstance(v, ast.Constant)
                                and isinstance(v.value, str))
            if texte and PROSE.search(texte):
                fautes.append((n.lineno, " ".join(texte.split())[:60]))

    assert not fautes, (
        "prose en dur dans le journal d'ingestion, a porter au catalogue : "
        + "; ".join(f"L{l} {s!r}" for l, s in sorted(set(fautes)))
    )


def test_le_libelle_du_profil_de_provenance_est_traduit(rapports):
    """
    Le libelle du profil est une ETIQUETTE D'AFFICHAGE, donc il se traduit -
    contrairement au texte d'attestation ci-dessus, qui est un engagement
    signe.

    Ce test existe parce qu'une mutation a montre qu'il manquait : revenir
    au champ `label` du profil, francais en dur, ne faisait echouer aucun
    test. Le cadre de la phrase etait traduit mais l'etiquette restait en
    francais, donc le rapport anglais disait « Declared provenance :
    Vehicule electrique (fin de vie) ».
    """
    from klastos.provenance import libelle_profil

    fr = libelle_profil("vehicule_electrique", "fr")
    en = libelle_profil("vehicule_electrique", "en")
    assert fr != en
    assert "Electric vehicle" in en

    journaux = " ".join(rapports["en"][0].traceability)
    assert en in journaux, journaux
    assert fr not in journaux, "le libelle francais fuit dans le rapport anglais"

#: Caracteres bannis des textes AFFICHES. Le cadratin a ete retire de tout
#: le projet le 24 octobre 2026 : il tranchait visuellement, et il servait
#: souvent de ponctuation en plein milieu de phrase la ou une virgule, un
#: deux-points ou un point disent la meme chose sans faire tache.
#:
#: Le demi-cadratin reste admis : il sert aux intervalles numeriques, ou il
#: est la convention typographique (« 18 - 46 % »).
CARACTERES_BANNIS = {
    "\u2014": "cadratin",   # le caractere lui-meme, en echappement
}


@pytest.mark.parametrize("caractere,nom", sorted(CARACTERES_BANNIS.items()))
def test_aucun_texte_affiche_ne_porte_un_caractere_banni(caractere, nom):
    """
    Garde typographique. Sans lui, le caractere revient a la premiere
    entree ajoutee au catalogue, et il faut tout reprendre.
    """
    fautifs = [
        f"{cle} [{lg}]"
        for cle, entree in i18n.CATALOGUE.items()
        for lg in i18n.LANGUES
        if caractere in entree[lg]
    ]
    assert not fautifs, (
        f"{nom} present dans {len(fautifs)} texte(s) affiche(s) : "
        f"{fautifs[:6]}")
