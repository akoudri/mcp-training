"""Le plan visible (LAB 13, bloc 21.3) — SQUELETTE : la forme du plan, sa lecture, son affichage et la décision
de l'exploitant sont fournis ; demander_plan (l'invite, et l'appel au modèle qui ne doit exécuter aucun outil) est
à écrire (étape 2).

    texte = demander_plan(messages, outils)          # un appel au modèle, SANS exécuter d'outil
    etapes = lire_plan(texte, catalogue.serveur_de)  # [Etape(numero, outil, serveur, raison)]
    afficher_plan(etapes)                            # avant le premier appel d'outil
    decision = valider_plan(etapes)                  # « ok », « non », ou une consigne (« ne publie rien »)

Le serveur de chaque étape vient du catalogue, pas du modèle : c'est ce qui dit, avant d'agir, quelles données
seront touchées et par quel serveur. Un outil que le catalogue ne connaît pas garde le serveur « ? » — le plan est
un contrat de lisibilité, pas d'exécution : il se compare à la trace (derive.py), il ne s'impose pas.

valider_plan est un point de remplacement, comme entrees.demander_utilisateur : l'appeler par le module.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field

from pharos_client import modele

INCONNU = "?"
INVITE_PLAN = ""     # à écrire : ce que l'on demande au modèle (bloc 21.3)


@dataclass(frozen=True)
class Etape:
    numero: int
    outil: str
    serveur: str
    raison: str


@dataclass
class Execution:
    """Ce que rend la boucle du LAB 13 : le plan annoncé, la réponse, la trace."""
    plan: list[Etape]
    reponse: str
    trace: list = field(default_factory=list)


class PlanIllisible(ValueError):
    """Le modèle n'a pas rendu un plan lisible."""


def demander_plan(messages: list[dict], outils: list[dict]) -> str:
    """Un appel au modèle (modele.completer, par l'attribut du module), avec le catalogue — pour qu'il nomme des
    outils réels — mais sans droit d'en appeler un maintenant. Rend le texte de sa réponse."""
    raise NotImplementedError("plan.demander_plan : à écrire (LAB 13, étape 2).")


def lire_plan(texte: str, serveur_de) -> list[Etape]:
    """Extrait le tableau JSON du texte (bloc ```json ou premier [ … ]) ; le serveur vient de serveur_de(outil)."""
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", texte, re.DOTALL) or re.search(r"\[.*\]", texte, re.DOTALL)
    if not m:
        raise PlanIllisible(f"aucun tableau JSON dans la réponse du modèle : « {texte[:200]} »")
    try:
        brut = json.loads(m.group(1) if m.re.groups else m.group(0))
    except json.JSONDecodeError as exc:
        raise PlanIllisible(f"plan JSON invalide ({exc}) : « {m.group(0)[:200]} »") from exc
    etapes = []
    for i, e in enumerate(brut, 1):
        if not isinstance(e, dict) or not e.get("outil"):
            raise PlanIllisible(f"étape {i} sans outil : {e!r}")
        outil = str(e["outil"])
        etapes.append(Etape(int(e.get("etape") or i), outil, serveur_de(outil) or INCONNU, str(e.get("raison", ""))))
    return etapes


def afficher_plan(etapes: list[Etape], sortie=print) -> str:
    if not etapes:
        texte = "Plan : aucun appel d'outil prévu."
    else:
        largeur = max(len(e.outil) for e in etapes)
        lignes = [f"Plan annoncé — {len(etapes)} étape(s), "
                  f"{len({e.serveur for e in etapes if e.serveur != INCONNU})} serveur(s)"]
        lignes += [f"  {e.numero}  {e.outil:<{largeur}}  {e.serveur:<12}  {e.raison}" for e in etapes]
        texte = "\n".join(lignes)
    sortie(texte)
    return texte


def valider_plan(etapes: list[Etape]) -> str:
    """Demande à l'exploitant : « ok » (tout exécuter), « non » (rien), ou une consigne libre. Défaut : « non »."""
    try:
        reponse = input("\n  Exécuter ce plan ? (ok / non / consigne) : ").strip()
    except EOFError:
        print("     (pas de terminal : plan refusé)", file=sys.stderr)
        return "non"
    return reponse or "non"
