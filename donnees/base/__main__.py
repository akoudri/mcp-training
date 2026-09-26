"""python -m donnees.base [--politique] — (re)charge la base PHAROS, lancé par make lab8-base.

Sans option : rôles, schéma, données et droits, en une transaction, idempotent ; puis réapplique
labs/lab9/politique.sql s'il existe (une réinitialisation ne perd pas le travail du LAB 9).
--politique : n'applique que labs/lab9/politique.sql (make lab9-politique).
"""

from __future__ import annotations

import argparse
import os
import asyncio
import sys
from pathlib import Path

import asyncpg

from donnees.base import generer
from pharos import base

DOSSIER = Path(__file__).resolve().parent
POLITIQUE = DOSSIER.parents[1] / "labs" / "lab9" / "politique.sql"
TABLES = ("tarifs", "esc_hdr_legacy", "mouvements", "escales", "quais", "navires", "agents")
METIER = ("agents", "navires", "quais", "escales", "mouvements")

ROLES_SQL = """
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['pharos_proprietaire', 'pharos_app', 'pharos_planification',
                           'pharos_exploitation', 'pharos_agent'] LOOP
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('CREATE ROLE %I', r);
    END IF;
  END LOOP;
END $$;
ALTER ROLE pharos_proprietaire LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{mdp}';
ALTER ROLE pharos_app LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEROLE PASSWORD '{mdp}';
ALTER ROLE pharos_planification LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{mdp}';
ALTER ROLE pharos_exploitation NOLOGIN NOBYPASSRLS;
ALTER ROLE pharos_agent NOLOGIN NOBYPASSRLS;
GRANT pharos_exploitation, pharos_agent TO pharos_app;
GRANT CREATE, USAGE ON SCHEMA public TO pharos_proprietaire;
ALTER DATABASE pharos SET timezone TO 'UTC';
"""

DROITS_SQL = """
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
GRANT SELECT ON agents, navires, quais, escales, mouvements, tarifs TO pharos_exploitation;
GRANT SELECT ON agents, navires, quais, escales, mouvements TO pharos_agent;
GRANT SELECT ON agents, navires, quais, escales, mouvements TO pharos_planification;
"""


def _lignes(d: generer.Donnees) -> dict[str, list[tuple]]:
    return {
        "agents": list(d.agents.items()),
        "navires": [(n.navire_id, n.nom, n.imo, n.longueur_m, n.tirant_eau_max_m, n.pavillon, n.agent_id)
                    for n in d.navires],
        "quais": [(q.quai, q.longueur_m, q.tirant_eau_max_m, list(q.equipements), q.latitude, q.longitude)
                  for q in d.quais],
        "escales": [(e.escale_id, e.navire_id, e.quai, e.debut, e.fin, e.statut, e.tirant_eau_m, e.tarif_negocie)
                    for e in d.escales],
        "mouvements": [(m.mouvement_id, m.escale_id, m.conteneur_id, m.sens, m.horodatage, m.type_conteneur)
                       for m in d.mouvements],
        "esc_hdr_legacy": [(m.mouvement_id, m.escale_id, m.conteneur_id, m.sens, m.horodatage, m.type_conteneur)
                           for m in d.legacy],
        "tarifs": [(t.navire_id, t.grille, t.montant) for t in d.tarifs],
    }


class PolitiqueInvalide(Exception):
    """labs/lab9/politique.sql ne s'applique pas ; le message est celui de PostgreSQL."""


async def appliquer_politique(connexion: asyncpg.Connection, chemin: Path = POLITIQUE) -> bool:
    """Exécute la politique du binôme sous le propriétaire des tables (seul à pouvoir la poser), en une transaction."""
    if not chemin.exists():
        return False
    try:
        async with connexion.transaction():
            await connexion.execute("SET LOCAL ROLE pharos_proprietaire")
            await connexion.execute(chemin.read_text(encoding="utf-8"))
    except asyncpg.PostgresError as exc:
        raise PolitiqueInvalide(f"{exc.__class__.__name__}: {exc}") from exc
    return True


async def charger(dsn_admin: str | None = None, politique: Path = POLITIQUE) -> generer.Donnees:
    """Recharge tout ; les données sont validées avant la politique : une politique invalide lève
    PolitiqueInvalide, mais la base reste chargée."""
    d = generer.generer()
    connexion = await asyncpg.connect(dsn_admin or base.dsn(base.ADMIN))
    try:
        mdp = os.environ.get("PHAROS_DB_MOT_DE_PASSE", "pharos-salle-2026").replace("'", "''")
        async with connexion.transaction():
            await connexion.execute(ROLES_SQL.replace("{mdp}", mdp))
            await connexion.execute(f"DROP TABLE IF EXISTS {', '.join(TABLES)} CASCADE")
            await connexion.execute("SET LOCAL ROLE pharos_proprietaire")
            await connexion.execute((DOSSIER / "schema.sql").read_text(encoding="utf-8"))
            for table, lignes in _lignes(d).items():
                await connexion.copy_records_to_table(table, records=lignes)
            await connexion.execute(DROITS_SQL)
        await appliquer_politique(connexion, politique)
    finally:
        await connexion.close()
    return d


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="make lab8-base")
    p.add_argument("--politique", action="store_true", help="applique seulement labs/lab9/politique.sql")
    a = p.parse_args(argv)

    async def executer() -> int:
        await base.attendre()
        if a.politique:
            connexion = await asyncpg.connect(base.dsn(base.ADMIN))
            try:
                if not await appliquer_politique(connexion):
                    print(f"{POLITIQUE.relative_to(POLITIQUE.parents[2])} absent : lancer d'abord « make depart LAB=9 ».")
                    return 1
            except PolitiqueInvalide as exc:
                print(f"labs/lab9/politique.sql ne s'applique pas (rien n'a changé) : {exc}")
                return 1
            print("Politique appliquée (labs/lab9/politique.sql).")
            return 0
        try:
            d = await charger()
        except PolitiqueInvalide as exc:
            print(f"Base PHAROS chargée, mais labs/lab9/politique.sql ne s'applique pas : {exc}\n"
                  "Corriger le fichier, puis « make lab9-politique ».")
            return 1
        except asyncpg.PostgresError as exc:
            print(f"Chargement impossible : {exc.__class__.__name__}: {exc}")
            return 1
        print(f"Base PHAROS chargée : {len(d.escales)} escales, {len(d.mouvements)} mouvements, "
              f"{len(d.navires)} navires, 7 quais."
              + (" Politique du LAB 9 réappliquée." if POLITIQUE.exists() else ""))
        return 0

    return asyncio.run(executer())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
