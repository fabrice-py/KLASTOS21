"""
KLASTOS21 - Rendu PDF du rapport.

Pourquoi un navigateur, et pas une bibliotheque PDF
---------------------------------------------------
DECISION, et elle est mesuree.

`render_html.py` produit deja un document concu pour le papier : il porte
`@page { size: A4; margin: 14mm 12mm 16mm }`, un bloc `@media print`, et des
`break-inside: avoid` sur le verdict, les tuiles, les bandeaux et les
lignes de tableau. Tout le travail de mise en page est donc fait, et il est
exprime en CSS moderne.

Les bibliotheques PDF de Python ne lisent pas ce CSS de la meme facon.
WeasyPrint le ferait bien, mais reclame GTK et Pango en natif, ce qui est
une installation lourde sous Windows. ReportLab imposerait de refaire toute
la mise en page a la main, donc d'entretenir DEUX descriptions du meme
document - exactement la duplication que ce depot passe son temps a
traquer. xhtml2pdf ne supporte qu'un sous-ensemble ancien de CSS.

Un navigateur, lui, applique EXACTEMENT le CSS deja ecrit : c'est le meme
moteur qui affiche le rapport a l'ecran. La fidelite est donc totale par
construction, et le projet ne gagne AUCUNE dependance Python - le fichier
`requirements.txt` ne bouge pas.

Ce que ce choix coute, et il faut le dire
------------------------------------------
Il demande un navigateur sur la machine. C'est acquis sous Windows, ou Edge
est installe d'office, et usuel ailleurs. Mais sur un serveur sans
interface graphique - un deploiement Streamlit Community Cloud, par
exemple - il n'y en a pas.

L'echec est alors BRUYANT et nomme le repli : telecharger le HTML et
l'imprimer depuis le navigateur par Ctrl+P, qui donne rigoureusement le
meme document. Jamais de PDF degrade produit en silence : un rapport dont
la mise en page a glisse se discute en reunion comme s'il etait juste.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile

#: Emplacements usuels d'un navigateur fonde sur Chromium, par ordre de
#: preference. Edge d'abord : il est present d'office sous Windows, qui est
#: la plateforme des postes de negoce.
CHEMINS_CONNUS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)

#: Noms cherches dans le PATH, pour Linux et les installations hors des
#: emplacements usuels.
NOMS_PATH = ("msedge", "microsoft-edge", "google-chrome", "chrome",
             "chromium", "chromium-browser")

#: Au-dela, on abandonne plutot que de laisser un processus pendre. Un
#: rapport de dix pages s'imprime en quelques secondes ; une minute et demie
#: signifie que quelque chose ne repond pas.
DELAI_MAX = 90

#: Ce que le repli coute a l'utilisateur : deux clics. Le message le dit
#: plutot que de laisser un echec sans suite.
REPLI = (
    "Telechargez le rapport HTML et imprimez-le depuis votre navigateur "
    "(Ctrl+P, puis « Enregistrer au format PDF »). Le document est concu "
    "pour le papier - format A4, marges et cesures de page definies - et "
    "le resultat est rigoureusement identique."
)


class PdfIndisponible(RuntimeError):
    """Aucun moteur de rendu PDF utilisable sur cette machine."""


class PdfEchec(RuntimeError):
    """Le moteur existe mais n'a pas produit de document exploitable."""


def trouver_navigateur(
    chemin: str | pathlib.Path | None = None,
) -> pathlib.Path | None:
    """
    Le premier navigateur utilisable, ou None.

    `chemin` force un executable precis : utile pour un poste ou le
    navigateur est installe ailleurs, et pour les tests.
    """
    if chemin is not None:
        p = pathlib.Path(chemin)
        return p if p.exists() else None

    for c in CHEMINS_CONNUS:
        p = pathlib.Path(c)
        if p.exists():
            return p
    for nom in NOMS_PATH:
        trouve = shutil.which(nom)
        if trouve:
            return pathlib.Path(trouve)
    return None


def pdf_disponible(chemin: str | pathlib.Path | None = None) -> bool:
    """Vrai si un PDF peut etre produit ici. L'interface s'en sert pour
    proposer le bouton, ou expliquer pourquoi elle ne le propose pas."""
    return trouver_navigateur(chemin) is not None


def html_vers_pdf(
    html: str,
    sortie: str | pathlib.Path,
    *,
    navigateur: str | pathlib.Path | None = None,
    delai: int = DELAI_MAX,
) -> pathlib.Path:
    """
    Imprime un document HTML en PDF, et rend le chemin ecrit.

    Leve `PdfIndisponible` si aucun navigateur n'est trouve, `PdfEchec` si
    l'impression n'aboutit pas. Dans les deux cas le message nomme le repli
    : aucun PDF degrade n'est produit en silence.
    """
    moteur = trouver_navigateur(navigateur)
    if moteur is None:
        raise PdfIndisponible(
            f"Aucun navigateur trouve pour produire le PDF. {REPLI}"
        )

    sortie = pathlib.Path(sortie).resolve()
    sortie.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as dossier:
        source = pathlib.Path(dossier) / "rapport.html"
        source.write_text(html, encoding="utf-8")
        commande = [
            str(moteur),
            "--headless=new",
            "--disable-gpu",
            # Sans cette option, le navigateur estampille SON entete - URL,
            # date, numero de page - par-dessus la notre. Le document porte
            # deja son pied de page et sa pagination.
            "--no-pdf-header-footer",
            f"--print-to-pdf={sortie}",
            source.as_uri(),
        ]
        try:
            fin = subprocess.run(commande, capture_output=True,
                                 timeout=delai)
        except subprocess.TimeoutExpired:
            raise PdfEchec(
                f"{moteur.name} n'a pas repondu en {delai} s. {REPLI}"
            ) from None
        except OSError as e:
            raise PdfEchec(f"{moteur.name} injoignable : {e}. {REPLI}") from None

    # Le code de retour ne suffit PAS : un navigateur sans tete rend 0 en
    # ecrivant sur stderr des avertissements sans rapport, et peut aussi
    # rendre 0 sans avoir rien ecrit. On verifie donc le FICHIER.
    if not sortie.exists() or sortie.stat().st_size == 0:
        detail = (fin.stderr or b"").decode("utf-8", "replace")[-300:]
        raise PdfEchec(
            f"{moteur.name} n'a produit aucun document. {REPLI}"
            + (f"\nSortie du moteur : {detail}" if detail.strip() else "")
        )
    if sortie.read_bytes()[:5] != b"%PDF-":
        raise PdfEchec(
            f"{sortie.name} n'est pas un PDF valide. {REPLI}"
        )
    return sortie


def rapport_en_pdf(
    rapport,
    sortie: str | pathlib.Path,
    **kw,
) -> pathlib.Path:
    """
    Raccourci : un `LotReport` vers un PDF.

    Passe par `render_html.to_html`, donc par le MEME document que le
    telechargement HTML. Deux chemins de rendu differents finiraient par
    dire deux choses du meme lot.
    """
    from .render_html import to_html

    return html_vers_pdf(to_html(rapport), sortie, **kw)
