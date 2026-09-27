"""Vérificateur du LAB 11 — recalcul de plan de quai : décision côté serveur, progression réelle, trois issues,
plan B, et la boucle honnête (critère décisif).

Aucun appel au modèle. Le vérificateur charge VOTRE serveur (serveurs/pharos_ops/serveur.py) dans son propre
processus, moteur en vitesse rapide (PHAROS_VITESSE) ; il lit le nombre réel d'escales du jour dans la base,
bascule la panne météo des mocks pendant un calcul, puis la lève. Ce que voit l'utilisateur à vitesse réelle
reste un constat (👁), consigné dans labs/lab11/observations.md.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import importlib.util
import io
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import asyncpg
from fastmcp import Client
from fastmcp_tasks import ToolTask
from fastmcp_tasks.client_models import ClientCreateTaskResult

from outils import lab10
from outils.verifier.commun import Echec, Verification
from outils.verifier.modele_simule import ModeleSimule, appel
from pharos import autorisation
from pharos_ops import planification

URL = "http://observateur:8103/mcp"
RACINE = Path(__file__).resolve().parents[2]
OBSERVATIONS = RACINE / "labs" / "lab11" / "observations.md"
OUTIL = "recalculer_plan_quai"
JEUDI = "2026-10-08"
TERMINAUX = ("completed", "failed", "cancelled")
INTERDITS = re.compile(r"^(async.*|asynchrone|synchrone|mode|tache.*|task.*|background|arriere_plan|en_fond|attendre)$")
PROGRESSION = re.compile(r"(\d+)\s+escales?\s+sur\s+(\d+)")
ATTENTE_MAX_S = 90.0

v = Verification("LAB 11 — recalcul de plan de quai", URL, "make lab8-base, make lab10-mocks, puis make lab10-up")


class ClientSansExtension(Client):
    _auto_internal_extensions = False


def charger_serveur():
    """Le serveur du binôme, importé sous un nom propre au vérificateur (serveurs.pharos_ops importable)."""
    chemin = RACINE / "serveurs" / "pharos_ops" / "serveur.py"
    if not chemin.exists():
        raise Echec("serveurs/pharos_ops/serveur.py absent : lancer « make depart LAB=11 ».")
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    spec = importlib.util.spec_from_file_location("verification_lab11_serveur", chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise Echec(f"serveurs/pharos_ops/serveur.py ne se charge pas : {exc.__class__.__name__}: {exc}") from exc
    return module.mcp


async def compter_escales() -> int:
    """Le nombre réel d'escales de jeudi, lu dans la base comme le moteur le lit."""
    escales, _ = await planification.lire_journee(date.fromisoformat(JEUDI), None)
    return len(escales)


async def _serveur(ctx):
    if "echec_preparation" in ctx.cache:
        raise Echec(ctx.cache["echec_preparation"])
    if "mcp" not in ctx.cache:
        try:
            lab10.attendre(delai_s=5)
            ctx.cache["total"] = await compter_escales()
        except lab10.MocksInjoignables as exc:
            ctx.cache["echec_preparation"] = str(exc)
            raise Echec(str(exc)) from exc
        except (OSError, asyncpg.PostgresError) as exc:
            ctx.cache["echec_preparation"] = f"base injoignable ({exc.__class__.__name__}) : lancer « make lab8-base »."
            raise Echec(ctx.cache["echec_preparation"]) from exc
        os.environ["PHAROS_VITESSE"] = "rapide"
        ctx.cache["mcp"] = charger_serveur()
    return ctx.cache["mcp"]


@contextlib.asynccontextmanager
async def _client(ctx, sans_extension: bool = False):
    serveur = await _serveur(ctx)
    classe = ClientSansExtension if sans_extension else Client
    with autorisation.en_tant_que("jeton-exploitation"):
        async with classe(serveur) as c:
            yield c


def _texte(resultat) -> str:
    import json

    texte = "\n".join(getattr(b, "text", "") or "" for b in resultat.content)
    if not texte and getattr(resultat, "structured_content", None) is not None:
        texte = json.dumps(resultat.structured_content, ensure_ascii=False)
    return texte


async def _soumettre(c, arguments: dict):
    return await c.session.call_tool(name=OUTIL, arguments=arguments, allow_claimed=True)


async def _suivre(c, brut, *, pendant=None) -> tuple[str, list[str], object]:
    """Suit la tâche jusqu'à un état terminal (sondage serré) ; pendant(messages) est appelé à chaque statut."""
    tache, messages = ToolTask(c, OUTIL, brut, raise_on_error=False), []
    fin = time.monotonic() + ATTENTE_MAX_S
    while True:
        etat = await tache.status()
        if etat.status_message and (not messages or messages[-1] != etat.status_message):
            messages.append(etat.status_message)
        if pendant is not None:
            await pendant(tache, messages)
        if etat.status in TERMINAUX:
            return etat.status, messages, await tache.result()
        if time.monotonic() > fin:
            await tache.cancel()
            raise Echec(f"la tâche n'a pas fini en {ATTENTE_MAX_S:.0f} s (moteur en vitesse rapide) : "
                        f"dernier statut {etat.status}, dernier message {etat.status_message!r}.")
        await asyncio.sleep(0.1)


@v.critere("recalculer_plan_quai est au catalogue, sous le nom du brief.")
async def _(ctx):
    async with _client(ctx) as c:
        noms = {o.name for o in await c.list_tools()}
    if OUTIL not in noms:
        raise Echec(f"{OUTIL} introuvable (catalogue : {', '.join(sorted(noms)) or 'vide'}) : garder le nom du brief — "
                    "le plan du LAB 13 l'appelle ainsi.")


@v.critere("Immédiat pour un quai (quai=3), une tâche pour la journée entière (client avec Tasks).")
async def _(ctx):
    async with _client(ctx) as c:
        debut = time.monotonic()
        direct = await _soumettre(c, {"date": JEUDI, "quai": 3})
        duree = time.monotonic() - debut
        if isinstance(direct, ClientCreateTaskResult):
            await ToolTask(c, OUTIL, direct).cancel()
            raise Echec("quai=3 rend une tâche : un quai seul se calcule en quelques secondes, réponse directe (étape 1).")
        if direct.is_error:
            raise Echec(f"quai=3 échoue : « {_texte(direct)[:200]} »")
        journee = await _soumettre(c, {"date": JEUDI})
        if not isinstance(journee, ClientCreateTaskResult):
            raise Echec("la journée entière (quai absent) répond directement au lieu de rendre une tâche : "
                        + (f"« {_texte(journee)[:200]} »" if journee.is_error else "décider côté serveur (étape 1)."))
        await ToolTask(c, OUTIL, journee).cancel()
    ctx.cache["intervalle_s"] = (journee.poll_interval_ms or 5000) / 1000
    return f"quai=3 : {duree:.1f} s ; journée : tâche, intervalle suggéré {journee.poll_interval_ms} ms"


@v.critere("La décision vient du serveur : aucun paramètre ne la commande, un seul outil de recalcul.")
async def _(ctx):
    async with _client(ctx) as c:
        outils = await c.list_tools()
    recalculs = [o.name for o in outils if "recalcul" in o.name]
    if len(recalculs) != 1:
        raise Echec(f"outils de recalcul : {', '.join(recalculs)} — un seul, et le serveur décide (bloc 18.2).")
    [outil] = [o for o in outils if o.name == OUTIL]
    fautifs = [p for p in (outil.input_schema or {}).get("properties", {}) if INTERDITS.match(p.casefold())]
    if fautifs:
        raise Echec(f"paramètres à retirer : {', '.join(fautifs)}. Aucun argument ne commande la tâche : le serveur "
                    "décide, d'après ce qui est demandé et ce que le client déclare.")


@v.critere("La progression est un compte réel, issu du moteur : « N escales sur M », N croissant, M exact.")
async def _(ctx):
    async with _client(ctx) as c:
        statut, messages, resultat = await _suivre(c, await _soumettre(c, {"date": JEUDI}))
    ctx.cache["journee"] = (statut, resultat)
    comptes = [tuple(map(int, m.groups())) for m in (PROGRESSION.search(t) for t in messages) if m]
    if len(comptes) < 2:
        raise Echec(f"messages de progression vus : {messages[:5] or 'aucun'} — au moins deux « N escales sur M » "
                    "attendus, depuis le rappel du moteur (ctx.report_progress).")
    total = ctx.cache["total"]
    if any(m != total for _, m in comptes):
        raise Echec(f"M vaut {sorted({m for _, m in comptes})}, or jeudi compte {total} escales en base : la "
                    "progression doit venir du moteur (rappel_progression), pas d'une estimation.")
    if any(b <= a for (a, _), (b, _) in zip(comptes, comptes[1:])):
        raise Echec(f"N n'est pas strictement croissant : {[n for n, _ in comptes]}.")
    return f"{len(comptes)} progressions vues : {', '.join(messages[:3])}… ({total} escales en base)"


@v.critere("Trois issues : terminé, échoué (panne météo pendant le calcul), annulé (tasks/cancel).")
async def _(ctx):
    if "journee" not in ctx.cache:
        async with _client(ctx) as c:
            statut, _, resultat = await _suivre(c, await _soumettre(c, {"date": JEUDI}))
        ctx.cache["journee"] = (statut, resultat)
    statut, resultat = ctx.cache["journee"]
    if statut != "completed" or resultat.is_error:
        raise Echec(f"la journée ne se termine pas : statut {statut}, « {_texte(resultat)[:200]} ».")

    async def couper(tache, messages):
        if messages and "coupee" not in etat_panne:
            etat_panne["coupee"] = True
            lab10.regler(panne="meteo")

    etat_panne: dict = {}
    avant = lab10.lire_config()
    try:
        async with _client(ctx) as c:
            statut_panne, _, en_panne = await _suivre(c, await _soumettre(c, {"date": JEUDI}), pendant=couper)
    finally:
        lab10.regler(**avant)
    if not (statut_panne == "failed" or (statut_panne == "completed" and en_panne.is_error)):
        raise Echec(f"météo coupée pendant le calcul : la tâche finit {statut_panne} sans erreur — l'échec doit "
                    "remonter au client (isError, ou failed).")
    message = _texte(en_panne)
    if not message.strip():
        raise Echec("la tâche échoue sans message : dire ce qui est tombé.")

    async def annuler(tache, messages):
        if messages and "annulee" not in etat_annulation:
            etat_annulation["annulee"] = True
            await tache.cancel()

    etat_annulation: dict = {}
    async with _client(ctx) as c:
        statut_annule, _, _ = await _suivre(c, await _soumettre(c, {"date": JEUDI}), pendant=annuler)
    if statut_annule != "cancelled":
        raise Echec(f"annulée à mi-parcours (tasks/cancel), la tâche finit {statut_annule} au lieu de cancelled.")
    ctx.cache["echec_meteo"] = message
    return f"échec en panne : « {message[:160]} »"


@v.constat("L'échec en panne porte les trois parties du bloc 17.3 (extension B).")
def _(ctx):
    message = ctx.cache.get("echec_meteo")
    return f"Relire : « {message} »" if message else "Relire l'échec obtenu avec make lab10-mocks PANNE=meteo pendant un calcul."


@v.critere("Plan B : un client sans l'extension obtient un refus explicite qui propose une alternative.")
async def _(ctx):
    async with _client(ctx, sans_extension=True) as c:
        debut = time.monotonic()
        brut = await _soumettre(c, {"date": JEUDI})
        duree = time.monotonic() - debut
    if isinstance(brut, ClientCreateTaskResult):
        raise Echec("une tâche est créée pour un client qui ne déclare pas l'extension : il ne pourra jamais la suivre.")
    texte = _texte(brut)
    if not brut.is_error:
        raise Echec(f"le client sans l'extension reçoit un résultat au bout de {duree:.0f} s, au lieu d'un refus "
                    "immédiat : le calcul de la journée ne tient pas dans un appel (étape 3).")
    if not re.search(r"\bquai", texte, re.IGNORECASE) or len(texte) < 60:
        raise Echec(f"refus trop sec : « {texte[:200]} » — dire ce qui n'est pas possible, et ce qui l'est (par "
                    "exemple, le recalcul quai par quai).")
    return f"« {texte[:220]} »"


def _boucle():
    try:
        return importlib.import_module("pharos_client.boucle")
    except ModuleNotFoundError as exc:
        raise Echec("pharos_client introuvable : ce lab part de etat/is2-fin (make depart LAB=11).") from exc


@v.critere("Critère décisif — la boucle affiche une progression qui avance, et ne réinjecte que le résultat reçu.")
async def _(ctx):
    serveur = await _serveur(ctx)
    intervalle = ctx.cache.get("intervalle_s", 2.0)
    # Assez lent pour que l'intervalle suggéré par le serveur laisse voir plusieurs progressions (≥ 3 intervalles).
    os.environ["PHAROS_VITESSE"] = str(max(1.0, min(10.0, 40.0 / max(intervalle, 0.1))))
    if "journee" not in ctx.cache:
        raise Echec("la journée n'a pas pu être calculée (critère de progression) : corriger d'abord ce critère.")
    reel = _texte(ctx.cache["journee"][1])
    boucle = _boucle()
    sortie = io.StringIO()

    def executer():
        with autorisation.en_tant_que("jeton-exploitation"), contextlib.redirect_stdout(sortie):
            return boucle.executer("Question simulée du LAB 11.", url=serveur)

    try:
        with ModeleSimule([[appel("a1", OUTIL, {"date": JEUDI})], "Réponse simulée."]) as simule:
            await asyncio.to_thread(executer)
    except NotImplementedError as exc:
        raise Echec("la boucle du LAB 4 n'est pas écrite : ce lab part de etat/is2-fin (make depart LAB=11).") from exc
    except Exception as exc:
        if hasattr(exc, "trace"):
            raise Echec(f"la boucle s'est arrêtée : {exc}") from exc
        raise
    finally:
        os.environ["PHAROS_VITESSE"] = "rapide"
    vues = {m.group(0) for m in PROGRESSION.finditer(sortie.getvalue())}
    if len(vues) < 2:
        raise Echec(f"la boucle n'affiche pas la progression ({len(vues)} vue(s)) : suivre la tâche — par exemple "
                    "pharos_client.taches.appeler_ou_suivre — au lieu d'un appel ordinaire qui attend en silence.")
    reinjecte = [m for tour in simule.recus for m in tour if m.get("role") == "tool"]
    if not reinjecte or reel[:300] not in (reinjecte[-1].get("content") or ""):
        apercu = (reinjecte[-1].get("content") or "")[:160] if reinjecte else "rien"
        raise Echec(f"le modèle n'a pas reçu le résultat réel de la tâche (reçu : « {apercu} ») : réinjecter le "
                    "résultat final, et seulement lui.")
    return f"{len(vues)} progressions affichées ; résultat réel réinjecté ({len(reel)} caractères)"


@v.constat("À vitesse réelle, ce que voit l'utilisateur minute par minute (labs/lab11/observations.md).")
def _(ctx):
    return "Relire labs/lab11/observations.md : à la quatre-vingt-dixième seconde, que voyait l'utilisateur ?"
