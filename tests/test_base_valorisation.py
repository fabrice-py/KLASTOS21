"""
SUR QUOI LE LOT EST-IL VALORISE : LE DOSAGE, OU LA RECONSTRUCTION ?

POURQUOI CE FICHIER EXISTE
--------------------------
La valorisation lisait les fonctionnelles `el_X`, definies comme la ligne
de la matrice de stoechiometrie : `el_X = (A @ x)`. C'est la teneur que le
modele RECONSTRUIT apres deconvolution, pas celle que le laboratoire a
dosee.

Tant que l'ajustement est bon, les deux coincident au millieme pres et le
detour ne coute rien. Des qu'une phase manque au modele, ils divergent :
nickel reconstruit a 15,3 % quand le bulletin en dit 17,6 %. Le lot etait
alors facture sur un nombre que le laboratoire n'avait jamais mesure - et
qu'aucune contrepartie n'accepterait d'opposer, puisqu'un contrat de
raffinage paie sur le dosage.

CE QUE CES TESTS GARDENT
------------------------
  1. que la valorisation retienne le DOSAGE des qu'il est disponible ;
  2. que l'ecart entre les deux soit RAPPORTE, jamais tu ;
  3. que le repli sur la reconstruction reste possible, pour un rapport
     qui ne porterait pas de dosage.
"""

from __future__ import annotations

import datetime as dt

import pytest

from klastos.market import MetalPrice, PayableTerms, PriceSet
from klastos.uncertainty import (UncertaintyConfig, UncertaintyReport,
                                UncertaintyResult)
from klastos.valuation import ECART_DOSAGE_MODELE, value_lot

AUJ = dt.date(2026, 9, 5)

PRIX = PriceSet(
    currency="USD", label="jeu de test", is_production_source=True,
    prices={
        "Ni": MetalPrice("Ni", 20_000.0, "USD", dt.date(2026, 9, 4),
                         "test", "LME Ni cash official"),
    },
)
TERMES = PayableTerms(market="test", payables={"Ni": 1.0}, as_of=AUJ,
                      source="test", validated=True)


def _resultat(**kw) -> UncertaintyResult:
    """Une teneur en nickel, dont on pilote dosage et reconstruction."""
    base = dict(
        key="el_Ni", label="Ni total", block="ferme_attendu",
        identifiable=True, median=0.16,
        analytic_lower=0.15, analytic_upper=0.17,
        total_lower=0.15, total_upper=0.17,
        assay_lower=0.15, assay_upper=0.17,
    )
    base.update(kw)
    return UncertaintyResult(**base)


def _rapport(res) -> UncertaintyReport:
    return UncertaintyReport(results=[res], degeneracy=0, n_draws=10,
                             n_failed=0, config=UncertaintyConfig())


def _valoriser(res):
    return value_lot(_rapport(res), PRIX, TERMES, today=AUJ)


# ==========================================================================
# 1. Le dosage l'emporte
# ==========================================================================

def test_la_valorisation_retient_le_dosage_et_non_la_reconstruction():
    """
    Le cas qui separe les deux : le modele reconstruit 12 %, le
    laboratoire dose 20 %. A un payable de 100 % et 20 000 USD la tonne,
    la difference vaut 1 600 USD par tonne de lot.
    """
    v = _valoriser(_resultat(
        total_lower=0.11, total_upper=0.13,      # reconstruction
        assay_lower=0.19, assay_upper=0.21,      # dosage
    ))
    contribution = next(c for c in v.contributions if c.element == "Ni")
    assert contribution.grade_low == pytest.approx(0.19), (
        "la valorisation a retenu la reconstruction, pas le dosage")
    assert contribution.grade_high == pytest.approx(0.21)


def test_sans_dosage_la_reconstruction_sert_de_repli():
    """
    Un rapport qui ne porte pas de dosage - grandeur sans mesure directe,
    ou rapport produit avant ce correctif - doit rester valorisable. Le
    repli est silencieux : il n'y a pas d'ecart a signaler quand il n'y a
    qu'une seule source.
    """
    v = _valoriser(_resultat(
        total_lower=0.11, total_upper=0.13,
        assay_lower=None, assay_upper=None,
    ))
    contribution = next(c for c in v.contributions if c.element == "Ni")
    assert contribution.grade_low == pytest.approx(0.11)
    assert contribution.grade_high == pytest.approx(0.13)


# ==========================================================================
# 2. L'ecart est rapporte
# ==========================================================================

def test_un_ecart_notable_entre_dosage_et_modele_est_signale():
    v = _valoriser(_resultat(
        total_lower=0.11, total_upper=0.13,
        assay_lower=0.19, assay_upper=0.21,
    ))
    avert = " ".join(v.warnings)
    assert "Ni" in avert and "dose" in avert.lower(), (
        f"l'ecart n'est pas signale au client : {v.warnings}")
    # Le chiffre du laboratoire doit figurer : un avertissement qui ne
    # porte pas les deux valeurs ne permet pas d'arbitrer.
    assert "20.00" in avert


def test_un_lot_sain_ne_produit_aucun_avertissement_d_ecart():
    """
    Le pendant du test precedent. Un avertissement systematique serait du
    bruit sur tous les lots sains, et plus personne ne le lirait le jour
    ou il compte.
    """
    v = _valoriser(_resultat(
        total_lower=0.1499, total_upper=0.1701,
        assay_lower=0.15, assay_upper=0.17,
    ))
    assert not any("ecart" in w.lower() or "écart" in w.lower()
                   for w in v.warnings), v.warnings


@pytest.mark.parametrize("ecart_rel, signale", [
    (ECART_DOSAGE_MODELE * 0.5, False),
    (ECART_DOSAGE_MODELE * 1.5, True),
])
def test_le_seuil_de_signalement_mord_des_deux_cotes(ecart_rel, signale):
    """
    Un seuil qui ne se teste que dans un sens laisse passer une
    comparaison inversee sans que rien ne le dise.
    """
    dose = 0.16
    recons = dose * (1.0 + ecart_rel)
    v = _valoriser(_resultat(
        total_lower=recons - 0.001, total_upper=recons + 0.001,
        assay_lower=dose - 0.001, assay_upper=dose + 0.001,
    ))
    present = any("dose" in w.lower() for w in v.warnings)
    assert present is signale, (
        f"ecart relatif {ecart_rel:.3f}, signalement attendu {signale}, "
        f"obtenu {present} : {v.warnings}")


# ==========================================================================
# 3. La note du rapport
# ==========================================================================

@pytest.mark.parametrize("langue", ["fr", "en"])
def test_le_rapport_montre_les_deux_valeurs_cote_a_cote(langue):
    from klastos.report import _note_dosage
    note = _note_dosage(_resultat(
        total_lower=0.11, total_upper=0.13,
        assay_lower=0.19, assay_upper=0.21,
    ), langue)
    assert note, "aucune note produite sur un ecart de 60 %"
    assert "12.00" in note and "20.00" in note, (
        f"les deux valeurs ne figurent pas cote a cote : {note}")
    assert not note.startswith("rapport."), (
        "une cle s'affiche a la place du texte")


def test_aucune_note_quand_le_modele_et_le_bulletin_s_accordent():
    from klastos.report import _note_dosage
    assert _note_dosage(_resultat(), "fr") == ""


def test_aucune_note_sur_une_grandeur_sans_dosage():
    """Une phase n'est pas mesuree par le laboratoire. Lui opposer un
    dosage reviendrait a fabriquer une mesure."""
    from klastos.report import _note_dosage
    sans = _resultat(key="C_total", assay_lower=None, assay_upper=None)
    assert _note_dosage(sans, "fr") == ""


# ==========================================================================
# 4. LA TABLE DOCUMENTEE EST VERIFIEE, PAS SEULEMENT RELUE
# ==========================================================================

#: Ecarts relatifs dosage / reconstruction cites dans le commentaire de
#: `ECART_DOSAGE_MODELE`, en pourcents. Ils sont la pour etre compares a
#: la mesure. Une premiere redaction annoncait « de 6 a 23 % » et « un
#: seuil a 5 % les attrape tous » : les deux etaient faux - la mesure va
#: de 0,0 a 40,9 % - et aucun test ne les gardait.
ECARTS_DOCUMENTES = {
    ("Li2CO3", 0.03): {"Li": 13.8, "Ni": 3.9, "Co": 4.6, "Cu": 0.0},
    ("Li2CO3", 0.05): {"Li": 22.3, "Ni": 5.7, "Co": 6.8, "Cu": 0.0},
    ("Li2CO3", 0.10): {"Li": 40.9, "Ni": 8.1, "Co": 9.7, "Cu": 0.0},
    ("NiO", 0.04): {"Li": 4.3, "Ni": 11.5, "Co": 5.5, "Cu": 0.0},
    ("NiO", 0.08): {"Li": 7.5, "Ni": 23.2, "Co": 9.6, "Cu": 0.0},
}

_HORS = {"Li2CO3": {"Li": 2.0, "C": 1.0, "O": 3.0},
         "NiO": {"Ni": 1.0, "O": 1.0}}
_SAIN = {"NMC811": .40, "C_total": .33, "Cu_metal": .10, "Al_metal": .07,
         "PVDF": .05, "LiPF6": .03, "Fe_metal": .02}
_DOSES = ["Li", "Ni", "Mn", "Co", "Al", "Fe", "P", "Cu", "C", "F"]


def _ecarts_mesures(phase, part):
    """Ecart relatif entre dosage et reconstruction, par element payable."""
    import numpy as np
    from klastos.elements import ATOMIC_MASS, ELEMENTS, formula_mass
    from klastos.phases import PHASES, stoichiometry_matrix
    from klastos.solver import SolverConfig, solve

    m = dict(_SAIN)
    m["NMC811"] = round(m["NMC811"] - part, 10)
    m[phase] = part
    b = {el: 0.0 for el in ELEMENTS}
    for ph, fr in m.items():
        comp = PHASES[ph]["composition"] if ph in PHASES else _HORS[ph]
        M = formula_mass(comp)
        for el, n in comp.items():
            b[el] += fr * ATOMIC_MASS[el] * n / M
    A, els, _ = stoichiometry_matrix(elements=_DOSES)
    r = solve({el: b[el] * 100 for el in _DOSES}, elements=_DOSES,
              config=SolverConfig())
    rec = A @ r.x
    return {el: abs(rec[els.index(el)] - b[el]) / b[el] * 100
            for el in ("Li", "Ni", "Co", "Cu")}


@pytest.mark.parametrize("cas", sorted(ECARTS_DOCUMENTES))
def test_les_ecarts_documentes_sont_les_vrais(cas):
    """
    LE COMMENTAIRE D'UN SEUIL EST UNE AFFIRMATION, DONC IL SE VERIFIE.

    C'est sur cette table qu'on juge si le seuil est au bon endroit. Une
    table fausse fonde un mauvais arbitrage, et elle se cite.
    """
    attendus = ECARTS_DOCUMENTES[cas]
    mesures = _ecarts_mesures(*cas)
    for el, attendu in attendus.items():
        assert mesures[el] == pytest.approx(attendu, abs=0.3), (
            f"{cas[0]} {cas[1]*100:.0f} %, {el} : le commentaire de "
            f"`valuation.py` annonce {attendu:.1f} %, la mesure donne "
            f"{mesures[el]:.1f} %. Corriger le COMMENTAIRE.")


def test_le_seuil_n_attrape_pas_tout_et_le_commentaire_le_dit():
    """
    CE TEST GARDE UN AVEU, PAS UNE REUSSITE.

    Sur les ecarts portant un element reellement affecte, quatre restent
    sous le seuil de 5 % et ne sont donc pas signales. Le commentaire
    doit continuer de le dire : c'est la difference entre un seuil
    honnete et un seuil qui se vante.
    """
    sous_le_seuil = 0
    total = 0
    for cas in ECARTS_DOCUMENTES:
        for el, e in _ecarts_mesures(*cas).items():
            if e < 1e-9:          # element non affecte : ne rien dire est juste
                continue
            total += 1
            sous_le_seuil += int(e < ECART_DOSAGE_MODELE * 100)
    assert sous_le_seuil > 0, (
        "le seuil attrape desormais tout : retirer l'aveu du commentaire "
        "de `valuation.py`, qui serait devenu faux dans l'autre sens")
    assert sous_le_seuil / total < 0.5, (
        f"{sous_le_seuil} ecarts sur {total} passent sous le seuil : il "
        f"ne signale plus grand-chose")
