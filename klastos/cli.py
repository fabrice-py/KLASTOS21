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


def _erreur(message: str) -> int:
    print(f"\n{PROG}: {message}\n", file=sys.stderr)
    return EXIT_REFUS


# ==========================================================================
# Arguments communs
# ==========================================================================

def _ajouter_lecture(p: argparse.ArgumentParser) -> None:
    p.add_argument("bulletin", help="certificat d'analyse au format CSV")
    p.add_argument(
        "--unite", default="%", metavar="UNITE",
        help="unite appliquee aux colonnes qui n'en declarent pas (defaut : %%)",
    )
    p.add_argument(
        "--censure", default="half", choices=("zero", "half", "threshold"),
        help="traitement des valeurs sous la limite de detection "
             "(defaut : half, convention geochimique)",
    )
    p.add_argument(
        "--separateur", default=",", metavar="CAR",
        help="separateur de colonnes du CSV (defaut : virgule)",
    )
    p.add_argument(
        "--devise", metavar="ISO", default=None, dest="devise_cible",
        help="convertit les prix vers cette devise avant valorisation, par "
             "exemple EUR. SANS CETTE OPTION, AUCUNE CONVERSION N'A LIEU : "
             "un jeu multi-devises reste refuse, et c'est voulu. Exige "
             "--taux.",
    )
    p.add_argument(
        "--taux", metavar="FICHIER", default=None,
        help="fichier de taux de change, CSV ou JSON. AUCUNE SOURCE DE TAUX "
             "N'EST INTEGREE : le taux est le votre, celui de votre banque, "
             "parce que c'est lui qui engage votre transaction. Format "
             "documente au README, exemple dans data/taux_exemple.json.",
    )
    p.add_argument(
        "--taux-age-max", type=int, default=MAX_RATE_AGE_DAYS, metavar="N",
        dest="taux_age_max",
        help=f"age maximal d'un taux, en jours (defaut : "
             f"{MAX_RATE_AGE_DAYS}, NON ARBITRE - voir klastos/fx.py)",
    )
    p.add_argument(
        "--langue", default=i18n.DEFAUT, choices=list(i18n.LANGUES),
        help=f"langue du rapport (defaut : {i18n.DEFAUT}). Le protocole "
             f"methodologique reste en francais et le rapport anglais le "
             f"cite en declarant sa langue.",
    )


def _ajouter_provenance(p: argparse.ArgumentParser) -> None:
    from .provenance import PROVENANCE_PROFILES

    p.add_argument(
        "--provenance", default="non_declaree",
        choices=sorted(PROVENANCE_PROFILES),
        help="provenance declaree par le client (defaut : non_declaree)",
    )
    p.add_argument(
        "--atteste", action="store_true",
        help="le client a signe l'attestation. SANS CE DRAPEAU, aucune phase "
             "n'est exclue, quelle que soit la provenance declaree.",
    )
    p.add_argument(
        "--grades", nargs="*", metavar="GRADE", default=None,
        help="grades de cathode produits, pour le profil chutes_gigafactory",
    )


def _ajouter_drx(p: argparse.ArgumentParser) -> None:
    from .structural import BASES, BASE_ABSOLUE

    p.add_argument(
        "--drx", metavar="FICHIER", default=None,
        help="quantification par diffraction : CSV phase, valeur, "
             "incertitude. LA COLONNE D'INCERTITUDE EST OBLIGATOIRE - une "
             "mesure Rietveld est precise a 1 ou 3 points, et sans son "
             "incertitude elle passerait pour exacte.",
    )
    p.add_argument(
        "--base", default=BASE_ABSOLUE, choices=sorted(BASES),
        help="base de normalisation de la quantification. 'absolue' : "
             "fraction de la masse totale, exige un standard interne. "
             "'cristalline' : fraction du seul cristallin, renormalisee - "
             "seuls les RAPPORTS entre phases sont alors exploitables, et il "
             "en faut une de plus. Defaut : absolue.",
    )
    p.add_argument(
        "--conseil-drx", action="store_true",
        help="classe les phases par le resserrement qu'une quantification "
             "apporterait, au pire placement de la mesure. Quelques secondes "
             "de calcul, donc hors du chemin par defaut.",
    )
    p.add_argument(
        "--incertitude-drx", type=float, default=None, metavar="POINTS",
        help="incertitude supposee du laboratoire pour --conseil-drx, en "
             "points de masse (defaut : 2).",
    )


def _ajouter_seuils(p: argparse.ArgumentParser) -> None:
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
        help=f"ecart de bouclage declenchant une alerte, en fraction "
             f"(defaut : {CLOSURE_ALERT}, ARBITRE contre le plancher de bruit)",
    )
    p.add_argument(
        "--seuil-rejet", type=float, default=CLOSURE_REJECT, metavar="X",
        dest="seuil_rejet",
        help=f"ecart de bouclage rendant le lot inexploitable "
             f"(defaut : {CLOSURE_REJECT}, ARBITRE contre le plancher de bruit)",
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
        return _erreur(f"bulletin illisible : {e}")

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
            return _erreur(f"prix inexploitables : {e}")
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
        return _erreur(f"bulletin illisible : {e}")
    except StructuralRefused as e:
        return _erreur(f"quantification structurale refusee : {e}")
    except UnboundedCompatibleSet as e:
        return _erreur(f"{e}")
    except NotAProductionSourceError as e:
        return _erreur(f"{e}")
    except StalePriceError as e:
        return _erreur(f"{e}")
    except MissingPriceError as e:
        return _erreur(f"prix manquant : {e}")
    except (ProviderError, ImplausiblePriceError) as e:
        return _erreur(f"prix inexploitables : {e}")
    except ReportRefused as e:
        return _erreur(
            f"rapport refuse : {e}\n"
            "       Relancez avec --demo pour obtenir un document marque "
            "non opposable."
        )

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
            print("Ouvrez-le dans un navigateur. Pour un PDF : Ctrl+P, "
                  "destination \"Enregistrer au format PDF\".")
        if val is None:
            print("Aucune valorisation : relancez avec --prix pour l'inclure.")
        print()
    else:
        print(texte)
        if val is None and fmt == "markdown":
            print("\n---\nAucune valorisation dans ce rapport : "
                  "relancez avec --prix pour l'inclure.")

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
                return _erreur(
                    f"{args.source} n'expose pas de catalogue de droits."
                )
            symboles = flux.entitlements()
            print(f"\n{len(symboles)} symbole(s) autorise(s) par votre abonnement :\n")
            for s in symboles:
                print(f"   {s}")
            print("\nConfrontez cette liste a data/symboles_pra.json.\n")
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
        return _erreur(f"prix invraisemblable, conversion d'unite suspecte : {e}")

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
        print("\nATTENTION - ces prix sont marques USAGE INTERNE. Un abonnement")
        print("d'agence n'autorise pas, par defaut, de les afficher dans un")
        print("rapport facture a un tiers. Obtenez l'autorisation ecrite de")
        print("l'agence, puis relancez avec --licence-rediffusion.")
    print()
    return EXIT_OK


# ==========================================================================
# Commande : ui
# ==========================================================================

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

    print(f"\nKLASTOS21 - interface sur http://localhost:{args.port}")
    print("Ctrl+C pour arreter.\n")
    try:
        return subprocess.call(commande)
    except KeyboardInterrupt:
        return EXIT_OK


# ==========================================================================
# Analyseur d'arguments
# ==========================================================================

def build_parser() -> argparse.ArgumentParser:
    from .market import REFERENCE_SPECS
    from .report import DESTINATAIRE_INTERNE, DESTINATAIRE_TIERS

    p = argparse.ArgumentParser(
        prog=PROG,
        description="KLASTOS21 - analyse predictive des matieres premieres "
                    "secondaires.",
        epilog="Exemple : klastos rapport bulletin.csv "
               "--provenance vehicule_electrique --atteste --demo",
    )
    sous = p.add_subparsers(dest="commande", metavar="COMMANDE")

    d = sous.add_parser(
        "diag", help="diagnostic rapide d'un bulletin",
        description="Lit un bulletin, le reconstitue, et rapporte les "
                    "diagnostics. Aucune valorisation.",
    )
    _ajouter_lecture(d)
    _ajouter_provenance(d)
    _ajouter_seuils(d)
    d.set_defaults(func=cmd_diag)

    r = sous.add_parser(
        "rapport", help="rapport complet, avec valorisation si des prix sont fournis",
        description="Produit le rapport client complet.",
    )
    _ajouter_lecture(r)
    _ajouter_provenance(r)
    _ajouter_drx(r)
    _ajouter_seuils(r)
    r.add_argument("--lot", default=None, metavar="ID",
                   help="identifiant du lot (defaut : nom du fichier)")
    r.add_argument("--client", default="Client", metavar="NOM")
    r.add_argument("--sortie", default=None, metavar="FICHIER",
                   help="ecrire le rapport dans ce fichier plutot qu'a l'ecran")
    r.add_argument("--format", default="auto",
                   choices=("auto", "markdown", "html"),
                   help="rendu du rapport. html produit un document autonome, "
                        "avec des barres d'intervalle, pret a imprimer en PDF "
                        "depuis le navigateur. auto (defaut) : html si "
                        "--sortie finit par .html, markdown sinon.")
    r.add_argument("--prix", default=None, metavar="FICHIER",
                   help="prix du client, en CSV (format de "
                        "data/prix_client_exemple.csv) ou en JSON. "
                        "SANS CETTE OPTION, AUCUNE VALORISATION.")
    r.add_argument("--payables", default=None, metavar="FICHIER",
                   help="conditions commerciales au format JSON")
    r.add_argument("--marche", default="cif_coree_sud", metavar="CLE",
                   help="cle du marche dans le fichier de payables")
    r.add_argument("--spec", default=None, choices=sorted(REFERENCE_SPECS),
                   help="specification commerciale a controler")
    r.add_argument("--cout", type=float, default=0.0, metavar="X",
                   help="cout de traitement par tonne")
    r.add_argument("--marge", type=float, default=0.0, metavar="X",
                   help="marge visee, en fraction (0.15 pour 15 %%)")
    r.add_argument("--tirages", type=int, default=200, metavar="N",
                   help="tirages de propagation d'incertitude (defaut : 200)")
    r.add_argument("--graine", type=int, default=0, metavar="N",
                   help="graine aleatoire, pour un resultat reproductible")
    r.add_argument("--destinataire", default=DESTINATAIRE_TIERS,
                   choices=(DESTINATAIRE_TIERS, DESTINATAIRE_INTERNE),
                   help="qui recoit ce document. tiers (defaut) : il sort de "
                        "la maison, et des prix d'agence sans licence de "
                        "rediffusion le font refuser. interne : il reste "
                        "chez vous, le refus ne s'applique pas.")
    r.add_argument("--demo", action="store_true",
                   help="utilise l'instantane de prix de demonstration et "
                        "produit un document marque NON OPPOSABLE")
    r.set_defaults(func=cmd_rapport)

    x = sous.add_parser(
        "prix", help="recupere les prix courants depuis un flux d'agence",
        description="Interroge Fastmarkets, Benchmark ou SMM et ecrit un "
                    "instantane de prix date, utilisable ensuite par "
                    "`rapport --prix`. Les identifiants sont lus dans "
                    "l'environnement, jamais en argument.",
    )
    x.add_argument("--source", required=True,
                   choices=("fastmarkets", "benchmark", "smm"))
    x.add_argument("--sortie", default="data/prix_du_jour.json", metavar="FICHIER")
    x.add_argument("--marche", default=None, metavar="CLE",
                   help="releve aussi les payables de ce marche "
                        "(exw_europe, cif_coree_sud...)")
    x.add_argument("--catalogue", action="store_true",
                   help="liste les symboles que votre abonnement autorise, "
                        "sans rien ecrire")
    x.add_argument("--licence-rediffusion", action="store_true",
                   dest="licence_rediffusion",
                   help="vous attestez detenir l'autorisation ecrite de "
                        "rediffuser ces prix a un tiers. Sans ce drapeau, "
                        "l'instantane est marque USAGE INTERNE.")
    x.set_defaults(func=cmd_prix)

    u = sous.add_parser(
        "ui", help="lance l'interface graphique dans le navigateur",
        description="Ouvre l'interface d'exploitation : depot d'un bulletin, "
                    "prix du jour, rapport, historique des lots.",
    )
    u.add_argument("--port", type=int, default=8501, metavar="N")
    u.add_argument("--sans-navigateur", action="store_true",
                   dest="sans_navigateur",
                   help="n'ouvre pas le navigateur automatiquement")
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
            return _erreur("--marge doit etre une fraction dans [0, 1[.")

    try:
        return args.func(args)
    except FileNotFoundError as e:
        return _erreur(f"fichier introuvable : {e}")
    except KeyboardInterrupt:
        return _erreur("interrompu.")