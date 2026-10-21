"""
KLASTOS21 - Point d'entree en ligne de commande.

    python -m klastos diag    bulletin.csv
    python -m klastos rapport bulletin.csv --provenance vehicule_electrique --atteste

Ce module n'a aucune logique metier. Il lit des arguments, appelle la chaine
existante, et met en forme. Toute regle de fond vit dans les modules
correspondants.

Deux principes de conception
----------------------------
1. SANS PRIX, PAS DE VALORISATION. Il n'y a pas de jeu de prix par defaut :
   l'option --prix est obligatoire pour obtenir une section valorisation. Un
   rapport sans prix reste parfaitement utile - il porte la reconstitution,
   les domaines compatibles et les diagnostics.

2. AUCUNE EXCEPTION BRUTE A L'ECRAN. Les refus prevus par le protocole -
   source de prix non destinee a la production, bouclage hors tolerance,
   bulletin illisible - sortent en message clair avec un code de retour, pas
   en trace d'appel.

Codes de retour : 0 succes, 1 refus ou erreur de traitement, 2 usage.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import pathlib
import sys

from . import i18n
from .fx import MAX_RATE_AGE_DAYS

PROG = "klastos"
EXIT_OK, EXIT_REFUS, EXIT_USAGE = 0, 1, 2


def _utf8_stdout() -> None:
    """
    Force la sortie en UTF-8.

    Les consoles Windows heritees sont en cp1252 et levent une
    UnicodeEncodeError sur le moindre tiret cadratin ou caractere accentue.
    Le rapport en contient partout.
    """
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass



def _langue_demandee(argv: list[str] | None = None) -> str:
    """
    La langue voulue, lue DANS argv avant toute analyse d'arguments.

    Pourquoi un pre-balayage, et pas simplement `args.langue`
    ---------------------------------------------------------
    L'aide d'argparse est construite au moment ou l'on DECLARE les options :
    `--help` affiche donc des textes figes avant qu'aucun argument n'ait ete
    lu. Attendre `args.langue` rendrait `klastos rapport --help --langue en`
    impossible a satisfaire - l'aide serait deja ecrite en francais.

    On balaie donc argv a la main, ce qui reste EXPLICITE : la langue vient
    de ce que l'utilisateur a tape, jamais d'une locale systeme devinee.
    Deviner serait contraire au principe du projet, qui n'invente ni unite,
    ni prix, ni taux.

    Les deux formes sont acceptees : « --langue en » et « --langue=en ».
    """
    import sys as _sys

    args = list(argv if argv is not None else _sys.argv[1:])
    for i, a in enumerate(args):
        if a == "--langue" and i + 1 < len(args):
            return i18n.langue_valide(args[i + 1])
        if a.startswith("--langue="):
            return i18n.langue_valide(a.partition("=")[2])
    return i18n.DEFAUT

def _langue(args=None) -> str:
    """
    La langue des sorties console.

    Lue sur `args` quand ils existent, sinon dans argv : certaines erreurs
    surviennent avant l'analyse complete des arguments.
    """
    if args is not None and getattr(args, "langue", None):
        return i18n.langue_valide(args.langue)
    return _langue_demandee()


def _erreur(message: str) -> int:
    print(f"\n{PROG}: {message}\n", file=sys.stderr)
    return EXIT_REFUS


# ==========================================================================
# Arguments communs
# ==========================================================================

def _ajouter_lecture(p: argparse.ArgumentParser,
                     lg: str = i18n.DEFAUT) -> None:
    p.add_argument("bulletin", help=i18n.t("cli.aide.bulletin", lg))
    p.add_argument(
        "--unite", default="%", metavar="UNITE",
        help=i18n.t("cli.aide.unite", lg),
    )
    p.add_argument(
        "--censure", default="half", choices=("zero", "half", "threshold"),
        help=i18n.t("cli.aide.censure", lg),
    )
    p.add_argument(
        "--separateur", default=",", metavar="CAR",
        help=i18n.t("cli.aide.separateur", lg),
    )
    p.add_argument(
        "--devise", metavar="ISO", default=None, dest="devise_cible",
        help=i18n.t("cli.aide.devise", lg),
    )
    p.add_argument(
        "--taux", metavar="FICHIER", default=None,
        help=i18n.t("cli.aide.taux", lg),
    )
    p.add_argument(
        "--taux-age-max", type=int, default=MAX_RATE_AGE_DAYS, metavar="N",
        dest="taux_age_max",
        help=i18n.t("cli.aide.taux_age_max", lg, defaut=MAX_RATE_AGE_DAYS),
    )
    p.add_argument(
        "--langue", default=i18n.DEFAUT, choices=list(i18n.LANGUES),
        help=i18n.t("cli.aide.langue", lg, defaut=i18n.DEFAUT),
    )


def _ajouter_provenance(p: argparse.ArgumentParser,
                        lg: str = i18n.DEFAUT) -> None:
    from .provenance import PROVENANCE_PROFILES

    p.add_argument(
        "--provenance", default="non_declaree",
        choices=sorted(PROVENANCE_PROFILES),
        help=i18n.t("cli.aide.provenance", lg),
    )
    p.add_argument(
        "--atteste", action="store_true",
        help=i18n.t("cli.aide.atteste", lg),
    )
    p.add_argument(
        "--grades", nargs="*", metavar="GRADE", default=None,
        help=i18n.t("cli.aide.grades", lg),
    )


def _ajouter_drx(p: argparse.ArgumentParser,
                 lg: str = i18n.DEFAUT) -> None:
    from .structural import BASES, BASE_ABSOLUE

    p.add_argument(
        "--drx", metavar="FICHIER", default=None,
        help=i18n.t("cli.aide.drx", lg),
    )
    p.add_argument(
        "--base", default=BASE_ABSOLUE, choices=sorted(BASES),
        help=i18n.t("cli.aide.base", lg),
    )
    p.add_argument(
        "--conseil-drx", action="store_true",
        help=i18n.t("cli.aide.conseil_drx", lg),
    )
    p.add_argument(
        "--incertitude-drx", type=float, default=None, metavar="POINTS",
        help=i18n.t("cli.aide.incertitude_drx", lg),
    )


def _ajouter_seuils(p: argparse.ArgumentParser,
                    lg: str = i18n.DEFAUT) -> None:
    """
    Seuils de bouclage, exposes parce qu'un lot peut demander un reglage
    propre - et non parce qu'ils seraient en attente d'arbitrage.

    Mesure a l'appui : sur des lots entierement decrits par le modele, le
    seul bruit analytique de 6 % produit une masse apparemment inexpliquee
    de 1,8 % en mediane, 5,7 % au 95e centile, et jusqu'a 10,3 % au pire.
    Les premiers seuils proposes (3 % et 8 %) etaient donc SOUS le plancher
    de bruit : ils refusaient des lots sains.

    Arbitrage du geometallurgiste, inscrit au protocole 2.6 ter : alerte a
    6 %, rejet a 20 %. `solver.py` porte les valeurs et le drapeau
    CLOSURE_THRESHOLDS_VALIDATED ; ce module ne fait que les exposer.
    """
    from .solver import CLOSURE_ALERT, CLOSURE_REJECT

    p.add_argument(
        "--seuil-alerte", type=float, default=CLOSURE_ALERT, metavar="X",
        dest="seuil_alerte",
        help=i18n.t("cli.aide.seuil_alerte", lg, defaut=CLOSURE_ALERT),
    )
    p.add_argument(
        "--seuil-rejet", type=float, default=CLOSURE_REJECT, metavar="X",
        dest="seuil_rejet",
        help=i18n.t("cli.aide.seuil_rejet", lg, defaut=CLOSURE_REJECT),
    )


def _config_solveur(args):
    from .solver import SolverConfig

    return SolverConfig(
        closure_alert=args.seuil_alerte,
        closure_reject=args.seuil_rejet,
    )


#: Extensions qui designent sans ambiguite un rendu HTML.
EXTENSIONS_HTML = (".html", ".htm")


def _format_sortie(demande: str, chemin: str | None) -> str:
    """
    Resout le format de rendu.

    `--format` explicite l'emporte toujours. A defaut, l'extension du fichier
    de sortie decide : ecrire du Markdown dans un fichier nomme rapport.html
    serait une mauvaise surprise, et personne ne nomme ainsi un fichier en
    attendant autre chose que du HTML. Sans fichier de sortie ni format
    demande, le Markdown reste la valeur par defaut : il s'affiche dans un
    terminal, pas le HTML.
    """
    if demande != "auto":
        return demande
    if chemin and pathlib.Path(chemin).suffix.lower() in EXTENSIONS_HTML:
        return "html"
    return "markdown"


def _lire(args) -> "object":
    from .ingestion import read_bulletin

    return read_bulletin(
        args.bulletin,
        default_unit=args.unite,
        censored_as=args.censure,
        delimiter=args.separateur,
    )


def _resoudre_provenance(args):
    from .provenance import ProvenanceDeclaration

    return ProvenanceDeclaration(
        profile_key=args.provenance,
        attested=args.atteste,
        declared_grades=tuple(args.grades) if args.grades else None,
    ).resolve()


# ==========================================================================
# Commande : diag
# ==========================================================================

def cmd_diag(args) -> int:
    from .identifiability import analyse
    from .ingestion import IngestionError
    from .phases import stoichiometry_matrix
    from .solver import solve

    try:
        lu = _lire(args)
    except IngestionError as e:
        return _erreur(i18n.t("cli.erreur.bulletin", _langue(args), e=e))

    keys, exclues, journal = _resoudre_provenance(args)
    res = solve(lu.b, phase_keys=keys, elements=lu.measured_elements,
                config=_config_solveur(args))
    A, _, _ = stoichiometry_matrix(phase_keys=keys,
                                   elements=lu.measured_elements)
    diag = analyse(A, keys)

    L = [f"\nKLASTOS21 - diagnostic de {pathlib.Path(args.bulletin).name}", ""]

    L.append("BULLETIN")
    for e in lu.measured_elements:
        L.append(f"   {e:3} {lu.values[e] * 100:9.4f} %")
    L.append(f"   {'':3} {'-' * 11}")
    L.append(f"   {'':3} {lu.total * 100:9.2f} %  somme des teneurs lues")
    if lu.ignored_columns:
        L.append(f"   colonnes ignorees : {', '.join(lu.ignored_columns)}")

    L += ["", "PROVENANCE"]
    for ligne in journal:
        L.append(f"   {ligne}")

    L += ["", "RECONSTITUTION"]
    L.append(f"   {'masse expliquee par le modele':<30}: {res.explained_mass * 100:7.2f} %")
    L.append(f"   {'masse non expliquee':<30}: {res.unexplained_mass * 100:7.2f} %")
    for el, v in sorted(res.predicted_unmeasured.items()):
        etiquette = f"{el} predit (non dose)"
        L.append(f"   {etiquette:<30}: {v * 100:7.2f} %")
    etiquette = "residu d'ajustement maximal"
    L.append(f"   {etiquette:<30}: {res.max_element_residual * 100:7.3f} pt")

    L += ["", "DIAGNOSTICS"]
    L.append(f"   bouclage : {res.closure.status.upper()} - {res.closure.message}")
    L.append(f"   {diag.summary()}")
    if res.max_element_residual > 0.01:
        L.append("   ATTENTION : residu eleve. Le bulletin pourrait etre "
                 "physiquement incoherent")
        L.append("   (par exemple du phosphore sans fer ni fluor) ou la "
                 "provenance mal declaree.")

    if lu.warnings:
        L += ["", "AVERTISSEMENTS"]
        for w in lu.warnings:
            L.append(f"   - {w}")

    L += ["", "PHASES RETENUES PAR LE SOLVEUR (representant, voir le rapport "
          "complet pour les domaines)"]
    for k, v in sorted(res.as_dict().items(), key=lambda t: -t[1]):
        if v >= 0.5:
            L.append(f"   {k:12} {v:7.2f} %")

    L.append("")
    print("\n".join(L))
    return EXIT_OK


# ==========================================================================
# Commande : rapport
# ==========================================================================

def cmd_rapport(args) -> int:
    """
    Adaptateur : des arguments vers une Demande, puis une Analyse vers
    l'ecran. AUCUNE LOGIQUE METIER ICI. La chaine vit dans `service.py`,
    pour que l'interface graphique emprunte exactement le meme chemin et
    que les deux ne puissent pas diverger. Un test le verrouille.
    """
    from .ingestion import IngestionError
    from .market import (MissingPriceError, NotAProductionSourceError,
                         REFERENCE_SPECS, StalePriceError, demo_payable_terms,
                         demo_price_set)
    from .identifiability import UnboundedCompatibleSet
    from .providers import ProviderError
    from .report import ReportRefused
    from .service import Demande, analyser, charger_prix, charger_termes
    from .structural import StructuralRefused
    from .units import ImplausiblePriceError

    prix = termes = None
    if args.prix or args.demo:
        try:
            prix = charger_prix(args.prix) if args.prix else demo_price_set()
            termes = (charger_termes(args.payables, args.marche)
                      if args.payables else demo_payable_terms()[args.marche])
        except (ProviderError, ImplausiblePriceError) as e:
            return _erreur(
                i18n.t("cli.erreur.prix_inexploitables", _langue(args), e=e))
        except KeyError as e:
            return _erreur(f"cle inconnue : {e}")

    demande = Demande(
        bulletin=args.bulletin,
        lot_id=args.lot or "",
        client=args.client,
        unite_par_defaut=args.unite,
        censure=args.censure,
        separateur=args.separateur,
        langue=getattr(args, "langue", i18n.DEFAUT),
        devise_cible=getattr(args, "devise_cible", None),
        taux=getattr(args, "taux", None),
        taux_age_max=getattr(args, "taux_age_max", MAX_RATE_AGE_DAYS),
        provenance=args.provenance,
        attestee=args.atteste,
        grades_declares=tuple(args.grades) if args.grades else None,
        drx=args.drx,
        base_drx=args.base,
        conseil_drx=args.conseil_drx,
        **({"incertitude_drx": args.incertitude_drx / 100.0}
           if args.incertitude_drx else {}),
        tirages=args.tirages,
        graine=args.graine,
        seuil_alerte=args.seuil_alerte,
        seuil_rejet=args.seuil_rejet,
        prix=prix,
        termes=termes,
        specification=REFERENCE_SPECS.get(args.spec) if args.spec else None,
        cout_traitement=args.cout,
        marge=args.marge,
        destinataire=args.destinataire,
        autoriser_demo=args.demo,
    )

    try:
        resultat = analyser(demande)
    except IngestionError as e:
        return _erreur(i18n.t("cli.erreur.bulletin", _langue(args), e=e))
    except StructuralRefused as e:
        return _erreur(i18n.t("cli.erreur.drx", _langue(args), e=e))
    except UnboundedCompatibleSet as e:
        return _erreur(f"{e}")
    except NotAProductionSourceError as e:
        return _erreur(f"{e}")
    except StalePriceError as e:
        return _erreur(f"{e}")
    except MissingPriceError as e:
        return _erreur(i18n.t("cli.erreur.prix_manquant", _langue(args), e=e))
    except (ProviderError, ImplausiblePriceError) as e:
        return _erreur(
            i18n.t("cli.erreur.prix_inexploitables", _langue(args), e=e))
    except ReportRefused as e:
        return _erreur(
            i18n.t("cli.erreur.rapport_refuse", _langue(args), e=e))

    rapport = resultat.rapport
    val = resultat.valorisation

    fmt = _format_sortie(args.format, args.sortie)
    if fmt == "html":
        from .render_html import to_html
        texte = to_html(rapport)
    else:
        texte = rapport.to_markdown()

    if args.sortie:
        p = pathlib.Path(args.sortie)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texte, encoding="utf-8")
        print(f"\nRapport ecrit : {p}  (format {fmt})")
        if fmt == "html":
            print(i18n.t("cli.rapport.navigateur", _langue(args)))
        if val is None:
            print(i18n.t("cli.rapport.sans_valorisation", _langue(args)))
        print()
    else:
        print(texte)
        if val is None and fmt == "markdown":
            print("\n" + i18n.t(
                "cli.rapport.sans_valorisation_bloc", _langue(args)))

    return EXIT_OK


# ==========================================================================
# Commande : prix
# ==========================================================================

def cmd_prix(args) -> int:
    """Interroge un flux d'agence et ecrit un instantane de prix date."""
    import json

    from .feeds import (BenchmarkFeed, CredentialsMissing, FastmarketsFeed,
                        FeedError, SMMFeed)
    from .providers import ProviderError, build_price_set
    from .units import ImplausiblePriceError

    constructeurs = {
        "fastmarkets": FastmarketsFeed,
        "benchmark": BenchmarkFeed,
        "smm": SMMFeed,
    }
    flux = constructeurs[args.source](
        redistribution_licensed=args.licence_rediffusion,
    )

    try:
        if args.catalogue:
            if not hasattr(flux, "entitlements"):
                return _erreur(i18n.t("cli.droits.absent", _langue(args),
                                      agence=args.source))
            symboles = flux.entitlements()
            print("\n" + i18n.t("cli.droits.autorises",
                                _langue(args), n=len(symboles))
                  + "\n")
            for s in symboles:
                print(f"   {s}")
            print("\n"
                  + i18n.t("cli.droits.confronter", _langue(args))
                  + "\n")
            return EXIT_OK

        cotations = flux.quotes()
        licence = ("rediffusion autorisee" if args.licence_rediffusion
                   else "USAGE INTERNE uniquement")
        prix = build_price_set(
            cotations,
            label=f"{args.source} du {cotations[0].as_of.isoformat()} - {licence}",
            is_production_source=True,
            origin=args.source,
            redistribution_licensed=bool(args.licence_rediffusion),
        )

        payables = None
        if args.marche and hasattr(flux, "payables"):
            payables = flux.payables(args.marche)

    except CredentialsMissing as e:
        return _erreur(f"{e}")
    except (FeedError, ProviderError) as e:
        return _erreur(f"{args.source} : {e}")
    except ImplausiblePriceError as e:
        return _erreur(i18n.t("cli.erreur.prix_invraisemblable",
                              _langue(args), e=e))

    instantane = {
        "label": prix.label,
        "currency": prix.currency,
        "is_production_source": True,
        "redistribution_licensed": bool(args.licence_rediffusion),
        "fetched_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "prices": {
            m: {
                "value_per_tonne": p.value_per_tonne,
                "as_of": p.as_of.isoformat(),
                "source": p.source,
                "reference_name": p.reference_name,
                "basis": p.basis,
                "note": p.note,
            }
            for m, p in prix.prices.items()
        },
    }

    cible = pathlib.Path(args.sortie)
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(json.dumps(instantane, indent=2, ensure_ascii=False),
                     encoding="utf-8")

    print(f"\nInstantane ecrit : {cible}")
    for m, p in sorted(prix.prices.items()):
        print(f"   {m:3} {p.value_per_tonne:12,.2f} {prix.currency}/t   "
              f"{p.as_of}   {p.reference_name}")

    if payables:
        pf = cible.with_name(cible.stem + "_payables.json")
        pf.write_text(json.dumps({"terms": {args.marche: {
            "market": args.marche,
            "payables": payables,
            "as_of": cotations[0].as_of.isoformat(),
            "source": f"{args.source}, releve automatique",
            "validated": True,
            "note": f"Payables releves sur le flux {args.source}.",
        }}}, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nPayables ecrits : {pf}")
        for m, v in sorted(payables.items()):
            print(f"   {m:3} {v * 100:6.2f} %")

    if not args.licence_rediffusion:
        print("\n" + i18n.t("cli.prix.usage_interne",
                            _langue(args)))
    print()
    return EXIT_OK


# ==========================================================================
# Commande : ui
# ==========================================================================

def cmd_pink_sheet(args) -> int:
    """
    Affiche - ou rafraichit - les moyennes mensuelles de la Banque mondiale.

    Seule source de prix gratuite et REDIFFUSABLE du projet : elle rend
    KLASTOS21 demontrable sans aucun abonnement d'agence. Elle ne couvre que
    l'aluminium, le cuivre et le nickel, et ce sont des MOYENNES MENSUELLES.
    """
    from .providers import (PINK_SHEET_ATTRIBUTION, PINK_SHEET_FICHIER,
                            PINK_SHEET_METAUX, PINK_SHEET_URL,
                            PinkSheetProvider, ProviderError)

    chemin = pathlib.Path(args.fichier or PINK_SHEET_FICHIER)
    url = args.url or PINK_SHEET_URL

    if args.rafraichir:
        # Le telechargement est une action EXPLICITE et separee de l'analyse.
        # L'URL porte un identifiant de document qui a deja change entre les
        # editions 2025 et 2026 : un lien mort ne doit jamais pouvoir casser
        # une valorisation en cours.
        import urllib.error
        import urllib.request

        print(f"Telechargement : {url}")
        chemin.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(url, timeout=60) as reponse:
                octets = reponse.read()
        except (urllib.error.URLError, OSError) as e:
            return _erreur(
                f"telechargement impossible : {e}\n"
                f"       L'URL du Pink Sheet porte un identifiant de document "
                f"qui change a chaque edition.\n"
                f"       Verifiez l'adresse courante sur worldbank.org, puis "
                f"relancez avec --url."
            )
        if not octets[:2] == b"PK":
            return _erreur(
                "le fichier telecharge n'est pas un classeur XLSX. "
                "L'URL a probablement change d'edition."
            )
        chemin.write_bytes(octets)
        print(f"Ecrit : {chemin}  ({len(octets):,} octets)")

    try:
        cotations = PinkSheetProvider(chemin, url=url).quotes()
    except ProviderError as e:
        return _erreur(str(e))

    print(f"\n{PINK_SHEET_ATTRIBUTION}")
    print(f"Fichier : {chemin}\n")
    for q in cotations:
        print(f"  {q.metal:3} {q.value:>12,.2f} USD/t   {q.reference_name}")
    print("\nMOYENNES MENSUELLES, pas des evaluations spot. Le cobalt, le "
          "lithium, le\nmanganese et le graphite n'y figurent pas : ce sont "
          "des marches de gre a gre.")
    print(f"Metaux couverts : {sorted(PINK_SHEET_METAUX)}")
    return EXIT_OK


def cmd_ui(args) -> int:
    """
    Lance l'interface. Streamlit n'est pas une dependance du coeur : le
    paquet s'installe et s'utilise sans lui, et seule cette commande le
    reclame.
    """
    import subprocess

    try:
        import streamlit                                   # noqa: F401
    except ImportError:
        return _erreur(
            "l'interface demande Streamlit, qui n'est pas installe.\n"
            "       Installez-le une fois :  pip install streamlit\n"
            "       Le reste de KLASTOS21 fonctionne sans lui."
        )

    app = pathlib.Path(__file__).resolve().parent / "app.py"
    commande = [sys.executable, "-m", "streamlit", "run", str(app),
                "--server.port", str(args.port)]
    if args.sans_navigateur:
        commande += ["--server.headless", "true"]

    print(i18n.t("cli.ui.lancement", _langue(args), port=args.port))
    print(i18n.t("cli.ui.arreter", _langue(args)))
    try:
        return subprocess.call(commande)
    except KeyboardInterrupt:
        return EXIT_OK


# ==========================================================================
# Analyseur d'arguments
# ==========================================================================

def build_parser(langue: str | None = None) -> argparse.ArgumentParser:
    """
    Construit le parseur, aide comprise, dans la langue demandee.

    `langue` a None prend ce que `_langue_demandee` lit dans argv : c'est ce
    que fait `main`. Un appelant - un test, un script - peut forcer la
    langue sans toucher a argv.
    """
    from .market import REFERENCE_SPECS
    from .report import DESTINATAIRE_INTERNE, DESTINATAIRE_TIERS

    lg = i18n.langue_valide(langue if langue is not None
                            else _langue_demandee())
    p = argparse.ArgumentParser(
        prog=PROG,
        description=i18n.t("cli.description", lg),
        epilog=i18n.t("cli.exemple", lg),
    )
    sous = p.add_subparsers(dest="commande", metavar="COMMANDE")
    # La langue circule dans le parseur : chaque helper d'options la lit.
    p.set_defaults(_langue_aide=lg)

    d = sous.add_parser(
        "diag", help=i18n.t("cli.cmd.diag", lg),
        description=i18n.t("cli.cmd.diag_description", lg),
    )
    _ajouter_lecture(d, lg)
    _ajouter_provenance(d, lg)
    _ajouter_seuils(d, lg)
    d.set_defaults(func=cmd_diag)

    r = sous.add_parser(
        "rapport", help=i18n.t("cli.cmd.rapport", lg),
        description=i18n.t("cli.cmd.rapport_description", lg),
    )
    _ajouter_lecture(r, lg)
    _ajouter_provenance(r, lg)
    _ajouter_drx(r, lg)
    _ajouter_seuils(r, lg)
    r.add_argument("--lot", default=None, metavar="ID",
                   help=i18n.t("cli.aide.lot", lg))
    r.add_argument("--client", default="Client", metavar="NOM")
    r.add_argument("--sortie", default=None, metavar="FICHIER",
                   help=i18n.t("cli.aide.sortie", lg))
    r.add_argument("--format", default="auto",
                   choices=("auto", "markdown", "html"),
                   help=i18n.t("cli.aide.format", lg))
    r.add_argument("--prix", default=None, metavar="FICHIER",
                   help=i18n.t("cli.aide.prix", lg))
    r.add_argument("--payables", default=None, metavar="FICHIER",
                   help=i18n.t("cli.aide.payables", lg))
    r.add_argument("--marche", default="cif_coree_sud", metavar="CLE",
                   help=i18n.t("cli.aide.marche_payables", lg))
    r.add_argument("--spec", default=None, choices=sorted(REFERENCE_SPECS),
                   help=i18n.t("cli.aide.spec", lg))
    r.add_argument("--cout", type=float, default=0.0, metavar="X",
                   help=i18n.t("cli.aide.cout", lg))
    r.add_argument("--marge", type=float, default=0.0, metavar="X",
                   help=i18n.t("cli.aide.marge", lg))
    r.add_argument("--tirages", type=int, default=200, metavar="N",
                   help=i18n.t("cli.aide.tirages", lg))
    r.add_argument("--graine", type=int, default=0, metavar="N",
                   help=i18n.t("cli.aide.graine", lg))
    r.add_argument("--destinataire", default=DESTINATAIRE_TIERS,
                   choices=(DESTINATAIRE_TIERS, DESTINATAIRE_INTERNE),
                   help=i18n.t("cli.aide.destinataire", lg))
    r.add_argument("--demo", action="store_true",
                   help=i18n.t("cli.aide.demo", lg))
    r.set_defaults(func=cmd_rapport)

    x = sous.add_parser(
        "prix", help=i18n.t("cli.cmd.prix", lg),
        description=i18n.t("cli.cmd.prix_description", lg),
    )
    x.add_argument("--source", required=True,
                   choices=("fastmarkets", "benchmark", "smm"))
    x.add_argument("--sortie", default="data/prix_du_jour.json", metavar="FICHIER")
    x.add_argument("--marche", default=None, metavar="CLE",
                   help=i18n.t("cli.aide.marche_releve", lg))
    x.add_argument("--catalogue", action="store_true",
                   help=i18n.t("cli.aide.catalogue", lg))
    x.add_argument("--licence-rediffusion", action="store_true",
                   dest="licence_rediffusion",
                   help=i18n.t("cli.aide.licence", lg))
    x.set_defaults(func=cmd_prix)

    ps = sous.add_parser(
        "pink-sheet",
        help=i18n.t("cli.cmd.pink", lg),
        description=i18n.t("cli.cmd.pink_description", lg),
    )
    ps.add_argument(
        "--fichier", metavar="FICHIER", default=None,
        help=i18n.t("cli.aide.fichier", lg),
    )
    ps.add_argument(
        "--url", metavar="URL", default=None,
        help=i18n.t("cli.aide.url", lg),
    )
    ps.add_argument(
        "--rafraichir", action="store_true",
        help=i18n.t("cli.aide.rafraichir", lg),
    )
    ps.set_defaults(func=cmd_pink_sheet)

    u = sous.add_parser(
        "ui", help=i18n.t("cli.cmd.ui", lg),
        description=i18n.t("cli.cmd.ui_description", lg),
    )
    u.add_argument("--port", type=int, default=8501, metavar="N")
    u.add_argument("--sans-navigateur", action="store_true",
                   dest="sans_navigateur",
                   help=i18n.t("cli.aide.sans_navigateur", lg))
    u.set_defaults(func=cmd_ui)

    return p


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE

    if args.marge if hasattr(args, "marge") else False:
        if not 0.0 <= args.marge < 1.0:
            return _erreur(i18n.t("cli.erreur.marge", _langue(args)))

    try:
        return args.func(args)
    except FileNotFoundError as e:
        return _erreur(f"fichier introuvable : {e}")
    except KeyboardInterrupt:
        return _erreur("interrompu.")