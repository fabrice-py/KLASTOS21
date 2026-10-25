"""
Tests du rendu PDF.

LA DECISION QUE CES TESTS TIENNENT
-----------------------------------
Le PDF est produit par un NAVIGATEUR sans tete, et non par une bibliotheque
Python. Ce n'est pas un expedient, c'est un choix mesure.

`render_html.py` produit deja un document concu pour le papier : il porte
`@page { size: A4 }`, un bloc `@media print`, et des `break-inside: avoid`
sur le verdict, les tuiles et les lignes de tableau. Toute la mise en page
est donc faite, en CSS moderne.

WeasyPrint lirait ce CSS correctement mais reclame GTK et Pango en natif,
installation lourde sous Windows. ReportLab imposerait de refaire la mise en
page a la main, donc d'entretenir DEUX descriptions du meme document -
exactement la duplication que ce depot traque partout ailleurs. xhtml2pdf ne
supporte qu'un sous-ensemble ancien de CSS.

Un navigateur applique EXACTEMENT le CSS deja ecrit, puisque c'est le meme
moteur qui affiche le rapport. La fidelite est totale par construction, et
le projet ne gagne aucune dependance.

Le cout : il faut un navigateur. Acquis sous Windows ou Edge est installe
d'office, absent d'un serveur sans interface graphique. L'echec est alors
bruyant et nomme le repli.
"""

from __future__ import annotations

import pathlib

import pytest

from klastos.pdf import (CHEMINS_CONNUS, NOMS_PATH, REPLI, PdfEchec,
                         PdfIndisponible, html_vers_pdf, pdf_disponible,
                         rapport_en_pdf, trouver_navigateur)

RACINE = pathlib.Path(__file__).resolve().parent.parent

#: Un document minimal mais reel : le moteur doit avoir quelque chose a
#: mettre en page.
HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>@page { size: A4; margin: 14mm; } h1 { font-size: 20pt; }</style>
</head><body><h1>KLASTOS21</h1><p>Essai de rendu.</p></body></html>"""


# ==========================================================================
# 1. La decision : aucune dependance Python ajoutee
# ==========================================================================

def test_aucune_bibliotheque_pdf_n_est_declaree():
    """
    LE test de la decision. Si une bibliotheque PDF apparait dans les
    dependances, c'est que le choix du navigateur a ete abandonne, et il
    faut alors reecrire la docstring du module plutot que de laisser deux
    recits contradictoires.
    """
    SUSPECTES = ("weasyprint", "reportlab", "xhtml2pdf", "pdfkit",
                 "playwright", "fpdf", "pypdf")
    for fichier in ("requirements.txt", "pyproject.toml"):
        texte = (RACINE / fichier).read_text(encoding="utf-8").lower()
        for nom in SUSPECTES:
            assert nom not in texte, (
                f"{fichier} declare « {nom} » : le PDF passe desormais par "
                f"une bibliotheque, pas par le navigateur")


def test_le_module_pdf_n_importe_aucune_bibliotheque_externe():
    """
    Meme garde, cote code : seule la bibliotheque standard est utilisee.
    """
    import ast

    arbre = ast.parse((RACINE / "klastos" / "pdf.py").read_text(
        encoding="utf-8"))
    STANDARD = {"pathlib", "shutil", "subprocess", "tempfile", "ast",
                "__future__", "klastos"}
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            noms = {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            # `from .render_html import ...` : `ast` range les points dans
            # `level`, pas dans `module`. Un import relatif reste dans le
            # paquet, donc il n'ajoute aucune dependance.
            if n.level > 0:
                continue
            noms = {n.module.split(".")[0]} if n.module else set()
        else:
            continue
        for nom in noms:
            assert nom in STANDARD, (
                f"klastos/pdf.py importe « {nom} », hors bibliotheque "
                f"standard")


# ==========================================================================
# 2. La recherche du moteur
# ==========================================================================

def test_un_chemin_force_inexistant_ne_rend_rien():
    """
    Forcer un executable absent ne doit pas faire retomber sur un autre
    navigateur en silence : l'utilisateur a demande celui-la.
    """
    assert trouver_navigateur("/chemin/qui/n/existe/pas.exe") is None


def test_les_deux_listes_de_recherche_sont_non_vides():
    assert CHEMINS_CONNUS, "aucun emplacement connu de navigateur"
    assert NOMS_PATH, "aucun nom cherche dans le PATH"
    assert any("edge" in c.lower() for c in CHEMINS_CONNUS), (
        "Edge doit etre cherche en premier : c'est le navigateur installe "
        "d'office sous Windows, plateforme des postes de negoce")


def test_la_disponibilite_suit_la_recherche():
    assert pdf_disponible() == (trouver_navigateur() is not None)
    assert pdf_disponible("/absent.exe") is False


# ==========================================================================
# 3. L'echec est bruyant, et nomme le repli
# ==========================================================================

def test_sans_navigateur_le_refus_nomme_le_repli():
    """
    Un echec sans suite laisserait l'utilisateur sans document. Le message
    doit dire quoi faire : telecharger le HTML et l'imprimer par Ctrl+P,
    qui donne rigoureusement le meme resultat.
    """
    with pytest.raises(PdfIndisponible) as capture:
        html_vers_pdf(HTML, "sortie.pdf", navigateur="/absent.exe")
    message = str(capture.value)
    assert "Ctrl+P" in message
    assert "HTML" in message


def test_le_repli_explique_pourquoi_il_est_equivalent():
    """
    Le repli n'est pas un pis-aller : c'est le MEME moteur appliquant le
    MEME CSS. Le dire evite qu'on le prenne pour une version degradee.
    """
    assert "identique" in REPLI
    assert "A4" in REPLI


def test_un_moteur_qui_n_ecrit_rien_est_refuse(tmp_path):
    """
    Un navigateur sans tete peut rendre 0 sans avoir rien ecrit. Le code de
    retour ne suffit donc pas : on verifie le FICHIER, sinon un PDF vide
    partirait chez un client.
    """
    faux = tmp_path / "faux_navigateur.bat"
    faux.write_text("@echo off\nexit 0\n", encoding="utf-8")
    with pytest.raises(PdfEchec) as capture:
        html_vers_pdf(HTML, tmp_path / "vide.pdf", navigateur=faux)
    assert "aucun document" in str(capture.value)


def test_un_fichier_qui_n_est_pas_un_pdf_est_refuse(tmp_path):
    """
    Second controle : le fichier existe, mais ce n'est pas un PDF. Sans
    cette verification, un message d'erreur du moteur ecrit a la place du
    document passerait pour un rapport.
    """
    sortie = tmp_path / "pas_un_pdf.pdf"
    faux = tmp_path / "ecrit_du_texte.bat"
    faux.write_text(
        f'@echo off\r\necho pas un pdf > "{sortie}"\r\nexit 0\r\n',
        encoding="utf-8")
    with pytest.raises(PdfEchec) as capture:
        html_vers_pdf(HTML, sortie, navigateur=faux)
    assert "PDF valide" in str(capture.value)


# ==========================================================================
# 4. L'impression reelle
# ==========================================================================

@pytest.mark.skipif(not pdf_disponible(),
                    reason="aucun navigateur sur cette machine")
def test_un_pdf_reel_est_produit(tmp_path):
    sortie = html_vers_pdf(HTML, tmp_path / "essai.pdf")
    assert sortie.exists()
    octets = sortie.read_bytes()
    assert octets[:5] == b"%PDF-", "l'entete n'est pas celle d'un PDF"
    assert len(octets) > 1000, (
        f"{len(octets)} octets seulement : document suspect")


@pytest.mark.skipif(not pdf_disponible(),
                    reason="aucun navigateur sur cette machine")
def test_le_rapport_passe_par_le_meme_html_que_le_telechargement(tmp_path):
    """
    `rapport_en_pdf` appelle `render_html.to_html`, donc le PDF et le
    telechargement HTML portent le MEME document. Deux chemins de rendu
    finiraient par dire deux choses du meme lot - c'est la faute que ce
    depot a deja corrigee sur le message de bouclage et sur la charte.
    """
    from klastos.service import Demande, analyser

    a = analyser(Demande(bulletin="data/exemples/bulletin_coherent.csv",
                         provenance="vehicule_electrique", attestee=True,
                         tirages=25))
    sortie = rapport_en_pdf(a.rapport, tmp_path / "rapport.pdf")
    assert sortie.read_bytes()[:5] == b"%PDF-"

    source = (RACINE / "klastos" / "pdf.py").read_text(encoding="utf-8")
    assert "from .render_html import to_html" in source, (
        "le PDF ne passe plus par le rendu HTML commun")
