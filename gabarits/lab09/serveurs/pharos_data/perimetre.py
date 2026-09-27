"""Le périmètre de l'appelant (LAB 9) : connexion sous son rôle, et SQL libre en lecture stricte (blocs 15.1 à 15.4).

Fourni : emprunter() — la connexion sous le rôle de l'appelant, variable de session pharos.agent posée —
et analyser() — l'analyse syntaxique d'une requête (sqlglot). À écrire : les quatre étages
d'executer_sur_perimetre, dans l'ordre du slide 290, le moins cher d'abord.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass

import sqlglot
from fastmcp.exceptions import ToolError
from sqlglot import exp

from pharos import journal
from pharos.autorisation import Identite

LIMITE = 200                      # LIMIT imposé par vous, jamais demandé au modèle
TIMEOUT = "3s"                    # statement_timeout, côté base
SEUIL_COUT = 50_000               # coût estimé (EXPLAIN) au-delà duquel on refuse
PROFONDEUR_MAX = 3                # tables par requête : au-delà, dans PHAROS, le modèle a inventé une relation
# Liste blanche : ce que l'agent peut lire. Elle est déjà publique dans la ressource de schéma.
LISTE_BLANCHE: dict[str, set[str]] = {
    "escales": {"escale_id", "navire_id", "quai", "debut", "fin", "statut", "tirant_eau_m"},
    "mouvements": {"mouvement_id", "escale_id", "conteneur_id", "sens", "horodatage", "type_conteneur"},
    "navires": {"navire_id", "nom", "imo", "longueur_m", "tirant_eau_max_m", "pavillon"},
    "quais": {"quai", "longueur_m", "tirant_eau_max_m", "equipements"},
}


@asynccontextmanager
async def emprunter(pool, appelant: Identite):
    """Une connexion du pool, dans une transaction en lecture seule, sous le rôle de l'appelant. pharos.agent est
    posé AVANT le changement de rôle : c'est pharos_app qui l'écrit (seul à en avoir le droit — GRANT EXECUTE
    ciblé dans donnees/base/__main__.py) ; une fois le rôle applicatif endossé, il ne peut plus l'écraser.

    C'est la base qui cloisonne (politique RLS de labs/lab9/politique.sql) : l'outil n'ajoute aucun WHERE."""
    if pool is None:
        raise ToolError("Base indisponible : le pool n'est pas créé.")
    async with pool.acquire() as connexion, connexion.transaction(readonly=True):
        await connexion.execute("SELECT set_config('pharos.agent', $1, true)", appelant.agent_id or "")
        await connexion.execute(f"SET LOCAL ROLE {appelant.role}")
        yield connexion


@dataclass(frozen=True)
class Analyse:
    instructions: int                     # nombre d'instructions (« SELECT 1; DROP … » en compte deux)
    select_seul: bool                     # une lecture, sans écriture cachée (CTE, sous-requête)
    tables: set[str]                      # tables lues (les noms de CTE exclus)
    colonnes: set[tuple[str | None, str]]  # (table réelle ou None si non qualifiée, colonne)
    etoile: bool                          # un * ailleurs que dans count(*)


def analyser(sql: str) -> Analyse:
    """Analyse syntaxique (dialecte PostgreSQL). Lève sqlglot.errors.ParseError si le SQL est illisible."""
    arbres = [a for a in sqlglot.parse(sql, read="postgres") if a is not None]
    racine = arbres[0] if arbres else exp.Select()
    ecritures = (exp.Delete, exp.Insert, exp.Update, exp.Drop, exp.Create, exp.Alter, exp.Command, exp.Merge)
    ctes = {c.alias_or_name for a in arbres for c in a.find_all(exp.CTE)}
    alias = {}
    tables = set()
    for a in arbres:
        for t in a.find_all(exp.Table):
            if t.name not in ctes:
                tables.add(t.name)
                alias[t.alias_or_name] = t.name
    colonnes = {(alias.get(c.table, c.table) if c.table else None, c.name)
                for a in arbres for c in a.find_all(exp.Column) if not isinstance(c.this, exp.Star)}
    etoile = any(isinstance(s, exp.Star) and not isinstance(s.parent, exp.Count)
                 for a in arbres for s in a.find_all(exp.Star))
    return Analyse(len(arbres), isinstance(racine, exp.Select) and not any(
        isinstance(n, ecritures) for a in arbres for n in a.walk()), tables, colonnes, etoile)


def refus(etage: str) -> ToolError:
    """Le message uniforme des refus : l'étage, puis la liste blanche — rien de ce qui existe vraiment."""
    disponibles = " ; ".join(f"{t} ({', '.join(sorted(c))})" for t, c in sorted(LISTE_BLANCHE.items()))
    return ToolError(f"Requête refusée ({etage}). Seules des lectures SELECT sur ces tables et colonnes sont "
                     f"possibles : {disponibles}.")


async def executer_sur_perimetre(pool, sql: str, appelant: Identite) -> list[dict]:
    """Bloc 15.2 : syntaxe, liste blanche, plan, exécution — chaque étage refuse avec refus(...).

    Une erreur brute de la base ne sort jamais : journal.consigner_erreur(exc), puis refus(...)."""
    # Étage 1 — syntaxe : une seule instruction, SELECT seul (pas d'écriture cachée), profondeur ≤ PROFONDEUR_MAX.
    # Étage 2 — liste blanche : tables et colonnes de LISTE_BLANCHE seulement, pas de * hors count(*).
    # Étage 3 — plan : EXPLAIN (FORMAT JSON), refus au-delà de SEUIL_COUT.
    # Étage 4 — exécution : SET LOCAL statement_timeout, puis la requête bornée par LIMITE.
    raise NotImplementedError("executer_sur_perimetre : à écrire (LAB 9, étape 4).")
