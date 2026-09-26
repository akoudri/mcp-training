"""Vérificateur du LAB 7 — pharos-docs v1 : ressources, prompt serveur, empreinte, suite rapide."""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from outils.client_test import ClientTest
from outils.verifier.commun import Echec, Verification
from pharos_docs import extraction

URL = "http://observateur:8101/mcp"
RACINE = Path(__file__).resolve().parents[2]
MOTIF_URI = re.compile(r"^pharos://escales/(ESC-\d{4}-\d{4})/documents/([A-Za-z0-9-]+)$")
SEUIL_S = 10.0
FAMILLES = ["schémas (énumération refusée avant le code métier)", "erreurs métier (les trois du LAB 1)",
            "formes et bornes (extrait borné)", "handles (expiré, altéré, hors portée)",
            "ressources (taille, type, lecture)", "empreinte du catalogue"]
IGNORES_COPIE = (".git", ".venv", "solutions", "__pycache__", ".pytest_cache", "logs", "sortie",
                 ".superpowers", ".env")

v = Verification("LAB 7 — pharos-docs v1", URL, "make lab1-up")


def _pytest(racine: Path, documents: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "OPENROUTER_API_KEY": "", "PHAROS_DOCUMENTS": str(documents),
           "PYTHONPATH": f"{racine / 'src'}:{racine}:{racine / 'client'}"}
    return subprocess.run([sys.executable, "-m", "pytest", "tests/pharos_docs", "-q", "-p", "no:cacheprovider"],
                          cwd=racine, env=env, capture_output=True, text=True, timeout=180)


def _fin(sortie: str, n: int = 12) -> str:
    return "\n".join(sortie.strip().splitlines()[-n:])


async def _ressources(ctx) -> list:
    if "ressources" not in ctx.cache:
        async with ClientTest(ctx.url) as c:
            ctx.cache["ressources"] = [r for r in await c.ressources() if MOTIF_URI.match(str(r.uri))]
    return ctx.cache["ressources"]


@v.critere("Les documents sont exposés en ressources ; lister_documents a disparu du catalogue.")
async def _(ctx):
    async with ClientTest(ctx.url) as c:
        outils = {o.name for o in await c.outils()}
    documents = await _ressources(ctx)
    attendus = len(extraction.documents())
    problemes = []
    if len(documents) != attendus:
        problemes.append(f"{len(documents)} ressources pharos://escales/{{escale_id}}/documents/{{document_id}}, "
                         f"{attendus} documents attendus.")
    if "lister_documents" in outils:
        problemes.append("lister_documents est encore au catalogue : les documents sont désormais des ressources.")
    if problemes:
        raise Echec("\n".join(problemes))


@v.critere("La taille et le mimeType annoncés sont justes.")
async def _(ctx):
    problemes = []
    async with ClientTest(ctx.url) as c:
        for r in await _ressources(ctx):
            contenus = await c.lire(str(r.uri))
            texte = "".join(getattr(x, "text", "") or "" for x in contenus)
            octets = len(texte.encode("utf-8")) if texte else \
                sum(len(base64.b64decode(x.blob)) for x in contenus if getattr(x, "blob", None))
            types = {getattr(x, "mime_type", None) for x in contenus}
            if r.size is None:
                problemes.append(f"{r.uri} : aucune taille annoncée (size)")
            elif r.size != octets:
                problemes.append(f"{r.uri} : taille annoncée {r.size}, contenu réel {octets} octets")
            if r.mime_type is None or types != {r.mime_type}:
                problemes.append(f"{r.uri} : mimeType annoncé {r.mime_type}, contenu {sorted(map(str, types))}")
    if problemes:
        reste = len(problemes) - 8
        raise Echec("\n".join(problemes[:8]) + (f"\n… et {reste} autres" if reste > 0 else ""))


@v.constat("Le coût du catalogue est mesuré avant et après.")
def _(ctx):
    return ("make tokens-catalogue SERVEUR=http://observateur:8101/mcp, sur etat/sr1-fin puis sur votre version ; "
            "consigner dans labs/lab7/mesures.md.")


@v.critere("Le prompt note_alerte_escale est exposé, et joint la ressource du contrat plutôt que d'en recopier le texte.")
async def _(ctx):
    async with ClientTest(ctx.url) as c:
        prompts = {p.name: p for p in await c.prompts()}
        prompt = prompts.get("note_alerte_escale")
        if prompt is None:
            raise Echec("prompt note_alerte_escale absent de prompts/list.")
        arguments = {a.name: bool(a.required) for a in prompt.arguments or []}
        if arguments != {"escale_id": True, "niveau": False}:
            raise Echec(f"arguments attendus : escale_id (requis), niveau (facultatif) — trouvés : {arguments}")
        rendu = await c.prompt("note_alerte_escale", {"escale_id": "ESC-2026-0412"})
    jointes = [m.content for m in rendu.messages if getattr(m.content, "type", "") == "resource"]
    if not any(str(j.resource.uri).endswith("/documents/CM-0412") for j in jointes):
        raise Echec("prompts/get doit joindre la ressource du contrat : EmbeddedResource de "
                    "pharos://escales/ESC-2026-0412/documents/CM-0412.")


@v.constat("Le prompt serveur est proposé à l'utilisateur par un client réel, et déclenchable par lui.")
def _(ctx):
    return ("Dans VS Code (mode PHAROS), taper « / » dans le chat : /mcp.pharos-docs.note_alerte_escale doit apparaître ; "
            "le lancer sur ESC-2026-0412. Ce n'est pas un outil que le modèle appelle.")


@v.constat("La suite couvre les six familles applicables.")
def _(ctx):
    return "Relire tests/pharos_docs/ : " + " ; ".join(FAMILLES) + "."


@v.critere("L'empreinte de catalogue est en place — et échoue si l'on renomme un outil.")
def _(ctx):
    fichier = RACINE / "tests" / "empreinte_catalogue.json"
    if not fichier.exists():
        raise Echec("tests/empreinte_catalogue.json absent : make lab7-empreinte, puis un test qui le compare.")
    catalogue = json.loads(fichier.read_text(encoding="utf-8"))
    if not catalogue:
        raise Echec("tests/empreinte_catalogue.json est vide.")
    nom = catalogue[0]["name"]
    with tempfile.TemporaryDirectory(prefix="pharos-empreinte-") as tmp:
        copie = Path(tmp) / "depot"
        shutil.copytree(RACINE, copie, ignore=shutil.ignore_patterns(*IGNORES_COPIE))
        documents = copie / "donnees" / "documents"
        intact = _pytest(copie, documents)
        if intact.returncode != 0:
            raise Echec("la suite n'est pas verte sur une copie intacte : impossible de vérifier l'empreinte. "
                        "Corriger d'abord la suite (voir le critère décisif).")
        fichier_copie = copie / "tests" / "empreinte_catalogue.json"
        catalogue_copie = json.loads(fichier_copie.read_text(encoding="utf-8"))
        catalogue_copie[0]["name"] += "_renomme"   # simule un outil renommé, sans toucher au code source
        fichier_copie.write_text(json.dumps(catalogue_copie, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        resultat = _pytest(copie, documents)
    if resultat.returncode == 0:
        raise Echec("la suite reste verte quand le catalogue ne correspond plus à l'empreinte : le test "
                    "d'empreinte ne compare pas le catalogue.")
    return f"renommer {nom} dans l'empreinte fait échouer la suite, comme attendu"


@v.critere("Critère décisif — la suite est verte et tourne en moins de dix secondes, sans appeler aucun modèle.")
def _(ctx):
    if not (RACINE / "tests" / "pharos_docs").is_dir():
        raise Echec("tests/pharos_docs absent : lancer « make depart LAB=7 ».")
    debut = time.perf_counter()
    resultat = _pytest(RACINE, RACINE / "donnees" / "documents")
    duree = time.perf_counter() - debut
    if resultat.returncode != 0:
        raise Echec("suite rouge :\n" + _fin(resultat.stdout + resultat.stderr))
    if duree >= SEUIL_S:
        raise Echec(f"{duree:.1f} s : chercher une fixture qui se régénère, un sleep, ou un test passé par HTTP.")
    return f"suite verte en {duree:.1f} s ({_fin(resultat.stdout, 1)})"
