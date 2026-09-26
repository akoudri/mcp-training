"""make lab6-mesurer [SORTIE=labs/lab6/avant.md] — le banc du premier appel sur pharos-quai (LAB 6).

Cinq questions, trois exécutions chacune. Les outils peuvent avoir été renommés : chacun est retrouvé
par son schéma d'entrée, figé dans tests/empreinte_schemas_quai.json. Un schéma modifié, un outil
ajouté ou retiré, et la mesure refuse de tourner : elle ne comparerait plus la même chose.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import httpx
from fastmcp import Client

from outils import banc
from pharos import openrouter

RACINE = Path(__file__).resolve().parents[1]
EMPREINTE = RACINE / "tests" / "empreinte_schemas_quai.json"
QUESTIONS = RACINE / "outils" / "questions" / "lab6.yaml"
URL = "http://observateur:8105/mcp"
EXECUTIONS = 3
TITRE = "Mesure LAB 6 — premier appel"


class SchemasModifies(Exception):
    """Le catalogue ne correspond plus à l'empreinte : la mesure ne compare plus la même chose."""


def empreinte_schemas(outils) -> dict[str, dict]:
    return {o.name: o.input_schema or {} for o in outils}


def charger_empreinte(chemin: Path = EMPREINTE) -> dict[str, dict]:
    return json.loads(chemin.read_text(encoding="utf-8"))


def _cle(schema: dict) -> str:
    """Forme canonique d'un schéma : l'ordre des paramètres obligatoires ne compte pas."""
    return json.dumps({**schema, "required": sorted(schema.get("required", []))}, sort_keys=True, ensure_ascii=False)


def correspondance(actuels: dict[str, dict], origine: dict[str, dict]) -> dict[str, str]:
    """Nom d'origine → nom actuel, par égalité stricte des schémas d'entrée."""
    par_schema = {_cle(s): nom for nom, s in actuels.items()}
    manquants = [nom for nom, s in origine.items() if _cle(s) not in par_schema]
    problemes = []
    if len(actuels) != len(origine):
        problemes.append(f"{len(actuels)} outils au catalogue, {len(origine)} attendus : ne pas ajouter ni retirer d'outil.")
    if manquants:
        problemes.append("schéma introuvable pour : " + ", ".join(manquants)
                         + " — les paramètres ont changé (noms, types, descriptions de paramètres (Field), "
                           "valeurs par défaut) ; revenir aux schémas d'origine.")
    if problemes:
        raise SchemasModifies("\n".join(problemes))
    return {nom: par_schema[_cle(s)] for nom, s in origine.items()}


async def mesurer(cible, executions: int = EXECUTIONS, completer=None) -> tuple[list[banc.Execution], dict[str, str]]:
    async with Client(cible) as client:
        noms = correspondance(empreinte_schemas(await client.list_tools()), charger_empreinte())
    questions = [replace(q, attendu=noms[q.attendu]) for q in banc.charger_questions(QUESTIONS)]
    return await banc.executer_banc(cible, questions, executions, completer=completer), noms


def rapport(executions: list[banc.Execution], noms: dict[str, str]) -> str:
    renommes = [f"{a} → {n}" for a, n in noms.items() if a != n]
    ligne = "Noms : " + (", ".join(renommes) if renommes else "catalogue d'origine (aucun outil renommé)")
    return banc.formater(executions, TITRE) + "\n\n" + ligne


@dataclass(frozen=True)
class LigneMesure:
    numero: int
    attendu: str
    executions: int
    reussites: int


@dataclass(frozen=True)
class Mesure:
    modele: str
    lignes: list[LigneMesure]

    @property
    def reussies(self) -> set[int]:
        return {l.numero for l in self.lignes if banc.question_reussie(l.reussites, l.executions)}


def lire_mesure(texte: str) -> Mesure:
    """Relit un tableau écrit par make lab6-mesurer (avant.md, apres.md). ValueError si le format n'y est pas."""
    modele = re.search(r"^Modèle : (\S+)", texte, re.M)
    lignes = []
    for ligne in texte.splitlines():
        cellules = [c.strip() for c in re.split(r"(?<!\\)\|", ligne.strip())[1:-1]]
        if len(cellules) < 5 or not cellules[0].isdigit():
            continue
        taux = re.fullmatch(r"(\d+)/(\d+)", cellules[-1])
        if not taux:
            raise ValueError(f"taux illisible à la question {cellules[0]} : « {cellules[-1]} »")
        executions_cellules = cellules[3:-1]
        reussites, executions = int(taux[1]), int(taux[2])
        reussies_comptees = sum(1 for c in executions_cellules if c.startswith("✅"))
        if reussites != reussies_comptees or executions != len(executions_cellules):
            raise ValueError(f"taux incohérent à la question {cellules[0]} : « {cellules[-1]} » ne correspond pas "
                             f"aux cellules de la ligne ({reussies_comptees} ✅ sur {len(executions_cellules)}).")
        lignes.append(LigneMesure(int(cellules[0]), cellules[2], executions, reussites))
    if not modele or not lignes:
        raise ValueError("ce n'est pas un tableau produit par « make lab6-mesurer »")
    return Mesure(modele[1], lignes)


async def _panne(url: str) -> str | None:
    """Sonde l'URL avant de mesurer, comme outils.verifier.commun.Verification._panne : un observateur qui
    tourne peut relayer un pharos-quai arrêté (502), ce que fastmcp ne rattrape pas avec un message utile
    (mcp.shared.exceptions.MCPError: Server returned an error response — trace de pile brute)."""
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            r = await http.post(url, json={})
    except httpx.HTTPError as exc:
        return exc.__class__.__name__
    return f"HTTP {r.status_code}" if r.status_code >= 500 else None


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="make lab6-mesurer")
    p.add_argument("--url", default=URL)
    p.add_argument("--sortie")
    p.add_argument("--executions", type=int, default=EXECUTIONS)
    a = p.parse_args(argv)
    if os.environ.get("SANS_MODELE") == "1":
        print("Mesure ignorée (SANS_MODELE=1) : aucun appel au modèle.")
        return 0
    panne = asyncio.run(_panne(a.url))
    if panne:
        print(f"pharos-quai ne répond pas à {a.url} ({panne}) : lancer « make lab6-quai », et vérifier "
              "« docker compose logs pharos-quai » (une erreur de syntaxe dans serveur.py l'arrête) ; "
              "puis relancer la mesure.")
        return 2
    try:
        executions, noms = asyncio.run(mesurer(a.url, a.executions))
    except SchemasModifies as exc:
        print(f"Mesure refusée : le catalogue ne compare plus la même chose.\n{exc}")
        return 1
    except openrouter.ErreurModele as exc:
        print(f"Mesure interrompue : {exc}")
        return 2
    except RuntimeError as exc:           # fastmcp : « Client failed to connect » (rattrapage si la sonde n'a rien vu)
        print(f"pharos-quai ne répond pas à {a.url} ({exc}) : lancer « make lab6-quai », puis relancer la mesure.")
        return 2
    texte = rapport(executions, noms)
    print(texte)
    if a.sortie:
        Path(a.sortie).parent.mkdir(parents=True, exist_ok=True)
        Path(a.sortie).write_text(texte + "\n", encoding="utf-8")
        print(f"\nÉcrit dans {a.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
