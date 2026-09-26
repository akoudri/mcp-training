"""Vérificateur du LAB 3 — un déploiement, deux révisions, derrière le répartiteur avec affinité."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

from outils.repartiteur import creer_repartiteur
from outils.scenario_legacy import Deroule, derouler
from outils.servir import servir
from outils.verifier.commun import Echec, Verification

URL = "http://observateur:8204/mcp"
ANCIENNE, RECENTE = "2025-11-25", "2026-07-28"
RACINE = Path(__file__).resolve().parents[2]
ATTENDU = {"quai": 3, "tirant_eau_m": 12.9}
INDICE_AFFINITE = ("\nSi sa session est « inconnue » : le répartiteur tourne-t-il avec affinité de session ? "
                   "(make lab3-deux-instances, pas lab2-deux-instances)")

v = Verification("LAB 3 — Un déploiement, deux révisions", URL, "make lab3-deux-instances")


def _journal() -> Path:
    return Path(os.environ.get("PHAROS_JOURNAL_LEGACY", RACINE / "logs" / "pharos-legacy.jsonl"))


def _lignes() -> list[str]:
    chemin = _journal()
    return chemin.read_text(encoding="utf-8").splitlines() if chemin.exists() else []


async def _deroules(ctx) -> dict[str, Deroule]:
    """Les deux clients, joués une fois chacun ; le journal est relevé avant et après."""
    if "deroules" not in ctx.cache:
        avant = len(_lignes())
        ctx.cache["deroules"] = {rev: await derouler(ctx.url, rev) for rev in (ANCIENNE, RECENTE)}
        ctx.cache["journal"] = _lignes()[avant:]
    return ctx.cache["deroules"]


def _resultat_brut(echange) -> dict:
    try:
        return json.loads(echange.corps_reponse).get("result") or {}
    except (ValueError, AttributeError):
        return {}


@v.constat("Le constat de l'étape 1 est écrit, et nomme le point de rupture exact du client ancien.")
def _(ctx):
    return "Relire labs/lab3/constat.md : la requête exacte où le client 2025-11-25 échoue est-elle nommée ?"


@v.critere("Les deux clients obtiennent une réponse correcte à etat_escale.")
async def _(ctx):
    problemes = []
    for rev, d in (await _deroules(ctx)).items():
        if d.etat is None:
            problemes.append(f"client {rev} : {d.erreur}")
        elif any(d.etat.get(k) != w for k, w in ATTENDU.items()):
            problemes.append(f"client {rev} : réponse inattendue {d.etat}")
    if problemes:
        raise Echec("\n".join(problemes))


@v.critere("Les deux clients obtiennent une réponse correcte à lister_mouvements puis page_suivante.")
async def _(ctx):
    problemes = []
    for rev, d in (await _deroules(ctx)).items():
        if d.erreur:
            problemes.append(f"client {rev} : {d.erreur}")
            continue
        total = d.pages[0].get("total")
        if len(d.mouvements) != total or len({m.get("conteneur") for m in d.mouvements}) != total:
            problemes.append(f"client {rev} : {len(d.mouvements)} mouvements lus pour {total} annoncés")
    if problemes:
        raise Echec("\n".join(problemes))
    return f"{len(d.mouvements)} mouvements en {len(d.pages)} pages, pour chaque client"


@v.critere("Le résultat d'appel porte le texte et structuredContent, dans les deux révisions (sur-ensemble).")
async def _(ctx):
    problemes = []
    for rev, d in (await _deroules(ctx)).items():
        reussis = [r for r in map(_resultat_brut, d.appels()) if r and not r.get("isError")]
        if not reussis:
            problemes.append(f"client {rev} : aucun appel réussi à examiner ({d.erreur})")
        elif any("structuredContent" not in r for r in reussis):
            problemes.append(f"client {rev} : un résultat sans structuredContent (renvoyer les deux formes)")
    if problemes:
        raise Echec("\n".join(problemes))


def _lit_les_mouvements(fonction: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    noms = {n.id for n in ast.walk(fonction) if isinstance(n, ast.Name)}
    chaines = [n.value for n in ast.walk(fonction) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return "FICHIER" in noms or any("mouvements.yaml" in c for c in chaines)


@v.constat("Le code métier de lecture des mouvements n'existe qu'en un seul exemplaire.")
def _(ctx):
    trouvees = [f"{fichier.name}:{noeud.name}"
                for fichier in sorted((RACINE / "serveurs" / "pharos_legacy").glob("*.py"))
                for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8")))
                if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)) and _lit_les_mouvements(noeud)]
    return (f"{len(trouvees)} définition(s) de lecture des mouvements : {', '.join(trouvees) or 'aucune'} "
            "(attendu : 1, metier.py:lire_mouvements).")


@v.critere("Aucun handle n'apparaît dans une réponse servie à un client 2025-11-25.")
async def _(ctx):
    d = (await _deroules(ctx))[ANCIENNE]
    if d.etat is None:
        raise Echec(f"le client 2025-11-25 n'obtient rien : {d.erreur}")
    fuites = [e.methode_mcp or e.methode_http for e in d.echanges if "hdl_" in e.corps_reponse]
    if fuites:
        raise Echec(f"chaîne hdl_ servie au client ancien sur : {', '.join(fuites)} (le handle est pour 2026-07-28).")


@v.critere("La révision demandée est journalisée à chaque requête.")
async def _(ctx):
    deroules = await _deroules(ctx)
    requetes = sum(len(d.echanges) for d in deroules.values())
    lignes = ctx.cache["journal"]
    if not lignes:
        raise Echec(f"rien de neuf dans {_journal()} : compat.journaliser(revision, methode, …) à chaque requête.")
    try:
        revisions = [json.loads(ligne).get("revision") for ligne in lignes]
    except ValueError:
        raise Echec("une ligne du journal n'est pas du JSON : utiliser compat.journaliser().") from None
    if len(lignes) < requetes:
        raise Echec(f"{len(lignes)} ligne(s) pour {requetes} requêtes : une ligne par requête, y compris la poignée de main.")
    if {ANCIENNE, RECENTE} - set(revisions):
        raise Echec(f"révisions journalisées : {sorted(set(map(str, revisions)))} ; les deux sont attendues.")
    return f"{len(lignes)} lignes pour {requetes} requêtes"


@v.critere("Critère décisif — le test passe derrière le répartiteur à deux instances, avec affinité de session.")
async def _(ctx):
    deroules = await _deroules(ctx)
    for rev, d in deroules.items():
        if d.erreur:
            raise Echec(f"client {rev} : {d.erreur}" + (INDICE_AFFINITE if rev == ANCIENNE else ""))
    instances = {e.entetes_reponse.get("x-pharos-instance", "?") for d in deroules.values() for e in d.echanges}
    if "?" in instances:
        raise Echec("pas d'en-tête X-Pharos-Instance : passer par le répartiteur (make lab3-deux-instances, port 8204).")
    return f"instances vues : {', '.join(sorted(instances))}"


@v.constat("Critère décisif — les deux traces Inspector proviennent du même processus.")
def _(ctx):
    return ("Inspector (http://localhost:7001) : filtrer sur le port 8204 ; les requêtes des deux clients portent "
            "les mêmes X-Pharos-Instance (a et b), donc les mêmes processus.")


@v.constat("Sans affinité de session, ce qui arrive au client ancien.")
async def _(ctx):
    if (await _deroules(ctx))[ANCIENNE].erreur is not None:
        return ("Faire d'abord passer le client 2025-11-25 derrière le répartiteur avec affinité ; "
                "ce constat n'a de sens qu'ensuite.")
    amont_a = os.environ.get("AMONT_LEGACY_A", "http://pharos-legacy-a:8000")
    amont_b = os.environ.get("AMONT_LEGACY_B", "http://pharos-legacy-b:8000")
    try:
        with servir(creer_repartiteur(amont_a, amont_b, affinite=False)) as sans_affinite:
            d = await derouler(f"{sans_affinite}/mcp", ANCIENNE)
    except Exception as exc:
        return f"essai impossible ({exc.__class__.__name__} : {exc}) ; le refaire à la main avec make lab2-deux-instances."
    if d.erreur is None:
        return "le client ancien a réussi sans affinité : sa session est-elle partagée entre les instances ? Le consigner."
    return (f"sans affinité, le client 2025-11-25 échoue : {d.erreur}\n"
            "C'est le prix de l'état conservé pour les clients anciens : le consigner dans labs/lab3/constat.md.")
