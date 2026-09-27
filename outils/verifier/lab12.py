"""Vérificateur du LAB 12 — confirmation avant publication : aucun chemin sans rejeu, demande conforme, rejeu
augmenté par la boucle, repli, deux instances, et le critère décisif (un refus laisse propre).

Aucun appel au modèle. Tout passe par le répartiteur à deux instances (make lab12-deux-instances) ; le canal des
mocks est remis à zéro avant chaque contrôle, et son compteur est la seule vérité. La boucle du binôme est
jouée avec un modèle simulé et une réponse de l'utilisateur scriptée (entrees.demander_utilisateur remplacé).
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import os
import re
from pathlib import Path

import mcp_types
from mcp.client.session import ClientSession
from mcp.shared.exceptions import MCPError

from outils import lab10, lab12
from outils.client_test import ClientTest
from outils.verifier.commun import Echec, Verification
from outils.verifier.modele_simule import ModeleSimule, appel
from pharos import journal

URL = "http://observateur:8203/mcp"
RACINE = Path(__file__).resolve().parents[2]
MESURES = RACINE / "labs" / "lab12" / "mesures.md"
OUTIL = "publier_alerte"
JETON = "jeton-exploitation"
ESCALE, AUTRE_ESCALE, DESTINATAIRE = "ESC-2026-0412", "ESC-2026-0413", "exploitation"

v = Verification("LAB 12 — confirmation avant publication", URL,
                 "make lab8-base, make lab10-mocks, puis make lab12-deux-instances")


def _compteur() -> int:
    try:
        return sum(lab12.alertes().values())
    except lab10.MocksInjoignables as exc:
        raise Echec(str(exc)) from exc


def _raz() -> None:
    try:
        lab12.raz()
    except lab10.MocksInjoignables as exc:
        raise Echec(str(exc)) from exc


def _client(ctx, profil: str = "complet") -> ClientTest:
    return ClientTest(ctx.url, jeton=JETON, profil=profil, nom=f"verificateur-lab12-{profil}")


def _texte(resultat) -> str:
    texte = "\n".join(getattr(b, "text", "") or "" for b in getattr(resultat, "content", None) or [])
    if not texte and getattr(resultat, "structured_content", None) is not None:
        texte = json.dumps(resultat.structured_content, ensure_ascii=False)
    return texte


async def _arguments(ctx) -> dict:
    """Arguments valides pour publier_alerte : un niveau pris dans l'énumération du schéma, s'il y en a une."""
    if "arguments" not in ctx.cache:
        async with _client(ctx) as c:
            outils = {o.name: o for o in await c.outils()}
        if OUTIL not in outils:
            raise Echec(f"{OUTIL} introuvable (catalogue : {', '.join(sorted(outils)) or 'vide'}) : garder le nom du brief.")
        niveau = ((outils[OUTIL].input_schema or {}).get("properties", {}).get("niveau") or {}).get("enum") or ["orange"]
        ctx.cache["arguments"] = {"escale_id": ESCALE, "niveau": niveau[0], "destinataire": DESTINATAIRE}
    return dict(ctx.cache["arguments"])


def _reponses(demande: mcp_types.InputRequiredResult, valeur: bool) -> dict:
    """Répond à chaque demande : tous les booléens du schéma à `valeur` (oui / non)."""
    reponses = {}
    for cle, requete in (demande.input_requests or {}).items():
        schema = getattr(requete.params, "requested_schema", None) or {}
        contenu = {k: valeur for k, p in (schema.get("properties") or {}).items() if p.get("type") == "boolean"}
        reponses[cle] = mcp_types.ElicitResult(action="accept", content=contenu)
    return reponses


async def _demande(c, arguments) -> mcp_types.InputRequiredResult:
    brut = await c.appeler_brut(OUTIL, arguments)
    if not isinstance(brut, mcp_types.InputRequiredResult):
        raise Echec(f"publier_alerte, client avec élicitation, sans réponse : pas de demande de confirmation "
                    f"(input_required) mais « {_texte(brut)[:200]} ».")
    return brut


async def _rejouer(c, arguments, reponses, etat):
    """Le rejeu ; un refus du SDK (MCPError) est rendu comme un résultat en erreur."""
    try:
        return await c.appeler_brut(OUTIL, arguments, reponses=reponses, etat=etat)
    except MCPError as exc:
        return mcp_types.CallToolResult(content=[mcp_types.TextContent(type="text", text=f"MCPError: {exc}")],
                                        is_error=True)


@v.critere("publier_alerte est au catalogue, sous le nom du brief, avec son destinataire.")
async def _(ctx):
    async with _client(ctx) as c:
        outils = {o.name: o for o in await c.outils()}
    if OUTIL not in outils:
        raise Echec(f"{OUTIL} introuvable (catalogue : {', '.join(sorted(outils)) or 'vide'}) : garder le nom du brief.")
    if "destinataire" not in (outils[OUTIL].input_schema or {}).get("properties", {}):
        raise Echec("publier_alerte n'a pas de paramètre destinataire : publier_alerte(escale_id, niveau, "
                    "destinataire=\"exploitation\", note=\"\") — il figure dans la demande de confirmation.")


@v.critere("Le chiffre de l'étape 1 (sans garde-fou) est consigné dans labs/lab12/mesures.md.")
def _(ctx):
    if not MESURES.exists():
        raise Echec("labs/lab12/mesures.md absent : lancer « make depart LAB=12 », puis consigner l'étape 1.")
    ligne = next((l for l in MESURES.read_text(encoding="utf-8").splitlines()
                  if l.startswith("| Alertes parties à l'étape 1")), "")
    chiffres = re.findall(r"\d+", ligne.split("|")[2] if ligne.count("|") >= 3 else "")
    if not chiffres:
        raise Echec("labs/lab12/mesures.md : consigner, ligne « Alertes parties à l'étape 1 », le compteur relevé "
                    "avant toute correction (make lab12-compteur, trois conversations).")
    return f"étape 1 : {', '.join(chiffres)}"


@v.critere("Aucun chemin ne publie sans rejeu : appel direct, avec ou sans élicitation déclarée → compteur inchangé.")
async def _(ctx):
    arguments = await _arguments(ctx)
    _raz()
    async with _client(ctx) as c:
        await c.appeler_brut(OUTIL, arguments)
    async with _client(ctx, "sans_elicitation") as c:
        await c.appeler_brut(OUTIL, arguments)
    parties = _compteur()
    if parties:
        raise Echec(f"{parties} alerte(s) partie(s) sans rejeu : publier_alerte doit rendre la main (input_required) "
                    "et ne publier qu'au rejeu confirmé.")


@v.critere("La demande est conforme : input_required, confirmation, default false, escale, niveau et destinataire.")
async def _(ctx):
    arguments = await _arguments(ctx)
    async with _client(ctx) as c:
        demande = await _demande(c, arguments)
    requetes = list((demande.input_requests or {}).values())
    booleens = [(getattr(r.params, "message", ""), p) for r in requetes
                for p in ((getattr(r.params, "requested_schema", None) or {}).get("properties") or {}).values()
                if p.get("type") == "boolean"]
    if not booleens:
        raise Echec("la demande ne porte aucune confirmation (un booléen dans requested_schema).")
    if any(p.get("default") is not False for _, p in booleens):
        raise Echec("la confirmation doit porter default: false — un client qui applique le défaut sans demander ne "
                    "doit rien publier (bloc 19.5, extension C).")
    message = " ".join(getattr(r.params, "message", "") for r in requetes)
    manques = [v for v in arguments.values() if v not in message]
    if manques:
        raise Echec(f"le message de la demande ne cite pas {', '.join(manques)} : le contexte va DANS la question "
                    f"(« {message[:160]} »).")
    if not demande.request_state:
        raise Echec("aucun requestState : ce que le serveur doit retrouver au rejeu y voyage.")
    return f"« {message[:160]} »"


@contextlib.contextmanager
def _espion():
    """Enregistre chaque tools/call du client MCP (nom, arguments, inputResponses, requestState)."""
    appels, original = [], ClientSession.call_tool

    async def enregistrer(self, name, arguments=None, *args, **kwargs):
        appels.append({"nom": name, "arguments": dict(arguments or {}),
                       "reponses": kwargs.get("input_responses"), "etat": kwargs.get("request_state")})
        return await original(self, name, arguments, *args, **kwargs)

    ClientSession.call_tool = enregistrer
    try:
        yield appels
    finally:
        ClientSession.call_tool = original


def _boucle_et_entrees():
    try:
        return importlib.import_module("pharos_client.boucle"), importlib.import_module("pharos_client.entrees")
    except ModuleNotFoundError as exc:
        raise Echec("pharos_client.entrees introuvable : ce lab part de etat/is3-fin (make depart LAB=12).") from exc


async def _jouer_boucle(ctx, arguments: dict, valeur: bool) -> list[dict]:
    boucle, entrees = _boucle_et_entrees()

    def repondre(demande):
        props = (demande.get("schema") or {}).get("properties") or {}
        return {"action": "accept", "content": {k: valeur for k, p in props.items() if p.get("type") == "boolean"}}

    ancien, ancien_jeton = entrees.demander_utilisateur, os.environ.get("PHAROS_JETON")
    entrees.demander_utilisateur, os.environ["PHAROS_JETON"] = repondre, JETON
    try:
        with _espion() as appels, ModeleSimule([[appel("a1", OUTIL, arguments)], "Réponse simulée."]):
            await asyncio.to_thread(boucle.executer, "Question simulée du LAB 12.", url=ctx.url)
    except NotImplementedError as exc:
        raise Echec("la boucle du LAB 4 n'est pas écrite : ce lab part de etat/is3-fin (make depart LAB=12).") from exc
    finally:
        entrees.demander_utilisateur = ancien
        if ancien_jeton is None:
            os.environ.pop("PHAROS_JETON", None)
        else:
            os.environ["PHAROS_JETON"] = ancien_jeton
    return [a for a in appels if a["nom"] == OUTIL]


@v.critere("La boucle repose le MÊME appel, augmenté : « non » → rien ne part ; « oui » → une alerte.")
async def _(ctx):
    arguments = await _arguments(ctx)
    _raz()
    appels = await _jouer_boucle(ctx, arguments, False)
    if _compteur():
        raise Echec("l'utilisateur a répondu « non » et une alerte est partie.")
    _raz()
    appels = await _jouer_boucle(ctx, arguments, True)
    if len(appels) < 2:
        raise Echec("la boucle n'a pas reposé l'appel après la demande : reconnaître input_required (ni succès ni "
                    "erreur), présenter la demande (entrees.demander_utilisateur), puis rejouer.")
    premier, rejeu = appels[0], appels[1]
    if (rejeu["nom"], rejeu["arguments"]) != (premier["nom"], premier["arguments"]):
        raise Echec(f"le rejeu n'est pas le même appel : {rejeu['arguments']} au lieu de {premier['arguments']}.")
    if not rejeu["reponses"] or not rejeu["etat"]:
        raise Echec("le rejeu ne porte pas inputResponses et le requestState reçu : le serveur repart de zéro (la "
                    "boucle de confirmation infinie du brief).")
    parties = _compteur()
    if parties != 1:
        raise Echec(f"« oui » : {parties} alerte(s) partie(s) au lieu d'une.")
    return "« non » : 0 ; « oui » : 1, par le même appel augmenté"


@v.critere("Repli : un client sans élicitation obtient un refus explicite, qui propose de préparer la note sans publier.")
async def _(ctx):
    arguments = await _arguments(ctx)
    _raz()
    async with _client(ctx, "sans_elicitation") as c:
        r = await c.appeler_brut(OUTIL, arguments)
    if _compteur():
        raise Echec("un client sans élicitation a fait partir une alerte.")
    if isinstance(r, mcp_types.InputRequiredResult):
        raise Echec("le client sans élicitation n'obtient pas un refus : le serveur lui envoie une demande "
                    "(input_required) qu'il ne sait pas présenter. Lire ses capacités dans _meta, et refuser.")
    texte = _texte(r)
    if not r.is_error:
        raise Echec(f"le client sans élicitation n'obtient pas un refus (isError) : « {texte[:200]} ».")
    if not re.search(r"note", texte, re.IGNORECASE) or not re.search(r"sans\s+(la\s+)?publi|prépar", texte, re.IGNORECASE):
        raise Echec(f"refus sans alternative : « {texte[:200]} » — dire pourquoi, et proposer de préparer la note "
                    "sans la publier.")
    return f"« {texte[:200]} »"


def _nouvelles_lignes(avant: int) -> list[dict]:
    return journal.lire("pharos-ops")[avant:]


@v.critere("Deux instances : le rejeu passe sur l'autre instance ; un requestState altéré est refusé et journalisé.")
async def _(ctx):
    arguments = await _arguments(ctx)
    _raz()
    async with _client(ctx) as c:
        for _ in range(4):
            demande = await _demande(c, arguments)
            instance_demande = c.instances()[-1]
            r = await _rejouer(c, arguments, _reponses(demande, True), demande.request_state)
            if c.instances()[-1] != instance_demande:
                break
        else:
            raise Echec("le rejeu n'a jamais atterri sur l'autre instance : vérifier make lab12-deux-instances.")
    if getattr(r, "is_error", False) or _compteur() != 1:
        raise Echec(f"rejeu sur l'autre instance ({instance_demande} → {c.instances()[-1]}) : « {_texte(r)[:200]} » — "
                    "chaque instance doit sceller et ouvrir l'état avec la même clé : RequestStateSecurity(keys=[…"
                    "CLE_ETAT…], audience=…) ; et rien ne doit rester en mémoire entre la demande et le rejeu.")
    _raz()
    lignes = len(journal.lire("pharos-ops"))
    async with _client(ctx) as c:
        demande = await _demande(c, arguments)
        etat = demande.request_state
        milieu = len(etat) // 2
        altere = etat[:milieu] + ("A" if etat[milieu] != "A" else "B") + etat[milieu + 1:]
        r = await _rejouer(c, arguments, _reponses(demande, True), altere)
    if not getattr(r, "is_error", False) or _compteur():
        raise Echec("un requestState altéré d'un caractère, au milieu de la chaîne, a été accepté.")
    refus = [l for l in _nouvelles_lignes(lignes) if l.get("issue") == "refus"]
    if not refus:
        raise Echec("le refus de l'état altéré ne figure pas dans logs/pharos-ops.jsonl : garder l'intergiciel "
                    "journal.Journal(\"pharos-ops\") branché sur le serveur.")
    return f"rejeu {instance_demande} → autre instance : publié ; altéré : refusé et journalisé (« {refus[-1]['message']} »)"


def _empreinte() -> dict[str, tuple[int, int]]:
    fichiers = {}
    for dossier in (RACINE / "labs" / "lab12", RACINE / "sortie"):
        if dossier.is_dir():
            for f in dossier.rglob("*"):
                if f.is_file():
                    etat = f.stat()
                    fichiers[str(f.relative_to(RACINE))] = (etat.st_size, etat.st_mtime_ns)
    return fichiers


@v.critere("Critère décisif — un refus laisse propre : compteur inchangé, rien d'écrit sous labs/lab12/ ni sortie/.")
async def _(ctx):
    arguments = await _arguments(ctx)
    avant = _empreinte()
    _raz()
    constats = []
    async with _client(ctx) as c:
        demande = await _demande(c, arguments)
        await _rejouer(c, arguments, _reponses(demande, False), demande.request_state)
        constats.append(("« non »", _compteur()))
        demande = await _demande(c, arguments)
        etat = demande.request_state
        milieu = len(etat) // 2
        await _rejouer(c, arguments, _reponses(demande, True), etat[:milieu] + ("A" if etat[milieu] != "A" else "B")
                       + etat[milieu + 1:])
        constats.append(("état altéré", _compteur()))
        demande = await _demande(c, arguments)
        await _rejouer(c, {**arguments, "escale_id": AUTRE_ESCALE}, _reponses(demande, True), demande.request_state)
        constats.append(("échange d'escale au rejeu", _compteur()))
    async with _client(ctx, "sans_elicitation") as c:
        await c.appeler_brut(OUTIL, arguments)
        constats.append(("repli", _compteur()))
    parties = [nom for nom, n in constats if n]
    if parties:
        raise Echec(f"une alerte est partie après : {', '.join(parties)}. Un refus ne publie rien.")
    ecrits = sorted(set(_empreinte().items()) - set(avant.items()))
    if ecrits:
        raise Echec(f"fichiers écrits ou modifiés pendant les refus : {', '.join(f for f, _ in ecrits)}. Demander "
                    "d'abord, écrire ensuite : un refus ne laisse rien derrière lui.")
    return "« non », état altéré, échange d'escale, repli : compteur à 0, aucun fichier écrit"
