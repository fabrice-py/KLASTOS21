"""
Tests des bandes de plausibilite sur les compositions predites.

Defaut d'origine, trouve le 22 octobre 2026 sur un lot reel : ni le
phosphore ni le fluor n'etant doses, le solveur a predit 17,79 % de FLUOR en
retenant 14,3 % de LiPF6 et 11,8 % de PVDF. Le materiau de reference
certifie OREAS donne un fluor a 2,44 % : la prediction valait sept fois la
valeur d'un materiau reel, et rien ne l'a signale. `is_exploitable` valait
True, et le lot serait parti en valorisation avec 110 % de masse.

Le generateur synthetique ne pouvait pas reveler ce trou : il produit des
lots coherents par construction, et `make_lot` refuse meme un bouclage
superieur a 1.
"""

from __future__ import annotations

import pathlib

import numpy as np
import pytest

from klastos import i18n
from klastos.phases import PHASE_KEYS
from klastos.plausibility import (ANCRAGES_CERTIFIES,
                                  FACTEUR_PLAUSIBILITE, FACTEUR_VALIDE,
                                  SANS_ANCRAGE_DOCUMENTE, bandes,
                                  verifier_predictions)
from klastos.service import Demande, analyser

#: Fractions de phases rapportees sur le lot reel BM1. Le reste du melange
#: est complete pour que la somme reste realiste ; seules LiPF6 et PVDF
#: portent le fluor, donc seules elles pilotent la prediction.
PHASES_BM1 = {"LiPF6": 0.143, "PVDF": 0.118, "NMC811": 0.40, "C_total": 0.25}

#: Teneurs certifiees du materiau OREAS, en %. Le fluor y EST dose.
OREAS_F_PCT = 2.44
OREAS_P_PCT = 0.350


def _x_depuis(fractions: dict[str, float]) -> tuple[np.ndarray, list[str]]:
    keys = list(PHASE_KEYS)
    x = np.zeros(len(keys))
    for phase, v in fractions.items():
        x[keys.index(phase)] = v
    return x, keys


# ==========================================================================
# 1. Ce que les bandes valent, et ce qu'elles ne valent pas
# ==========================================================================

def test_les_ancrages_viennent_d_un_seul_certificat():
    """
    UN POINT N'EST PAS UNE BANDE. Une valeur sur un seul materiau ne
    decrit pas une population : elle dit seulement qu'un materiau reel
    existe a ce niveau-la. Le test fige cette modestie pour qu'un ajout
    silencieux d'ancrages inventes echoue.

    Le certificat porte DEUX valeurs utilisables en principe, F et P, et
    une seule est retenue. Le phosphore a ete ecarte sur mesure, pas par
    prudence vague : voir `test_le_phosphore_n_est_pas_ancre_et_c_est_mesure`.
    """
    assert set(ANCRAGES_CERTIFIES) == {"F"}, (
        "aucun ancrage ne doit etre ajoute sans certificat a l'appui")
    assert ANCRAGES_CERTIFIES["F"] == pytest.approx(OREAS_F_PCT / 100.0)
    # Le certificat porte aussi P = 0,350 %, et ce n'est PAS un ancrage.
    # Voir `test_le_phosphore_n_est_pas_ancre_et_c_est_mesure`.
    assert "P" not in ANCRAGES_CERTIFIES
    assert "P" in SANS_ANCRAGE_DOCUMENTE, (
        "un element ecarte doit l'etre pour une raison ecrite")


def test_aucune_borne_n_est_declaree_validee():
    """
    Le facteur n'est pas arbitre, donc aucune borne ne peut l'etre. Le
    rapport doit porter cette mention, comme il porte « NON ARBITRE » sur
    l'age maximal d'un taux de change.
    """
    assert FACTEUR_VALIDE is False
    for bande in bandes().values():
        assert bande.validated is False, bande.element
        assert "OREAS" in bande.source
        assert "un seul materiau" in bande.source


def test_la_borne_haute_derive_de_l_ancrage_et_du_facteur():
    for el, ancre in ANCRAGES_CERTIFIES.items():
        bande = bandes(facteur=4.0)[el]
        assert bande.high == pytest.approx(ancre * 4.0)
        assert bande.low == 0.0, (
            "la borne basse est zero : un element non dose peut etre absent")


def test_les_bandes_suivent_le_facteur():
    """
    Les bandes sont CALCULEES et non figees dans une constante. Une table
    figee aurait ignore un changement de facteur en silence.
    """
    etroite = bandes(facteur=1.5)["F"].high
    large = bandes(facteur=6.0)["F"].high
    assert etroite < large
    assert large / etroite == pytest.approx(4.0)


# ==========================================================================
# 2. Ce qui est controle, et ce qui ne l'est pas
# ==========================================================================

def test_un_element_dose_n_est_jamais_controle():
    """
    La regle qui epargne le lot OREAS. Une teneur dosee est une MESURE, pas
    une prediction : la refuser reviendrait a contester le laboratoire. Le
    controle ne porte que sur ce que le solveur invente.
    """
    x, keys = _x_depuis(PHASES_BM1)
    # Meme melange, mais le bulletin dose F et P.
    c = verifier_predictions(x, keys, ["Li", "Ni", "Mn", "Co", "Al", "Fe",
                                       "Cu", "C", "F", "P"])
    assert c.depassements == (), (
        "un element dose a ete signale : le controle sort de son role")
    assert not c


def test_un_element_sans_ancrage_est_declare_non_controle():
    """
    « N'invente aucune borne pour les elements sans ancrage. » L'absence de
    controle est DECLAREE, elle n'est pas un satisfecit : c'est la regle du
    projet, ne jamais afficher ce que la donnee ne porte pas.

    H et O n'ont pas d'ancrage certifie, et l'oxygene n'est jamais dose
    (protocole 2.6). Ils doivent donc ressortir comme non controles, et
    jamais comme conformes.
    """
    x, keys = _x_depuis(PHASES_BM1)
    c = verifier_predictions(x, keys, ["Li", "Ni", "Mn", "Co", "Al", "Fe",
                                       "Cu", "C"])
    assert "O" in c.non_controles
    assert "H" in c.non_controles
    for el in c.non_controles:
        assert el not in ANCRAGES_CERTIFIES, (
            f"{el} a un ancrage : il devait etre controle, pas ecarte")


# ==========================================================================
# 3. Le lot reel
# ==========================================================================

def test_la_prediction_de_fluor_du_lot_reel_est_signalee():
    """
    Le cas de non-regression. 17,7 % de fluor predit contre 2,44 %
    certifie : un facteur sept, qu'aucun reglage raisonnable ne doit
    laisser passer.
    """
    x, keys = _x_depuis(PHASES_BM1)
    c = verifier_predictions(x, keys, ["Li", "Ni", "Mn", "Co", "Al", "Fe",
                                       "Cu", "C"])
    assert c, "la prediction de fluor du lot reel n'est plus signalee"

    fluor = next(d for d in c.depassements if d.element == "F")
    assert fluor.fraction == pytest.approx(0.1773, abs=5e-4)
    assert fluor.facteur_observe > 7.0
    assert fluor.fraction > fluor.borne


def test_le_depassement_nomme_la_phase_porteuse():
    """
    « Depassement -> le rapport nomme l'element ET la phase porteuse
    responsable. » Sans le nom de la phase, l'utilisateur sait qu'un
    chiffre est faux mais pas ou agir.

    Sur ce melange, LiPF6 est a 75,04 % de fluor et PVDF a 59,34 % : la
    phase porteuse majoritaire est donc LiPF6, et c'est elle qu'il faut
    nommer.
    """
    x, keys = _x_depuis(PHASES_BM1)
    c = verifier_predictions(x, keys, ["Li", "Ni", "Mn", "Co", "Al", "Fe",
                                       "Cu", "C"])
    fluor = next(d for d in c.depassements if d.element == "F")
    assert fluor.phase == "LiPF6"
    assert fluor.phase_fraction == pytest.approx(0.143)


def test_le_phosphore_n_est_pas_ancre_et_c_est_mesure():
    """
    Ce test affirmait l'inverse, et il celebrait un FAUX POSITIF.

    Une premiere version ancrait le phosphore sur le certificat - P =
    0,350 % - et se felicitait de voir le melange de BM1 signale a 8,3 fois
    cette valeur. Mesure sur 1 200 lots que les profils du projet declarent
    plausibles, phosphore non dose : 45,8 % etaient signales, et 100 % des
    lots riches en LFP.

    La cause est chimique et elle condamne l'ancrage : LFP est LiFePO4, le
    phosphore y est un element MAJEUR. Les profils du projet produisent
    jusqu'a 11,70 % de P, soit 33 fois la teneur du certificat, parce que le
    materiau OREAS ne contient quasiment pas de LFP.

    Le phosphore est donc declare non controle, et le dire est la seule
    honnetete disponible : l'outil ne sait pas borner cette prediction.
    """
    x, keys = _x_depuis(PHASES_BM1)
    c = verifier_predictions(x, keys, ["Li", "Ni", "Mn", "Co", "Al", "Fe",
                                       "Cu", "C"])
    assert all(d.element != "P" for d in c.depassements), (
        "le phosphore est de nouveau signale : la bande a ete rendue, et "
        "elle refuse 100 % des lots LFP")
    assert "P" in c.non_controles, (
        "le phosphore doit etre DECLARE non controle, pas passe sous "
        "silence")


def test_aucun_lot_plausible_du_projet_n_est_refuse():
    """
    Le test de faux positifs qui manquait, et dont l'absence a laisse
    passer la bande de phosphore.

    Il porte sur les lots que le generateur du projet declare plausibles,
    avec F et P non doses - la situation de BM1. Aucun ne doit etre
    signale. Le generateur n'est pas un oracle du reel, mais refuser ce
    qu'il juge normal est un signe sur pour une borne mal posee.
    """
    from klastos.generator import NOISE_FREE, make_lot

    DOSES = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "Cu", "C"]
    refuses = []
    for profil in ("gigafactory_nmc", "mixed_ev", "consumer_electronics",
                   "lfp_heavy"):
        for graine in range(60):
            lot = make_lot(rng=graine, profile=profil, noise=NOISE_FREE,
                           closure=1.0)
            c = verifier_predictions(lot.x_true, lot.phase_keys, DOSES)
            for d in c.depassements:
                refuses.append(f"{profil}/{graine} : {d.element} a "
                               f"{d.fraction * 100:.2f} %")
    assert not refuses, (
        f"{len(refuses)} lot(s) plausible(s) refuse(s), par exemple "
        f"{refuses[:3]}")


# ==========================================================================
# 4. Sur le chemin unique, de bout en bout
# ==========================================================================

BULLETIN_COMPLET = pathlib.Path("data/exemples/bulletin_coherent.csv")


@pytest.fixture
def bulletin_sans_f_ni_p(tmp_path):
    """
    Le bulletin d'exemple prive de ses colonnes F et P.

    C'est la reproduction exacte de la situation du lot reel : meme
    matiere, meme tout, seule la COUVERTURE du bulletin change. Le fluor y
    est mesure a 1,70 % ; sans la colonne, le solveur le predit a 8,92 %.
    """
    lignes = BULLETIN_COMPLET.read_text(encoding="utf-8").splitlines()
    entetes = lignes[0].split(",")
    valeurs = lignes[1].split(",")
    garde = [i for i, e in enumerate(entetes)
             if not e.startswith(("P (", "F ("))]
    f = tmp_path / "sans_fp.csv"
    f.write_text(
        ",".join(entetes[i] for i in garde) + "\n"
        + ",".join(valeurs[i] for i in garde) + "\n",
        encoding="utf-8")
    return f


def _analyser(chemin, **kw):
    return analyser(Demande(bulletin=str(chemin),
                            provenance="vehicule_electrique",
                            attestee=True, tirages=30, **kw))


def test_un_bulletin_complet_ne_declenche_rien():
    """Le pendant positif : F et P doses, donc aucune prediction a juger."""
    a = _analyser(BULLETIN_COMPLET)
    assert "F" in a.lecture.measured_elements
    assert "P" in a.lecture.measured_elements
    assert a.plausibilite.depassements == ()


def test_retirer_les_colonnes_f_et_p_fait_apparaitre_l_alerte(
        bulletin_sans_f_ni_p):
    """
    La demonstration du defaut, sur le chemin unique. Le fluor MESURE vaut
    1,70 % ; sans sa colonne, le modele lui en attribue cinq fois plus et
    le signale desormais.
    """
    a = _analyser(bulletin_sans_f_ni_p)
    assert "F" not in a.lecture.measured_elements
    assert a.plausibilite, "aucune alerte alors que F et P sont predits"

    fluor = next(d for d in a.plausibilite.depassements if d.element == "F")
    assert fluor.fraction > 3.0 * 0.0170, (
        "le fluor predit devrait depasser largement sa valeur mesuree")
    assert fluor.phase in ("PVDF", "LiPF6")


def test_le_rapport_nomme_l_element_et_la_phase(bulletin_sans_f_ni_p):
    """L'avertissement doit atteindre le document, pas rester dans l'objet."""
    a = _analyser(bulletin_sans_f_ni_p)
    fluor = next(d for d in a.plausibilite.depassements if d.element == "F")

    vise = [w for w in a.rapport.warnings if "F" in w and fluor.phase in w]
    assert vise, (
        f"aucun avertissement ne nomme a la fois F et {fluor.phase} ; "
        f"avertissements : {a.rapport.warnings}")
    avert = vise[0]
    assert "NON ARBITRÉ" in avert, (
        "le rapport doit dire que la borne n'est pas arbitree")


def test_l_avertissement_est_bilingue(bulletin_sans_f_ni_p):
    fr = _analyser(bulletin_sans_f_ni_p, langue="fr")
    en = _analyser(bulletin_sans_f_ni_p, langue="en")
    a_fr = [w for w in fr.rapport.warnings if "implausible" in w.lower()]
    a_en = [w for w in en.rapport.warnings if "implausible" in w.lower()]
    assert a_fr and a_en
    assert a_fr[0] != a_en[0]
    assert "NOT ARBITRATED" in a_en[0]
    # Le francais ne doit pas fuir dans le rapport anglais.
    assert "matériau certifié" not in a_en[0]


def test_le_facteur_est_expose_comme_les_seuils_de_bouclage(
        bulletin_sans_f_ni_p):
    """
    « Expose le seuil en parametre comme les seuils de bouclage. » Un
    reglage non arbitre doit pouvoir se discuter sans toucher au code.
    """
    large = _analyser(bulletin_sans_f_ni_p, facteur_plausibilite=50.0)
    assert large.plausibilite.depassements == (), (
        "un facteur tres large doit tout laisser passer")

    etroit = _analyser(bulletin_sans_f_ni_p, facteur_plausibilite=1.0)
    assert etroit.plausibilite.depassements, (
        "un facteur de 1 doit signaler toute prediction au-dessus de "
        "l'ancrage")


def test_le_facteur_par_defaut_attrape_le_lot_reel():
    """
    Garde sur la valeur par defaut. Le lot reel est a 7,3 fois l'ancrage :
    tout facteur par defaut au-dela le laisserait passer, et le defaut
    serait de retour sans qu'aucun autre test ne bouge.
    """
    assert FACTEUR_PLAUSIBILITE < 7.0, (
        f"un facteur par defaut de {FACTEUR_PLAUSIBILITE} ne signalerait "
        f"plus la prediction de fluor du lot reel (7,3 x l'ancrage)")


def test_la_cle_de_l_avertissement_existe_dans_les_deux_langues():
    for langue in ("fr", "en"):
        texte = i18n.t("rapport.avert.prediction_implausible", langue,
                       element="F", valeur=17.73, facteur=7.3, ancrage=2.44,
                       phase="LiPF6", part=14.3, borne=7.32, ecart=3.0)
        assert "F" in texte and "LiPF6" in texte
