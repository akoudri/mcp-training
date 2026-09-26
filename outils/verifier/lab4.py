"""Vérificateur du LAB 4 — pharos-client.

La mécanique de la boucle (trace, arrêts, réinjection) est vérifiée avec un MODÈLE SIMULÉ, contre le
vrai pharos-docs : déterministe et gratuit. Les questions 1 et 3 passent ensuite par le vrai modèle.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import importlib
import json
import os

from outils.verifier.commun import Echec, Verification
from pharos.openrouter import Appel, ErreurModele, Reponse

URL = "http://observateur:8101/mcp"
SECRET = "sk-or-secret-verification-123"
Q1 = "Quelles sont les pénalités de retard prévues au contrat de manutention de l'escale ESC-2026-0412 ?"
Q3 = "Quelle est la météo à Marseille jeudi ?"

v = Verification("LAB 4 — pharos-client", URL, "make lab4-docs")


def _modules():
    try:
        return (importlib.import_module("pharos_client.boucle"), importlib.import_module("pharos_client.modele"),
                importlib.import_module("pharos_client.trace"))
    except ModuleNotFoundError as exc:
        raise Echec("pharos_client introuvable (client/pharos_client/) : lancer « make depart LAB=4 ».") from exc


def appel(ident: str, nom: str, arguments: dict) -> tuple[str, str, dict]:
    return ident, nom, arguments


def _normaliser_nombre(texte: str) -> str:
    """Espaces insécables françaises des milliers (fine « \u202f », normale « \xa0 ») → espace normale."""
    return texte.replace("\u202f", " ").replace("\xa0", " ")


class ModeleSimule:
    """Répond selon un scénario ; le contexte estimé vaut 1000 tokens par message."""

    def __init__(self, tours: list, panne: bool = False):
        self.tours, self.panne, self.recus = tours, panne, []

    def completer(self, messages, outils, modele=None, **_):
        self.recus.append(copy.deepcopy(messages))
        if self.panne:
            raise ErreurModele("crédit épuisé sur cette clé : prévenir le formateur.")
        tour = self.tours[min(len(self.recus) - 1, len(self.tours) - 1)]
        usage = {"prompt_tokens": self.estimer(messages), "completion_tokens": 20}
        if isinstance(tour, str):
            return Reponse({"role": "assistant", "content": tour}, [], usage)
        message = {"role": "assistant", "content": None, "tool_calls": [
            {"id": i, "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, n, a in tour]}
        return Reponse(message, [Appel(i, n, a) for i, n, a in tour], usage)

    def estimer(self, messages, outils=()):
        return 1000 * len(messages)


@contextlib.contextmanager
def _simule(modele, simule: ModeleSimule):
    """Remplace modele.completer/estimer_tokens par le simulé ; coupe aussi la clé réelle : un import
    direct de la fonction (au lieu de l'attribut du module) ne doit jamais pouvoir dépenser de crédit."""
    anciens = modele.completer, modele.estimer_tokens
    ancienne_cle = os.environ.get("OPENROUTER_API_KEY")
    modele.completer, modele.estimer_tokens = simule.completer, simule.estimer
    os.environ["OPENROUTER_API_KEY"] = ""
    try:
        yield
    finally:
        modele.completer, modele.estimer_tokens = anciens
        if ancienne_cle is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = ancienne_cle


async def _scenario(ctx, simule: ModeleSimule, **options):
    """Rend (resultat, exception) de boucle.executer avec le modèle simulé."""
    boucle, modele, _ = _modules()
    with _simule(modele, simule):
        try:
            resultat, exc = await asyncio.to_thread(boucle.executer, "Question simulée sur l'escale ESC-2026-0412.",
                                                     url=ctx.url, **options), None
        except NotImplementedError as e:
            raise Echec("executer() lève NotImplementedError : la boucle n'est pas encore écrite.") from e
        except Exception as e:  # les arrêts attendus sont examinés par le critère
            resultat, exc = None, e
    if not simule.recus:
        raise Echec("la boucle n'a pas appelé modele.completer(...) : appeler le modèle par l'attribut du "
                     "module (from pharos_client import modele ; modele.completer(...)), pas par un import "
                     "direct de la fonction.")
    return resultat, exc


async def _nominal(ctx):
    if "nominal" not in ctx.cache:
        simule = ModeleSimule([
            [appel("a1", "rechercher_clause", {"escale_id": "ESC-2026-0412", "sujet": "penalites"}),
             appel("a2", "lister_documents", {"escale_id": "ESC-2026-0412", "cle_api": SECRET})],
            "La pénalité est de 1 850 € par heure."])
        resultat, exc = await _scenario(ctx, simule)
        if exc is not None:
            raise Echec(f"scénario simulé à deux appels puis une réponse : exception {exc.__class__.__name__}: {exc}")
        ctx.cache["nominal"] = (resultat, simule)
    return ctx.cache["nominal"]


@v.critere("La question 1 obtient une réponse correcte, sans intervention.", modele=True)
async def _(ctx):
    boucle, _, trace = _modules()
    try:
        reponse, enregistrements = await asyncio.to_thread(boucle.executer, Q1, url=ctx.url)
    except NotImplementedError as exc:
        raise Echec("la boucle n'est pas encore écrite.") from exc
    normal = _normaliser_nombre(reponse)
    if "1 850" not in normal and "1850" not in normal:
        raise Echec(f"la réponse ne cite pas la pénalité de 1 850 € par heure : « {reponse[:200]} »")
    return f"{len(enregistrements)} appel(s) d'outil — à consigner dans labs/lab4/mesures.md, sans corriger."


@v.critere("La trace porte les cinq champs, pour chaque appel.")
async def _(ctx):
    (reponse, enregistrements), _ = await _nominal(ctx)
    if len(enregistrements) != 2:
        raise Echec(f"deux appels d'outil attendus dans la trace, {len(enregistrements)} trouvés.")
    problemes = []
    if len({e.correlation for e in enregistrements}) != 1 or not enregistrements[0].correlation:
        problemes.append("un seul identifiant de corrélation, non vide, pour toute l'exécution")
    if [e.tour for e in enregistrements] != [1, 1]:
        problemes.append(f"les deux appels sont du tour 1 (trouvé : {[e.tour for e in enregistrements]})")
    if [e.outil for e in enregistrements] != ["rechercher_clause", "lister_documents"]:
        problemes.append("outils dans l'ordre des appels : rechercher_clause, lister_documents")
    for e in enregistrements:
        if not isinstance(e.duree_ms, (int, float)) or e.duree_ms < 0:
            problemes.append(f"{e.outil} : duree_ms en millisecondes")
        if not isinstance(e.octets, int) or e.octets <= 0:
            problemes.append(f"{e.outil} : octets = taille du résultat")
        if not isinstance(e.tokens_cumules, int) or e.tokens_cumules <= 0:
            problemes.append(f"{e.outil} : tokens_cumules = contexte estimé avant l'appel au modèle")
    if problemes:
        raise Echec("\n".join(problemes))


@v.critere("Les secrets sont masqués à l'écriture de la trace (étape 2).")
async def _(ctx):
    (_, enregistrements), _ = await _nominal(ctx)
    if SECRET in repr(enregistrements):
        raise Echec("l'argument cle_api apparaît en clair dans la trace : le masquer au moment où l'on enregistre.")


@v.critere("Le tour du modèle est réinjecté en entier : appels et résultats corrélés (étape 1).")
async def _(ctx):
    _, simule = await _nominal(ctx)
    if len(simule.recus) < 2:
        raise Echec("le modèle n'a été appelé qu'une fois : les résultats ne lui ont pas été rendus.")
    second = simule.recus[1]
    assistant = [m for m in second if m.get("role") == "assistant" and m.get("tool_calls")]
    outils = {m.get("tool_call_id") for m in second if m.get("role") == "tool"}
    if not assistant:
        raise Echec("au second appel, le message du modèle qui demandait les outils manque : le réinjecter tel quel.")
    if outils != {"a1", "a2"}:
        raise Echec(f"résultats d'outils attendus pour a1 et a2 (tool_call_id), trouvés : {sorted(map(str, outils))}")


@v.critere("afficher(trace) produit un arbre : exécution → tour → appels.")
async def _(ctx):
    (_, enregistrements), _ = await _nominal(ctx)
    _, _, trace = _modules()
    texte = trace.afficher(enregistrements, sortie=lambda _t: None)
    if "tour 1" not in texte or "rechercher_clause" not in texte:
        raise Echec("afficher() n'a pas produit l'arbre attendu : vérifier le format des enregistrements.")
    return texte


@v.critere("Le budget coupe, sur les tours comme sur les tokens, et l'exception porte la trace.")
async def _(ctx):
    boucle, _, _ = _modules()
    toujours = [[appel("b1", "lister_documents", {"escale_id": "ESC-2026-0412"})]]
    problemes = []
    simule = ModeleSimule(toujours)
    _, exc = await _scenario(ctx, simule, max_tours=2)
    if not isinstance(exc, boucle.BudgetDepasse):
        problemes.append(f"max_tours=2 avec un modèle qui appelle toujours un outil : BudgetDepasse attendu, obtenu {exc!r}")
    elif not exc.trace or len(simule.recus) > 2:
        problemes.append("budget de tours : la trace doit être portée par l'exception, et le modèle appelé au plus 2 fois")
    simule = ModeleSimule(toujours)
    _, exc = await _scenario(ctx, simule, max_tokens=3000)
    if not isinstance(exc, boucle.BudgetDepasse):
        problemes.append(f"max_tokens=3000 : BudgetDepasse attendu au deuxième tour, obtenu {exc!r}")
    elif len(simule.recus) > 1:
        problemes.append("budget de tokens vérifié après l'appel : le contrôle se place AVANT d'envoyer au modèle")
    elif not exc.trace:
        problemes.append("budget de tokens : l'exception doit porter la trace du premier tour")
    if problemes:
        raise Echec("\n".join(problemes))


@v.critere("L'arrêt sur échec non récupérable porte la trace (étape 3).")
async def _(ctx):
    boucle, _, _ = _modules()
    _, exc = await _scenario(ctx, ModeleSimule(["—"], panne=True))
    if not isinstance(exc, boucle.EchecNonRecuperable):
        raise Echec(f"modèle indisponible : EchecNonRecuperable attendu, obtenu {exc!r}")
    if not isinstance(exc.trace, list):
        raise Echec("EchecNonRecuperable doit porter la trace (une liste, même vide).")


@v.critere("La question 3 s'arrête en deux tours au plus, avec une réponse honnête.", modele=True)
async def _(ctx):
    boucle, modele, _ = _modules()
    appels = []
    reel = modele.completer

    def compteur(*a, **k):
        appels.append(1)
        return reel(*a, **k)

    modele.completer = compteur
    try:
        reponse, _ = await asyncio.to_thread(boucle.executer, Q3, url=ctx.url)
    finally:
        modele.completer = reel
    if len(appels) > 2:
        raise Echec(f"{len(appels)} tours pour une question à laquelle aucun outil ne répond (2 au plus).")
    return f"réponse (à juger : est-elle honnête ?) : « {reponse[:200]} »"


@v.constat("Les mesures de l'étape 5 sont consignées.")
def _(ctx):
    return "Compléter labs/lab4/mesures.md (make lab4-question Q=1, Q=2, Q=3 ; make tokens-catalogue SERVEUR=http://observateur:8101/mcp)."


@v.constat("Critère décisif — la trace, donnée au binôme voisin sans le code, suffit à dire ce qui s'est passé.")
def _(ctx):
    return "Échanger vos traces (make lab4-question Q=2) : outils, ordre, arguments, et raison de l'arrêt."
