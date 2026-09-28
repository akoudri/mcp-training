"""pharos-client — la boucle agentique (LAB 4), qui suit les tâches (LAB 11). Solution de référence."""

from __future__ import annotations

import re
import time
import uuid

from pharos_client import modele, taches
from pharos_client.trace import Enregistrement, borner
from pharos_client.transport import URL_DEFAUT, Session

CONSIGNE = ("Tu es l'assistant de l'exploitant du terminal portuaire PHAROS. Nous sommes le mardi "
            "6 octobre 2026, à Paris. Utilise les outils disponibles ; si aucun ne permet de répondre, dis-le.")
CLES_SENSIBLES = ("cle", "key", "token", "secret", "password", "mot_de_passe")

SEUIL_ATTACHE = 6000   # octets : au-delà, la ressource est annoncée, pas attachée (80 pages ne vont pas au contexte)


def _documents_de_la_question(session: Session, question: str) -> str:
    """Liste les ressources des escales citées ; attache les petites, annonce les grandes."""
    escales = set(re.findall(r"ESC-\d{4}-\d{4}", question))
    if not escales:
        return ""
    lignes = []
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


def executer(question: str, *, url: str = URL_DEFAUT, max_tours: int = 8,
             max_tokens: int = 30_000) -> tuple[str, list[Enregistrement]]:
    """Pose la question, laisse le modèle appeler les outils, sait s'arrêter. Rend (réponse, trace)."""
    correlation = uuid.uuid4().hex[:12]
    trace: list[Enregistrement] = []
    messages = [{"role": "system", "content": CONSIGNE}, {"role": "user", "content": question}]
    try:
        with Session(url) as session:
            outils = session.lister_outils()
            documents = _documents_de_la_question(session, question)
            if documents:
                messages.insert(1, {"role": "system", "content": documents})
            for tour in range(1, max_tours + 1):
                contexte = modele.estimer_tokens(messages, outils)
                if contexte > max_tokens:
                    raise BudgetDepasse(f"budget de tokens atteint avant le tour {tour} : {contexte} > {max_tokens}", trace)
                reponse = modele.completer(messages, outils)
                messages.append(reponse.message)                 # le tour du modèle, en entier
                if not reponse.appels:
                    return reponse.message.get("content") or "", trace
                for appel in reponse.appels:
                    debut = time.perf_counter()
                    # LAB 11 : un outil qui répond en tâche est suivi jusqu'au bout, progression affichée ; le
                    # modèle ne reçoit que le résultat final, réel — jamais un résultat supposé.
                    resultat = taches.appeler_ou_suivre(session, appel.nom, appel.arguments, correlation=correlation)
                    trace.append(Enregistrement(correlation, tour, appel.nom, _masquer(appel.arguments),
                                                round((time.perf_counter() - debut) * 1000, 1), resultat.octets,
                                                contexte, resultat.est_erreur, borner(_masquer_texte(resultat.texte, appel.arguments)),
                                                session.url))
                    messages.append({"role": "tool", "tool_call_id": appel.id, "content": resultat.texte})
            raise BudgetDepasse(f"budget de tours épuisé ({max_tours})", trace)
    except ArretBoucle:
        raise
    except modele.ErreurModele as exc:
        raise EchecNonRecuperable(f"modèle indisponible : {exc}", trace) from exc
    except Exception as exc:
        raise EchecNonRecuperable(f"serveur injoignable ou transport en échec : {exc}", trace) from exc
