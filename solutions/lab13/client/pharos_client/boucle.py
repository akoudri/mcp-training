"""pharos-client — la boucle agentique (LAB 4), qui suit les tâches (LAB 11), rejoue les demandes de
confirmation (LAB 12), et parle à trois serveurs à la fois derrière un plan visible (LAB 13). Solution de référence."""

from __future__ import annotations

import re
import time
import uuid
from pathlib import Path

from pharos_client import agregation, entrees, modele, plan
from pharos_client.trace import Enregistrement, borner
from pharos_client.transport import Resultat

CONSIGNE = Path(__file__).with_name("consigne.md").read_text(encoding="utf-8").strip()
CLES_SENSIBLES = ("cle", "key", "token", "secret", "password", "mot_de_passe")

REJEUX_MAX = 3         # demandes d'entrée successives acceptées pour un même appel, avant d'abandonner
SEUIL_ATTACHE = 6000   # octets : au-delà, la ressource est annoncée, pas attachée (80 pages ne vont pas au contexte)


def _documents_de_la_question(catalogue, question: str) -> str:
    """Liste les ressources des escales citées, sur tous les serveurs ; attache les petites, annonce les grandes."""
    escales = set(re.findall(r"ESC-\d{4}-\d{4}", question))
    if not escales:
        return ""
    lignes = []
    for session in catalogue.sessions().values():
        for r in session.lister_ressources():
            if not any(f"/escales/{e}/" in r["uri"] for e in escales):
                continue
            if r["taille"] is not None and r["taille"] <= SEUIL_ATTACHE:
                lignes.append(f"--- {r['uri']} ---\n{session.lire_ressource(r['uri'])}")
            else:
                lignes.append(f"{r['uri']} ({r['taille']} octets) : non attaché — utiliser les outils pour en citer une clause.")
    return "Documents des escales citées :\n" + "\n".join(lignes) if lignes else ""


class ArretBoucle(Exception):
    """Arrêt anormal de la boucle : porte toujours la trace complète."""

    def __init__(self, message: str, trace: list[Enregistrement]):
        super().__init__(message)
        self.trace = trace


class BudgetDepasse(ArretBoucle):
    """Budget de tours, ou de tokens, épuisé."""


class EchecNonRecuperable(ArretBoucle):
    """Échec que le modèle ne peut pas corriger : modèle indisponible, serveur injoignable."""


def _masquer(arguments: dict) -> dict:
    return {k: "***" if any(s in k.casefold() for s in CLES_SENSIBLES) else w for k, w in arguments.items()}


def _masquer_texte(texte: str, arguments: dict) -> str:
    """Un serveur peut renvoyer un argument dans son résultat : ses valeurs secrètes n'entrent pas non plus dans la trace."""
    for k, w in arguments.items():
        if any(s in k.casefold() for s in CLES_SENSIBLES) and isinstance(w, str) and w:
            texte = texte.replace(w, "***")
    return texte


def _appeler(session, nom: str, arguments: dict, correlation: str):
    """Un appel d'outil, jusqu'à son résultat final.

    LAB 11 : une tâche est suivie jusqu'au bout, progression affichée (entrees.appeler_brut s'en charge) ; le
    modèle ne reçoit que le résultat final, réel — jamais un résultat supposé.
    LAB 12 : une demande d'entrée n'est ni un succès ni une erreur. Elle est présentée à l'utilisateur, puis LE
    MÊME appel est reposé — même nom, mêmes arguments — augmenté des réponses et du requestState reçu, tel quel."""
    resultat = entrees.appeler_brut(session, nom, arguments, correlation=correlation)
    for _ in range(REJEUX_MAX):
        if not isinstance(resultat, entrees.DemandeEntree):
            return resultat
        reponses = {cle: entrees.demander_utilisateur(demande) for cle, demande in resultat.demandes.items()}
        resultat = entrees.appeler_brut(session, nom, arguments, reponses=reponses, etat=resultat.etat,
                                        correlation=correlation)
    if isinstance(resultat, entrees.DemandeEntree):
        texte = f"{nom} : trop de demandes successives ({REJEUX_MAX}), appel abandonné — rien n'a été confirmé."
        return Resultat(texte, True, len(texte.encode("utf-8")))
    return resultat


def _planifier(messages: list[dict], outils: list[dict], catalogue) -> tuple[list, str | None]:
    """Le plan, affiché avant toute action, puis la décision de l'exploitant : « ok », « non », ou une consigne."""
    texte = plan.demander_plan(messages, outils)
    try:
        etapes = plan.lire_plan(texte, catalogue.serveur_de)
    except plan.PlanIllisible as exc:
        print(f"Plan illisible ({exc}) : exécution sans plan annoncé.")
        return [], "ok"
    plan.afficher_plan(etapes)
    messages.append({"role": "assistant", "content": texte})
    return etapes, plan.valider_plan(etapes).strip()


def executer(question: str, *, config=agregation.CONFIG, max_tours: int = 12, max_tokens: int = 40_000,
             planifier: bool = True) -> plan.Execution:
    """Pose la question aux trois serveurs, derrière un plan visible. Rend Execution(plan, reponse, trace)."""
    correlation = uuid.uuid4().hex[:12]
    trace: list[Enregistrement] = []
    messages = [{"role": "system", "content": CONSIGNE}, {"role": "user", "content": question}]
    try:
        with agregation.Catalogue(agregation.lire_config(config)) as catalogue:
            outils = catalogue.outils()
            documents = _documents_de_la_question(catalogue, question)
            if documents:
                messages.insert(1, {"role": "system", "content": documents})
            etapes, decision = _planifier(messages, outils, catalogue) if planifier else ([], "ok")
            if decision.casefold() in ("non", "n", "no"):
                return plan.Execution(etapes, "Plan refusé par l'exploitant : rien n'a été exécuté.", trace)
            messages.append({"role": "user", "content": "Plan accepté : exécute-le." if decision.casefold() in
                             ("ok", "oui", "o", "") else f"Plan accepté, avec cette consigne : {decision}"})
            for tour in range(1, max_tours + 1):
                contexte = modele.estimer_tokens(messages, outils)
                if contexte > max_tokens:
                    raise BudgetDepasse(f"budget de tokens atteint avant le tour {tour} : {contexte} > {max_tokens}", trace)
                reponse = modele.completer(messages, outils)
                messages.append(reponse.message)                 # le tour du modèle, en entier
                if not reponse.appels:
                    return plan.Execution(etapes, reponse.message.get("content") or "", trace)
                for appel in reponse.appels:
                    debut = time.perf_counter()
                    serveur = catalogue.serveur_de(appel.nom)
                    if serveur is None:
                        texte = f"Outil inconnu : {appel.nom}. Outils disponibles : {', '.join(o['function']['name'] for o in outils)}."
                        resultat = Resultat(texte, True, len(texte.encode("utf-8")))
                    else:
                        resultat = _appeler(catalogue.session_de(appel.nom), appel.nom, appel.arguments, correlation)
                    trace.append(Enregistrement(correlation, tour, appel.nom, _masquer(appel.arguments),
                                                round((time.perf_counter() - debut) * 1000, 1), resultat.octets,
                                                contexte, resultat.est_erreur,
                                                borner(_masquer_texte(resultat.texte, appel.arguments)),
                                                serveur or "?"))
                    messages.append({"role": "tool", "tool_call_id": appel.id, "content": resultat.texte})
            raise BudgetDepasse(f"budget de tours épuisé ({max_tours})", trace)
    except ArretBoucle:
        raise
    except agregation.CollisionDeNoms as exc:
        raise EchecNonRecuperable(str(exc), trace) from exc
    except modele.ErreurModele as exc:
        raise EchecNonRecuperable(f"modèle indisponible : {exc}", trace) from exc
    except Exception as exc:
        raise EchecNonRecuperable(f"serveur injoignable ou transport en échec : {exc}", trace) from exc
