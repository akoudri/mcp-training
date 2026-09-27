"""make lab8-verite — la réponse exacte à la question de référence du LAB 8, calculée contre la base.

« Combien de conteneurs réfrigérés sont passés quai 3 la semaine dernière ? »
Affiche la définition de la période, le SQL de référence et, pour comparaison, le même calcul avec des
bornes lues en UTC — le piège du fuseau : un résultat faux, plausible, et indiscernable sans vérification.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import date

import asyncpg

from pharos import base

QUESTION = "Combien de conteneurs réfrigérés sont passés quai 3 la semaine dernière ?"
PERIODE = ("semaine calendaire précédant le mardi 6 octobre 2026 : du lundi 28 septembre 00:00 "
           "au dimanche 4 octobre 23:59:59, heure de Paris (Europe/Paris)")


def _bornes_paris(debut: int, fin_exclue: int) -> str:
    """La période [$debut, $fin_exclue[ (numéros de paramètres date), bornes lues à minuit heure de Paris."""
    return (f"m.horodatage >= (${debut}::date::timestamp AT TIME ZONE 'Europe/Paris')\n"
            f"  AND m.horodatage <  (${fin_exclue}::date::timestamp AT TIME ZONE 'Europe/Paris')")


SQL_REFERENCE = f"""SELECT count(*)
FROM mouvements m JOIN escales e USING (escale_id)
WHERE e.quai = $1
  AND m.type_conteneur = $2
  AND {_bornes_paris(3, 4)}"""
SQL_UTC = """SELECT count(*)
FROM mouvements m JOIN escales e USING (escale_id)
WHERE e.quai = $1 AND m.type_conteneur = $2 AND m.horodatage >= $3::date AND m.horodatage < $4::date"""
PARAMETRES = (3, "refrigere", date(2026, 9, 28), date(2026, 10, 5))


@dataclass(frozen=True)
class Verite:
    nombre: int
    nombre_utc: int


async def _compter(sql: str, *parametres) -> int:
    connexion = await asyncpg.connect(base.dsn("pharos_app"))
    try:
        async with connexion.transaction():
            await connexion.execute("SET LOCAL ROLE pharos_exploitation")
            return await connexion.fetchval(sql, *parametres)
    finally:
        await connexion.close()


async def verite() -> Verite:
    return Verite(await _compter(SQL_REFERENCE, *PARAMETRES), await _compter(SQL_UTC, *PARAMETRES))


async def compter_mouvements(date_debut: date, date_fin_exclue: date, quai: int | None = None) -> int:
    """Compte exact, bornes en heure de Paris (sert au contrôle du plafond)."""
    sql = ("SELECT count(*) FROM mouvements m JOIN escales e USING (escale_id) "
           f"WHERE {_bornes_paris(1, 2)} AND ($3::int IS NULL OR e.quai = $3)")
    return await _compter(sql, date_debut, date_fin_exclue, quai)


def main() -> int:
    try:
        v = asyncio.run(verite())
    except (OSError, asyncpg.PostgresError) as exc:
        print(f"Base injoignable ({exc.__class__.__name__}) : lancer « make lab8-base ».")
        return 1
    print(f"Question : {QUESTION}\n")
    print(f"Période  : {PERIODE}.")
    print(f"Réponse exacte : {v.nombre} conteneurs réfrigérés (type_conteneur = 'refrigere'), quai 3.\n")
    print("SQL de référence ($1=3, $2='refrigere', $3=2026-09-28, $4=2026-10-05, borne de fin exclue) :")
    print(SQL_REFERENCE)
    print(f"\nPour comparaison — mêmes dates, bornes lues en UTC (la base est réglée sur UTC) : {v.nombre_utc}.")
    print("Si votre agent a répondu ce nombre-là, regarder les paramètres de la requête dans la trace.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
