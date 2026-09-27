"""Le périmètre de l'appelant (LAB 9) — solution de référence : connexion sous son rôle, et SQL libre en
lecture stricte, en quatre étages, le moins cher d'abord (blocs 15.1 à 15.4, slide 290).
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass

import asyncpg
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
    """Une connexion du pool, dans une transaction, sous le rôle de l'appelant et avec pharos.agent posé.

    C'est la base qui cloisonne (politique RLS de labs/lab9/politique.sql) : l'outil n'ajoute aucun WHERE."""
    if pool is None:
        raise ToolError("Base indisponible : le pool n'est pas créé.")
    async with pool.acquire() as connexion, connexion.transaction():
        await connexion.execute(f"SET LOCAL ROLE {appelant.role}")
        await connexion.execute("SELECT set_config('pharos.agent', $1, true)", appelant.agent_id or "")
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
    # Étage 1 — syntaxe.
    try:
        analyse = analyser(sql)
    except sqlglot.errors.ParseError as exc:
        journal.consigner_erreur(exc)
        raise refus("SQL illisible") from None
    if analyse.instructions != 1 or not analyse.select_seul:
        raise refus("instruction non autorisée")
    if len(analyse.tables) > PROFONDEUR_MAX:
        raise refus(f"plus de {PROFONDEUR_MAX} tables")
    # Étage 2 — liste blanche, avant toute exécution.
    if analyse.etoile or not analyse.tables <= set(LISTE_BLANCHE):
        raise refus("table ou colonne hors périmètre")
    autorisees = set().union(*(LISTE_BLANCHE[t] for t in analyse.tables))
    for table, colonne in analyse.colonnes:
        if colonne not in (LISTE_BLANCHE[table] if table in LISTE_BLANCHE else autorisees):
            raise refus("table ou colonne hors périmètre")
    async with emprunter(pool, appelant) as connexion:
        try:
            # Étage 3 — plan.
            plan = await connexion.fetchval(f"EXPLAIN (FORMAT JSON) {sql}")
            cout = (plan if isinstance(plan, list) else json.loads(plan))[0]["Plan"]["Total Cost"]
            if cout > SEUIL_COUT:
                raise refus("requête trop coûteuse : filtrer par quai ou réduire la période")
            # Étage 4 — exécution, bornée dans le temps et en lignes.
            await connexion.execute(f"SET LOCAL statement_timeout = '{TIMEOUT}'")
            lignes = await connexion.fetch(f"SELECT * FROM ({sql}) AS resultat LIMIT {LIMITE}")
        except asyncpg.PostgresError as exc:
            journal.consigner_erreur(exc)
            raise refus("exécution impossible sur ce périmètre") from None
    return [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(l).items()} for l in lignes]
