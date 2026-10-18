"""
KLASTOS21 - Interface d'exploitation.

    klastos ui
    streamlit run klastos/app.py

Ce que ce module est, et n'est pas
----------------------------------
C'est un ADAPTATEUR. Il traduit des widgets en `Demande`, appelle
`service.analyser`, et met en forme une `Analyse`. Il ne calcule rien, ne
decide rien, et n'a le droit d'appeler ni `propagate`, ni `value_lot`, ni
`build_report` : un test le verifie. La ligne de commande et cette interface
empruntent exactement le meme chemin, faute de quoi elles finiraient par ne
plus dire la meme chose du meme lot.

IMPORTS ABSOLUS, A DESSEIN. `streamlit run klastos/app.py` execute ce
fichier comme un script et non comme un module du paquet : un import relatif
y echoue avec « attempted relative import with no known parent package ».

Ce que l'ecran montre, et ce qu'il refuse de montrer
----------------------------------------------------
L'affichage suit le STATUT de chaque grandeur, jamais une forme fixe. Une
grandeur determinee sort en chiffre, une grandeur non identifiable sort en
intervalle. Le meme ecran convient donc aux deux situations, et le jour ou
une quantification par diffraction (DRX) leve la degenerescence, les
intervalles deviennent des chiffres sans qu'une ligne change ici.

Ce qu'il ne fera jamais : un camembert de phases a valeur unique sommant a
100 %. Mesure a l'appui, deux assemblages differant de 2,86 points sur le
PVDF produisent le meme bulletin a 3e-15 point pres. Afficher la part de
l'un revient a presenter un arbitrage numerique comme une mesure.

Deux attestations, jamais deux cases a cocher anodines
------------------------------------------------------
L'interface rend visibles les deux declarations que le systeme refuse de
deviner : l'ATTESTATION DE PROVENANCE, sans laquelle aucune phase n'est
exclue, et la LICENCE DE REDIFFUSION, sans laquelle des prix d'agence ne
peuvent pas figurer dans un document remis a un tiers. Les deux sont
formulees a la premiere personne, parce que les cocher engage l'utilisateur
et non le code.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import pathlib
import tempfile

import streamlit as st

from klastos import charts, theme
from klastos.ingestion import IngestionError, parse_rows
from klastos.market import (MissingPriceError, NotAProductionSourceError,
                            REFERENCE_SPECS, StalePriceError)
from klastos.provenance import PROVENANCE_PROFILES
from klastos.report import DESTINATAIRE_INTERNE, DESTINATAIRE_TIERS, ReportRefused
from klastos.service import Analyse, Demande, analyser, charger_prix, charger_termes
from klastos.identifiability import (CONSEIL_U_DEFAUT, UnboundedCompatibleSet)
from klastos.solver import CLOSURE_ALERT, CLOSURE_REJECT
from klastos.structural import (BASE_ABSOLUE, BASE_CRISTALLINE, BASES,
                                LIBELLE_BASE, StructuralRefused)
from klastos.units import ImplausiblePriceError

TITRE = "KLASTOS21"
SOUS_TITRE = "Analyse prédictive des matières premières secondaires"

PAGES = ["Analyse", "Prix", "Historique", "Aide"]


# ==========================================================================
# Fonctions pures : testables sans lancer Streamlit
# ==========================================================================

def lignes_depuis_csv(contenu: bytes, separateur: str = ",") -> dict[str, str]:
    """
    Transforme un fichier televerse en lignes exploitables par l'ingestion.

    Le fichier arrive en octets, pas en chemin : il n'est jamais ecrit sur
    le disque. La reconnaissance de format appartient a l'ingestion, pas a
    l'interface. La reimplementer ici avait produit une detection fausse :
    un bulletin large a deux colonnes se lisait comme un format long.
    """
    texte = contenu.decode("utf-8-sig", errors="replace")
    lignes = list(csv.reader(io.StringIO(texte), delimiter=separateur))
    return parse_rows(lignes, "fichier televerse")


def construire_demande(
    lignes: dict[str, str],
    *,
    lot_id: str,
    client: str,
    provenance: str,
    attestee: bool,
    grades: tuple[str, ...] | None,
    tirages: int,
    graine: int,
    seuil_alerte: float,
    seuil_rejet: float,
    prix=None,
    termes=None,
    specification=None,
    cout: float = 0.0,
    marge: float = 0.0,
    destinataire: str = DESTINATAIRE_TIERS,
    autoriser_demo: bool = False,
    emis_le: _dt.date | None = None,
    drx=None,
    base_drx: str = BASE_ABSOLUE,
    conseil_drx: bool = False,
    incertitude_drx: float = CONSEIL_U_DEFAUT,
) -> Demande:
    """Assemble la demande. Fonction pure : c'est elle qui est testee."""
    return Demande(
        lignes=lignes,
        lot_id=lot_id.strip(),
        client=client.strip() or "Client",
        provenance=provenance,
        attestee=attestee,
        grades_declares=grades,
        drx=drx,
        base_drx=base_drx,
        conseil_drx=conseil_drx,
        incertitude_drx=incertitude_drx,
        tirages=tirages,
        graine=graine,
        seuil_alerte=seuil_alerte,
        seuil_rejet=seuil_rejet,
        prix=prix,
        termes=termes,
        specification=specification,
        cout_traitement=cout,
        marge=marge,
        destinataire=destinataire,
        autoriser_demo=autoriser_demo,
        emis_le=emis_le,
    )


def message_de_refus(exc: Exception) -> tuple[str, str]:
    """
    Traduit un refus du protocole en (titre, explication).

    Un refus n'est pas un plantage : c'est le systeme qui tient parole. Il
    doit donc s'afficher comme une decision motivee, jamais comme une trace
    d'appel.
    """
    if isinstance(exc, ReportRefused):
        return ("Rapport refusé", str(exc))
    if isinstance(exc, NotAProductionSourceError):
        return ("Source de prix non destinée à la production", str(exc))
    if isinstance(exc, StalePriceError):
        return ("Prix périmés", str(exc))
    if isinstance(exc, MissingPriceError):
        return ("Prix manquant", str(exc))
    if isinstance(exc, ImplausiblePriceError):
        return ("Prix invraisemblable", str(exc))
    if isinstance(exc, IngestionError):
        return ("Bulletin illisible", str(exc))
    return ("Analyse impossible", str(exc))


def resume_statuts(analyse: Analyse) -> dict[str, int]:
    """Combien de grandeurs dans chaque statut. Sert au bandeau."""
    out = {"ferme": 0, "ferme_large": 0, "ouvert": 0}
    for r in analyse.incertitude.results:
        if r.block in ("phase", "ventilation"):
            out[charts._statut(r)] += 1
    return out


# ==========================================================================
# Fragments d'habillage
# ==========================================================================

def _marque() -> None:
    st.sidebar.markdown(
        f"""<div class="marque">
              <div class="marque-cube">K21</div>
              <div>
                <div class="marque-nom">KLASTOS<span>21</span></div>
                <div class="marque-sous">{SOUS_TITRE}</div>
              </div>
            </div>""",
        unsafe_allow_html=True)


def _fil(page: str) -> None:
    st.markdown(
        f"""<div class="fil">
              <div class="fil-gauche"><b>{TITRE}</b>
                <span class="fil-sep">&rsaquo;</span>{page}</div>
            </div>""",
        unsafe_allow_html=True)


def _heros(titre: str, texte: str, note_titre: str, note: str) -> None:
    st.markdown(
        f"""<div class="heros">
              <div><h1>{titre}</h1><p>{texte}</p></div>
              <div class="heros-note"><b>{note_titre}</b><span>{note}</span></div>
            </div>""",
        unsafe_allow_html=True)


def _carte_titre(numero: str | None, titre: str) -> str:
    puce = f'<span class="puce">{numero}</span>' if numero else ""
    return f'<div class="carte-titre">{puce}{titre}</div>'


def _tuile(cle: str, valeur: str, note: str = "", classe: str = "") -> str:
    n = f'<div class="tuile-n">{note}</div>' if note else ""
    return (f'<div class="tuile {classe}"><div class="tuile-k">{cle}</div>'
            f'<div class="tuile-v">{valeur}</div>{n}</div>')


# ==========================================================================
# Page : Analyse
# ==========================================================================

def _page_analyse(reglages: dict) -> None:
    _fil("Analyse")
    _heros(
        "Analyse minéralogique de black mass",
        "Importez votre bulletin d'analyse et obtenez la reconstitution "
        "minéralogique de votre échantillon, avec ce qui est déterminé et "
        "ce qui ne peut pas l'être.",
        "Ce que l'outil garantit",
        "Aucun chiffre que la donnée ne porte. Une grandeur non "
        "identifiable sort en domaine, jamais en valeur unique.")

    gauche, droite = st.columns([1, 2], gap="medium")

    with gauche:
        with st.container(border=True):
            st.markdown(_carte_titre("1", "Importer votre bulletin"),
                        unsafe_allow_html=True)
            fichier = st.file_uploader(
                "Glissez-déposez votre fichier",
                type=["csv"], label_visibility="collapsed",
                help="Format large (intitulés puis valeurs) ou long "
                     "(élément, valeur). Les unités se déclarent dans "
                     "l'intitulé : « Ni (%) », « Fe (mg/kg) ». L'oxygène "
                     "n'est pas attendu, il est prédit.")
            st.caption("Format accepté : **CSV**  ·  séparateur réglable "
                       "dans les paramètres")

        if fichier is None:
            st.markdown(
                '<div class="methode">Déposez un bulletin pour lancer une '
                'analyse. Un exemple est fourni dans '
                '<b>data/exemples/</b>.</div>', unsafe_allow_html=True)
            return

        try:
            lignes = lignes_depuis_csv(fichier.getvalue(),
                                       reglages["separateur"])
        except Exception as e:
            titre, detail = message_de_refus(e)
            st.error(f"**{titre}** — {detail}")
            return

        with st.expander("Ce que KLASTOS21 a lu dans votre fichier"):
            st.dataframe([{"Colonne": k, "Valeur lue": v}
                          for k, v in lignes.items()],
                         use_container_width=True, hide_index=True)

        with st.container(border=True):
            st.markdown(_carte_titre("2", "Identifier le lot"),
                        unsafe_allow_html=True)
            lot_id = st.text_input("Identifiant du lot",
                                   value=pathlib.Path(fichier.name).stem)
            client = st.text_input("Client", value="Client")

        with st.container(border=True):
            st.markdown(
                _carte_titre("3", "Quantification par diffraction"),
                unsafe_allow_html=True)
            st.caption("Facultatif. C'est le levier le plus puissant du lot.")
            f_drx = st.file_uploader(
                "Fichier de quantification DRX",
                type=["csv"], label_visibility="collapsed",
                key="drx_upload",
                help="Une phase par ligne : phase, valeur, incertitude. "
                     "La colonne d'incertitude est OBLIGATOIRE — une mesure "
                     "Rietveld est précise à 1 ou 3 points, et sans son "
                     "incertitude elle passerait pour exacte.")
            base = st.radio(
                "Base de normalisation", list(BASES),
                format_func=lambda b: LIBELLE_BASE[b],
                horizontal=False, key="drx_base",
                help="Un diffractogramme ne voit que le cristallin. Sur base "
                     "cristalline, les niveaux ne sont pas contraints : seuls "
                     "les rapports entre phases le sont, et il faut donc une "
                     "phase de plus.")
            conseil = st.checkbox(
                "Calculer quelle phase faire quantifier",
                value=False, key="drx_conseil",
                help="Classe les phases par le resserrement qu'une mesure "
                     "apporterait, au pire placement. Quelques secondes.")
            u_drx = st.number_input(
                "Incertitude supposée du laboratoire (points)",
                min_value=0.1, max_value=10.0, step=0.5,
                value=CONSEIL_U_DEFAUT * 100, key="drx_u",
                disabled=not conseil)

        chemin_drx = None
        if f_drx is not None:
            # Le lecteur de quantifications travaille sur un fichier. On
            # materialise donc le depot dans un repertoire temporaire propre
            # a la session, plutot que d'ecrire dans le dossier courant.
            dossier = pathlib.Path(
                tempfile.gettempdir()) / "klastos_drx"
            dossier.mkdir(parents=True, exist_ok=True)
            chemin_drx = dossier / f_drx.name
            chemin_drx.write_bytes(f_drx.getvalue())

        prix = st.session_state.get("prix")
        if prix is None:
            st.caption("Aucun prix chargé : le rapport sortira sans "
                       "valorisation. Onglet **Prix** pour en fournir.")
        else:
            st.caption(f"Prix : {prix.label}")

        lancer = st.button("Lancer l'analyse", type="primary",
                           use_container_width=True)

    if lancer:
        demande = construire_demande(
            lignes, lot_id=lot_id, client=client,
            provenance=reglages["provenance"], attestee=reglages["attestee"],
            grades=reglages["grades"], tirages=reglages["tirages"],
            graine=reglages["graine"], seuil_alerte=reglages["seuil_alerte"],
            seuil_rejet=reglages["seuil_rejet"],
            prix=st.session_state.get("prix"),
            termes=st.session_state.get("termes"),
            specification=reglages["specification"],
            cout=reglages["cout"], marge=reglages["marge"],
            destinataire=reglages["destinataire"],
            emis_le=reglages["emis_le"],
            drx=chemin_drx,
            base_drx=base,
            conseil_drx=conseil,
            incertitude_drx=u_drx / 100.0)
        with st.spinner("Reconstitution et propagation d'incertitude…"):
            try:
                st.session_state["analyse"] = analyser(demande)
                st.session_state["enregistre"] = False
            except Exception as e:
                st.session_state["analyse"] = None
                titre, detail = message_de_refus(e)
                with droite:
                    st.error(f"**{titre}** — {detail}")

    analyse = st.session_state.get("analyse")
    with droite:
        if analyse is None:
            st.markdown(
                '<div class="carte" style="text-align:center;padding:56px 20px">'
                '<div style="font-size:15px;font-weight:600;color:#13171E">'
                'Aucune analyse en cours</div>'
                '<div style="font-size:13px;color:#5A6472;margin-top:7px">'
                'Importez un bulletin à gauche, puis lancez l\'analyse.</div>'
                "</div>", unsafe_allow_html=True)
            return
        _resultats(analyse, reglages)


def _resultats(a: Analyse, reglages: dict) -> None:
    bouclage = a.incertitude.meta.get("closure")
    statut = bouclage.status if bouclage else "ok"
    teinte, fond = theme.TEINTE_BOUCLAGE.get(statut, theme.TEINTE_BOUCLAGE["ok"])
    verdict = {"ok": "Analyse terminée", "alerte": "Analyse terminée — à vérifier",
               "rejet": "Lot inexploitable en l'état"}[statut]
    sous = {"ok": "Votre rapport est prêt.",
            "alerte": "Le rapport est disponible, mais le bouclage massique "
                      "demande une explication.",
            "rejet": "Le bouclage est hors tolérance."}[statut]

    st.markdown(
        f"""<div class="bandeau" style="background:{fond};border-color:{teinte};
                 color:{teinte}">
              <div><div class="bandeau-titre">{verdict}</div>
                   <div class="bandeau-sous">{sous}</div></div>
              <div class="bandeau-droite">
                {a.rapport.issued_on.isoformat()}<br>
                Échantillon : {a.rapport.lot_id}</div>
            </div>""", unsafe_allow_html=True)

    if a.rapport.is_demo:
        st.warning("Document de démonstration — non opposable.")

    t1, t2, t3, t4 = st.tabs(["Vue d'ensemble", "Composition minéralogique",
                              "Réduire l'incertitude", "Rapport"])
    with t1:
        _vue_ensemble(a)
    with t2:
        _composition(a)
    with t3:
        _incertitude(a)
    with t4:
        _rapport(a, reglages)


def _vue_ensemble(a: Analyse) -> None:
    central = a.incertitude.meta["central"]
    bouclage = a.incertitude.meta.get("closure")
    statut = bouclage.status if bouclage else "ok"
    compte = resume_statuts(a)

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_tuile("Bouclage massique",
                       f"{central.explained_mass * 100:.2f} %",
                       f"{central.unexplained_mass * 100:.2f} % non expliqués",
                       statut), unsafe_allow_html=True)
    c2.markdown(_tuile("Degrés de liberté", str(a.incertitude.degeneracy),
                       "non contraints par l'analyse élémentaire"),
                unsafe_allow_html=True)
    c3.markdown(_tuile("Grandeurs déterminées",
                       f"{compte['ferme']} / {sum(compte.values())}",
                       f"{compte['ouvert']} en domaine compatible"),
                unsafe_allow_html=True)
    if a.valorisation is not None:
        v = a.valorisation
        c4.markdown(_tuile(
            "Prix maximal à payer",
            f"{v.max_price_low:,.0f}–{v.max_price_high:,.0f}".replace(",", " "),
            f"{v.currency} par tonne", "prix"), unsafe_allow_html=True)
    else:
        c4.markdown(_tuile("Prix maximal à payer", "—",
                           "aucun prix fourni"), unsafe_allow_html=True)

    st.write("")
    g, d = st.columns([1, 1], gap="medium")

    with g, st.container(border=True):
        _, mode = charts.donnees_composition(a)
        st.markdown(_carte_titre(None, "Composition reconstituée"),
                    unsafe_allow_html=True)
        st.altair_chart(charts.camembert(a), use_container_width=True)
        if mode == "elements":
            st.markdown(
                '<div class="methode">Ce camembert porte la composition '
                '<b>élémentaire</b>, qui est déterminée, et non les phases '
                'minérales, qui ne le sont pas. Le gris est la masse que le '
                'modèle n\'explique pas : humidité, phase absente du modèle, '
                'ou provenance mal déclarée. Il bascule automatiquement sur '
                'les phases le jour où celles-ci deviennent fermes.</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="methode">Toutes les phases sont déterminées sur '
                'ce lot : le camembert porte donc directement la '
                '<b>minéralogie</b>.</div>', unsafe_allow_html=True)

    with d, st.container(border=True):
        st.markdown(_carte_titre(None, "Teneurs élémentaires du bulletin"),
                    unsafe_allow_html=True)
        st.altair_chart(charts.barres_elements(a), use_container_width=True)
        st.markdown(_carte_titre(None, "Bouclage massique"),
                    unsafe_allow_html=True)
        st.altair_chart(charts.barre_bouclage(a), use_container_width=True)
        if bouclage is not None and statut != "ok":
            st.caption(bouclage.message)


def _composition(a: Analyse) -> None:
    g, d = st.columns([3, 2], gap="medium")
    with g, st.container(border=True):
        st.markdown(_carte_titre(None, "Domaines compatibles par phase"),
                    unsafe_allow_html=True)
        st.altair_chart(charts.barres_domaines(a), use_container_width=True)
        st.markdown(
            '<div class="methode">Un <b>trait fin</b> se lit « déterminé ». '
            'Une <b>bande large</b> se lit « toute valeur de cette bande '
            'explique le bulletin aussi bien qu\'une autre ». Une '
            'quantification par diffraction (DRX) de deux phases suffirait à '
            'ramener toutes ces bandes à des traits.</div>',
            unsafe_allow_html=True)

    with d, st.container(border=True):
        st.markdown(_carte_titre(None, "Détail des phases"),
                    unsafe_allow_html=True)
        st.markdown(_table_phases(a), unsafe_allow_html=True)


def _table_phases(a: Analyse) -> str:
    """
    Le tableau de la maquette, avec le statut au lieu d'un faux chiffre.

    Deux colonnes et non trois : la carte est etroite, et une troisieme
    colonne poussait la pastille de statut hors du cadre. Le statut se lit
    donc sous la valeur, ou il reste associe au bon chiffre.
    """
    lignes = ['<table class="phases"><thead><tr>'
              '<th>Minéral / Phase</th>'
              '<th style="text-align:right">% massique</th>'
              "</tr></thead><tbody>"]
    resultats = [r for r in a.incertitude.results
                 if r.block in ("phase", "ventilation")]
    for r in sorted(resultats, key=lambda r: -r.total_upper):
        s = charts._statut(r)
        couleur = charts.COULEUR_STATUT[s]
        court = r.label.split(" (")[0]
        formule = r.label[len(court):].strip(" ()")
        formule_html = (f'<div style="color:#8C95A4;font-size:11px;'
                        f'margin-left:16px">{formule}</div>'
                        if formule else "")
        lignes.append(
            f'<tr>'
            f'<td><span class="point" style="background:{couleur}"></span>'
            f'{court}{formule_html}</td>'
            f'<td class="num">{r.format_value()}'
            f'<div style="margin-top:3px">'
            f'{theme.chip(s, charts.LIBELLE_STATUT[s])}</div></td>'
            f"</tr>")
    lignes.append("</tbody></table>")
    return "".join(lignes)


def _incertitude(a: Analyse) -> None:
  with st.container(border=True):
    st.markdown(_carte_titre(None, "Ce qu'un dosage d'oxygène apporterait"),
                unsafe_allow_html=True)
    graphe = charts.barres_scenario(a)
    if graphe is None:
        st.caption("L'oxygène est dosé dans ce bulletin : il n'y a plus rien "
                   "à projeter.")
    else:
        st.altair_chart(graphe, use_container_width=True)
        sc = a.incertitude.meta["scenarios"][0]
        st.markdown(
            f'<div class="methode">La reconstitution contraint déjà '
            f'l\'oxygène entre <b>{sc.value_low * 100:.2f} %</b> et '
            f'<b>{sc.value_high * 100:.2f} %</b>. Un dosage n\'apporte donc '
            f'quelque chose que si son incertitude reste sous '
            f'<b>{sc.max_useful_uncertainty * 100:.2f} point</b>. Au-delà, '
            f'il confirme ce que le calcul donne déjà. Ces largeurs sont des '
            f'projections : aucune n\'est opposable.</div>',
            unsafe_allow_html=True)

  with st.container(border=True):
    st.markdown(_carte_titre(None, "Quantification par diffraction (DRX)"),
                unsafe_allow_html=True)

    if a.contrainte_par_drx:
        u = a.incertitude
        taux = u.structural_conflict_rate
        st.markdown(
            f'<div class="methode">{len(a.structurale)} phase(s) quantifiée(s), '
            f'base <b>{a.structurale.basis}</b>. Une mesure entre en '
            f'<b>encadrement</b> et non en égalité : elle resserre les plages, '
            f'elle ne rend aucune grandeur ferme — une inégalité borne une '
            f'direction nulle, elle ne la supprime pas.</div>',
            unsafe_allow_html=True)

        resserres = [r for r in u.results
                     if r.structural_gain is not None
                     and r.structural_gain > 0.01]
        resserres.sort(key=lambda r: -(r.structural_gain or 0.0))
        if resserres:
            st.dataframe(
                [{"Grandeur": r.label,
                  "Plage avant": f"{r.open_width * 100:.2f} pt",
                  "Plage après":
                      f"{((r.struct_upper or 0) - (r.struct_lower or 0)) * 100:.2f} pt",
                  "Gain": f"{(r.structural_gain or 0) * 100:.0f} %"}
                 for r in resserres],
                use_container_width=True, hide_index=True)
        else:
            st.info("Cette quantification ne resserre aucune plage de ce lot : "
                    "les phases qu'elle désigne étaient déjà déterminées, ou "
                    "elle ne contraint pas les directions non identifiables.")

        if taux > 0.20:
            st.warning(
                f"**{u.n_structural_conflicts} tirage(s) sur {u.n_draws} en "
                f"conflit ({taux * 100:.0f} %).** Pour cette part des tirages "
                "de bruit analytique, aucune répartition des phases ne "
                "satisfait à la fois le bulletin et la quantification. Ces "
                "tirages sont **conservés** avec leurs bornes non "
                "contraintes : les écarter aurait resserré l'incertitude du "
                "laboratoire au motif d'une mesure qui ne porte pas sur elle. "
                "Un taux élevé signale une analyse, une quantification ou un "
                "modèle de phases à reprendre.")
    else:
        st.markdown(
            '<div class="methode">Aucune quantification fournie. Déposez-en '
            'une dans la colonne de gauche. Mesuré sur un lot en provenance '
            'VE attestée : une seule phase quantifiée à <b>±2 points</b> '
            'retire <b>72 %</b> de la largeur cumulée. Mais toutes les phases '
            'ne se valent pas — cochez le calcul du conseil pour savoir '
            'laquelle commander.</div>',
            unsafe_allow_html=True)

  if a.conseil is not None and a.conseil.rows:
    with st.container(border=True):
        st.markdown(_carte_titre(None, "Quelle phase faire quantifier"),
                    unsafe_allow_html=True)
        c = a.conseil
        st.markdown(
            f'<div class="methode">{c.resume()} Les gains sont des '
            f'<b>planchers</b> : ils sont pris au pire placement de la valeur '
            f'mesurée dans la plage compatible, puisque cette valeur est '
            f'inconnue avant la mesure.</div>', unsafe_allow_html=True)
        st.dataframe(
            [{"Phase": r.label,
              "Plage actuelle": f"{r.width_open * 100:.2f} pt",
              "Gain au pire cas": f"{r.gain * 100:.0f} %",
              "Verdict": "à commander" if r.useful else "sans effet"}
             for r in c.rows],
            use_container_width=True, hide_index=True)

  with st.container(border=True):
    for section in a.rapport.sections:
        if section.title.startswith("Comment reduire"):
            with st.expander(section.title):
                st.caption(section.intro)
                st.dataframe(
                    [{"Grandeur": r.label, "Largeur": r.value,
                      "Remède": r.note} for r in section.rows],
                    use_container_width=True, hide_index=True)


def _rapport(a: Analyse, reglages: dict) -> None:
    from klastos.render_html import to_html

    html = to_html(a.rapport)
    c1, c2, c3 = st.columns([1, 1, 2])
    c1.download_button("Télécharger le rapport (HTML)", data=html,
                       file_name=f"rapport_{a.rapport.lot_id}.html",
                       mime="text/html", use_container_width=True,
                       type="primary",
                       help="Ouvrez-le dans un navigateur, puis Ctrl+P pour "
                            "un PDF.")
    c2.download_button("Markdown", data=a.rapport.to_markdown(),
                       file_name=f"rapport_{a.rapport.lot_id}.md",
                       mime="text/markdown", use_container_width=True)

    if reglages["historique"] and not st.session_state.get("enregistre"):
        import klastos.store as store

        cx = store.ouvrir(reglages["base"])
        try:
            i = store.enregistrer(cx, a)
            st.session_state["enregistre"] = True
            c3.success(f"Enregistré dans l'historique (#{i})")
        finally:
            cx.close()

    for titre, elements in (("Avertissements", a.rapport.warnings),
                            ("Limites déclarées", a.rapport.limitations),
                            ("Traçabilité", a.rapport.traceability)):
        if elements:
            with st.expander(titre):
                for x in elements:
                    st.write("- " + x)

    with st.expander("Aperçu du rapport imprimable", expanded=True):
        st.components.v1.html(html, height=720, scrolling=True)


# ==========================================================================
# Page : Prix
# ==========================================================================

def _page_prix(reglages: dict) -> None:
    _fil("Prix")
    _heros("Prix de référence",
           "Sans prix, pas de valorisation : le rapport reste complet mais "
           "ne porte aucun chiffre commercial. Il n'existe nulle part dans "
           "KLASTOS21 de jeu de prix par défaut.",
           "Route prioritaire",
           "Les prix fournis par le client. Ce sont ses données : aucune "
           "licence d'agence ne les restreint.")

    g, d = st.columns([1, 2], gap="medium")
    with g:
        with st.container(border=True):
            st.markdown(_carte_titre("1", "Source"), unsafe_allow_html=True)
            mode = st.radio("Source", ["Fichier de prix", "Flux d'agence"],
                            label_visibility="collapsed")

        if mode == "Fichier de prix":
            _source_fichier()
        else:
            _source_agence()

    with d:
        prix = st.session_state.get("prix")
        if prix is None:
            st.markdown(
                '<div class="carte" style="text-align:center;padding:48px 20px">'
                '<div style="font-size:15px;font-weight:600">Aucun prix chargé'
                '</div><div style="font-size:13px;color:#5A6472;margin-top:7px">'
                'Le rapport sortira sans valorisation.</div></div>',
                unsafe_allow_html=True)
            return

        with st.container(border=True):
         st.markdown(_carte_titre(None, prix.label), unsafe_allow_html=True)
        st.dataframe(
            [{"Métal": m,
              f"Prix ({prix.currency}/t)": f"{p.value_per_tonne:,.2f}",
              "Date": p.as_of.isoformat(), "Référence": p.reference_name,
              "Source": p.source}
              for m, p in sorted(prix.prices.items())],
             use_container_width=True, hide_index=True)

        if not prix.redistribution_licensed:
            st.warning(
                "**USAGE INTERNE.** Ces prix ne peuvent pas figurer dans un "
                "document remis à un tiers. Un rapport avec destinataire "
                "« tiers » sera refusé — et c'est voulu.")


def _source_fichier() -> None:
  with st.container(border=True):
    st.markdown(_carte_titre("2", "Fichier"), unsafe_allow_html=True)
    f = st.file_uploader("Prix au format CSV ou JSON", type=["csv", "json"],
                         key="fichier_prix")
    chemin_payables = st.text_input("Conditions commerciales (JSON)",
                                    value="data/payable_terms.json")
    marche = st.text_input("Marché", value="cif_coree_sud")
    if f is not None and st.button("Charger ces prix", type="primary",
                                   use_container_width=True):
        import tempfile

        with tempfile.TemporaryDirectory() as dossier:
            tmp = pathlib.Path(dossier) / f.name
            tmp.write_bytes(f.getvalue())
            try:
                st.session_state["prix"] = charger_prix(tmp)
                st.session_state["termes"] = charger_termes(chemin_payables,
                                                            marche)
            except Exception as e:
                titre, detail = message_de_refus(e)
                st.error(f"**{titre}** — {detail}")


def _source_agence() -> None:
  with st.container(border=True):
    st.markdown(_carte_titre("2", "Agence"), unsafe_allow_html=True)
    source = st.selectbox("Agence", ["fastmarkets", "benchmark", "smm"])
    st.caption("Les identifiants sont lus dans les variables "
               "d'environnement, jamais saisis ici ni stockés.")
    licence = st.checkbox(
        "J'atteste détenir l'autorisation écrite de rediffuser ces prix à "
        "un tiers.",
        help="Un abonnement d'agence couvre l'usage interne, pas la "
             "rediffusion. Sans cette autorisation, un rapport destiné à un "
             "client sera refusé — et c'est voulu.")
    marche = st.text_input("Marché pour les payables", value="cif_coree_sud",
                           key="marche_agence")
    if st.button("Récupérer les prix du jour", type="primary",
                 use_container_width=True):
        _recuperer_prix(source, licence, marche)


def _recuperer_prix(source: str, licence: bool, marche: str) -> None:
    from klastos.feeds import (BenchmarkFeed, CredentialsMissing,
                               FastmarketsFeed, FeedError, SMMFeed)
    from klastos.providers import ProviderError, build_price_set

    constructeurs = {"fastmarkets": FastmarketsFeed,
                     "benchmark": BenchmarkFeed, "smm": SMMFeed}
    flux = constructeurs[source](redistribution_licensed=licence)
    etat = "rediffusion autorisée" if licence else "USAGE INTERNE uniquement"
    try:
        cotations = flux.quotes()
        st.session_state["prix"] = build_price_set(
            cotations,
            label=f"{source} du {cotations[0].as_of.isoformat()} — {etat}",
            is_production_source=True, origin=source,
            redistribution_licensed=licence)
        if hasattr(flux, "payables"):
            from klastos.market import PayableTerms

            st.session_state["termes"] = PayableTerms(
                market=marche, payables=flux.payables(marche),
                as_of=cotations[0].as_of,
                source=f"{source}, relevé automatique", validated=True)
    except CredentialsMissing as e:
        st.error(f"**Identifiants absents** — {e}")
    except (FeedError, ProviderError, ImplausiblePriceError) as e:
        st.error(f"**{source}** — {e}")


# ==========================================================================
# Page : Historique
# ==========================================================================

def _page_historique(reglages: dict) -> None:
    import klastos.store as store

    _fil("Historique")
    _heros("Lots analysés",
           "Retrouver un lot, ressortir le rapport tel qu'il a été émis, "
           "rejouer une reconstitution contestée.",
           "Donnée locale",
           "L'historique reste sur cette machine. Un carnet de lots est une "
           "donnée commerciale.")

    try:
        cx = store.ouvrir(reglages["base"])
    except store.StoreError as e:
        st.error(str(e))
        return

    try:
        entrees = store.lister(cx, limite=200)
        if not entrees:
            st.markdown(
                '<div class="carte" style="text-align:center;padding:48px">'
                '<div style="font-size:15px;font-weight:600">Aucune analyse '
                'enregistrée</div></div>', unsafe_allow_html=True)
            return

        with st.container(border=True):
         st.dataframe(
            [{"#": e.id, "Lot": e.lot_id, "Client": e.client,
              "Analysé le": e.analyse_le.strftime("%Y-%m-%d %H:%M"),
              "Bouclage": e.bouclage_statut.upper(),
              "Prix maximal": e.fourchette(),
              "Destinataire": e.destinataire,
              "Démo": "oui" if e.demo else ""} for e in entrees],
            use_container_width=True, hide_index=True)

        choix = st.selectbox(
            "Ressortir une analyse", entrees,
            format_func=lambda e: f"#{e.id} — {e.lot_id} — "
                                  f"{e.analyse_le:%Y-%m-%d %H:%M}")
        if choix is None:
            return
        c1, c2 = st.columns(2)
        if c1.button("Afficher le rapport émis", use_container_width=True):
            st.markdown(store.rapport(cx, choix.id))
        if c2.button("Rejouer la reconstitution", use_container_width=True,
                     help="Mêmes teneurs, même provenance, même graine. Les "
                          "prix ne sont pas restitués : ceux de l'époque "
                          "seraient périmés."):
            try:
                st.session_state["analyse"] = analyser(store.refaire(cx, choix.id))
                st.session_state["enregistre"] = True
                st.success("Reconstitution rejouée. Voir la page Analyse.")
            except Exception as e:
                titre, detail = message_de_refus(e)
                st.error(f"**{titre}** — {detail}")
    finally:
        cx.close()


# ==========================================================================
# Page : Aide
# ==========================================================================

def _page_aide() -> None:
    _fil("Aide")
    _heros("Comment lire un rapport KLASTOS21",
           "Trois notions suffisent à exploiter l'outil sans se tromper.",
           "Engagement", "Le protocole méthodologique complet accompagne "
           "chaque rapport.")
    for titre, texte in (
        ("Grandeur déterminée",
         "L'analyse élémentaire la contraint à une valeur unique, quelle que "
         "soit la ventilation retenue par le solveur. Ce sont les seules "
         "grandeurs opposables, et les seules qui entrent dans le prix."),
        ("Grandeur mal déterminée",
         "Déterminée en théorie, mais le conditionnement du système rend la "
         "fourchette trop large pour être exploitée. L'identifiabilité est "
         "binaire, le conditionnement est continu."),
        ("Domaine compatible",
         "Toute valeur du domaine explique le bulletin aussi bien qu'une "
         "autre. Ce n'est pas une imprécision de mesure : c'est une "
         "propriété du système. Une meilleure analyse chimique ne la réduit "
         "pas ; une donnée structurale ou une attestation de provenance, si."),
        ("Bouclage massique",
         "La somme des phases reconstituées. Ce qui manque pour atteindre "
         "100 % n'est pas une erreur de calcul : c'est de l'humidité, une "
         "phase absente du modèle, ou une provenance mal déclarée."),
    ):
        st.markdown(
            f'<div class="carte">{_carte_titre(None, titre)}'
            f'<div style="font-size:13.5px;color:#5A6472;line-height:1.6">'
            f'{texte}</div></div>', unsafe_allow_html=True)


# ==========================================================================
# Barre laterale
# ==========================================================================

def _reglages() -> dict:
    _marque()
    page = st.sidebar.radio("Navigation", PAGES, label_visibility="collapsed")
    st.sidebar.markdown("---")

    def _libelle_profil(cle: str) -> str:
        p = PROVENANCE_PROFILES[cle]
        suffixe = "" if getattr(p, "validated", True) else "  (non arbitré)"
        return f"{p.label}{suffixe}"

    provenance = st.sidebar.selectbox(
        "Provenance déclarée", sorted(PROVENANCE_PROFILES),
        index=sorted(PROVENANCE_PROFILES).index("non_declaree"),
        format_func=_libelle_profil)
    if not getattr(PROVENANCE_PROFILES[provenance], "validated", True):
        st.sidebar.warning(
            "Ce profil d'exclusion n'a pas été arbitré métier. Les phases "
            "qu'il écarte relèvent d'une hypothèse, pas d'une décision.")

    attestee = st.sidebar.checkbox(
        "Le client a signé l'attestation de provenance.",
        help="SANS CETTE ATTESTATION, AUCUNE PHASE N'EST EXCLUE, quelle que "
             "soit la provenance choisie. Exclure une phase sur une simple "
             "déclaration orale reviendrait à sous-estimer un lot sans trace.")
    if not attestee and provenance != "non_declaree":
        st.sidebar.info("Provenance renseignée sans attestation : aucune "
                        "phase ne sera exclue. Le rapport le dira.")

    grades = None
    if provenance == "chutes_gigafactory":
        saisis = st.sidebar.multiselect(
            "Grades produits sur le site",
            ["NMC111", "NMC532", "NMC622", "NMC811", "NCA", "LFP", "LCO",
             "LMO"])
        grades = tuple(saisis) if saisis else None

    destinataire = st.sidebar.radio(
        "Destinataire du rapport", [DESTINATAIRE_TIERS, DESTINATAIRE_INTERNE],
        format_func=lambda x: "Un tiers (client)" if x == DESTINATAIRE_TIERS
                              else "Usage interne",
        help="Des prix d'agence sans licence de rediffusion font refuser un "
             "document destiné à un tiers.")

    with st.sidebar.expander("Valorisation"):
        spec = st.selectbox("Spécification à contrôler",
                            ["(aucune)"] + sorted(REFERENCE_SPECS))
        cout = st.number_input("Coût de traitement (par tonne)",
                               min_value=0.0, value=0.0, step=10.0)
        marge = st.slider("Marge visée", 0.0, 0.6, 0.0, 0.01)

    with st.sidebar.expander("Seuils et calcul"):
        st.caption(f"Seuils arbitrés : alerte {CLOSURE_ALERT:.0%}, "
                   f"rejet {CLOSURE_REJECT:.0%}.")
        seuil_alerte = st.number_input("Seuil d'alerte", 0.0, 1.0,
                                       CLOSURE_ALERT, 0.01)
        seuil_rejet = st.number_input("Seuil de rejet", 0.0, 1.0,
                                      CLOSURE_REJECT, 0.01)
        tirages = st.slider("Tirages de propagation", 40, 500, 200, 20)
        graine = st.number_input("Graine aléatoire", 0, 10_000, 0, 1,
                                 help="Même graine, même résultat.")
        separateur = st.text_input("Séparateur du CSV", value=",")

    with st.sidebar.expander("Historique"):
        historique = st.checkbox("Enregistrer les analyses", value=True)
        base = st.text_input("Fichier d'historique",
                             value=str(pathlib.Path("data")
                                       / "historique.sqlite"))

    st.sidebar.markdown(
        '<div class="etat-systeme"><span class="pastille-verte"></span>'
        '<b>Système prêt</b><br>Prêt à traiter un nouveau bulletin.</div>',
        unsafe_allow_html=True)

    return dict(
        page=page, provenance=provenance, attestee=attestee, grades=grades,
        destinataire=destinataire,
        specification=REFERENCE_SPECS.get(spec) if spec != "(aucune)" else None,
        cout=cout, marge=marge, seuil_alerte=seuil_alerte,
        seuil_rejet=seuil_rejet, tirages=tirages, graine=int(graine),
        separateur=separateur or ",", historique=historique, base=base,
        emis_le=_dt.date.today())


# ==========================================================================
# Point d'entree
# ==========================================================================

def main() -> None:
    st.set_page_config(page_title=TITRE, page_icon="⚗", layout="wide",
                       initial_sidebar_state="expanded")
    st.markdown(theme.CSS, unsafe_allow_html=True)
    reglages = _reglages()

    page = reglages["page"]
    if page == "Analyse":
        _page_analyse(reglages)
    elif page == "Prix":
        _page_prix(reglages)
    elif page == "Historique":
        _page_historique(reglages)
    else:
        _page_aide()


if __name__ == "__main__":
    main()