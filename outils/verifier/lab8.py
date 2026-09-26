"""Vérificateur du LAB 8 — pharos-data v0 : pool, schéma en ressource, réponse exacte, plafond, requête lisible.

Aucun appel au modèle : le serveur est appelé directement, la vérité est calculée contre la base, et la
lisibilité dans la trace est vérifiée par la boucle du binôme avec un modèle simulé.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import re
from datetime import date
from pathlib import Path

import asyncpg

from outils import verite_lab8
from outils.client_test import ClientTest
from outils.verifier.commun import Echec, Verification
from outils.verifier.modele_simule import ModeleSimule, appel
from pharos import base

URL = "http://observateur:8102/mcp"
RACINE = Path(__file__).resolve().parents[2]
MESURES = RACINE / "labs" / "lab8" / "mesures.md"
OUTIL = "requete_mouvements"
REFERENCE = {"date_debut": "2026-09-28", "date_fin": "2026-10-04", "quai": 3, "type_conteneur": "refrigere"}
SEPTEMBRE = {"date_debut": "2026-09-01", "date_fin": "2026-09-30"}
PLAFOND = 200

v = Verification("LAB 8 — pharos-data v0", URL, "make lab8-base puis make lab8-up")


def _texte(resultat) -> str:
    texte = "\n".join(getattr(b, "text", "") or "" for b in resultat.content)
    if not texte and resultat.structured_content is not None:
        texte = json.dumps(resultat.structured_content, ensure_ascii=False)
    return texte


def _nombres(valeur) -> set[int]:
    """Les entiers qu'une réponse peut porter comme « le compte » : champs entiers, longueurs de listes."""
    if isinstance(valeur, bool):
        return set()
    if isinstance(valeur, int):
        return {valeur}
    if isinstance(valeur, list):
        return {len(valeur)}
    if isinstance(valeur, dict):
        return set().union(*(_nombres(w) for w in valeur.values())) if valeur else set()
    return set()


async def _appeler(ctx, arguments: dict):
    async with ClientTest(ctx.url) as c:
        return await c.appeler(OUTIL, arguments)


async def _verite(ctx) -> verite_lab8.Verite:
    if "verite" not in ctx.cache:
        try:
            ctx.cache["verite"] = await verite_lab8.verite()
        except (OSError, asyncpg.PostgresError) as exc:
            raise Echec(f"base injoignable ({exc.__class__.__name__}) : lancer « make lab8-base ».") from exc
    return ctx.cache["verite"]


async def _reference(ctx):
    if "reference" not in ctx.cache:
        ctx.cache["reference"] = await _appeler(ctx, REFERENCE)
    return ctx.cache["reference"]


@v.critere("requete_mouvements est au catalogue, sous le nom du brief.")
async def _(ctx):
    async with ClientTest(ctx.url) as c:
        noms = {o.name for o in await c.outils()}
    if OUTIL not in noms:
        raise Echec(f"{OUTIL} introuvable (catalogue : {', '.join(sorted(noms)) or 'vide'}) : garder le nom du brief, "
                    "le plan du LAB 13 et le jeu d'évaluation du LAB 15 l'appellent ainsi.")


async def _pids() -> set[int]:
    connexion = await asyncpg.connect(base.dsn(base.ADMIN))
    try:
        lignes = await connexion.fetch("SELECT pid FROM pg_stat_activity WHERE application_name = 'pharos-data'")
    finally:
        await connexion.close()
    return {l["pid"] for l in lignes}


@v.critere("Le pool est créé au démarrage du processus, jamais par appel.")
async def _(ctx):
    releves = []
    for _ in range(10):
        await _appeler(ctx, REFERENCE)
        releves.append(await _pids())
    if not releves[0]:
        raise Echec("aucune connexion « pharos-data » ouverte entre deux appels : créer le pool dans cycle_de_vie, "
                    "avec PARAMETRES_POOL (application_name = pharos-data), et l'emprunter à chaque appel.")
    if any(r != releves[0] for r in releves):
        raise Echec("les connexions changent d'un appel à l'autre : le pool est recréé à chaque appel. "
                    "Le créer une seule fois, dans cycle_de_vie.")


@v.critere("Le schéma est exposé en ressource pharos://schema/…, avec unités et fuseau horaire.")
async def _(ctx):
    async with ClientTest(ctx.url) as c:
        ressources = [r for r in await c.ressources() if str(r.uri).startswith("pharos://schema/")]
        if not ressources:
            raise Echec("aucune ressource pharos://schema/… : exposer le dictionnaire de colonnes en ressource (bloc 13.3).")
        morceaux = []
        for r in ressources:
            morceaux += [getattr(x, "text", "") or "" for x in await c.lire(str(r.uri))]
    texte = "\n".join(morceaux)
    manques = []
    if "Europe/Paris" not in texte:
        manques.append("le fuseau horaire (Europe/Paris) des colonnes debut, fin et horodatage")
    if not re.search(r"\bm(è|e)tres?\b|\(m\)|\ben m\b", texte):
        manques.append("les unités (mètres pour longueur et tirant d'eau)")
    if manques:
        raise Echec("le dictionnaire ne dit pas " + " ni ".join(manques) + ".")
    return f"{len(ressources)} ressource(s) : {', '.join(str(r.uri) for r in ressources)}"


@v.critere("esc_hdr_legacy n'apparaît nulle part dans ce qui est exposé.")
async def _(ctx):
    async with ClientTest(ctx.url) as c:
        morceaux = [o.model_dump_json() for o in await c.outils()]
        ressources = await c.ressources()
        morceaux += [r.model_dump_json() for r in ressources]
        morceaux += [t.model_dump_json() for t in await c._client.list_resource_templates()]
        morceaux += [p.model_dump_json() for p in await c.prompts()]
        for r in ressources:
            morceaux += [getattr(x, "text", "") or "" for x in await c.lire(str(r.uri))]
    if any("esc_hdr_legacy" in m for m in morceaux):
        raise Echec("esc_hdr_legacy est cité dans le catalogue ou dans une ressource : ne pas l'exposer, et dire "
                    "dans le dictionnaire qu'il n'existe pas d'autre source de mouvements.")


@v.critere("La réponse à la question de référence est exacte (make lab8-verite).")
async def _(ctx):
    verite = await _verite(ctx)
    r = await _reference(ctx)
    texte = _texte(r)
    if r.is_error:
        raise Echec(f"requete_mouvements({', '.join(f'{k}={w}' for k, w in REFERENCE.items())}) a échoué : {texte[:300]}")
    try:
        nombres = _nombres(json.loads(texte))
    except ValueError:
        nombres = {int(n) for n in re.findall(r"\b\d+\b", texte)}
    if verite.nombre not in nombres:
        piege = " — c'est le compte avec des bornes en UTC : passer les dates en heure de Paris" \
            if verite.nombre_utc in nombres else ""
        raise Echec(f"sur la semaine de référence (dates de fin incluses), le résultat ne porte pas le compte "
                    f"exact {verite.nombre}{piege}.")
    if not MESURES.exists():
        raise Echec("labs/lab8/mesures.md absent : lancer « make depart LAB=8 », puis le remplir.")
    ligne = next((l for l in MESURES.read_text(encoding="utf-8").splitlines() if l.startswith("| Réponse obtenue")), "")
    consigne = re.findall(r"\d+", ligne)
    if not consigne:
        raise Echec("labs/lab8/mesures.md : consigner la réponse obtenue par la boucle (ligne « Réponse obtenue »).")
    if int(consigne[0]) != verite.nombre:
        raise Echec(f"labs/lab8/mesures.md : la réponse consignée ({consigne[0]}) n'est pas la vérité ({verite.nombre}). "
                    "Regarder la requête dans la trace avant de toucher au code, puis reposer la question.")
    return f"{verite.nombre} conteneurs réfrigérés, quai 3, semaine du 28 septembre (en UTC : {verite.nombre_utc})"


@v.critere("Au-delà du plafond, le refus porte le compte réel et le plafond.")
async def _(ctx):
    reel = await verite_lab8.compter_mouvements(date(2026, 9, 1), date(2026, 10, 1))
    r = await _appeler(ctx, SEPTEMBRE)
    texte = _texte(r)
    if not r.is_error:
        raise Echec(f"tous les mouvements de septembre ({reel}) sont rendus sans refus : compter d'abord, "
                    f"et refuser au-delà de {PLAFOND} lignes (bloc 13.4).")
    chiffres = {int(n.replace(" ", "").replace(" ", "").replace("\xa0", ""))
                for n in re.findall(r"\d[\d  \xa0]*\d|\d", texte)}
    manques = [m for m, n in (("le compte réel", reel), ("le plafond", PLAFOND)) if n not in chiffres]
    if manques:
        raise Echec(f"le refus ne porte pas {' ni '.join(manques)} ({reel} lignes, plafond {PLAFOND}) : « {texte[:200]} »")
    return f"« {texte[:160]} »"


@v.constat("Le refus propose deux façons d'affiner (un quai, une période plus courte, un agrégat…).")
def _(ctx):
    return "Relire le refus ci-dessus : deux façons concrètes, que le modèle peut appliquer au tour suivant."


def _boucle():
    try:
        return importlib.import_module("pharos_client.boucle")
    except ModuleNotFoundError as exc:
        raise Echec("pharos_client introuvable : ce lab part de etat/tq1-fin (make depart LAB=8).") from exc


@v.critere("Critère décisif — la requête réellement exécutée est lisible dans la trace, sans ouvrir la base.")
async def _(ctx):
    texte = _texte(await _reference(ctx))
    if "select" not in texte.casefold() or "mouvements" not in texte.casefold():
        raise Echec("le résultat de requete_mouvements ne montre pas le SQL exécuté : le rendre, avec ses paramètres.")
    if "refrigere" not in texte or "2026-09-28" not in texte:
        raise Echec("le résultat montre le SQL mais pas ses paramètres (type, dates) : les rendre aussi.")
    boucle = _boucle()
    try:
        with ModeleSimule([[appel("a1", OUTIL, REFERENCE)], "Réponse simulée."]):
            _, trace = await asyncio.to_thread(boucle.executer, "Question simulée du LAB 8.", url=ctx.url)
    except NotImplementedError as exc:
        raise Echec("la boucle du LAB 4 n'est pas écrite : ce lab part de etat/tq1-fin (make depart LAB=8).") from exc
    resultat = getattr(trace[0], "resultat", None) if trace else None
    if resultat is None:
        raise Echec("la trace de la boucle n'a pas de champ resultat : repartir de etat/tq1-fin (make depart LAB=8).")
    if "select" not in resultat.casefold():
        raise Echec("la trace de la boucle ne porte pas le SQL : il doit figurer dans le résultat de l'outil.")
