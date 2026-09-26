"""Adaptateur OpenRouter commun : un appel au modèle, avec outils — jamais une boucle.

Utilisé par make doctor, le banc du premier appel et pharos_client.modele (LAB 4).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import httpx
import tiktoken

URL = "https://openrouter.ai/api/v1/chat/completions"
MODELE_DEFAUT = "google/gemini-3.6-flash"
MESSAGES_HTTP = {
    400: "requête refusée pour le modèle {modele} : vérifier qu'il accepte les outils.",
    401: "clé invalide ou révoquée : demander une nouvelle clé au formateur.",
    402: "crédit épuisé sur cette clé : prévenir le formateur.",
    404: "modèle introuvable : vérifier PHAROS_MODELE ({modele}).",
    429: "trop de requêtes vers OpenRouter : patienter une minute, puis relancer.",
}
_ENCODAGE = tiktoken.get_encoding("o200k_base")


class ErreurModele(RuntimeError):
    """Appel au modèle impossible ; le message dit quoi faire."""


@dataclass(frozen=True)
class Appel:
    id: str
    nom: str
    arguments: dict


@dataclass(frozen=True)
class Reponse:
    message: dict          # message assistant tel que renvoyé : à réinjecter tel quel
    appels: list[Appel]
    usage: dict


def outils_openai(tools) -> list[dict]:
    """tools/list MCP (objets fastmcp ou dicts) → format « function calling »."""
    resultat = []
    for o in tools:
        if isinstance(o, dict):
            nom, description, schema = o["name"], o.get("description") or "", o.get("inputSchema")
        else:
            nom, description, schema = o.name, o.description or "", o.input_schema
        resultat.append({"type": "function", "function": {
            "name": nom, "description": description,
            "parameters": schema or {"type": "object", "properties": {}}}})
    return resultat


def estimer_tokens(messages: list[dict], outils=()) -> int:
    """Estimation (o200k_base) de ce que coûtera l'envoi : à comparer au budget AVANT d'appeler."""
    return len(_ENCODAGE.encode(json.dumps([messages, list(outils)], ensure_ascii=False)))


def _arguments(brut) -> dict:
    if isinstance(brut, dict):
        return brut
    try:
        valeur = json.loads(brut or "{}")
    except json.JSONDecodeError:
        return {"_brut": brut}
    return valeur if isinstance(valeur, dict) else {"_brut": valeur}


def completer(messages: list[dict], outils: list[dict], modele: str | None = None, *,
              client: httpx.Client | None = None, **options) -> Reponse:
    """Un appel au modèle. options : paramètres OpenRouter supplémentaires (max_tokens, tool_choice…)."""
    if "parallel_tool_calls" in options:
        raise ValueError("parallel_tool_calls n'est jamais envoyé à OpenRouter.")
    cle = os.environ.get("OPENROUTER_API_KEY")
    if not cle:
        raise ErreurModele("clé OpenRouter absente : renseigner OPENROUTER_API_KEY dans .env (remise par le formateur).")
    modele = modele or os.environ.get("PHAROS_MODELE") or MODELE_DEFAUT
    corps = {"model": modele, "messages": messages, **options}
    if outils:
        corps["tools"] = list(outils)
        corps.setdefault("tool_choice", "auto")
    proprietaire = client is None
    http = client or httpx.Client(timeout=90)
    try:
        r = http.post(URL, json=corps, headers={"Authorization": f"Bearer {cle}"})
    except httpx.HTTPError as exc:
        raise ErreurModele(f"OpenRouter injoignable ({exc.__class__.__name__}) : vérifier l'accès Internet ou le proxy.") from exc
    finally:
        if proprietaire:
            http.close()
    if r.status_code != 200:
        gabarit = MESSAGES_HTTP.get(r.status_code, "réponse HTTP {code} d'OpenRouter : réessayer, puis prévenir le formateur.")
        raise ErreurModele(gabarit.format(modele=modele, code=r.status_code))
    donnees = r.json()
    message = ((donnees.get("choices") or [{}])[0].get("message")) or {}
    appels = [Appel(a.get("id", ""), a["function"]["name"], _arguments(a["function"].get("arguments")))
              for a in message.get("tool_calls") or []]
    return Reponse(message=message, appels=appels, usage=donnees.get("usage") or {})
