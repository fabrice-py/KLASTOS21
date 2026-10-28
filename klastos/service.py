"""
KLASTOS21 - Orchestration d'une analyse de lot.

Pourquoi ce module existe
-------------------------
La chaine complete - lire le bulletin, resoudre la provenance, propager
l'incertitude, valoriser, assembler le rapport - vivait dans `cli.py`. Tant
qu'il n'y avait qu'un point d'entree, cela ne portait pas a consequence.

Des qu'une interface graphique s'ajoute, cela en porte une, et toujours la
meme : les deux chemins divergent. L'un recoit un correctif, l'autre non ;
l'un pose un verrou, l'autre l'oublie. Le jour ou le rapport de l'interface
ne dit plus la meme chose que celui de la ligne de commande, le client a
raison et nous avons tort.

Il n'y a donc qu'un chemin, ici, et `cli.py` comme l'interface ne sont plus
que des adaptateurs : ils traduisent des arguments en `Demande`, puis une
`Analyse` en affichage. Un test verrouille cette separation.

Ce module ne decide rien non plus
---------------------------------
Il n'invente aucun prix, aucune provenance, aucun seuil. Il ne connait ni
fichier de configuration, ni variable d'environnement. Tout entre par la
`Demande`, tout sort par l'`Analyse`, et les refus prevus par le protocole
remontent tels quels a l'appelant, qui saura les presenter.
"""

from __future__ import annotations

import datetime as _dt
import pathlib

import numpy as np
from dataclasses import dataclass, field

from . import i18n
from .identifiability import (CONSEIL_U_DEFAUT, ConseilQuantification,
                              analyse as _analyse_systeme,
                              conseil_quantification, IdentifiabilityAnalysis)
from .ingestion import (BulletinReading, _decoder, detecter_delimiteur,
                        read_bulletin)
from .market import PayableTerms, PriceSet, Specification
from .phases import stoichiometry_matrix
from .plausibility import (FACTEUR_PLAUSIBILITE, ControlePlausibilite,
                           verifier_predictions)
from .provenance import ProvenanceDeclaration
from .report import DESTINATAIRE_TIERS, LotReport, build_report
from .solver import (CLOSURE_ALERT, CLOSURE_REJECT, CLOSURE_REJECT_OVER,
                     SolverConfig, check_closure)
from .structural import (BASE_ABSOLUE, BASE_CRISTALLINE, StructuralData,
                         lire_fichier as _lire_drx)
from .generator import DEFAULT_NOISE, NoiseModel
from .uncertainty import UncertaintyConfig, UncertaintyReport, propagate
from .fx import MAX_RATE_AGE_DAYS, RateError, charger_taux, convertir
from .valuation import Valuation, value_lot

#: Plafond de tirages de bornage. Au-dela, le cout grimpe sans que les
#: domaines compatibles bougent de facon utile.
MAX_BOUND_DRAWS = 40

#: Bases de teneur admises. La black mass contient de l'eau : le lot est
#: pese humide, mais les laboratoires expriment presque toujours leurs
#: teneurs sur matiere SECHE. Confondre les deux fait payer l'eau au prix
#: du nickel.
BASE_SEC = "sec"
BASE_HUMIDE = "humide"
BASES_TENEURS = (BASE_SEC, BASE_HUMIDE)


class HumiditeInvalide(ValueError):
    """Humidite hors du domaine physique, ou base de teneurs inconnue."""


def facteur_sec(humidite: float | None) -> float:
    """
    Facteur qui ramene une teneur HUMIDE sur base seche : 1 / (1 - h).

    C'est un facteur d'echelle COMMUN a toutes les teneurs. L'eau ne touche
    pas un element plutot qu'un autre : elle dilue tout le bulletin du meme
    coefficient. Cette propriete est ce qui permet de deriver un bouclage
    de l'autre exactement, sans resoudre deux fois.
    """
    if humidite is None:
        return 1.0
    if not 0.0 <= humidite < 100.0:
        raise HumiditeInvalide(
            f"Humidite de {humidite} % hors du domaine physique. "
            "Elle doit etre comprise entre 0 et 100 %, bornes exclues pour "
            "100 % : un lot entierement constitue d'eau n'a aucune teneur."
        )
    return 1.0 / (1.0 - humidite / 100.0)


@dataclass(frozen=True)
class Demande:
    """
    Tout ce qu'il faut pour analyser un lot, et rien d'autre.

    Deux regles de fond s'y lisent directement.

    AUCUN PRIX PAR DEFAUT. `prix` et `termes` valent None, et une analyse
    sans eux produit un rapport complet mais sans valorisation. Il n'existe
    nulle part dans le systeme de jeu de prix implicite.

    LE DESTINATAIRE EST DECLARE. Le systeme ne devine pas si un document
    sort de la maison. Le defaut est `tiers`, le cas reel et le plus
    contraignant.
    """

    # --- source du bulletin : un fichier OU des lignes en memoire ---------
    bulletin: str | pathlib.Path | None = None
    lignes: dict[str, str] | None = None

    # --- identification ---------------------------------------------------
    lot_id: str = ""
    client: str = "Client"

    # --- lecture ----------------------------------------------------------
    unite_par_defaut: str = "%"
    censure: str = "half"
    #: Separateur de colonnes. Laisse a None, il est DETECTE. Le defaut
    #: etait la virgule, et un bulletin europeen separe par des
    #: points-virgules - le defaut d'Excel en France, en Allemagne, en
    #: Espagne et en Italie - rebondissait sur un refus qui ne nommait pas
    #: le remede. Une valeur explicite reste respectee.
    separateur: str | None = None

    # --- langue du livrable ------------------------------------------------
    #: « fr » ou « en ». Le protocole n'etant pas traduit, un rapport
    #: anglais le cite en declarant sa langue. Voir klastos/i18n.py.
    langue: str = i18n.DEFAUT

    # --- provenance -------------------------------------------------------
    provenance: str = "non_declaree"
    attestee: bool = False
    grades_declares: tuple[str, ...] | None = None
    drx: str | pathlib.Path | None = None
    base_drx: str = BASE_ABSOLUE
    #: Calcule le classement des phases a faire quantifier. Hors du chemin
    #: par defaut : environ 4 s sur quatorze phases, le conseil balayant le
    #: placement de chaque mesure hypothetique.
    conseil_drx: bool = False
    incertitude_drx: float = CONSEIL_U_DEFAUT

    # --- solveur et incertitude -------------------------------------------
    tirages: int = 200
    graine: int = 0
    seuil_alerte: float = CLOSURE_ALERT
    seuil_rejet: float = CLOSURE_REJECT
    #: Seuil de rejet dans le sens du SUR-bouclage. Asymetrique : un lot
    #: peut porter de la masse non expliquee, pas en porter moins que ce
    #: que le modele lui attribue. Voir protocole 2.6 ter.
    seuil_rejet_sur: float = CLOSURE_REJECT_OVER
    #: Facteur des bandes de plausibilite de composition. EXPOSE parce
    #: qu'il n'est PAS arbitre : il repose sur un unique certificat.
    facteur_plausibilite: float = FACTEUR_PLAUSIBILITE
    #: Modele de bruit analytique. Laisse par defaut, il vaut 6 % uniformes
    #: (source LNE-LiB01). Un bruit PAR ELEMENT est un choix explicite de
    #: l'appelant : voir PROTOCOLE.md § 1.3 bis, et l'avertissement de
    #: `NoiseModel.rel_sigma_par_element` - resserrer le bruit resserre le
    #: prix annonce, et c'est la direction dangereuse.
    bruit: NoiseModel = DEFAULT_NOISE

    # --- humidite ----------------------------------------------------------
    #: Humidite mesuree par le laboratoire, en POUR-CENT. Laissee a None,
    #: aucune valeur n'est supposee : le rapport dira qu'elle n'a pas ete
    #: mesuree plutot que d'inventer un chiffre.
    humidite: float | None = None
    #: Incertitude sur l'humidite, en points de pour-cent. Elle se propage
    #: comme un facteur d'echelle COMMUN a toutes les teneurs, et non comme
    #: une teneur de plus : l'eau deplace toutes les teneurs ENSEMBLE.
    humidite_incertitude: float | None = None
    #: Base sur laquelle le bulletin exprime ses teneurs : « sec » ou
    #: « humide ». Le defaut est « sec », convention de la quasi-totalite
    #: des laboratoires.
    base_teneurs: str = BASE_SEC

    # --- valorisation -----------------------------------------------------
    prix: PriceSet | None = None
    termes: PayableTerms | None = None

    # --- conversion de devises -------------------------------------------
    #: Devise cible. Laissee a None, AUCUNE CONVERSION N'A LIEU : un jeu
    #: multi-devises reste refuse par `check_currency`, comme avant. La
    #: conversion est un acte explicite, parce que le taux engage la
    #: transaction de celui qui le fournit.
    devise_cible: str | None = None
    #: Fichier de taux fourni par l'utilisateur, CSV ou JSON. Aucune source
    #: de taux n'est integree : voir klastos/fx.py.
    taux: str | pathlib.Path | None = None
    #: Age maximal d'un taux, en jours. EXPOSE parce qu'il n'est pas
    #: arbitre, comme les seuils de bouclage.
    taux_age_max: int = MAX_RATE_AGE_DAYS
    specification: Specification | None = None
    cout_traitement: float = 0.0
    marge: float = 0.0

    # --- emission ---------------------------------------------------------
    destinataire: str = DESTINATAIRE_TIERS
    autoriser_demo: bool = False

    #: Date de l'analyse. Elle sert DEUX FOIS : elle date le rapport, et
    #: c'est la date a laquelle la fraicheur des prix est jugee. Les deux
    #: doivent coincider, sans quoi un rapport date du 7 septembre
    #: s'appuierait sur un controle de peremption fait au 10 octobre.
    #: Laissee a None, c'est la date du jour - mais une analyse rejouee
    #: plus tard ne redonnerait alors pas le meme verdict de fraicheur.
    emis_le: _dt.date | None = None

    def identifiant(self) -> str:
        """Identifiant du lot : celui fourni, sinon le nom du fichier."""
        if self.lot_id:
            return self.lot_id
        if self.bulletin:
            return pathlib.Path(self.bulletin).stem
        return "lot"


@dataclass
class Analyse:
    """Resultat complet, dans l'ordre ou il a ete produit."""

    lecture: BulletinReading
    phases_retenues: list[str]
    phases_exclues: list[str]
    journal: list[str]
    systeme: IdentifiabilityAnalysis
    incertitude: UncertaintyReport
    valorisation: Valuation | None
    rapport: LotReport
    demande: Demande = field(repr=False, default=None)
    structurale: StructuralData | None = None
    conseil: ConseilQuantification | None = None
    plausibilite: ControlePlausibilite | None = None

    @property
    def valorise(self) -> bool:
        return self.valorisation is not None

    @property
    def contrainte_par_drx(self) -> bool:
        return self.structurale is not None and len(self.structurale) > 0

    def resume(self) -> str:
        """Une ligne, pour un journal ou une liste d'historique."""
        bouclage = self.incertitude.meta.get("closure")
        etat = bouclage.status.upper() if bouclage else "?"
        if self.valorisation is None:
            prix = "sans valorisation"
        else:
            prix = (f"{self.valorisation.max_price_low:,.0f}"
                    f"–{self.valorisation.max_price_high:,.0f} "
                    f"{self.valorisation.currency}/t")
        return f"{self.rapport.lot_id} | bouclage {etat} | {prix}"


def charger_prix(chemin: str | pathlib.Path) -> PriceSet:
    """
    Charge un jeu de prix depuis un fichier, CSV ou JSON.

    Partage entre la ligne de commande et l'interface : deux lecteurs de
    prix differents finiraient par traiter differemment un meme fichier.

    Le CSV est la route du client - ses propres prix, qu'aucune licence
    d'agence ne restreint. Le JSON est soit un instantane d'agence, qui
    porte son droit de rediffusion, soit un fichier client qui n'en porte
    pas et vaut donc libre.
    """
    from .providers import CSVProvider, build_price_set
    from .market import load_price_set

    chemin = pathlib.Path(chemin)
    if chemin.suffix.lower() == ".csv":
        return build_price_set(
            CSVProvider(chemin).quotes(),
            label=f"flux client ({chemin.name})",
            is_production_source=True,
            origin=str(chemin),
        )
    return load_price_set(chemin)


def charger_termes(chemin: str | pathlib.Path, marche: str) -> PayableTerms:
    """Charge les conditions commerciales d'un marche donne."""
    from .market import load_payable_terms

    return load_payable_terms(chemin)[marche]


def lire(demande: Demande) -> BulletinReading:
    """Etape 1 seule, pour une interface qui veut montrer le bulletin lu
    avant de lancer le calcul complet."""
    if (demande.bulletin is None) == (demande.lignes is None):
        from .ingestion import IngestionError

        raise IngestionError(
            "Fournir soit un fichier de bulletin, soit des lignes en "
            "memoire, mais pas les deux."
        )
    if demande.lignes is not None:
        return read_bulletin(
            rows=demande.lignes,
            default_unit=demande.unite_par_defaut,
            censored_as=demande.censure,
        )
    return read_bulletin(
        demande.bulletin,
        default_unit=demande.unite_par_defaut,
        censored_as=demande.censure,
        delimiter=demande.separateur,
        # Le journal de lecture part dans la tracabilite du rapport : il
        # sort donc dans la langue du document, pas dans celle du code.
        langue=demande.langue,
    )


def analyser(demande: Demande) -> Analyse:
    """
    Execute la chaine complete et rend tout ce qu'elle a produit.

    Les exceptions du protocole - bulletin illisible, bouclage hors
    tolerance, prix non destines a la production, prix d'agence sans licence
    de rediffusion - ne sont pas rattrapees ici. Elles remontent a
    l'appelant, seul a savoir comment les presenter : un message en console,
    un bandeau rouge dans une interface.
    """
    lecture = lire(demande)

    cles, exclues, journal = ProvenanceDeclaration(
        profile_key=demande.provenance,
        attested=demande.attestee,
        declared_grades=demande.grades_declares,
    ).resolve(
        # Le journal de provenance ouvre la tracabilite du rapport :
        # il sort dans la langue du document.
        langue=demande.langue)

    config = UncertaintyConfig(
        seed=demande.graine,
        n_draws=demande.tirages,
        n_bound_draws=min(demande.tirages, MAX_BOUND_DRAWS),
        noise=demande.bruit,
        # Incertitude d'humidite, convertie en ecart-type RELATIF du
        # facteur d'echelle commun. k(h) = 1/(1-h/100), donc
        # (dk/k)/dh = k/100 : une incertitude de 2 points sur une humidite
        # de 10 % vaut 2,2 % sur le facteur.
        #
        # Elle ne s'applique QUE sur un bulletin exprime sur humide : sur
        # un bulletin deja sec, l'humidite ne touche aucune teneur, elle ne
        # sert qu'a reexprimer la valeur par tonne pesee.
        facteur_rel_sigma=(
            facteur_sec(demande.humidite) * demande.humidite_incertitude / 100.0
            if (demande.base_teneurs == BASE_HUMIDE
                and demande.humidite_incertitude)
            else 0.0),
        solver=SolverConfig(
            noise=demande.bruit,
            closure_alert=demande.seuil_alerte,
            closure_reject=demande.seuil_rejet,
            closure_reject_over=demande.seuil_rejet_sur),
    )
    # Quantification structurale, si elle est fournie. Elle est lue APRES la
    # resolution des phases retenues : une phase que l'attestation de
    # provenance a exclue et que la diffraction observe est une
    # contradiction, et `lire_fichier` la refuse plutot que de l'arbitrer.
    structurale = None
    if demande.drx is not None:
        # `structural.lire_fichier` passe le separateur droit a `csv.reader`,
        # qui refuse None. La detection se fait donc ICI, au point d'appel :
        # le fichier de diffraction merite le meme traitement que le
        # bulletin, et il arrive du meme laboratoire, donc du meme Excel.
        sep_drx = demande.separateur
        if sep_drx is None:
            texte, _ = _decoder(pathlib.Path(demande.drx).read_bytes())
            sep_drx = detecter_delimiteur(texte)
        structurale = _lire_drx(demande.drx, basis=demande.base_drx,
                                separateur=sep_drx,
                                phase_keys=cles)
        journal = journal + structurale.journal

    # --- humidite : conversion humide -> sec ------------------------------
    # Les teneurs d'un bulletin exprime SUR HUMIDE sont diluees par l'eau.
    # Toutes le sont du MEME facteur : l'eau ne touche pas un element
    # plutot qu'un autre. La conversion est donc une homothetie du vecteur
    # de bulletin, et elle a lieu AVANT la resolution, parce que le modele
    # de phases suppose une composition qui somme vers 1.
    if demande.base_teneurs not in BASES_TENEURS:
        raise HumiditeInvalide(
            f"Base de teneurs inconnue : {demande.base_teneurs!r}. "
            f"Valeurs admises : {', '.join(BASES_TENEURS)}."
        )
    k_sec = 1.0
    if demande.base_teneurs == BASE_HUMIDE:
        if demande.humidite is None:
            raise HumiditeInvalide(
                "Bulletin declare sur matiere humide sans humidite mesuree. "
                "Fournir l'humidite, ou declarer le bulletin sur matiere "
                "seche si c'est le cas."
            )
        k_sec = facteur_sec(demande.humidite)
    else:
        facteur_sec(demande.humidite)        # valide la borne, sans convertir

    b_sec = lecture.b * k_sec

    incertitude = propagate(b_sec, phase_keys=cles,
                            elements=lecture.measured_elements, config=config,
                            structural=structurale)

    # DOUBLE BOUCLAGE. Les seuils d'alerte et de rejet continuent de
    # s'appliquer au bouclage TEL QUE LU : une humidite declaree par le
    # client, et non verifiee, ne doit pas pouvoir liberer un verrou. Sans
    # cette precaution, il suffirait d'ajuster l'humidite jusqu'a ce que le
    # bouclage passe au vert.
    #
    # Le bouclage tel que lu se DERIVE exactement du converti : le systeme
    # etant lineaire et la non-negativite stable par homothetie positive,
    # la solution se met a l'echelle du meme facteur que le bulletin.
    if k_sec != 1.0:
        lu = check_closure(
            np.array([incertitude.meta["closure"].total / k_sec]),
            alert=demande.seuil_alerte, reject=demande.seuil_rejet,
            reject_over=demande.seuil_rejet_sur)
        incertitude.meta["closure_converti"] = incertitude.meta["closure"]
        incertitude.meta["closure"] = lu
        incertitude.meta["facteur_sec"] = k_sec
    incertitude.meta["humidite"] = demande.humidite
    incertitude.meta["base_teneurs"] = demande.base_teneurs

    A, _, _ = stoichiometry_matrix(phase_keys=cles,
                                   elements=lecture.measured_elements)
    systeme = _analyse_systeme(A, cles)

    conseil = None
    if demande.conseil_drx:
        extra = None
        if structurale is not None and len(structurale):
            from .structural import contraintes as _c
            G, h, _ = _c(structurale, cles)
            if G.size:
                extra = (G, h)
        conseil = conseil_quantification(
            incertitude.meta["central"].x, A, cles,
            uncertainty=demande.incertitude_drx, extra=extra)

    # Conversion de devises, si et seulement si elle est demandee. Posee
    # ICI, juste avant la valorisation : c'est le seul endroit ou la devise
    # compte, et le reste de la chaine n'a pas a connaitre les taux.
    prix = demande.prix
    if prix is not None and demande.devise_cible:
        if demande.taux is None:
            raise RateError(
                "Devise cible demandee sans fichier de taux. Aucune source "
                "de taux n'est integree a KLASTOS21 : fournissez le taux de "
                "votre banque, celui qui engage votre transaction."
            )
        prix = convertir(
            prix, demande.devise_cible, charger_taux(demande.taux),
            aujourdhui=demande.emis_le, max_age=demande.taux_age_max,
        )

    valorisation = None
    if prix is not None and demande.termes is not None:
        valorisation = value_lot(
            incertitude,
            prices=prix,
            terms=demande.termes,
            spec=demande.specification,
            processing_cost=demande.cout_traitement,
            margin_rate=demande.marge,
            moisture=demande.humidite,
            today=demande.emis_le,
            allow_stale=demande.autoriser_demo,
        )

    # Plausibilite des elements NON DOSES. Posee apres la resolution - il
    # faut les phases retenues - et avant le rapport, qui doit nommer
    # l'element et sa phase porteuse.
    plausibilite = verifier_predictions(
        incertitude.meta["central"].x, cles, lecture.measured_elements,
        facteur=demande.facteur_plausibilite,
    )

    rapport = build_report(
        lot_id=demande.identifiant(),
        client=demande.client,
        uncertainty=incertitude,
        valuation=valorisation,
        provenance_journal=journal + lecture.journal,
        issued_on=demande.emis_le,
        allow_demo=demande.autoriser_demo,
        destinataire=demande.destinataire,
        conseil=conseil,
        plausibilite=plausibilite,
        langue=demande.langue,
    )

    return Analyse(
        lecture=lecture,
        phases_retenues=cles,
        phases_exclues=exclues,
        journal=journal + lecture.journal,
        systeme=systeme,
        incertitude=incertitude,
        valorisation=valorisation,
        rapport=rapport,
        demande=demande,
        structurale=structurale,
        conseil=conseil,
        plausibilite=plausibilite,
    )