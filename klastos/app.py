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

from klastos import charts, i18n, theme
from klastos.ingestion import IngestionError, parse_rows
from klastos.market import (MissingPriceError, NotAProductionSourceError,
                            REFERENCE_SPECS, StalePriceError)
from klastos.provenance import PROVENANCE_PROFILES
from klastos.report import (DESTINATAIRE_INTERNE, DESTINATAIRE_TIERS,
                            SECTION_REDUIRE, ReportRefused)
from klastos.service import Analyse, Demande, analyser, charger_prix, charger_termes
from klastos.identifiability import (CONSEIL_U_DEFAUT, UnboundedCompatibleSet)
from klastos.solver import CLOSURE_ALERT, CLOSURE_REJECT
from klastos.structural import (BASE_ABSOLUE, BASE_CRISTALLINE, BASES,
                                LIBELLE_BASE, StructuralRefused)
from klastos.units import ImplausiblePriceError

TITRE = "KLASTOS21"

#: Cles STABLES des pages. Elles etaient les libelles francais eux-memes, et
#: le routage comparait `page == "Analyse"` : traduire la navigation aurait
#: donc envoye toutes les pages sur la page d'aide, sans erreur visible.
#: Meme faute que les titres de sections du rapport. Voir klastos/i18n.py.
PAGES = ["analyse", "prix", "historique", "aide"]


def _langue() -> str:
    """
    La langue choisie dans la barre laterale.

    Lue dans l'etat de session parce que le selecteur est rendu APRES
    certains textes de la barre : sans memoire, le premier affichage sortirait
    dans la langue precedente a chaque changement.
    """
    return i18n.langue_valide(st.session_state.get("langue", i18n.DEFAUT))


def T(cle: str, **champs: object) -> str:
    """Raccourci de traduction, dans la langue courante de l'interface."""
    return i18n.t(cle, _langue(), **champs)


def SOUS_TITRE() -> str:
    return T("rapport.doc.soustitre")


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
    langue: str = i18n.DEFAUT,
) -> Demande:
    """Assemble la demande. Fonction pure : c'est elle qui est testee."""
    return Demande(
        lignes=lignes,
        langue=langue,
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
        return (T("ui.refus.rapport"), str(exc))
    if isinstance(exc, NotAProductionSourceError):
        return (T("ui.refus.source_prix"), str(exc))
    if isinstance(exc, StalePriceError):
        return (T("ui.refus.prix_perimes"), str(exc))
    if isinstance(exc, MissingPriceError):
        return (T("ui.refus.prix_manquant"), str(exc))
    if isinstance(exc, ImplausiblePriceError):
        return (T("ui.refus.prix_invraisemblable"), str(exc))
    if isinstance(exc, IngestionError):
        return (T("ui.refus.bulletin"), str(exc))
    return (T("ui.refus.analyse"), str(exc))


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
                <div class="marque-sous">{SOUS_TITRE()}</div>
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
    _fil(T("ui.page.analyse"))
    _heros(
        T("ui.analyse.titre"),
        T("ui.analyse.chapeau"),
        T("ui.analyse.garantie_titre"),
        T("ui.analyse.garantie"))

    gauche, droite = st.columns([1, 2], gap="medium")

    with gauche:
        with st.container(border=True):
            st.markdown(_carte_titre("1", T("ui.import.titre")),
                        unsafe_allow_html=True)
            fichier = st.file_uploader(
                T("ui.import.depot"),
                type=["csv"], label_visibility="collapsed",
                help=T("ui.import.aide"))
            # Le separateur est ICI, et non dans un volet de reglages : il
            # porte sur le fichier qu'on vient de deposer. Enfoui ailleurs,
            # il a fait echouer deux analyses d'affilee sur un CSV en
            # point-virgule, l'erreur ne disant qu'« Aucune colonne
            # exploitable ».
            st.text_input(T("ui.separateur.libelle"), value=",",
                          key="separateur", help=T("ui.separateur.aide"))

        if fichier is None:
            st.markdown(
                f'<div class="methode">{T("ui.import.invite")}</div>',
                unsafe_allow_html=True)
            return

        try:
            lignes = lignes_depuis_csv(fichier.getvalue(),
                                       reglages["separateur"])
        except Exception as e:
            titre, detail = message_de_refus(e)
            st.error(f"**{titre}** : {detail}")
            return

        with st.expander(T("ui.import.lu")):
            st.dataframe([{T("ui.import.col_colonne"): k,
                           T("ui.import.col_valeur"): v}
                          for k, v in lignes.items()],
                         use_container_width=True, hide_index=True)

        with st.container(border=True):
            st.markdown(_carte_titre("2", T("ui.lot.titre")),
                        unsafe_allow_html=True)
            lot_id = st.text_input(T("ui.lot.identifiant"),
                                   value=pathlib.Path(fichier.name).stem)
            client = st.text_input(T("ui.lot.client"), value="Client")

        with st.container(border=True):
            st.markdown(
                _carte_titre("3", T("ui.drx.titre")),
                unsafe_allow_html=True)
            st.caption(T("ui.drx.facultatif"))
            f_drx = st.file_uploader(
                T("ui.drx.fichier"),
                type=["csv"], label_visibility="collapsed",
                key="drx_upload",
                help=T("ui.drx.aide"))
            base = st.radio(
                T("ui.drx.base"), list(BASES),
                format_func=lambda b: LIBELLE_BASE[b],
                horizontal=False, key="drx_base",
                help=T("ui.drx.base_aide"))
            conseil = st.checkbox(
                T("ui.drx.conseil"),
                value=False, key="drx_conseil",
                help=T("ui.drx.conseil_aide"))
            u_drx = st.number_input(
                T("ui.drx.incertitude"),
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
            st.caption(T("ui.prix.absent"))
        else:
            st.caption(T("ui.prix.charge", label=prix.label))

        lancer = st.button(T("ui.analyse.lancer"), type="primary",
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
            incertitude_drx=u_drx / 100.0,
            # Le rapport sort dans la langue de l'interface : sans cette
            # ligne, un operateur en anglais telechargeait un document
            # francais sans comprendre pourquoi.
            langue=reglages["langue"])
        with st.spinner(T("ui.analyse.en_cours")):
            try:
                st.session_state["analyse"] = analyser(demande)
                st.session_state["enregistre"] = False
            except Exception as e:
                st.session_state["analyse"] = None
                titre, detail = message_de_refus(e)
                with droite:
                    st.error(f"**{titre}** : {detail}")

    analyse = st.session_state.get("analyse")
    with droite:
        if analyse is None:
            st.markdown(
                f'<div class="carte" style="text-align:center;padding:56px 20px">'
                f'<div style="font-size:15px;font-weight:600;color:#13171E">'
                f'{T("ui.analyse.aucune")}</div>'
                f'<div style="font-size:13px;color:#5A6472;margin-top:7px">'
                f'{T("ui.analyse.aucune_detail")}</div>'
                f"</div>", unsafe_allow_html=True)
            return
        _resultats(analyse, reglages)


def _resultats(a: Analyse, reglages: dict) -> None:
    bouclage = a.incertitude.meta.get("closure")
    statut = bouclage.status if bouclage else "ok"
    teinte, fond = theme.TEINTE_BOUCLAGE.get(statut, theme.TEINTE_BOUCLAGE["ok"])
    verdict = T(f"ui.verdict.{statut}")
    sous = T(f"ui.verdict.{statut}_sous")

    st.markdown(
        f"""<div class="bandeau" style="background:{fond};border-color:{teinte};
                 color:{teinte}">
              <div><div class="bandeau-titre">{verdict}</div>
                   <div class="bandeau-sous">{sous}</div></div>
              <div class="bandeau-droite">
                {a.rapport.issued_on.isoformat()}<br>
                {T("ui.lot.echantillon")} : {a.rapport.lot_id}</div>
            </div>""", unsafe_allow_html=True)

    if a.rapport.is_demo:
        st.warning(T("ui.demo.avert"))

    t1, t2, t3, t4 = st.tabs([T("ui.onglet.ensemble"),
                              T("ui.onglet.composition"),
                              T("ui.onglet.reduire"),
                              T("ui.onglet.rapport")])
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
    c1.markdown(_tuile(T("ui.carte.bouclage"),
                       f"{central.explained_mass * 100:.2f} %",
                       T("ui.tuile.non_expliques",
                         part=central.unexplained_mass * 100),
                       statut), unsafe_allow_html=True)
    c2.markdown(_tuile(T("ui.tuile.degres"),
                       str(a.incertitude.degeneracy),
                       T("ui.tuile.degres_note")),
                unsafe_allow_html=True)
    c3.markdown(_tuile(T("ui.tuile.determinees"),
                       f"{compte['ferme']} / {sum(compte.values())}",
                       T("ui.tuile.en_domaine", n=compte["ouvert"])),
                unsafe_allow_html=True)
    if a.valorisation is not None:
        v = a.valorisation
        c4.markdown(_tuile(
            T("ui.tuile.prix_max"),
            f"{v.max_price_low:,.0f}–{v.max_price_high:,.0f}".replace(",", " "),
            T("ui.tuile.par_tonne", devise=v.currency), "prix"),
            unsafe_allow_html=True)
    else:
        c4.markdown(_tuile(T("ui.tuile.prix_max"),
                           T("ui.tuile.sans_valeur"),
                           T("ui.tuile.sans_prix")),
                    unsafe_allow_html=True)

    st.write("")
    g, d = st.columns([1, 1], gap="medium")

    with g, st.container(border=True):
        _, mode = charts.donnees_composition(a)
        st.markdown(_carte_titre(None, T("ui.carte.composition")),
                    unsafe_allow_html=True)
        st.altair_chart(charts.camembert(a), use_container_width=True)
        if mode == "elements":
            st.markdown(
                f'<div class="methode">'
                f'{T("ui.methode.camembert_elements")}</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="methode">'
                f'{T("ui.methode.camembert_phases")}</div>',
                unsafe_allow_html=True)

    with d, st.container(border=True):
        st.markdown(_carte_titre(None, T("ui.carte.teneurs")),
                    unsafe_allow_html=True)
        st.altair_chart(charts.barres_elements(a), use_container_width=True)
        st.markdown(_carte_titre(None, T("ui.carte.bouclage")),
                    unsafe_allow_html=True)
        st.altair_chart(charts.barre_bouclage(a), use_container_width=True)
        if bouclage is not None and statut != "ok":
            # Idem report.py : la cle est portee par le diagnostic, parce
            # qu'elle depend du sens de l'ecart et pas seulement du statut.
            st.caption(T(bouclage.cle_message))


def _composition(a: Analyse) -> None:
    g, d = st.columns([3, 2], gap="medium")
    with g, st.container(border=True):
        st.markdown(_carte_titre(None, T("ui.carte.domaines")),
                    unsafe_allow_html=True)
        st.altair_chart(charts.barres_domaines(a), use_container_width=True)
        st.markdown(
            f'<div class="methode">{T("ui.methode.domaines")}</div>',
            unsafe_allow_html=True)

    with d, st.container(border=True):
        st.markdown(_carte_titre(None, T("ui.carte.detail_phases")),
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
    st.markdown(_carte_titre(None, T("ui.carte.scenario")),
                unsafe_allow_html=True)
    graphe = charts.barres_scenario(a)
    if graphe is None:
        st.caption(T("ui.scenario.deja_dose"))
    else:
        st.altair_chart(graphe, use_container_width=True)
        sc = a.incertitude.meta["scenarios"][0]
        st.markdown(
            f'<div class="methode">'
            f'{T("ui.methode.scenario", bas=sc.value_low * 100, haut=sc.value_high * 100, umax=sc.max_useful_uncertainty * 100)}'
            f'</div>',
            unsafe_allow_html=True)

  with st.container(border=True):
    st.markdown(_carte_titre(None, T("ui.carte.drx")),
                unsafe_allow_html=True)

    if a.contrainte_par_drx:
        u = a.incertitude
        taux = u.structural_conflict_rate
        st.markdown(
            f'<div class="methode">'
            f'{T("ui.methode.drx_posee", n=len(a.structurale), base=a.structurale.basis)}'
            f'</div>',
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
            st.info(T("ui.drx.sans_effet"))

        if taux > 0.20:
            st.warning(T("ui.drx.conflit",
                         n=u.n_structural_conflicts, total=u.n_draws,
                         taux=taux * 100))
    else:
        st.markdown(
            f'<div class="methode">{T("ui.methode.drx_absente")}</div>',
            unsafe_allow_html=True)

  if a.conseil is not None and a.conseil.rows:
    with st.container(border=True):
        st.markdown(_carte_titre(None, T("ui.carte.conseil")),
                    unsafe_allow_html=True)
        c = a.conseil
        st.markdown(
            f'<div class="methode">'
            f'{T("ui.methode.conseil", resume=c.resume())}</div>',
            unsafe_allow_html=True)
        st.dataframe(
            [{T("ui.conseil.col_phase"): r.label,
              T("ui.conseil.col_plage"): f"{r.width_open * 100:.2f} pt",
              T("ui.conseil.col_gain"): f"{r.gain * 100:.0f} %",
              T("ui.conseil.col_verdict"): T("ui.conseil.a_commander")
              if r.useful else T("ui.conseil.sans_effet")}
             for r in c.rows],
            use_container_width=True, hide_index=True)

  with st.container(border=True):
    for section in a.rapport.sections:
        # Par la CLE, jamais par le titre. Ce filtre comparait
        # « Comment reduire » sans accent : depuis que le titre du rapport
        # porte le sien, il ne reconnaissait plus la section et l'encart
        # disparaissait de l'ecran sans qu'aucun test ne le signale.
        if section.cle == SECTION_REDUIRE:
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
    c1.download_button(T("ui.rapport.telecharger"), data=html,
                       file_name=f"rapport_{a.rapport.lot_id}.html",
                       mime="text/html", use_container_width=True,
                       type="primary",
                       help=T("ui.rapport.telecharger_aide"))
    c2.download_button("Markdown", data=a.rapport.to_markdown(),
                       file_name=f"rapport_{a.rapport.lot_id}.md",
                       mime="text/markdown", use_container_width=True)

    if reglages["historique"] and not st.session_state.get("enregistre"):
        import klastos.store as store

        cx = store.ouvrir(reglages["base"])
        try:
            i = store.enregistrer(cx, a)
            st.session_state["enregistre"] = True
            c3.success(T("ui.rapport.enregistre", i=i))
        finally:
            cx.close()

    for titre, elements in (
            (T("rapport.section.avertissements"), a.rapport.warnings),
            (T("ui.rapport.limites_courtes"), a.rapport.limitations),
            (T("rapport.section.tracabilite"), a.rapport.traceability)):
        if elements:
            with st.expander(titre):
                for x in elements:
                    st.write("- " + x)

    with st.expander(T("ui.rapport.apercu"), expanded=True):
        st.components.v1.html(html, height=720, scrolling=True)


# ==========================================================================
# Page : Prix
# ==========================================================================

def _page_prix(reglages: dict) -> None:
    _fil(T("ui.page.prix"))
    _heros(T("ui.prix.titre"), T("ui.prix.chapeau"),
           T("ui.prix.route_titre"), T("ui.prix.route"))

    g, d = st.columns([1, 2], gap="medium")
    with g:
        with st.container(border=True):
            st.markdown(_carte_titre("1", T("ui.prix.source")),
                        unsafe_allow_html=True)
            # Cles stables : comparer le LIBELLE affiche aurait envoye les
            # deux modes sur le flux d'agence des que l'ecran passe en
            # anglais. Meme faute que le routage des pages.
            mode = st.radio(T("ui.prix.source"), ["fichier", "agence"],
                            format_func=lambda m: T(f"ui.prix.mode_{m}"),
                            label_visibility="collapsed")

        if mode == "fichier":
            _source_fichier()
        else:
            _source_agence()

    with d:
        prix = st.session_state.get("prix")
        if prix is None:
            st.markdown(
                f'<div class="carte" style="text-align:center;padding:48px 20px">'
                f'<div style="font-size:15px;font-weight:600">'
                f'{T("ui.prix.aucun_titre")}</div>'
                f'<div style="font-size:13px;color:#5A6472;margin-top:7px">'
                f'{T("ui.prix.aucun_detail")}</div></div>',
                unsafe_allow_html=True)
            return

        with st.container(border=True):
         st.markdown(_carte_titre(None, prix.label), unsafe_allow_html=True)
        st.dataframe(
            [{T("ui.prix.col_metal"): m,
              T("ui.prix.col_prix", devise=prix.currency):
                  f"{p.value_per_tonne:,.2f}",
              T("ui.prix.col_date"): p.as_of.isoformat(),
              T("ui.prix.col_reference"): p.reference_name,
              T("ui.prix.col_source"): p.source}
              for m, p in sorted(prix.prices.items())],
             use_container_width=True, hide_index=True)

        if not prix.redistribution_licensed:
            st.warning(T("ui.prix.usage_interne"))


def _source_fichier() -> None:
  with st.container(border=True):
    st.markdown(_carte_titre("2", T("ui.prix.carte_fichier")),
                unsafe_allow_html=True)
    f = st.file_uploader(T("ui.prix.fichier"), type=["csv", "json"],
                         key="fichier_prix")
    chemin_payables = st.text_input(T("ui.prix.payables"),
                                    value="data/payable_terms.json")
    marche = st.text_input(T("ui.prix.marche"), value="cif_coree_sud")
    if f is not None and st.button(T("ui.prix.charger"), type="primary",
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
                st.error(f"**{titre}** : {detail}")


def _source_agence() -> None:
  with st.container(border=True):
    st.markdown(_carte_titre("2", T("ui.prix.carte_agence")),
                unsafe_allow_html=True)
    source = st.selectbox(T("ui.prix.agence"),
                          ["fastmarkets", "benchmark", "smm"])
    st.caption(T("ui.prix.identifiants"))
    licence = st.checkbox(T("ui.prix.licence"),
                          help=T("ui.prix.licence_aide"))
    marche = st.text_input(T("ui.prix.marche_payables"),
                           value="cif_coree_sud", key="marche_agence")
    if st.button(T("ui.prix.recuperer"), type="primary",
                 use_container_width=True):
        _recuperer_prix(source, licence, marche)


def _recuperer_prix(source: str, licence: bool, marche: str) -> None:
    from klastos.feeds import (BenchmarkFeed, CredentialsMissing,
                               FastmarketsFeed, FeedError, SMMFeed)
    from klastos.providers import ProviderError, build_price_set

    constructeurs = {"fastmarkets": FastmarketsFeed,
                     "benchmark": BenchmarkFeed, "smm": SMMFeed}
    flux = constructeurs[source](redistribution_licensed=licence)
    etat = T("ui.prix.licence_ok") if licence else T("ui.prix.licence_non")
    try:
        cotations = flux.quotes()
        st.session_state["prix"] = build_price_set(
            cotations,
            label=f"{source} du {cotations[0].as_of.isoformat()}, {etat}",
            is_production_source=True, origin=source,
            redistribution_licensed=licence)
        if hasattr(flux, "payables"):
            from klastos.market import PayableTerms

            st.session_state["termes"] = PayableTerms(
                market=marche, payables=flux.payables(marche),
                as_of=cotations[0].as_of,
                source=T("ui.prix.releve_auto", source=source),
                validated=True)
    except CredentialsMissing as e:
        st.error(f"**{T("ui.prix.identifiants_absents")}** : {e}")
    except (FeedError, ProviderError, ImplausiblePriceError) as e:
        st.error(f"**{source}** : {e}")


# ==========================================================================
# Page : Historique
# ==========================================================================

def _page_historique(reglages: dict) -> None:
    import klastos.store as store

    _fil(T("ui.page.historique"))
    _heros(T("ui.histo.titre"), T("ui.histo.chapeau"),
           T("ui.histo.locale_titre"), T("ui.histo.locale"))

    try:
        cx = store.ouvrir(reglages["base"])
    except store.StoreError as e:
        st.error(str(e))
        return

    try:
        entrees = store.lister(cx, limite=200)
        if not entrees:
            st.markdown(
                f'<div class="carte" style="text-align:center;padding:48px">'
                f'<div style="font-size:15px;font-weight:600">'
                f'{T("ui.histo.vide")}</div></div>', unsafe_allow_html=True)
            return

        with st.container(border=True):
         st.dataframe(
            [{"#": e.id, T("ui.histo.col_lot"): e.lot_id,
              T("ui.histo.col_client"): e.client,
              T("ui.histo.col_analyse_le"):
                  e.analyse_le.strftime("%Y-%m-%d %H:%M"),
              T("ui.histo.col_bouclage"): e.bouclage_statut.upper(),
              T("ui.histo.col_prix_max"): e.fourchette(),
              T("ui.histo.col_destinataire"): e.destinataire,
              T("ui.histo.col_demo"): T("ui.histo.oui") if e.demo else ""}
             for e in entrees],
            use_container_width=True, hide_index=True)

        choix = st.selectbox(
            T("ui.histo.ressortir"), entrees,
            format_func=lambda e: f"#{e.id} | {e.lot_id} | "
                                  f"{e.analyse_le:%Y-%m-%d %H:%M}")
        if choix is None:
            return
        c1, c2 = st.columns(2)
        if c1.button(T("ui.histo.afficher"), use_container_width=True):
            st.markdown(store.rapport(cx, choix.id))
        if c2.button(T("ui.histo.rejouer"), use_container_width=True,
                     help=T("ui.histo.rejouer_aide")):
            try:
                st.session_state["analyse"] = analyser(store.refaire(cx, choix.id))
                st.session_state["enregistre"] = True
                st.success(T("ui.histo.rejoue"))
            except Exception as e:
                titre, detail = message_de_refus(e)
                st.error(f"**{titre}** : {detail}")
    finally:
        cx.close()


# ==========================================================================
# Page : Aide
# ==========================================================================

def _page_aide() -> None:
    _fil(T("ui.page.aide"))
    _heros(T("ui.aide.titre"), T("ui.aide.chapeau"),
           T("ui.aide.engagement_titre"), T("ui.aide.engagement"))
    for titre, texte in (
        (T("ui.aide.determinee_titre"), T("ui.aide.determinee")),
        (T("ui.aide.mal_determinee_titre"), T("ui.aide.mal_determinee")),
        (T("ui.aide.domaine_titre"), T("ui.aide.domaine")),
        (T("ui.aide.bouclage_titre"), T("ui.aide.bouclage")),
    ):
        st.markdown(
            f'<div class="carte">{_carte_titre(None, titre)}'
            f'<div style="font-size:13.5px;color:#5A6472;line-height:1.6">'
            f'{texte}</div></div>', unsafe_allow_html=True)


# ==========================================================================
# Barre laterale
# ==========================================================================

def _reglages() -> dict:
    # Le selecteur de langue vient en PREMIER, avant la marque : c'est le
    # seul reglage dont depend l'affichage de tous les autres.
    st.sidebar.selectbox(
        T("ui.langue.libelle"), i18n.LANGUES, key="langue",
        format_func=lambda lg: T(f"ui.langue.nom.{lg}"),
        help=T("ui.langue.aide"))

    _marque()
    page = st.sidebar.radio(
        T("ui.nav.libelle"), PAGES, label_visibility="collapsed",
        format_func=lambda cle: T(f"ui.page.{cle}"))
    st.sidebar.markdown("---")

    def _libelle_profil(cle: str) -> str:
        p = PROVENANCE_PROFILES[cle]
        suffixe = ("" if getattr(p, "validated", True)
                   else T("ui.provenance.non_arbitre"))
        return f"{p.label}{suffixe}"

    provenance = st.sidebar.selectbox(
        T("ui.provenance.libelle"), sorted(PROVENANCE_PROFILES),
        index=sorted(PROVENANCE_PROFILES).index("non_declaree"),
        format_func=_libelle_profil)
    if not getattr(PROVENANCE_PROFILES[provenance], "validated", True):
        st.sidebar.warning(T("ui.provenance.avert_non_arbitre"))

    attestee = st.sidebar.checkbox(
        T("ui.attestation.libelle"), help=T("ui.attestation.aide"))
    if not attestee and provenance != "non_declaree":
        st.sidebar.info(T("ui.attestation.sans"))

    grades = None
    if provenance == "chutes_gigafactory":
        # Les noms de grade sont des designations techniques : ils ne se
        # traduisent pas.
        saisis = st.sidebar.multiselect(
            T("ui.grades.libelle"),
            ["NMC111", "NMC532", "NMC622", "NMC811", "NCA", "LFP", "LCO",
             "LMO"])
        grades = tuple(saisis) if saisis else None

    destinataire = st.sidebar.radio(
        T("ui.destinataire.libelle"),
        [DESTINATAIRE_TIERS, DESTINATAIRE_INTERNE],
        format_func=lambda x: T("ui.destinataire.tiers")
        if x == DESTINATAIRE_TIERS else T("ui.destinataire.interne"),
        help=T("ui.destinataire.aide"))

    with st.sidebar.expander(T("ui.volet.valorisation")):
        aucune = T("ui.spec.aucune")
        spec = st.selectbox(T("ui.spec.libelle"),
                            [aucune] + sorted(REFERENCE_SPECS))
        cout = st.number_input(T("ui.cout.libelle"),
                               min_value=0.0, value=0.0, step=10.0)
        marge = st.slider(T("ui.marge.libelle"), 0.0, 0.6, 0.0, 0.01)

    with st.sidebar.expander(T("ui.volet.seuils")):
        st.caption(T("ui.seuils.arbitres",
                     alerte=CLOSURE_ALERT, rejet=CLOSURE_REJECT))
        seuil_alerte = st.number_input(T("ui.seuil.alerte"), 0.0, 1.0,
                                       CLOSURE_ALERT, 0.01)
        seuil_rejet = st.number_input(T("ui.seuil.rejet"), 0.0, 1.0,
                                      CLOSURE_REJECT, 0.01)
        tirages = st.slider(T("ui.tirages.libelle"), 40, 500, 200, 20)
        graine = st.number_input(T("ui.graine.libelle"), 0, 10_000, 0, 1,
                                 help=T("ui.graine.aide"))

    with st.sidebar.expander(T("ui.volet.historique")):
        historique = st.checkbox(T("ui.historique.enregistrer"), value=True)
        base = st.text_input(T("ui.historique.fichier"),
                             value=str(pathlib.Path("data")
                                       / "historique.sqlite"))

    st.sidebar.markdown(
        f'<div class="etat-systeme"><span class="pastille-verte"></span>'
        f'<b>{T("ui.etat.pret")}</b><br>{T("ui.etat.pret_detail")}</div>',
        unsafe_allow_html=True)

    return dict(
        page=page, langue=_langue(), provenance=provenance,
        attestee=attestee, grades=grades, destinataire=destinataire,
        specification=REFERENCE_SPECS.get(spec) if spec != aucune else None,
        cout=cout, marge=marge, seuil_alerte=seuil_alerte,
        seuil_rejet=seuil_rejet, tirages=tirages, graine=int(graine),
        # Le separateur a quitte ce volet : il est desormais pose a cote du
        # televersement, ou l'utilisateur le cherche. Enfoui sous « Seuils et
        # calcul », il a fait echouer deux analyses d'affilee sur un CSV en
        # point-virgule, avec pour seul indice « Aucune colonne exploitable ».
        separateur=st.session_state.get("separateur") or ",",
        historique=historique, base=base,
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
    if page == "analyse":
        _page_analyse(reglages)
    elif page == "prix":
        _page_prix(reglages)
    elif page == "historique":
        _page_historique(reglages)
    else:
        _page_aide()


if __name__ == "__main__":
    main()