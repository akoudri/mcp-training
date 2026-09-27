"""Outils du LAB 13 : catalogue agrégé, question complète, vérification de la note, signaux de dérive, banc.

python -m outils.lab13 catalogue                  (make lab13-catalogue)       coût fixe par serveur et agrégé, collisions
python -m outils.lab13 question [--q 1|2|3] [--question "…"]   (make lab13-question)   votre agent, le vrai modèle
python -m outils.lab13 note                       (make lab13-verifier-note)   la dernière note, élément par élément
python -m outils.lab13 derive                     (make lab13-derive)          les trois signaux de la dernière exécution
python -m outils.lab13 banc [--executions 3]      (make lab13-banc)            extension B : le premier appel, catalogue agrégé

La configuration des serveurs est labs/lab13/serveurs.json. L'exécution de la question cible (Q=1) est gardée dans
labs/lab13/execution.json (question, plan, réponse, trace) : c'est elle que relisent note, derive et le critère
décisif. Les autres questions sont gardées à côté (execution-q2.json, execution-q3.json, execution-libre.json).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
import json
import os
import sys
import traceback
from dataclasses import asdict, is_dataclass
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastmcp import Client

from outils import banc, tokens_catalogue
from outils.verifier import note
from pharos import openrouter

RACINE = Path(__file__).resolve().parents[1]
CONFIG = RACINE / "labs" / "lab13" / "serveurs.json"
DERNIERE = RACINE / "labs" / "lab13" / "execution.json"
QUESTIONS_BANC = RACINE / "outils" / "questions" / "lab13.yaml"
QUESTIONS = {
    "1": "L'escale du Vent d'Autan de jeudi est-elle à risque ? Si oui, prépare la note d'alerte pour l'exploitant.",
    "2": "Quelles sont les pénalités de retard prévues au contrat de manutention de l'escale ESC-2026-0412 ?",
    "3": "Quelles escales sont en conflit de créneau jeudi 8 octobre ?",
}


def lire_serveurs(chemin: Path = CONFIG) -> list[dict]:
    if not chemin.exists():
        raise SystemExit(f"{chemin.relative_to(RACINE)} absent : lancer « make depart LAB=13 ».")
    return json.loads(chemin.read_text(encoding="utf-8"))["serveurs"]


def _jeton(serveur: dict) -> str | None:
    return os.environ.get("PHAROS_JETON") or serveur.get("jeton")


async def _statut_http(url: str, jeton: str | None) -> int | None:
    """Le code HTTP d'un POST nu : le client MCP ne le rapporte pas (un 401 y devient une erreur -32603)."""
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            r = await http.post(url, json={}, headers={"Authorization": f"Bearer {jeton}"} if jeton else {})
    except httpx.HTTPError:
        return None
    return r.status_code


async def lister(serveurs: list[dict]) -> dict[str, list]:
    """Les outils de chaque serveur (objets fastmcp), dans l'ordre de la configuration. Un serveur injoignable
    est signalé, pas ignoré."""
    catalogues = {}
    for s in serveurs:
        jeton = _jeton(s)
        url = s["url"]
        try:
            async with (Client(url, auth=jeton) if jeton and isinstance(url, str) else Client(url)) as c:
                catalogues[s["nom"]] = await c.list_tools()
        except Exception as exc:
            statut = await _statut_http(url, jeton) if isinstance(url, str) else None
            if statut in (401, 403):
                raise SystemExit(f"{s['nom']} ({url}) : jeton refusé (HTTP {statut}) — vérifier PHAROS_JETON, ou le "
                                 "jeton de ce serveur dans labs/lab13/serveurs.json.") from exc
            raise SystemExit(f"{s['nom']} ({url}) ne répond pas ({exc.__class__.__name__}) : lancer « make "
                             "lab13-tout ».") from exc
    return catalogues


def collisions(catalogues: dict[str, list]) -> dict[str, list[str]]:
    vus: dict[str, list[str]] = {}
    for serveur, outils in catalogues.items():
        for o in outils:
            vus.setdefault(o.name, []).append(serveur)
    return {nom: s for nom, s in vus.items() if len(s) > 1}


def rapport_catalogue(catalogues: dict[str, list]) -> str:
    lignes = ["Catalogue agrégé — coût fixe en tokens (o200k_base, approximation), payé à chaque tour", ""]
    total = nombre = 0
    for serveur, outils in catalogues.items():
        cout = sum(m.total for m in tokens_catalogue.mesurer(outils))
        total, nombre = total + cout, nombre + len(outils)
        lignes.append(f"  {serveur:<14}{len(outils):>3} outil(s)  {cout:>6} tokens")
    lignes += [f"  {'agrégé':<14}{nombre:>3} outil(s)  {total:>6} tokens", ""]
    trouvees = collisions(catalogues)
    if trouvees:
        lignes += ["Collisions de noms :"] + [f"  ❌ {nom} — {', '.join(s)}" for nom, s in sorted(trouvees.items())]
        lignes.append("Le modèle voit une liste plate : deux outils du même nom, c'est l'un qui écrase l'autre, ou "
                      "l'indéfini. Préfixer par domaine, côté serveur (bloc 21.1).")
    else:
        lignes.append("Aucune collision de noms sur le catalogue agrégé.")
    return "\n".join(lignes)


def _en_dict(valeur):
    return asdict(valeur) if is_dataclass(valeur) else dict(vars(valeur))


def chemin_execution(question: str) -> Path:
    """labs/lab13/execution.json est réservé à la question cible (celle du critère décisif) ; les autres à côté."""
    numero = next((n for n, q in QUESTIONS.items() if q == question), None)
    if numero == "1":
        return DERNIERE
    return DERNIERE.with_name(f"execution-q{numero}.json" if numero else "execution-libre.json")


def _affichable(chemin: Path) -> Path:
    try:
        return chemin.resolve().relative_to(RACINE)
    except ValueError:
        return chemin


def enregistrer(question: str, plan: list, reponse: str, trace: list, arret: str | None = None) -> Path:
    chemin = chemin_execution(question)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps({"question": question, "plan": [_en_dict(e) for e in plan], "reponse": reponse,
                                  "arret": arret, "trace": [_en_dict(e) for e in trace]},
                                 ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return chemin


def prend_config(executer) -> bool:
    """executer(question, *, config=…) : l'étape 1 du LAB 13 est-elle faite ? (lu sur la signature, sans l'appeler)"""
    try:
        parametres = inspect.signature(executer).parameters
    except (TypeError, ValueError):
        return True
    return "config" in parametres or any(p.kind is p.VAR_KEYWORD for p in parametres.values())


SANS_CONFIG = ("la boucle ne prend pas encore config= : c'est l'étape 1 du LAB 13 — executer(question, *, config=…) "
               "→ Execution(plan, reponse, trace).")


def decrire_erreur(exc: BaseException) -> str:
    """« TypeError : 'NoneType' object is not subscriptable (client/pharos_client/plan.py:57) » : type, message, et
    fichier:ligne du dernier cadre de la pile."""
    cadres = traceback.extract_tb(exc.__traceback__)
    ou = f" ({_affichable(Path(cadres[-1].filename))}:{cadres[-1].lineno})" if cadres else ""
    return f"{exc.__class__.__name__} : {exc}{ou}"


def poser(question: str) -> int:
    try:
        boucle = importlib.import_module("pharos_client.boucle")
        trace_mod = importlib.import_module("pharos_client.trace")
    except ModuleNotFoundError as exc:
        print(f"pharos_client introuvable ({exc.name}) : ce lab part de etat/sr3-fin (make depart LAB=13).")
        return 1
    if not prend_config(boucle.executer):
        print(SANS_CONFIG[0].upper() + SANS_CONFIG[1:])
        return 1
    print(f"Question : {question}\n")
    try:
        execution = boucle.executer(question, config=CONFIG)
    except boucle.ArretBoucle as arret:
        print(f"Arrêt : {arret}\n")
        trace_mod.afficher(arret.trace)
        chemin = enregistrer(question, [], "", arret.trace, str(arret))
        print(f"\nExécution gardée dans {_affichable(chemin)}.")
        return 1
    except TypeError as exc:
        print(f"Erreur dans la boucle — {decrire_erreur(exc)}")
        return 1
    trace_mod.afficher(execution.trace)
    print(f"\nRéponse :\n{execution.reponse}")
    chemin = enregistrer(question, execution.plan, execution.reponse, execution.trace)
    if chemin == DERNIERE:
        print(f"\nExécution gardée dans {_affichable(chemin)} : make lab13-verifier-note, make lab13-derive.")
    else:
        print(f"\nExécution gardée dans {_affichable(chemin)} — ce n'est pas la question cible : "
              f"{_affichable(DERNIERE)}, que relisent make lab13-verifier-note, make lab13-derive et le critère "
              "décisif, n'a pas changé.")
    return 0


def derniere() -> dict:
    if not DERNIERE.exists():
        raise SystemExit("Aucune exécution gardée : lancer d'abord « make lab13-question ».")
    return note.lire_execution(DERNIERE)


RIEN_A_VERIFIER = "poser la question cible (make lab13-question) et accepter le plan (« ok »)"


def verifier_execution(execution: dict) -> tuple[list, str | None]:
    """Les éléments de la note d'une exécution gardée, et pourquoi il n'y a rien à vérifier (sinon None) : une note
    sans aucun appel d'outil derrière, ou sans un seul chiffre, date ou nom, ne prouve rien."""
    if execution.get("arret"):
        return [], f"la dernière exécution s'est arrêtée ({execution['arret']}) : pas de note à vérifier."
    if not execution.get("trace"):
        return [], f"aucun appel d'outil dans la trace (plan refusé ?) : pas de note à vérifier — {RIEN_A_VERIFIER}."
    elements = note.verifier_note(execution["reponse"], execution["trace"], execution["question"])
    if not elements:
        return [], ("aucun chiffre, aucune date ni aucun nom connu dans la réponse : pas de note à vérifier — "
                    f"{RIEN_A_VERIFIER}.")
    return elements, None


def verifier_derniere_note() -> int:
    execution = derniere()
    elements, rien = verifier_execution(execution)
    if rien:
        print(rien[0].upper() + rien[1:])
        return 1
    print(f"Note de la dernière exécution — {len(execution['trace'])} appel(s) dans la trace\n")
    print(note.formater(elements))
    return 1 if note.sans_origine(elements) else 0


def signaux_derniere() -> int:
    execution = derniere()
    try:
        derive = importlib.import_module("pharos_client.derive")
        resultat = derive.signaux([SimpleNamespace(**e) for e in execution["plan"]],
                                  [SimpleNamespace(**e) for e in execution["trace"]])
    except NotImplementedError as exc:
        print(f"Signaux non calculés : {exc}")
        return 1
    print("Signaux de dérive de la dernière exécution (bloc 21.4) :")
    for cle, libelle in (("hors_plan", "appels hors plan"), ("jamais_executees", "étapes jamais exécutées"),
                         ("retours_arriere", "retours en arrière")):
        print(f"  {libelle:<26} {resultat[cle]}")
    if not execution["plan"]:
        print("  (aucun plan gardé : les deux premiers signaux ne veulent rien dire)")
    return 0


def outils_ecrases(catalogues: dict[str, list]) -> list[dict]:
    """Le catalogue agrégé tel qu'un client naïf le présente : en cas de collision, le dernier serveur écrase."""
    par_nom = {}
    for outils in catalogues.values():
        for o in outils:
            par_nom[o.name] = o
    return openrouter.outils_openai(list(par_nom.values()))


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="outils.lab13")
    sous = p.add_subparsers(dest="commande", required=True)
    sous.add_parser("catalogue")
    q = sous.add_parser("question")
    q.add_argument("--q", default="1")
    q.add_argument("--question")
    sous.add_parser("note")
    sous.add_parser("derive")
    b = sous.add_parser("banc")
    b.add_argument("--executions", type=int, default=3)
    a = p.parse_args(argv)
    if a.commande == "catalogue":
        print(rapport_catalogue(asyncio.run(lister(lire_serveurs()))))
        return 0
    if a.commande == "question":
        return poser(a.question or QUESTIONS.get(a.q, QUESTIONS["1"]))
    if a.commande == "note":
        return verifier_derniere_note()
    if a.commande == "derive":
        return signaux_derniere()
    if os.environ.get("SANS_MODELE") == "1":
        print("Banc ignoré (SANS_MODELE=1) : aucun appel au modèle.")
        return 0
    catalogues = asyncio.run(lister(lire_serveurs()))
    print(rapport_catalogue(catalogues) + "\n")
    executions = asyncio.run(banc.executer_banc(None, banc.charger_questions(QUESTIONS_BANC), a.executions,
                                                outils=outils_ecrases(catalogues)))
    print(banc.formater(executions, "Banc du premier appel — catalogue agrégé (LAB 13, extension B)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
