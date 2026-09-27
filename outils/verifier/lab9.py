"""Vérificateur du LAB 9 — pharos-data v1 : outils métier, identité hors arguments, cloisonnement dans la base,
contournements refusés sans fuite, test automatisé.

Aucun appel au modèle. Le serveur est appelé sous les trois identités de salle ; la vérité vient du
générateur de la base (donnees.base.generer), et la preuve décisive, d'une connexion directe à la base.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import asyncpg
import httpx

from donnees.base import generer
from outils.client_test import ClientTest
from outils.lab9 import CONTOURNEMENTS
from outils.verifier.commun import Echec, Verification
from pharos import base, journal

URL = "http://observateur:8102/mcp"
RACINE = Path(__file__).resolve().parents[2]
JEUDI = {"date": "2026-10-08"}
NOMS = ("escales_a_risque", "conflits_de_creneau", "requete_sql")
PARAMETRES_D_IDENTITE = re.compile(r"^(agent|identite|role|utilisateur|appelant)", re.IGNORECASE)
INTERDITS = ("esc_hdr_legacy", "tarifs", "tarif_negocie", "armateur", "SQLSTATE", "ERROR:", "does not exist",
             "permission denied")
QUAI_3_JEUDI = ("SELECT count(*) AS n FROM escales WHERE quai = 3 "
                "AND debut < '2026-10-09 00:00+02' AND fin > '2026-10-08 00:00+02'")
SEUIL_S = 10.0

v = Verification("LAB 9 — pharos-data v1", URL, "make lab8-base, make lab9-politique puis make lab8-up")


def _donnees(ctx) -> generer.Donnees:
    if "donnees" not in ctx.cache:
        ctx.cache["donnees"] = generer.generer()
    return ctx.cache["donnees"]


def _escales_de(d: generer.Donnees, agent_id: str) -> set[str]:
    navires = {n.navire_id for n in d.navires if n.agent_id == agent_id}
    return {e.escale_id for e in d.escales if e.navire_id in navires}


def _texte(r) -> str:
    texte = "\n".join(getattr(b, "text", "") or "" for b in r.content)
    return texte or json.dumps(r.structured_content, ensure_ascii=False)


async def _appeler(ctx, jeton: str, outil: str, arguments: dict):
    async with ClientTest(ctx.url, jeton=jeton) as c:
        return await c.appeler(outil, arguments)


@v.critere("Les outils du brief sont au catalogue : escales_a_risque, conflits_de_creneau, requete_sql.")
async def _(ctx):
    async with ClientTest(ctx.url, jeton="jeton-exploitation") as c:
        noms = {o.name for o in await c.outils()}
    manquants = [n for n in NOMS if n not in noms]
    if manquants:
        raise Echec(f"introuvable(s) : {', '.join(manquants)} — garder les noms du brief (plan du LAB 13, jeu du LAB 15).")


def _escale(valeur, escale_id: str):
    """Le dict de la réponse qui décrit l'escale, où qu'il soit."""
    if isinstance(valeur, dict):
        if valeur.get("escale_id") == escale_id and len(valeur) > 1:
            return valeur
        valeurs = valeur.values()
    elif isinstance(valeur, list):
        valeurs = valeur
    else:
        return None
    for w in valeurs:
        trouve = _escale(w, escale_id)
        if trouve is not None:
            return trouve
    return None


@v.critere("escales_a_risque renvoie critères déclenchés, détail chiffré et definition_version.")
async def _(ctx):
    r = await _appeler(ctx, "jeton-exploitation", "escales_a_risque", JEUDI)
    if r.is_error:
        raise Echec(f"escales_a_risque(date=2026-10-08) a échoué : {_texte(r)[:300]}")
    donnees = r.structured_content or json.loads(_texte(r))
    if "definition_version" not in json.dumps(donnees):
        raise Echec("la réponse ne porte pas definition_version (serveurs/pharos_data/definition.py).")
    vent = _escale(donnees, "ESC-2026-0412")
    if vent is None:
        raise Echec("ESC-2026-0412 (Vent d'Autan, jeudi, quai 3) n'est pas dans la réponse : à 12,9 m au quai 3 "
                    "(13,5 m, marge 1,0 m) et en conflit avec ESC-2026-0413, elle est à risque.")
    texte = json.dumps(vent, ensure_ascii=False)
    manques = [c for c in ("tirant_eau", "conflit_creneau") if c not in texte]
    if manques:
        raise Echec(f"ESC-2026-0412 : critère(s) {', '.join(manques)} absent(s) — les critères déclenchés, par leur nom.")
    if "12.9" not in texte or "13.5" not in texte:
        raise Echec("ESC-2026-0412 : le détail chiffré du tirant d'eau manque (12,9 m, quai 13,5 m, marge) — "
                    "l'exploitant doit pouvoir contester.")


@v.critere("conflits_de_creneau répond, avec la durée du chevauchement.")
async def _(ctx):
    r = await _appeler(ctx, "jeton-exploitation", "conflits_de_creneau", JEUDI)
    texte = _texte(r)
    if r.is_error:
        raise Echec(f"conflits_de_creneau(date=2026-10-08) a échoué : {texte[:300]}")
    manques = [f"{a} / {b} ({m} min)" for a, b, m in _donnees(ctx).conflits_jeudi
               if a not in texte or b not in texte or not re.search(rf"\b{m}\b", texte)]
    if manques:
        raise Echec("paire(s) manquante(s) ou sans durée en minutes : " + " ; ".join(manques))


@v.critere("Aucun outil ne prend l'identité en paramètre ; sans jeton, le serveur refuse.")
async def _(ctx):
    async with ClientTest(ctx.url, jeton="jeton-exploitation") as c:
        outils = await c.outils()
    fautifs = [f"{o.name}({p})" for o in outils for p in (o.input_schema or {}).get("properties", {})
               if PARAMETRES_D_IDENTITE.match(p)]
    if fautifs:
        raise Echec(f"paramètre(s) d'identité : {', '.join(fautifs)} — l'identité vient du jeton (autorisation.identite()).")
    async with httpx.AsyncClient(timeout=10) as http:
        reponse = await http.post(ctx.url, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                  headers={"Accept": "application/json, text/event-stream"})
    if reponse.status_code != 401:
        raise Echec(f"une requête sans jeton reçoit HTTP {reponse.status_code}, 401 attendu : brancher "
                    "auth=autorisation.verificateur() sur FastMCP(...).")


@v.critere("L'agent Iroise ne voit aucune escale de Rance, y compris sur une question formulée pour cela.")
async def _(ctx):
    d = _donnees(ctx)
    rance = _escales_de(d, "AG-RANCE")
    textes = []
    for outil, arguments in (("escales_a_risque", JEUDI), ("conflits_de_creneau", JEUDI),
                             ("requete_mouvements", {"date_debut": "2026-10-05", "date_fin": "2026-10-09"}),
                             ("requete_sql", {"sql": "SELECT escale_id FROM escales"})):
        r = await _appeler(ctx, "jeton-iroise", outil, arguments)
        textes.append((outil, _texte(r)))
    fuites = sorted({(o, e) for o, t in textes for e in re.findall(r"ESC-\d{4}-\d{4}", t) if e in rance})
    if fuites:
        raise Echec("vu par Iroise : " + ", ".join(f"{e} ({o})" for o, e in fuites[:6]))
    comptes = {}
    for jeton in ("jeton-rance", "jeton-iroise", "jeton-exploitation"):
        r = await _appeler(ctx, jeton, "requete_sql", {"sql": QUAI_3_JEUDI})
        nombres = re.findall(r'"n":\s*(\d+)', _texte(r))
        comptes[jeton] = int(nombres[0]) if nombres else None
    attendu = {"jeton-rance": 1, "jeton-iroise": 1, "jeton-exploitation": 2}
    if comptes != attendu:
        raise Echec(f"escales au quai 3 jeudi, toutes compagnies confondues : {comptes}, attendu {attendu} "
                    "— chacun son seul périmètre, l'exploitation le total.")


async def _compter_mouvements() -> int:
    connexion = await asyncpg.connect(base.dsn(base.ADMIN))
    try:
        return await connexion.fetchval("SELECT count(*) FROM mouvements")
    finally:
        await connexion.close()


def _partie_commune(messages: list[str]) -> int:
    prefixe = os.path.commonprefix(messages)
    suffixe = os.path.commonprefix([m[::-1] for m in messages])
    return max(len(prefixe), len(suffixe))


@v.critere("Les trois contournements échouent, avec un message interprétable qui ne révèle rien du schéma.")
async def _(ctx):
    avant = await _compter_mouvements()
    messages, passes, fuites = [], [], []
    for n, requetes in CONTOURNEMENTS.items():
        for sql in requetes:
            r = await _appeler(ctx, "jeton-rance", "requete_sql", {"sql": sql})
            texte = _texte(r)
            if not r.is_error:
                passes.append(f"n° {n} : {sql}")
            messages.append(texte)
            fuites += [f"n° {n} : « {mot} »" for mot in INTERDITS if mot in texte]
    problemes = []
    if passes:
        problemes.append("passé(s) : " + " ; ".join(passes))
    if await _compter_mouvements() != avant:
        problemes.append("la table mouvements a changé : l'écriture déguisée est passée (rôle en lecture seule ?).")
    if fuites:
        problemes.append("le message révèle le schéma : " + ", ".join(sorted(set(fuites))))
    if _partie_commune(messages) < 20:
        problemes.append("les refus n'ont pas la même forme : une même phrase, par exemple la liste blanche, "
                         "sans rien de ce qui existe vraiment.")
    refus = [l for l in journal.lire("pharos-data") if l.get("outil") == "requete_sql" and l.get("issue") == "refus"]
    if len(refus) < len(messages) and not problemes:
        problemes.append("les refus ne sont pas tous dans logs/pharos-data.jsonl : lever ToolError (le journal "
                         "est branché par le squelette), et consigner l'erreur brute par journal.consigner_erreur.")
    if problemes:
        raise Echec("\n".join(problemes))
    return f"« {messages[0][:120]}… »"


@v.critere("Le test de cloisonnement tourne dans la suite, sans modèle, en moins de dix secondes.")
def _(ctx):
    if not (RACINE / "tests" / "pharos_data").is_dir():
        raise Echec("tests/pharos_data absent : lancer « make depart LAB=9 », puis écrire le test (étape 5).")
    env = {**os.environ, "OPENROUTER_API_KEY": "", "PYTHONPATH": f"{RACINE / 'src'}:{RACINE}:{RACINE / 'client'}"}
    debut = time.monotonic()
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/pharos_data", "-k", "cloisonnement", "-q",
                        "-p", "no:cacheprovider"], cwd=RACINE, env=env, capture_output=True, text=True, timeout=120)
    duree = time.monotonic() - debut
    fin = "\n".join((r.stdout.strip() or r.stderr.strip()).splitlines()[-6:])
    if r.returncode != 0 or " passed" not in r.stdout:
        raise Echec(f"pytest tests/pharos_data -k cloisonnement : aucun test passé, ou un échec.\n{fin}")
    if duree > SEUIL_S:
        raise Echec(f"{duree:.1f} s : au-delà de {SEUIL_S:.0f} s, le test passe par quelque chose qu'il ne devrait pas.")
    return f"{r.stdout.strip().splitlines()[-1]} ({duree:.1f} s)"


@v.critere("Critère décisif — la protection vit dans la base : sans aucun filtre d'outil, l'agent ne voit que ses escales.")
async def _(ctx):
    iroise = _escales_de(_donnees(ctx), "AG-IROISE")
    connexion = await asyncpg.connect(base.dsn("pharos_app"))
    try:
        async with connexion.transaction():
            await connexion.execute("SELECT set_config('pharos.agent', 'AG-IROISE', true)")
            await connexion.execute("SET LOCAL ROLE pharos_agent")
            vues = {l["escale_id"] for l in await connexion.fetch("SELECT escale_id FROM escales")}
    finally:
        await connexion.close()
    if not vues:
        raise Echec("sous le rôle pharos_agent (pharos.agent = AG-IROISE), la base ne rend aucune escale : écrire la "
                    "politique de l'agent dans labs/lab9/politique.sql, puis « make lab9-politique ».")
    if vues != iroise:
        raise Echec(f"sous le rôle pharos_agent (pharos.agent = AG-IROISE), la base rend {len(vues)} escales, dont "
                    f"{len(vues - iroise)} hors de son périmètre : la protection n'est pas dans la base.")
    return f"{len(vues)} escales, toutes d'Iroise, sans qu'aucun outil n'ait filtré."
