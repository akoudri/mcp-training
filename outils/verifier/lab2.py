"""Vérificateur du LAB 2 — pharos-legacy migré en 2026-07-28, à travers le répartiteur à deux instances."""

from __future__ import annotations

import os

from outils.client_test import ClientTest
from outils.scenario_legacy import ESCALE, Deroule, derouler
from outils.verifier.commun import Echec, Verification
from pharos import jetons

URL = "http://observateur:8204/mcp"
REVISION = "2026-07-28"
META = {"io.modelcontextprotocol/protocolVersion": REVISION,
        "io.modelcontextprotocol/clientInfo": {"name": "pharos-verificateur", "version": "1.0"},
        "io.modelcontextprotocol/clientCapabilities": {}}

v = Verification("LAB 2 — Autopsie protocolaire et migration", URL, "make lab2-deux-instances")


async def _deroule(ctx) -> Deroule:
    """Le scénario complet, joué une fois par le client 2026-07-28 et partagé entre les critères."""
    if "deroule" not in ctx.cache:
        ctx.cache["deroule"] = await derouler(ctx.url, REVISION)
    return ctx.cache["deroule"]


def _exiger_connexion(d: Deroule) -> None:
    if d.erreur and d.etat is None:
        raise Echec(f"le client 2026-07-28 n'obtient même pas etat_escale : {d.erreur}")


def _texte(r) -> str:
    return " ".join(getattr(b, "text", "") or "" for b in r.content)


def _alterer(jeton: str) -> str:
    i = len(jeton) - 3
    return jeton[:i] + ("A" if jeton[i] != "A" else "B") + jeton[i + 1:]


@v.constat("La grille d'inventaire est remplie, les cinq ruptures identifiées.")
def _(ctx):
    return "Relire labs/lab2/inventaire.md : chaque rupture a-t-elle son « où » et son « quoi faire » ?"


@v.critere("Aucun Mcp-Session-Id ne circule dans le trafic, dans aucun sens.")
async def _(ctx):
    d = await _deroule(ctx)
    _exiger_connexion(d)
    vus = [e.methode_mcp or e.methode_http for e in d.echanges
           if "mcp-session-id" in e.entetes_requete or "mcp-session-id" in e.entetes_reponse]
    if vus:
        raise Echec(f"Mcp-Session-Id présent sur : {', '.join(vus)} — le serveur ne doit plus en émettre (étape 2).")


@v.critere("Aucun échange initialize / initialized ne précède le premier appel utile.")
async def _(ctx):
    d = await _deroule(ctx)
    _exiger_connexion(d)
    methodes = [e.methode_mcp for e in d.echanges]
    poignee = [m for m in methodes if m in ("initialize", "notifications/initialized")]
    if poignee:
        raise Echec(f"poignée de main observée ({', '.join(poignee)}) : la retirer (étape 2).")
    return f"premier échange : {methodes[0]}"


@v.critere("server/discover répond, et annonce la révision 2026-07-28.")
async def _(ctx):
    async with ClientTest(ctx.url) as c:
        r = await c.brut({"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": META}},
                         {"Mcp-Protocol-Version": REVISION, "Mcp-Method": "server/discover"})
    try:
        corps = r.json()
    except ValueError:
        raise Echec(f"server/discover : réponse HTTP {r.status_code} illisible.") from None
    if "error" in corps:
        raise Echec(f"server/discover renvoie une erreur : {corps['error'].get('message')} (étape 2, point 3).")
    resultat = corps.get("result") or {}
    if REVISION not in (resultat.get("supportedVersions") or []):
        raise Echec("server/discover doit annoncer supportedVersions: [\"2026-07-28\"].")
    manquants = [k for k in ("capabilities", "resultType", "ttlMs", "cacheScope") if k not in resultat]
    if manquants:
        raise Echec(f"server/discover : champs manquants {', '.join(manquants)} (le client 2026-07-28 les exige).")
    identite = (resultat.get("_meta") or {}).get("io.modelcontextprotocol/serverInfo")
    return f"identité annoncée : {identite}" if identite else "identité absente de _meta (facultatif)"


@v.critere("Mcp-Method et Mcp-Name sont présents sur chaque requête et portent les bonnes valeurs.")
async def _(ctx):
    d = await _deroule(ctx)
    _exiger_connexion(d)
    problemes = [f"{e.methode_mcp} : Mcp-Method = {e.entetes_requete.get('mcp-method')!r}"
                 for e in d.echanges if e.methode_mcp and e.entetes_requete.get("mcp-method") != e.methode_mcp]
    # Les en-têtes déclarent, ils ne prouvent pas : le serveur doit refuser ceux qui contredisent le corps.
    corps = {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
             "params": {"name": "etat_escale", "arguments": {"escale_id": ESCALE}, "_meta": META}}
    async with ClientTest(ctx.url) as c:
        for entetes, cas in [({"Mcp-Method": "tools/list"}, "Mcp-Method contredit le corps"),
                             ({"Mcp-Method": "tools/call", "Mcp-Name": "page_suivante"}, "Mcp-Name contredit le corps")]:
            r = await c.brut(corps, {"Mcp-Protocol-Version": REVISION, **entetes})
            if r.status_code != 400:
                problemes.append(f"{cas} : réponse HTTP {r.status_code}, 400 attendu (le serveur doit comparer "
                                 "les en-têtes au corps)")
    if problemes:
        raise Echec("\n".join(problemes))


@v.critere("Un handle expiré ou altéré d'un caractère est refusé, avec une erreur métier.")
async def _(ctx):
    d = await _deroule(ctx)
    _exiger_connexion(d)
    handle = d.pages[0].get("handle") if d.pages else None
    if not str(handle or "").startswith(jetons.PREFIXE):
        raise Echec("lister_mouvements doit rendre un champ « handle » produit par pharos.jetons.signer (étape 3).")
    try:
        charge = {k: w for k, w in jetons.lire_charge(handle).items() if k != "exp"}
    except jetons.JetonInvalide:
        raise Echec("le handle n'a pas le format de pharos.jetons (utiliser signer()).") from None
    cle = os.environ.get("CLE_SERVEUR")
    if not cle:
        raise Echec("CLE_SERVEUR absente de l'environnement du vérificateur (compose.yaml, service atelier).")
    problemes = []
    async with ClientTest(ctx.url) as c:
        for cas, jeton in [("altéré d'un caractère", _alterer(handle)),
                           ("expiré", jetons.signer(charge, cle, duree_s=-60))]:
            try:
                r = await c.appeler("page_suivante", {"handle": jeton})
            except Exception as exc:
                problemes.append(f"handle {cas} : erreur protocolaire ({exc}) au lieu d'une erreur métier (isError)")
                continue
            if not r.is_error:
                problemes.append(f"handle {cas} : accepté — le refuser en erreur métier (isError) "
                                 "qui dit de relancer lister_mouvements")
            elif _texte(r).startswith("Error calling tool") or "Traceback" in _texte(r):
                problemes.append(f"handle {cas} : exception non rattrapée — dire au client quoi faire")
    if problemes:
        raise Echec("\n".join(problemes))


@v.critere("Critère décisif — lister_mouvements puis page_suivante fonctionnent à travers le répartiteur "
           "à deux instances, sans stockage partagé.")
async def _(ctx):
    d = await _deroule(ctx)
    _exiger_connexion(d)
    if d.erreur:
        raise Echec(d.erreur)
    appels = d.appels()
    instances = [e.entetes_reponse.get("x-pharos-instance", "?") for e in appels]
    if "?" in instances:
        raise Echec("pas d'en-tête X-Pharos-Instance : passer par le répartiteur (make lab2-deux-instances, port 8204).")
    total = d.pages[0].get("total")
    conteneurs = {m.get("conteneur") for m in d.mouvements}
    if len(d.mouvements) != total or len(conteneurs) != total:
        raise Echec(f"{len(d.mouvements)} mouvements lus ({len(conteneurs)} distincts) pour {total} annoncés.")
    pages = instances[1:]            # lister_mouvements puis chaque page_suivante
    if len(set(pages)) < 2:
        raise Echec(f"toutes les pages ont été servies par l'instance {pages[0]} : la pagination n'a pas "
                    "traversé les deux instances (le répartiteur est-il démarré par make lab2-deux-instances ?).")
    return f"{total} mouvements en {len(d.pages)} pages, servies par {' → '.join(pages)}"
