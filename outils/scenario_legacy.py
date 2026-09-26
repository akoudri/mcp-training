"""Le scénario de pharos-legacy, joué par un client de test d'une révision donnée (LAB 2, 3).

etat_escale, puis lister_mouvements et page_suivante jusqu'à la dernière page : sans argument en
2025-11-25 (le curseur vit dans la session), avec le handle rendu en 2026-07-28. S'arrête à la
première erreur et la consigne. Utilisé par make lab3-clients et par les vérificateurs.
Usage : python -m outils.scenario_legacy [--rev REV] URL
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field

import httpx

from outils.client_test import REVISIONS, ClientTest, Echange

ESCALE = "ESC-2026-0412"
PAGES_MAX = 10          # garde-fou : un serveur qui rendrait toujours une page suivante


@dataclass
class Deroule:
    revision: str
    etat: dict | None = None
    pages: list[dict] = field(default_factory=list)
    erreur: str | None = None
    echanges: list[Echange] = field(default_factory=list)

    @property
    def mouvements(self) -> list[dict]:
        return [m for p in self.pages for m in p.get("mouvements", [])]

    def appels(self) -> list[Echange]:
        return [e for e in self.echanges if e.methode_mcp == "tools/call"]


class Arret(Exception):
    """Le scénario ne peut pas continuer ; le message dit pourquoi."""


def donnees(r) -> dict:
    """La donnée d'un résultat d'outil : structuredContent, à défaut le JSON du contenu textuel."""
    if isinstance(r.structured_content, dict):
        return r.structured_content
    texte = "\n".join(getattr(b, "text", "") or "" for b in r.content)
    try:
        valeur = json.loads(texte)
    except ValueError:
        raise Arret(f"résultat illisible (ni structuredContent, ni JSON) : « {texte[:160]} »") from None
    if not isinstance(valeur, dict):
        raise Arret(f"résultat inattendu : « {texte[:160]} »")
    return valeur


async def _appel(c: ClientTest, outil: str, arguments: dict) -> dict:
    try:
        r = await c.appeler(outil, arguments)
    except Exception as exc:  # erreur JSON-RPC, refus HTTP, serveur injoignable : on consigne
        raise Arret(f"{outil} : erreur protocolaire — {exc}") from None
    if r.is_error:
        texte = " ".join(getattr(b, "text", "") or "" for b in r.content)
        raise Arret(f"{outil} : erreur métier — {texte[:200]}")
    return donnees(r)


async def derouler(url: str, revision: str, escale: str = ESCALE, nom: str = "pharos-test") -> Deroule:
    d = Deroule(revision)
    c = ClientTest(url, revision, nom)
    try:
        async with c:
            d.etat = await _appel(c, "etat_escale", {"escale_id": escale})
            page = await _appel(c, "lister_mouvements", {"escale_id": escale})
            d.pages.append(page)
            while page.get("page", 0) < page.get("pages", 0) and len(d.pages) < PAGES_MAX:
                if revision == "2026-07-28":
                    if not page.get("handle"):
                        raise Arret(f"page {page.get('page')} sur {page.get('pages')} rendue sans handle : "
                                    "impossible de demander la suivante")
                    arguments = {"handle": page["handle"]}
                else:
                    arguments = {}
                page = await _appel(c, "page_suivante", arguments)
                d.pages.append(page)
    except Arret as arret:
        d.erreur = str(arret)
    except Exception as exc:  # la connexion elle-même a échoué (poignée de main, session…)
        d.erreur = f"connexion : {exc.__class__.__name__} — {exc}"
    d.echanges = c.echanges
    return d


def attendre(url: str, delai: float = 30, conseil: str = "") -> None:
    """Attend que le serveur réponde (tout code < 500) : utile juste après « docker compose up »."""
    fin = time.monotonic() + delai
    while True:
        try:
            if httpx.post(url, json={}, timeout=3).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        if time.monotonic() > fin:
            message = f"{url} ne répond pas après {delai:.0f} s : le service est-il démarré ?"
            raise SystemExit(f"{message} ({conseil})" if conseil else message)
        time.sleep(1)


def afficher(d: Deroule) -> str:
    lignes = [f"── Client {d.revision} ──"]
    for e in d.echanges:
        session = e.entetes_reponse.get("mcp-session-id") or e.entetes_requete.get("mcp-session-id")
        lignes.append(f"  {e.methode_http:<6} {e.methode_mcp or '–':<26} → {e.statut}"
                      + (f"   Mcp-Session-Id: {session[:8]}…" if session else ""))
    if d.etat:
        lignes.append(f"  etat_escale : quai {d.etat.get('quai')}, statut {d.etat.get('statut')}")
    if d.pages:
        handles = sum(1 for p in d.pages if p.get("handle"))
        lignes.append(f"  mouvements : {len(d.mouvements)} en {len(d.pages)} page(s)"
                      + (f", {handles} handle(s) reçu(s)" if handles else ", aucun handle"))
    lignes.append(f"  ÉCHEC : {d.erreur}" if d.erreur else "  scénario complet")
    return "\n".join(lignes)


async def _principal(url: str, revisions: list[str]) -> int:
    for revision in revisions:
        print(afficher(await derouler(url, revision)) + "\n")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="make lab3-clients")
    p.add_argument("--rev", choices=list(REVISIONS), help="une seule révision (par défaut : les deux)")
    p.add_argument("url")
    a = p.parse_args(argv)
    attendre(a.url)
    return asyncio.run(_principal(a.url, [a.rev] if a.rev else list(REVISIONS)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
