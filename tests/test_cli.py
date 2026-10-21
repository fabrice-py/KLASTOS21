"""Tests de klastos/cli.py.

Le CLI est la premiere chose qu'un utilisateur touche. Trois exigences :

  1. SANS PRIX, PAS DE VALORISATION. Il n'existe aucun jeu de prix par
     defaut, et l'absence de prix ne doit pas empecher de produire le reste.
  2. AUCUNE TRACE D'APPEL A L'ECRAN. Les refus prevus par le protocole
     sortent en message clair avec un code de retour.
  3. Les seuils non arbitres sont exposes, pas figes.
"""

import pathlib

import pytest

from klastos.cli import EXIT_OK, EXIT_REFUS, EXIT_USAGE, build_parser, main

RACINE = pathlib.Path(__file__).resolve().parent.parent
BULLETIN = RACINE / "data" / "exemples" / "bulletin_coherent.csv"
INCOHERENT = RACINE / "data" / "exemples" / "bulletin_2026-RA-04871.csv"
PRIX_CSV = RACINE / "data" / "prix_client_exemple.csv"

# Seuils larges, au-dessus du plancher de bruit, pour que les tests portent
# sur le CLI et non sur l'arbitrage des seuils.
LARGE = ["--seuil-alerte", "0.08", "--seuil-rejet", "0.25"]


@pytest.fixture(autouse=True)
def _bulletins_presents():
    if not BULLETIN.exists():
        pytest.skip("bulletins d'exemple absents")


# ==========================================================================
# 1. Analyseur d'arguments
# ==========================================================================

def test_sans_commande_affiche_l_aide(capsys):
    assert main([]) == EXIT_USAGE
    assert "COMMANDE" in capsys.readouterr().out


def test_les_deux_commandes_existent():
    p = build_parser()
    for cmd in ("diag", "rapport"):
        args = p.parse_args([cmd, "x.csv"])
        assert args.func is not None


def test_l_attestation_est_un_drapeau_explicite():
    p = build_parser()
    assert p.parse_args(["diag", "x.csv"]).atteste is False
    assert p.parse_args(["diag", "x.csv", "--atteste"]).atteste is True


def test_provenance_inconnue_rejetee():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["diag", "x.csv", "--provenance", "mars"])


def test_censure_inconnue_rejetee():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["diag", "x.csv", "--censure", "au_pif"])


# ==========================================================================
# 2. Commande diag
# ==========================================================================

def test_diag_reussit(capsys):
    assert main(["diag", str(BULLETIN)]) == EXIT_OK
    out = capsys.readouterr().out
    for bloc in ("BULLETIN", "PROVENANCE", "RECONSTITUTION", "DIAGNOSTICS"):
        assert bloc in out, bloc


def test_diag_rapporte_la_masse_et_l_oxygene_predit(capsys):
    main(["diag", str(BULLETIN)])
    out = capsys.readouterr().out
    assert "masse expliquee par le modele" in out
    assert "masse non expliquee" in out
    assert "O predit (non dose)" in out


def test_diag_signale_un_bulletin_incoherent(capsys):
    """Le phosphore sans fer ni fluor doit declencher l'avertissement."""
    if not INCOHERENT.exists():
        pytest.skip("bulletin incoherent absent")
    main(["diag", str(INCOHERENT)])
    out = capsys.readouterr().out
    assert "residu eleve" in out
    assert "physiquement incoherent" in out


def test_diag_ne_signale_rien_sur_un_bulletin_coherent(capsys):
    main(["diag", str(BULLETIN)])
    assert "residu eleve" not in capsys.readouterr().out


def test_diag_reprend_le_journal_de_provenance(capsys):
    main(["diag", str(BULLETIN), "--provenance", "vehicule_electrique",
          "--atteste"])
    out = capsys.readouterr().out
    assert "Attestation client fournie" in out
    assert "LCO" in out


def test_diag_sans_attestation_n_exclut_rien(capsys):
    main(["diag", str(BULLETIN), "--provenance", "vehicule_electrique"])
    assert "ATTESTATION NON FOURNIE" in capsys.readouterr().out


def test_bulletin_introuvable_sort_en_message_clair(capsys):
    code = main(["diag", "nexiste_pas.csv"])
    assert code == EXIT_REFUS
    err = capsys.readouterr().err
    assert "klastos:" in err
    assert "Traceback" not in err


def test_bulletin_illisible_sort_en_message_clair(tmp_path, capsys):
    f = tmp_path / "vide.csv"
    f.write_text("Echantillon,Densite\nX,2.4\n", encoding="utf-8")
    assert main(["diag", str(f)]) == EXIT_REFUS
    assert "illisible" in capsys.readouterr().err


# ==========================================================================
# 3. Commande rapport, sans prix
# ==========================================================================

def test_rapport_sans_prix_reste_utile(capsys):
    code = main(["rapport", str(BULLETIN), "--tirages", "30"] + LARGE)
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "# Rapport de lot" in out
    assert "## Grandeurs fermes" in out
    assert "Aucune valorisation" in out
    assert "## Valorisation" not in out


def test_rapport_sans_prix_n_invente_aucun_prix(capsys):
    main(["rapport", str(BULLETIN), "--tirages", "30"] + LARGE)
    out = capsys.readouterr().out
    assert "USD/t" not in out
    assert "PRIX MAXIMAL" not in out


def test_rapport_ecrit_dans_un_fichier(tmp_path, capsys):
    cible = tmp_path / "sous" / "rapport.md"
    code = main(["rapport", str(BULLETIN), "--tirages", "30",
                 "--sortie", str(cible)] + LARGE)
    assert code == EXIT_OK
    assert cible.exists()
    texte = cible.read_text(encoding="utf-8")
    assert "# Rapport de lot" in texte
    assert "Rapport ecrit" in capsys.readouterr().out


def test_l_identifiant_de_lot_vient_du_nom_de_fichier(tmp_path):
    cible = tmp_path / "r.md"
    main(["rapport", str(BULLETIN), "--tirages", "30",
          "--sortie", str(cible)] + LARGE)
    assert "bulletin_coherent" in cible.read_text(encoding="utf-8")


def test_l_identifiant_de_lot_est_surchargeable(tmp_path):
    cible = tmp_path / "r.md"
    main(["rapport", str(BULLETIN), "--lot", "BM-2026-0207",
          "--client", "Negoce SAS", "--tirages", "30",
          "--sortie", str(cible)] + LARGE)
    texte = cible.read_text(encoding="utf-8")
    assert "BM-2026-0207" in texte
    assert "Negoce SAS" in texte


# ==========================================================================
# 4. Commande rapport, avec prix
# ==========================================================================

def test_rapport_avec_prix_client_valorise(tmp_path, capsys):
    if not PRIX_CSV.exists():
        pytest.skip("data/prix_client_exemple.csv absent")
    cible = tmp_path / "r.md"
    code = main(["rapport", str(BULLETIN), "--prix", str(PRIX_CSV),
                 "--demo", "--cout", "350", "--marge", "0.15",
                 "--tirages", "30", "--sortie", str(cible)] + LARGE)
    assert code == EXIT_OK
    texte = cible.read_text(encoding="utf-8")
    assert "## Valorisation" in texte
    assert "PRIX MAXIMAL A PAYER" in texte


def test_la_source_de_demonstration_est_refusee_sans_le_drapeau(capsys):
    """Verrou du protocole : aucun prix de demonstration en production."""
    code = main(["rapport", str(BULLETIN), "--prix", str(PRIX_CSV),
                 "--tirages", "30"] + LARGE) if PRIX_CSV.exists() else EXIT_REFUS
    # sans --demo, les conditions de payable livrees sont perimees
    assert code == EXIT_REFUS
    err = capsys.readouterr().err
    assert "Traceback" not in err


def test_fichier_de_prix_introuvable_sort_en_message_clair(capsys):
    code = main(["rapport", str(BULLETIN), "--prix", "nexiste_pas.csv",
                 "--demo", "--tirages", "30"] + LARGE)
    assert code == EXIT_REFUS
    assert "Traceback" not in capsys.readouterr().err


def test_marche_inconnu_sort_en_message_clair(capsys):
    code = main(["rapport", str(BULLETIN), "--demo", "--marche", "mars",
                 "--tirages", "30"] + LARGE)
    assert code == EXIT_REFUS
    assert "Traceback" not in capsys.readouterr().err


# ==========================================================================
# 5. Refus du rapport et seuils
# ==========================================================================

def test_un_bouclage_hors_tolerance_refuse_le_rapport(capsys):
    """Seuils par defaut : le refus doit etre explique, pas crypte."""
    code = main(["rapport", str(BULLETIN), "--seuil-rejet", "0.01",
                 "--tirages", "30"])
    assert code == EXIT_REFUS
    err = capsys.readouterr().err
    assert "rapport refusé" in err
    assert "--demo" in err, "le message doit indiquer la sortie de secours"


def test_le_mode_demo_lève_le_refus(tmp_path):
    cible = tmp_path / "r.md"
    code = main(["rapport", str(BULLETIN), "--seuil-rejet", "0.01",
                 "--demo", "--tirages", "30", "--sortie", str(cible)])
    assert code == EXIT_OK
    assert "NON OPPOSABLE" in cible.read_text(encoding="utf-8")


def test_les_seuils_sont_exposes_car_non_arbitres():
    from klastos.solver import CLOSURE_ALERT, CLOSURE_REJECT

    p = build_parser()
    args = p.parse_args(["diag", "x.csv"])
    assert args.seuil_alerte == CLOSURE_ALERT
    assert args.seuil_rejet == CLOSURE_REJECT

    args = p.parse_args(["diag", "x.csv", "--seuil-rejet", "0.18"])
    assert args.seuil_rejet == pytest.approx(0.18)


def test_l_aide_dit_d_ou_viennent_les_seuils_de_bouclage(capsys):
    """
    L'aide doit porter l'origine des seuils, pas seulement leur valeur.

    Ce test a longtemps verifie l'inverse : il exigeait « NON ARBITRE »,
    etat anterieur a l'arbitrage du geometallurgiste. Depuis, le protocole
    2.6 ter arbitre 6 % et 20 %, `solver.py` pose
    CLOSURE_THRESHOLDS_VALIDATED a True, et test_protocole.py l'affirme -
    pendant que cette aide-ci soutenait encore le contraire a l'utilisateur.
    Deux tests du depot se contredisaient donc sur le meme sujet.

    L'assertion negative est la part qui mord : « ARBITRÉ » est un sous-mot
    de « NON ARBITRÉ », donc sans elle le texte perime repasserait. Elle
    porte sur la phrase entiere et non sur « NON ARBITRÉ » seul, parce que
    `--taux-age-max` affiche legitimement « NON ARBITRÉ » dans la meme aide
    pour l'age des taux de change, lui qui n'est effectivement pas arbitre.
    Un garde nu interdirait donc une mention juste.
    """
    with pytest.raises(SystemExit):
        build_parser().parse_args(["diag", "--help"])
    # argparse enroule l'aide : « NON » et « ARBITRÉ » peuvent se
    # retrouver separes par un retour a la ligne, et la coupure depend de
    # la largeur du terminal. On compare donc sur un texte dont les blancs
    # sont normalises, sinon l'assertion passe ici et tombe ailleurs.
    aide = " ".join(capsys.readouterr().out.split())
    assert "ARBITRÉ contre le plancher de bruit" in aide
    assert "NON ARBITRÉ contre le plancher de bruit" not in aide


def test_l_aide_signale_qu_il_n_y_a_pas_de_prix_par_defaut(capsys):
    with pytest.raises(SystemExit):
        build_parser().parse_args(["rapport", "--help"])
    assert "AUCUNE VALORISATION" in capsys.readouterr().out


# ==========================================================================
# 6. Reproductibilite
# ==========================================================================

def test_la_graine_rend_le_rapport_reproductible(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    for cible in (a, b):
        main(["rapport", str(BULLETIN), "--graine", "7", "--tirages", "40",
              "--sortie", str(cible)] + LARGE)
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")


# ==========================================================================
# 6 bis. Format de rendu
# ==========================================================================

def test_le_markdown_reste_le_format_par_defaut(tmp_path):
    """Le HTML ne s'affiche pas dans un terminal. Le defaut ne change pas."""
    cible = tmp_path / "r.txt"
    assert main(["rapport", str(BULLETIN), "--tirages", "40",
                 "--sortie", str(cible)] + LARGE) == EXIT_OK
    assert cible.read_text(encoding="utf-8").lstrip().startswith("#")


def test_le_format_html_produit_un_document_html(tmp_path):
    cible = tmp_path / "r.out"
    assert main(["rapport", str(BULLETIN), "--tirages", "40",
                 "--format", "html", "--sortie", str(cible)] + LARGE) == EXIT_OK
    texte = cible.read_text(encoding="utf-8")
    assert texte.startswith("<!doctype html>")
    assert "</html>" in texte


def test_une_sortie_en_point_html_donne_du_html(tmp_path):
    """
    Ecrire du Markdown dans un fichier nomme rapport.html serait une
    mauvaise surprise. L'extension decide quand --format n'est pas donne.
    """
    cible = tmp_path / "rapport.html"
    assert main(["rapport", str(BULLETIN), "--tirages", "40",
                 "--sortie", str(cible)] + LARGE) == EXIT_OK
    assert cible.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_un_format_explicite_l_emporte_sur_l_extension(tmp_path):
    cible = tmp_path / "rapport.html"
    assert main(["rapport", str(BULLETIN), "--tirages", "40",
                 "--format", "markdown", "--sortie", str(cible)]
                + LARGE) == EXIT_OK
    assert cible.read_text(encoding="utf-8").lstrip().startswith("#")


def test_le_format_html_indique_comment_obtenir_un_pdf(tmp_path, capsys):
    """Le client veut un PDF ; le chemin pour l'obtenir doit etre dit."""
    cible = tmp_path / "r.html"
    main(["rapport", str(BULLETIN), "--tirages", "40",
          "--sortie", str(cible)] + LARGE)
    sortie = capsys.readouterr().out
    assert "PDF" in sortie and "navigateur" in sortie


def test_un_format_inconnu_est_refuse():
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["rapport", str(BULLETIN), "--format", "pdf"])


def test_la_resolution_du_format_est_testable_seule():
    from klastos.cli import _format_sortie

    assert _format_sortie("auto", None) == "markdown"
    assert _format_sortie("auto", "x.md") == "markdown"
    assert _format_sortie("auto", "x.HTML") == "html"
    assert _format_sortie("auto", "x.htm") == "html"
    assert _format_sortie("html", "x.md") == "html"
    assert _format_sortie("markdown", "x.html") == "markdown"


# ==========================================================================
# 7. Commande prix
# ==========================================================================

def test_la_commande_prix_existe():
    args = build_parser().parse_args(["prix", "--source", "benchmark"])
    assert args.func is not None
    assert args.sortie.endswith(".json")


def test_source_inconnue_rejetee():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["prix", "--source", "mon_cousin"])


def test_la_rediffusion_est_un_drapeau_explicite():
    p = build_parser()
    assert p.parse_args(["prix", "--source", "benchmark"]).licence_rediffusion is False
    assert p.parse_args(["prix", "--source", "benchmark",
                         "--licence-rediffusion"]).licence_rediffusion is True


def test_identifiants_absents_sortent_en_message_clair(monkeypatch, capsys):
    for v in ("KLASTOS_FM_SERVICE_KEY", "KLASTOS_FM_SERVICE_NAME"):
        monkeypatch.delenv(v, raising=False)
    code = main(["prix", "--source", "fastmarkets", "--sortie", "/tmp/x.json"])
    assert code == EXIT_REFUS
    err = capsys.readouterr().err
    assert "KLASTOS_FM_SERVICE_KEY" in err
    assert "Traceback" not in err


def test_l_aide_prix_dissuade_de_passer_la_cle_en_argument(capsys):
    with pytest.raises(SystemExit):
        build_parser().parse_args(["prix", "--help"])
    out = capsys.readouterr().out
    assert "environnement" in out
    assert "jamais en argument" in out


def test_l_aide_prix_signale_la_contrainte_de_licence(capsys):
    with pytest.raises(SystemExit):
        build_parser().parse_args(["prix", "--help"])
    assert "USAGE INTERNE" in capsys.readouterr().out


# ==========================================================================
# 6 ter. Destinataire du document
# ==========================================================================

def test_le_destinataire_est_expose_et_defaut_tiers():
    from klastos.report import DESTINATAIRE_TIERS

    args = build_parser().parse_args(["rapport", str(BULLETIN)])
    assert args.destinataire == DESTINATAIRE_TIERS


def test_le_destinataire_interne_est_acceptable():
    from klastos.report import DESTINATAIRE_INTERNE

    args = build_parser().parse_args(
        ["rapport", str(BULLETIN), "--destinataire", "interne"])
    assert args.destinataire == DESTINATAIRE_INTERNE


def test_un_destinataire_inconnu_est_refuse_par_l_analyseur():
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["rapport", str(BULLETIN), "--destinataire", "client"])


def test_l_aide_explique_la_consequence_du_destinataire(capsys):
    """Le refus doit etre comprehensible avant de le rencontrer."""
    with pytest.raises(SystemExit):
        main(["rapport", "--help"])
    aide = capsys.readouterr().out
    assert "rediffusion" in aide and "interne" in aide
