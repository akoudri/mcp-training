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
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

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
# Fonctions autorisées dans une requête libre : tout appel absent d'ici est refusé (étage 2), y compris tout
# exp.Anonymous — c'est-à-dire toute fonction que sqlglot ne reconnaît pas nommément dans ce dialecte
# (query_to_xml, set_config, to_regclass, lo_from_bytea, pg_read_file… autant de portes vers le catalogue,
# une autre identité ou l'écriture, qu'aucune liste blanche de tables ne peut arrêter).
# exp.Connector (AND, OR, XOR) est un pur connecteur logique, sans appel ni argument propre : chez sqlglot,
# And/Or/Xor héritent aussi de exp.Func (détail d'implémentation), sans quoi tout WHERE avec un AND serait
# refusé ; leurs opérandes restent, eux, inspectés un par un. Même chose pour exp.Exists (EXISTS (…)) : un
# prédicat sur une sous-requête, elle-même analysée comme le reste de la requête.
# exp.Cast (et sa sous-classe exp.TryCast) ne sont PAS ici : une conversion n'est permise que vers un type de
# donnée ordinaire — voir TYPES_DE_DONNEES_AUTORISEES et conversion_autorisee(). Sans cette restriction,
# '...'::regclass, ::regrole, ::regproc ou ::oid transforment le CAST en oracle du catalogue (existence d'une
# table, d'un rôle, d'une fonction — jusqu'à une énumération par OID).
FONCTIONS_AUTORISEES = (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max, exp.TimestampTrunc, exp.Extract,
                        exp.Coalesce, exp.Lower, exp.Upper, exp.Round, exp.Abs, exp.Connector, exp.Exists)
# Ce qui figure dans FONCTIONS_AUTORISEES sans être une fonction qu'on appelle : jamais cité dans le refus.
_PREDICATS = (exp.Connector, exp.Exists)
# Types de données ordinaires : tout le reste (regclass, regrole, regproc, oid, json(b), bytea, xml, tableaux,
# types utilisateur…) fait d'un CAST une porte vers le catalogue ou l'écriture, jamais une simple conversion
# de valeur.
TYPES_DE_DONNEES_AUTORISEES = {
    exp.DataType.Type.INT, exp.DataType.Type.BIGINT, exp.DataType.Type.SMALLINT,
    exp.DataType.Type.DECIMAL, exp.DataType.Type.FLOAT, exp.DataType.Type.DOUBLE,
    exp.DataType.Type.TEXT, exp.DataType.Type.VARCHAR, exp.DataType.Type.CHAR,
    exp.DataType.Type.BOOLEAN, exp.DataType.Type.DATE, exp.DataType.Type.TIME,
    exp.DataType.Type.TIMESTAMP, exp.DataType.Type.TIMESTAMPTZ, exp.DataType.Type.INTERVAL,
}


def conversion_autorisee(f: exp.Expression) -> bool:
    """Une exp.Cast (ou exp.TryCast) n'est permise que vers un type de TYPES_DE_DONNEES_AUTORISEES ;
    une exp.JSONCast est toujours refusée (elle n'existe pas pour convertir une simple valeur)."""
    if isinstance(f, exp.JSONCast):
        return False
    return isinstance(f, exp.Cast) and f.to.this in TYPES_DE_DONNEES_AUTORISEES


# Libellés lisibles, pour le message de refus, de FONCTIONS_AUTORISEES et TYPES_DE_DONNEES_AUTORISEES —
# jamais une liste à part qu'on pourrait laisser dériver : ne couvre que les entrées où le nom de classe
# sqlglot ou l'intitulé du type diffère du nom SQL usuel (date_trunc, numeric, real, double precision).
_NOM_FONCTION = {exp.TimestampTrunc: "date_trunc"}
_NOM_TYPE = {exp.DataType.Type.DECIMAL: "numeric", exp.DataType.Type.FLOAT: "real",
             exp.DataType.Type.DOUBLE: "double precision"}


def _fonctions_possibles() -> str:
    """Les noms SQL lisibles de FONCTIONS_AUTORISEES — _PREDICATS exclus (AND/OR/XOR, EXISTS) : jamais une
    fonction appelable par le modèle."""
    return ", ".join(sorted({_NOM_FONCTION.get(f, f.key) for f in FONCTIONS_AUTORISEES if f not in _PREDICATS}))


def _conversions_possibles() -> str:
    """Les cibles de conversion lisibles (« ::type ») de TYPES_DE_DONNEES_AUTORISEES."""
    return ", ".join(sorted(f"::{_NOM_TYPE.get(t, t.value.lower())}" for t in TYPES_DE_DONNEES_AUTORISEES))


# Le schéma de la liste blanche, tel que sqlglot le lit pour résoudre les colonnes (le type n'y sert pas).
_SCHEMA = {table: dict.fromkeys(colonnes, "text") for table, colonnes in LISTE_BLANCHE.items()}


def _tri_par_alias(colonne: exp.Column) -> bool:
    """« ORDER BY n », nu, dans l'ORDER BY de la requête elle-même, n alias de sa liste SELECT : le seul endroit
    où PostgreSQL lit un alias de sortie. Ailleurs — WHERE, GROUP BY, HAVING, OVER (ORDER BY …), ou dans une
    expression (« ORDER BY -n ») — il lit d'abord la colonne d'entrée du même nom, éventuellement cachée."""
    tri = colonne.parent
    return (not colonne.table and isinstance(tri, exp.Ordered) and isinstance(tri.parent, exp.Order)
            and colonne.name in getattr(tri.parent.parent, "named_selects", ()))


def colonnes_resolues(arbre: exp.Expression) -> bool:
    """Chaque colonne de la requête désigne une colonne de la liste blanche d'une table de sa portée (ou une
    colonne de sortie d'une sous-requête, d'une CTE, d'un alias de SELECT en ORDER BY) — résolution structurelle,
    portée par portée, par l'optimiseur de sqlglot, sur un schéma qui ne connaît QUE la liste blanche.

    Pourquoi pas un simple contrôle des noms : pour PostgreSQL, un nom non qualifié qui n'est la colonne d'aucune
    table mais l'alias d'une table est une référence de LIGNE ENTIÈRE. « SELECT nom::text FROM escales nom » rend
    toute la ligne d'escale, tarif_negocie compris, alors que « nom » est une colonne autorisée (de navires).
    Ici, un nom qui ne se résout pas en colonne autorisée — ligne entière, colonne cachée, alias ambigu — est refusé."""
    arbre = arbre.copy()
    for colonne in arbre.find_all(exp.Column):
        colonne.meta["non_qualifiee"] = not colonne.table
        # Un alias de SELECT repris ailleurs qu'en _tri_par_alias() : sqlglot y lirait l'alias, PostgreSQL la
        # colonne d'entrée du même nom. Écrire GROUP BY 1 plutôt que GROUP BY <alias>.
        select = colonne.parent_select
        if (not colonne.table and select is not None and not _tri_par_alias(colonne)
                and colonne.name in {e.alias for e in select.expressions if isinstance(e, exp.Alias)}):
            return False
    # Renommer les colonnes d'une table (« escales AS e(a, b, …, h) ») nomme aussi ses colonnes cachées, par position.
    if any(isinstance(t.args.get("alias"), exp.TableAlias) and t.args["alias"].columns
           for t in arbre.find_all(exp.Table)):
        return False
    # NATURAL JOIN : PostgreSQL joint sur les colonnes communes de la VRAIE table, colonnes cachées comprises
    # (« escales NATURAL JOIN (SELECT 56000.00 AS tarif_negocie) v » filtre sur tarif_negocie), là où sqlglot ne
    # connaît que la liste blanche. Écrire la jointure : JOIN … USING (colonne) ou JOIN … ON.
    if any((j.args.get("method") or "").upper() == "NATURAL" for j in arbre.find_all(exp.Join)):
        return False
    try:
        qualify(arbre, schema=_SCHEMA, dialect="postgres", infer_schema=False, validate_qualify_columns=True)
    except sqlglot.errors.SqlglotError:
        return False
    # Resté sans table après résolution (sqlglot ne valide pas tout, HAVING par exemple) : refusé, sauf l'alias
    # de sortie en ORDER BY.
    if any(not c.table and not _tri_par_alias(c) for c in arbre.find_all(exp.Column)):
        return False
    for portee in traverse_scope(arbre):
        for colonne in portee.columns:
            if colonne.table not in portee.sources and colonne.meta.get("non_qualifiee"):
                return False      # corrélation implicite vers une requête englobante : la qualifier (e.escale_id)
    return True


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
    colonnes_resolues: bool               # voir colonnes_resolues() : chaque colonne est une colonne autorisée
    etoile: bool                          # un * ailleurs que dans count(*)
    fonction_interdite: bool              # un appel absent de FONCTIONS_AUTORISEES (dont tout exp.Anonymous),
                                          # ou une conversion refusée par conversion_autorisee()
    table_hors_perimetre: bool            # une table qualifiée par un schéma, ou du catalogue (pg_*, information_schema)


def analyser(sql: str) -> Analyse:
    """Analyse syntaxique (dialecte PostgreSQL). Lève sqlglot.errors.SqlglotError si le SQL est illisible."""
    arbres = [a for a in sqlglot.parse(sql, read="postgres") if a is not None]
    racine = arbres[0] if arbres else exp.Select()
    ecritures = (exp.Delete, exp.Insert, exp.Update, exp.Drop, exp.Create, exp.Alter, exp.Command, exp.Merge)
    ctes = {c.alias_or_name for a in arbres for c in a.find_all(exp.CTE)}
    alias = {}
    tables = set()
    table_hors_perimetre = False
    for a in arbres:
        for t in a.find_all(exp.Table):
            if t.name in ctes:
                continue
            tables.add(t.name)
            alias[t.alias_or_name] = t.name
            if t.db or t.name.lower().startswith("pg_") or t.name.lower() == "information_schema":
                table_hors_perimetre = True
    colonnes = {(alias.get(c.table, c.table) if c.table else None, c.name)
                for a in arbres for c in a.find_all(exp.Column) if not isinstance(c.this, exp.Star)}
    etoile = any(isinstance(s, exp.Star) and not isinstance(s.parent, exp.Count)
                 for a in arbres for s in a.find_all(exp.Star))
    fonction_interdite = any(
        not (conversion_autorisee(f) if isinstance(f, exp.Cast) else isinstance(f, FONCTIONS_AUTORISEES))
        for a in arbres for f in a.find_all(exp.Func))
    return Analyse(len(arbres), isinstance(racine, exp.Select) and not any(
        isinstance(n, ecritures) for a in arbres for n in a.walk()), tables, colonnes,
        len(arbres) == 1 and colonnes_resolues(racine), etoile, fonction_interdite, table_hors_perimetre)


def refus(etage: str) -> ToolError:
    """Le message uniforme des refus : l'étage, puis la liste blanche des tables/colonnes, des fonctions et
    des conversions possibles — rien de ce qui existe vraiment. Toujours dérivé de LISTE_BLANCHE,
    FONCTIONS_AUTORISEES et TYPES_DE_DONNEES_AUTORISEES : le modèle peut se corriger sans qu'aucun nom
    refusé (table, colonne, fonction, type) ne soit jamais cité."""
    disponibles = " ; ".join(f"{t} ({', '.join(sorted(c))})" for t, c in sorted(LISTE_BLANCHE.items()))
    return ToolError(f"Requête refusée ({etage}). Seules des lectures SELECT sur ces tables et colonnes sont "
                     f"possibles : {disponibles}. Fonctions possibles : {_fonctions_possibles()}. "
                     f"Conversions possibles : {_conversions_possibles()}.")


async def executer_sur_perimetre(pool, sql: str, appelant: Identite) -> list[dict]:
    """Bloc 15.2 : syntaxe, liste blanche, plan, exécution — chaque étage refuse avec refus(...).

    Une erreur brute de la base ne sort jamais : journal.consigner_erreur(exc), puis refus(...)."""
    # Étage 1 — syntaxe.
    try:
        analyse = analyser(sql)
    except sqlglot.errors.SqlglotError as exc:
        journal.consigner_erreur(exc)
        raise refus("SQL illisible") from None
    if analyse.instructions != 1 or not analyse.select_seul:
        raise refus("instruction non autorisée")
    if len(analyse.tables) > PROFONDEUR_MAX:
        raise refus(f"plus de {PROFONDEUR_MAX} tables")
    # Étage 2 — liste blanche, avant toute exécution : tables, colonnes, et les fonctions appelables.
    if analyse.etoile or analyse.table_hors_perimetre or not analyse.tables <= set(LISTE_BLANCHE):
        raise refus("table ou colonne hors périmètre")
    if analyse.fonction_interdite:
        raise refus("fonction non autorisée")
    if not analyse.colonnes_resolues:
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
