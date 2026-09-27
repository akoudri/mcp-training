"""Banc du premier appel (LAB 1, LAB 6).

Pour chaque question : UN appel au modèle, avec le catalogue du serveur, et l'on relève le premier
outil choisi. Aucune boucle — c'est le protocole du bloc 10.2, et rien de la boucle du LAB 4 n'est
fourni. Le modèle garde sa température par défaut : la variance entre exécutions est une information.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from fastmcp import Client

from pharos import openrouter

CONSIGNE = ("Tu es l'assistant de l'exploitant du terminal portuaire PHAROS. Nous sommes le mardi "
            "6 octobre 2026, à Paris. Utilise les outils disponibles quand ils permettent de répondre.")


@dataclass(frozen=True)
class Question:
    numero: int
    texte: str
    attendu: str
    arguments_attendus: dict = field(default_factory=dict)
    resultat_attendu: str | None = None     # "erreur_metier" : le premier appel doit produire isError
    constat: bool = False                   # consignée sans verdict (LAB 1, question 2)
    contexte: tuple = ()                    # tours précédents rejoués avant la question (LAB 1, Q4 après Q3)


@dataclass
class Execution:
    question: Question
    outil: str | None
    arguments: dict
    ok: bool | None
    resultat: str | None = None
    est_erreur: bool | None = None
    usage: dict = field(default_factory=dict)


def charger_questions(chemin) -> list[Question]:
    donnees = yaml.safe_load(Path(chemin).read_text(encoding="utf-8"))
    return [Question(i, q["question"], q["attendu"], q.get("arguments_attendus") or {},
                     q.get("resultat_attendu"), bool(q.get("constat")),
                     tuple(dict(m) for m in q.get("contexte") or ()))
            for i, q in enumerate(donnees, 1)]


AUCUN = "aucun"     # attendu: aucun — réussi si et seulement si le modèle n'appelle aucun outil (LAB 6, extension B)


def juger(q: Question, outil: str | None, arguments: dict, est_erreur: bool | None) -> bool | None:
    if q.constat:
        return None
    if q.attendu == AUCUN:
        return outil is None
    if outil != q.attendu or any(arguments.get(k) != v for k, v in q.arguments_attendus.items()):
        return False
    return not (q.resultat_attendu == "erreur_metier" and est_erreur is not True)


async def _executer_appel(client: Client, appel: openrouter.Appel) -> tuple[str, bool]:
    try:
        r = await client.call_tool(appel.nom, appel.arguments, raise_on_error=False)
    except Exception as exc:  # outil inexistant, arguments refusés au niveau protocole : on le montre
        return f"appel impossible : {exc}", True
    return " ".join(getattr(b, "text", "") or "" for b in r.content), bool(r.is_error)


async def executer_banc(cible, questions: list[Question], executions: int = 1, executer: bool = False,
                        completer=None, outils: list[dict] | None = None) -> list[Execution]:
    """cible : le serveur dont on présente le catalogue. outils (LAB 13) : un catalogue déjà composé, présenté tel
    quel — cible vaut alors None, et aucun premier appel n'est exécuté."""
    if cible is None and outils is None:
        raise ValueError("executer_banc : ni cible (le serveur dont on lit le catalogue) ni outils (un catalogue "
                         "composé) — il faut l'un des deux.")
    completer = completer or openrouter.completer
    resultats: list[Execution] = []
    async with (Client(cible) if cible is not None else contextlib.nullcontext()) as client:
        if outils is None:
            outils = openrouter.outils_openai(await client.list_tools())
        for q in questions:
            for _ in range(executions):
                messages = [{"role": "system", "content": CONSIGNE}, *q.contexte,
                            {"role": "user", "content": q.texte}]
                reponse = await asyncio.to_thread(completer, messages, outils)
                premier = reponse.appels[0] if reponse.appels else None
                resultat = est_erreur = None
                if premier and client is not None and (executer or q.resultat_attendu):
                    resultat, est_erreur = await _executer_appel(client, premier)
                nom = premier.nom if premier else None
                arguments = premier.arguments if premier else {}
                resultats.append(Execution(q, nom, arguments, juger(q, nom, arguments, est_erreur),
                                           resultat, est_erreur, reponse.usage))
    return resultats


def bilan(executions: list[Execution]) -> dict[int, tuple[int, int]]:
    compte: dict[int, list[int]] = {}
    for e in executions:
        if e.ok is None:
            continue
        r = compte.setdefault(e.question.numero, [0, 0])
        r[0] += int(e.ok)
        r[1] += 1
    return {n: (r[0], r[1]) for n, r in compte.items()}


def question_reussie(reussites: int, total: int) -> bool:
    return reussites * 2 > total


def _sans_sauts_de_ligne(valeur) -> str:
    """Un argument multi-ligne casserait la ligne du tableau Markdown."""
    return str(valeur).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def _cellule(e: Execution) -> str:
    appel = "aucun appel" if e.outil is None else \
        f"{e.outil}({', '.join(f'{k}={_sans_sauts_de_ligne(v)}' for k, v in e.arguments.items())})"
    marque = {True: "✅", False: "❌", None: "👁"}[e.ok]
    return f"{marque} {appel}"[:90].replace("|", "\\|")


def formater(executions: list[Execution], titre: str = "Banc du premier appel") -> str:
    par_question: dict[int, list[Execution]] = {}
    for e in executions:
        par_question.setdefault(e.question.numero, []).append(e)
    n = max((len(v) for v in par_question.values()), default=0)
    modele = os.environ.get("PHAROS_MODELE") or openrouter.MODELE_DEFAUT
    lignes = [f"## {titre}", "", f"Modèle : {modele} · {n} exécution(s) par question", "",
              "| # | Question | Attendu | " + " | ".join(f"Exécution {i}" for i in range(1, n + 1)) + " | Taux |",
              "|---|---|---|" + "---|" * n + "---|"]
    scores = bilan(executions)
    for numero, execs in par_question.items():
        q = execs[0].question
        taux = "consignée" if q.constat else f"{scores[numero][0]}/{scores[numero][1]}"
        lignes.append(f"| {numero} | {q.texte.replace('|', '/')} | {q.attendu} | "
                      + " | ".join(_cellule(e) for e in execs) + f" | {taux} |")
    executees = [e for e in executions if e.resultat is not None]
    if executees:
        lignes += ["", "Premier appel exécuté :"]
        lignes += [f"- Q{e.question.numero} : {'isError' if e.est_erreur else 'succès'} — {e.resultat[:200]}"
                   for e in executees]
    reussies = sum(question_reussie(*s) for s in scores.values())
    entree = sum(e.usage.get("prompt_tokens", 0) for e in executions)
    sortie = sum(e.usage.get("completion_tokens", 0) for e in executions)
    cout = sum(e.usage.get("cost", 0) or 0 for e in executions)
    lignes += ["", f"Questions réussies (majorité des exécutions) : {reussies}/{len(scores)}",
               f"Tokens : {entree} en entrée, {sortie} en sortie · coût : {cout:.4f} $"]
    return "\n".join(lignes)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="banc", description="Relève le premier appel d'outil pour chaque question.")
    p.add_argument("url")
    p.add_argument("--questions", required=True)
    p.add_argument("--executions", type=int, default=1)
    p.add_argument("--executer", action="store_true", help="exécuter le premier appel et montrer son résultat")
    p.add_argument("--sortie")
    p.add_argument("--titre", default="Banc du premier appel")
    a = p.parse_args(argv)
    if os.environ.get("SANS_MODELE") == "1":
        print("Banc ignoré (SANS_MODELE=1) : aucun appel au modèle.")
        return 0
    try:
        executions = asyncio.run(executer_banc(a.url, charger_questions(a.questions), a.executions, a.executer))
    except openrouter.ErreurModele as exc:
        print(f"Banc interrompu : {exc}")
        return 2
    texte = formater(executions, a.titre)
    print(texte)
    if a.sortie:
        Path(a.sortie).parent.mkdir(parents=True, exist_ok=True)
        Path(a.sortie).write_text(texte + "\n", encoding="utf-8")
        print(f"\nÉcrit dans {a.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
