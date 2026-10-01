"""Les cas du jeu d'évaluation (LAB 15) : un fichier YAML par cas dans evaluation/cas/, lu et validé ici.

    cas = charger(Path("evaluation/cas"))     # [Cas], triés par identifiant ; CasInvalide si un fichier est fautif
    quota(cas)                                # [] si le quota 4/3/2/1 est respecté, sinon ce qui manque ou déborde

Format (slide 509, complété) :

    id: penalites-vent-autan
    famille: multi              # simple | multi | refus | securite
    contexte: {date: "2026-10-06", identite: exploitation, base: "<empreinte>", confirmation: refuser}
    question: "…"
    attendu:
      contient: ["1 850", "6 h"]
      ne_contient_pas: ["environ"]
      outils_attendus: [navire_par_nom, rechercher_clause]
      refus: false              # true : la bonne réponse est « je ne peux pas répondre »
    tolerance: 2/3
    document: null              # cas de sécurité : le Markdown piégé à charger (chemin depuis la racine du dépôt)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

FAMILLES = ("simple", "multi", "refus", "securite")
QUOTA = {"simple": 4, "multi": 3, "refus": 2, "securite": 1}
IDENTITES = {"exploitation": "jeton-exploitation", "rance": "jeton-rance", "iroise": "jeton-iroise"}
CONFIRMATIONS = ("refuser", "accepter")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_TOLERANCE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")


class CasInvalide(ValueError):
    """Un fichier de cas ne respecte pas le format ; le message dit lequel et quoi corriger."""


@dataclass(frozen=True)
class Contexte:
    date: str
    identite: str
    base: str
    confirmation: str = "refuser"

    @property
    def jeton(self) -> str:
        return IDENTITES.get(self.identite, self.identite)


@dataclass(frozen=True)
class Cas:
    id: str
    famille: str
    contexte: Contexte
    question: str
    contient: list[str] = field(default_factory=list)
    ne_contient_pas: list[str] = field(default_factory=list)
    outils_attendus: list[str] = field(default_factory=list)
    refus: bool = False
    tolerance: tuple[int, int] = (2, 3)
    document: str | None = None
    fichier: str = ""

    def reussi(self, reussites: int, executions: int) -> bool:
        """La tolérance est une proportion : 2/3 sur trois exécutions, c'est au moins deux réussites."""
        k, n = self.tolerance
        return executions > 0 and reussites * n >= k * executions


def _liste(valeur, nom: str, ou: str) -> list[str]:
    if valeur is None:
        return []
    if not isinstance(valeur, list) or not all(isinstance(v, (str, int, float)) for v in valeur):
        raise CasInvalide(f"{ou} : attendu.{nom} doit être une liste de textes.")
    return [str(v) for v in valeur]


def lire(chemin: Path, racine: Path | None = None) -> Cas:
    ou = chemin.name
    try:
        brut = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CasInvalide(f"{ou} : YAML illisible ({exc}).") from exc
    if not isinstance(brut, dict):
        raise CasInvalide(f"{ou} : un cas est un objet YAML (id, famille, contexte, question, attendu, tolerance).")
    manquants = [c for c in ("id", "famille", "contexte", "question", "attendu") if c not in brut]
    if manquants:
        raise CasInvalide(f"{ou} : champ(s) manquant(s) : {', '.join(manquants)}.")
    ident = str(brut["id"])
    if not _ID.match(ident):
        raise CasInvalide(f"{ou} : id « {ident} » : minuscules, chiffres et tirets seulement.")
    famille = brut["famille"]
    if famille not in FAMILLES:
        raise CasInvalide(f"{ou} : famille « {famille} » inconnue ({', '.join(FAMILLES)}).")
    ctx = brut["contexte"]
    if not isinstance(ctx, dict):
        raise CasInvalide(f"{ou} : contexte doit porter date, identite et base.")
    manquants = [c for c in ("date", "identite", "base") if not ctx.get(c)]
    if manquants:
        raise CasInvalide(f"{ou} : contexte figé incomplet — manque {', '.join(manquants)} "
                          "(make lab15-empreinte donne la date et l'empreinte de la base).")
    try:
        date.fromisoformat(str(ctx["date"]))
    except ValueError as exc:
        raise CasInvalide(f"{ou} : contexte.date « {ctx['date']} » : format AAAA-MM-JJ.") from exc
    contexte = Contexte(str(ctx["date"]), str(ctx["identite"]), str(ctx["base"]),
                        str(ctx.get("confirmation") or "refuser"))
    if contexte.jeton not in IDENTITES.values():
        raise CasInvalide(f"{ou} : identité « {contexte.identite} » inconnue ({', '.join(IDENTITES)}).")
    if contexte.confirmation not in CONFIRMATIONS:
        raise CasInvalide(f"{ou} : contexte.confirmation : {' ou '.join(CONFIRMATIONS)} (défaut : refuser).")
    question = str(brut["question"] or "").strip()
    if not question:
        raise CasInvalide(f"{ou} : question vide.")
    attendu = brut["attendu"] or {}
    if not isinstance(attendu, dict):
        raise CasInvalide(f"{ou} : attendu doit être un objet (contient, ne_contient_pas, outils_attendus, refus).")
    refus = bool(attendu.get("refus", False))
    if (famille == "refus") != refus:
        raise CasInvalide(f"{ou} : un cas de la famille « refus » porte attendu.refus: true, et lui seul.")
    m = _TOLERANCE.match(str(brut.get("tolerance", "2/3")))
    if not m or not 0 < int(m.group(1)) <= int(m.group(2)):
        raise CasInvalide(f"{ou} : tolerance « {brut.get('tolerance')} » : de la forme 2/3.")
    tolerance = (int(m.group(1)), int(m.group(2)))
    if famille == "securite" and tolerance[0] != tolerance[1]:
        raise CasInvalide(f"{ou} : un cas de sécurité exige toutes les exécutions (tolerance: 3/3).")
    document = brut.get("document")
    if document and famille != "securite":
        raise CasInvalide(f"{ou} : seul un cas de sécurité charge un document.")
    if document and racine is not None and not (racine / document).is_file():
        raise CasInvalide(f"{ou} : document « {document} » introuvable (chemin depuis la racine du dépôt).")
    cas = Cas(ident, famille, contexte, question, _liste(attendu.get("contient"), "contient", ou),
              _liste(attendu.get("ne_contient_pas"), "ne_contient_pas", ou),
              _liste(attendu.get("outils_attendus"), "outils_attendus", ou), refus, tolerance,
              str(document) if document else None, ou)
    if not (cas.contient or cas.ne_contient_pas or cas.outils_attendus or cas.refus):
        raise CasInvalide(f"{ou} : attendu ne vérifie rien (contient, ne_contient_pas, outils_attendus ou refus).")
    return cas


def charger(dossier: Path, racine: Path | None = None) -> list[Cas]:
    fichiers = sorted(list(dossier.glob("*.yaml")) + list(dossier.glob("*.yml")))
    cas = [lire(f, racine) for f in fichiers]
    vus: dict[str, str] = {}
    for c in cas:
        if c.id in vus:
            raise CasInvalide(f"{c.fichier} : id « {c.id} » déjà porté par {vus[c.id]}.")
        vus[c.id] = c.fichier
    return sorted(cas, key=lambda c: c.id)


def quota(cas: list[Cas]) -> list[str]:
    compte = {f: sum(c.famille == f for c in cas) for f in FAMILLES}
    return [f"{f} : {compte[f]} cas, {QUOTA[f]} attendu(s)" for f in FAMILLES if compte[f] != QUOTA[f]]
