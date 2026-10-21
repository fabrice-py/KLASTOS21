"""
KLASTOS21 - Provenance declaree et restriction de la liste de phases.

Principe (decisions 2 et 3, validees)
-------------------------------------
La provenance declaree par le client est une INFORMATION qui reduit la
degenerescence du systeme. Declarer "vehicule electrique" permet d'exclure
LCO et LMO, ce qui rend la ventilation par grade NMC identifiable.

REGLE NON NEGOCIABLE
--------------------
Aucune phase n'est exclue sans attestation explicite du client. Une
declaration de provenance sans attestation laisse la liste large et la
degenerescence assumee. Cette regle est verrouillee par
`ProvenanceDeclaration.resolve()` et testee dans tests/test_provenance.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import i18n
from .phases import GROUP_NMC, PHASE_KEYS, PHASES


@dataclass(frozen=True)
class ProvenanceProfile:
    """Un profil d'origine de matiere et les phases qu'il permet d'exclure."""

    key: str
    label: str
    excluded_phases: tuple[str, ...]
    attestation_text: str
    validated: bool  # False = liste d'exclusion non validee metier
    rationale: str = ""


# --------------------------------------------------------------------------
# Profils de provenance.
#
# `validated=True`  : liste d'exclusion validee par le geometallurgiste.
# `validated=False` : A VALIDER. Le profil est utilisable mais le journal
#                     le signale, et le rapport doit porter la mention.
# --------------------------------------------------------------------------
#: Les libelles sont LUS PAR LE CLIENT - dans l'interface comme dans le
#: journal de tracabilite du rapport - et portent donc leurs accents. Les
#: CLES, elles, restent en ASCII : ce sont des identifiants techniques, et
#: elles circulent en ligne de commande.
PROVENANCE_PROFILES: dict[str, ProvenanceProfile] = {
    "non_declaree": ProvenanceProfile(
        key="non_declaree",
        label="Provenance non déclarée",
        excluded_phases=(),
        attestation_text="",
        validated=True,
        rationale="Liste large. Degenerescence assumee et rapportee.",
    ),
    "vehicule_electrique": ProvenanceProfile(
        key="vehicule_electrique",
        label="Véhicule électrique (fin de vie)",
        excluded_phases=("LCO", "LMO"),
        attestation_text=(
            "J'atteste que ce lot provient de batteries de vehicules "
            "electriques et ne contient ni LCO ni LMO."
        ),
        validated=True,
        rationale=(
            "Sur flux VE modernes, LCO est negligeable et LMO marginal. "
            "Reserve : la collecte peut etre melangee (vieilles series, "
            "hybrides, erreurs de tri), d'ou l'attestation obligatoire."
        ),
    ),
    "stationnaire": ProvenanceProfile(
        key="stationnaire",
        label="Stockage stationnaire",
        excluded_phases=("LCO", "LMO"),
        attestation_text=(
            "J'atteste que ce lot provient de stockage stationnaire et ne "
            "contient ni LCO ni LMO."
        ),
        validated=True,
        rationale=(
            "Flux oriente NMC/LFP. LCO tres peu probable."
        ),
    ),
    "deee": ProvenanceProfile(
        key="deee",
        label="Électronique grand public (DEEE)",
        excluded_phases=("NMC532", "NMC811"),
        attestation_text=(
            "J'atteste que ce lot provient d'electronique grand public et ne "
            "contient ni NMC 532 ni NMC 811."
        ),
        validated=False,  # A VALIDER : liste d'exclusion non arbitree
        rationale=(
            "A VALIDER. Hypothese de travail : les grades NMC riches en Ni "
            "sont rares en electronique portable. Non arbitre a ce jour."
        ),
    ),
    "chutes_gigafactory": ProvenanceProfile(
        key="chutes_gigafactory",
        label="Chutes de production (gigafactory)",
        excluded_phases=(),  # determine dynamiquement par les grades declares
        attestation_text=(
            "J'atteste que ce lot provient de chutes de production et ne "
            "contient que les grades de cathode declares ci-dessus."
        ),
        validated=True,
        rationale=(
            "Chimie tracee a la ligne de production. Les grades non declares "
            "sont exclus, ce qui annule generalement la degenerescence."
        ),
    ),
}


def libelle_profil(cle: str, langue: str = i18n.DEFAUT) -> str:
    """
    Le libelle affichable d'un profil, dans la langue demandee.

    Le champ `label` du profil reste la VUE FRANCAISE - des appelants
    l'utilisent directement - mais c'est le catalogue qui fait foi des que
    le document change de langue.
    """
    return i18n.t(f"provenance.profil.{cle}", langue)

@dataclass(frozen=True)
class ProvenanceDeclaration:
    """
    Declaration du client pour un lot donne.

    Parameters
    ----------
    profile_key : cle d'un profil de PROVENANCE_PROFILES.
    attested : le client a-t-il coche l'attestation ? Sans cela, AUCUNE
        exclusion n'est appliquee.
    declared_grades : pour 'chutes_gigafactory', les grades de cathode
        effectivement produits sur la ligne. Les autres cathodes NMC sont
        alors exclues.
    """

    profile_key: str = "non_declaree"
    attested: bool = False
    declared_grades: tuple[str, ...] | None = None
    journal: list[str] = field(default_factory=list, compare=False)

    @property
    def profile(self) -> ProvenanceProfile:
        if self.profile_key not in PROVENANCE_PROFILES:
            raise KeyError(
                f"Profil de provenance inconnu : {self.profile_key!r}. "
                f"Valeurs admises : {sorted(PROVENANCE_PROFILES)}"
            )
        return PROVENANCE_PROFILES[self.profile_key]

    def _excluded(self) -> tuple[str, ...]:
        """Phases que le profil propose d'exclure, avant controle d'attestation."""
        prof = self.profile
        if prof.key == "chutes_gigafactory":
            if not self.declared_grades:
                return ()
            declared = set(self.declared_grades)
            return tuple(
                pk
                for pk in PHASE_KEYS
                if PHASES[pk]["group"] == GROUP_NMC and pk not in declared
            )
        return prof.excluded_phases

    def resolve(
        self, phase_keys: list[str] | None = None,
        langue: str = i18n.DEFAUT,
    ) -> tuple[list[str], list[str], list[str]]:
        """
        Applique la restriction de provenance.

        Parameters
        ----------
        langue : langue du JOURNAL. Ces lignes ouvrent la section de
            tracabilite du rapport - c'est ce qu'un acheteur lit en premier.

            LE TEXTE D'ATTESTATION, LUI, N'EST PAS TRADUIT : c'est l'enonce
            que le client a SIGNE, et le traduire ferait dire a son
            engagement des mots qu'il n'a pas signes. Le journal le cite
            verbatim en declarant qu'il est reproduit tel que signe.

        Returns
        -------
        retained : liste de phases retenue pour la deconvolution.
        excluded : liste de phases effectivement exclues.
        journal : lignes de tracabilite a reporter dans le rapport client.
        """
        lg = i18n.langue_valide(langue)
        phase_keys = list(PHASE_KEYS) if phase_keys is None else list(phase_keys)
        prof = self.profile
        log: list[str] = [i18n.t("journal.provenance.declaree", lg,
                                 profil=libelle_profil(prof.key, lg))]

        proposed = self._excluded()

        if not proposed:
            log.append(i18n.t("journal.provenance.sans_exclusion", lg))
            return phase_keys, [], log

        if not self.attested:
            log.append(i18n.t("journal.provenance.sans_attestation", lg,
                              possibles=", ".join(proposed)))
            return phase_keys, [], log

        excluded = [pk for pk in phase_keys if pk in proposed]
        retained = [pk for pk in phase_keys if pk not in proposed]

        if not retained:
            raise ValueError(
                "La restriction de provenance exclurait toutes les phases."
            )

        # Le texte d'attestation passe TEL QUEL : voir la docstring.
        log.append(i18n.t("journal.provenance.attestation", lg,
                          texte=prof.attestation_text))
        log.append(
            i18n.t("journal.provenance.exclues", lg,
                   phases=", ".join(excluded))
            if excluded
            else i18n.t("journal.provenance.aucune_concernee", lg)
        )
        if not prof.validated:
            log.append(i18n.t("journal.provenance.profil_non_valide", lg))
        return retained, excluded, log
