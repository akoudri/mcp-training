"""make doctor — trois vérifications, trois lignes. Voir le LAB 0."""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass

import httpx

from pharos.openrouter import MESSAGES_HTTP, URL as OPENROUTER
URLS_SOCLE = {"observateur": "http://observateur:8081/"}
URL_SERVEUR = "http://observateur:8100/mcp"
OUTILS_ATTENDUS = {"lister_documents", "lire_document", "rechercher_clause"}


@dataclass(frozen=True)
class Verification:
    nom: str
    ok: bool
    detail: str


def verifier_socle(client: httpx.Client, urls: dict[str, str]) -> Verification:
    absents = []
    for service, url in urls.items():
        try:
            if client.get(url, timeout=5).status_code >= 500:
                absents.append(service)
        except httpx.HTTPError:
            absents.append(service)
    if absents:
        return Verification("socle", False, f"injoignable : {', '.join(absents)}. Lancer `make up`, puis `make logs S={absents[0]}`.")
    return Verification("socle", True, "observateur joignable")


def verifier_modele(client: httpx.Client, cle: str | None, modele: str) -> Verification:
    if not cle:
        return Verification("modèle", False, "clé OpenRouter absente : renseigner OPENROUTER_API_KEY dans .env (remise par le formateur).")
    corps = {
        "model": modele,
        "messages": [{"role": "user", "content": "Quelle heure est-il ? Utilise l'outil."}],
        "tools": [{"type": "function", "function": {
            "name": "donner_l_heure", "description": "Donne l'heure courante.",
            "parameters": {"type": "object", "properties": {}}}}],
        "tool_choice": "required",
        # Marge pour les modèles qui raisonnent avant d'appeler l'outil (Gemini 3.x : ~50 à 100 tokens).
        "max_tokens": 1000,
    }
    try:
        r = client.post(OPENROUTER, json=corps, headers={"Authorization": f"Bearer {cle}"}, timeout=30)
    except httpx.HTTPError as exc:
        return Verification("modèle", False, f"OpenRouter injoignable ({exc.__class__.__name__}) : vérifier l'accès Internet ou le proxy.")
    messages = {code: gabarit.format(modele=modele) for code, gabarit in MESSAGES_HTTP.items()}
    if r.status_code != 200:
        return Verification("modèle", False, messages.get(r.status_code, f"réponse HTTP {r.status_code} d'OpenRouter."))
    choix = (r.json().get("choices") or [{}])[0]
    appels = choix.get("message", {}).get("tool_calls")
    if not appels and choix.get("finish_reason") == "length":
        return Verification("modèle", False, f"réponse de {modele} tronquée avant l'appel d'outil (max_tokens atteint) : prévenir le formateur.")
    if not appels:
        return Verification("modèle", False, f"le modèle {modele} n'a pas appelé l'outil : choisir un modèle qui gère les outils.")
    return Verification("modèle", True, f"{modele} répond et appelle un outil")


async def verifier_serveur(url: str = URL_SERVEUR) -> Verification:
    from fastmcp import Client
    try:
        async with asyncio.timeout(10):
            async with Client(url) as c:
                noms = {o.name for o in await c.list_tools()}
    except Exception as exc:  # toute panne ici est un diagnostic, pas un plantage
        return Verification("serveur", False, f"pharos-docs-demo injoignable via l'observateur ({exc.__class__.__name__}) : `make lab0-up`, puis `make logs S=pharos-docs-demo`.")
    manquants = OUTILS_ATTENDUS - noms
    if manquants:
        return Verification("serveur", False, f"outils manquants : {', '.join(sorted(manquants))}.")
    return Verification("serveur", True, f"pharos-docs-demo expose {len(noms)} outils via l'observateur")


def main(argv: list[str]) -> int:
    resultats = []
    with httpx.Client() as client:
        resultats.append(verifier_socle(client, URLS_SOCLE))
        if "--sans-modele" not in argv:
            resultats.append(verifier_modele(client, os.environ.get("OPENROUTER_API_KEY"),
                                             os.environ.get("PHAROS_MODELE", "google/gemini-3.6-flash")))
    resultats.append(asyncio.run(verifier_serveur()))
    for v in resultats:
        print(f"  {v.nom:<9} {'OK' if v.ok else 'ÉCHEC':<6} {v.detail}")
    return 0 if all(v.ok for v in resultats) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
