"""Chargement de pharos-db : rôles, droits, fuseau, idempotence, politique réappliquée (base réelle, PHAROS_DSN_TEST)."""

import asyncio
from datetime import date

import asyncpg
import pytest

from donnees.base import generer
from pharos import base
from tests.aides import DSN_TEST, base_requise

pytestmark = base_requise

COMPTE = """SELECT count(*) FROM mouvements m JOIN escales e USING (escale_id)
            WHERE e.quai = 3 AND m.type_conteneur = 'refrigere' AND m.horodatage >= {debut} AND m.horodatage < {fin}"""


async def _sous(role: str | None, sql: str, *args, login: str = "pharos_app"):
    c = await asyncpg.connect(base.dsn(login))
    try:
        async with c.transaction():
            if role:
                await c.execute(f"SET LOCAL ROLE {role}")
            return await c.fetchval(sql, *args)
    finally:
        await c.close()


def _refuse(role, sql, login="pharos_app"):
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(_sous(role, sql, login=login))


def test_contenu_charge(base_de_test):
    assert asyncio.run(_sous("pharos_exploitation", "SELECT count(*) FROM mouvements")) == len(base_de_test.mouvements)
    assert asyncio.run(_sous("pharos_exploitation", "SELECT count(*) FROM escales")) == len(base_de_test.escales)
    assert asyncio.run(_sous(None, "SHOW timezone")) == "UTC"


def test_piege_du_fuseau_dans_la_base(base_de_test):
    paris = COMPTE.format(debut="($1::date::timestamp AT TIME ZONE 'Europe/Paris')",
                          fin="($2::date::timestamp AT TIME ZONE 'Europe/Paris')")
    nu = COMPTE.format(debut="$1::date", fin="$2::date")
    lundis = (date(2026, 9, 28), date(2026, 10, 5))
    verite = generer.compter(base_de_test, *generer.SEMAINE_REFERENCE, quai=3, type_conteneur="refrigere")
    assert asyncio.run(_sous("pharos_exploitation", paris, *lundis)) == verite
    assert asyncio.run(_sous("pharos_exploitation", nu, *lundis)) == verite - 1


def test_droits_des_roles(base_de_test):
    _refuse(None, "SELECT count(*) FROM escales")                               # NOINHERIT : rien sans SET ROLE
    _refuse("pharos_exploitation", "SELECT count(*) FROM esc_hdr_legacy")
    _refuse("pharos_agent", "SELECT count(*) FROM tarifs")
    _refuse("pharos_exploitation", "DELETE FROM mouvements WHERE false")
    _refuse(None, "SELECT count(*) FROM tarifs", login="pharos_planification")
    assert asyncio.run(_sous("pharos_exploitation", "SELECT count(*) FROM tarifs")) == len(base_de_test.navires)
    assert asyncio.run(_sous(None, "SELECT count(*) FROM escales", login="pharos_planification")) > 0


def test_rechargement_idempotent_et_politique_reappliquee(base_de_test, tmp_path):
    from donnees.base.__main__ import charger

    politique = tmp_path / "politique.sql"
    politique.write_text("ALTER TABLE escales ENABLE ROW LEVEL SECURITY;\n"
                         "CREATE POLICY rien ON escales FOR SELECT TO pharos_agent USING (false);\n", encoding="utf-8")
    try:
        asyncio.run(charger(DSN_TEST, politique=politique))
        assert asyncio.run(_sous("pharos_agent", "SELECT count(*) FROM escales")) == 0
        assert asyncio.run(_sous("pharos_exploitation", "SELECT count(*) FROM escales")) == 0   # aucune politique pour lui
    finally:
        asyncio.run(charger(DSN_TEST, politique=tmp_path / "absente.sql"))
    assert asyncio.run(_sous("pharos_agent", "SELECT count(*) FROM escales")) == len(base_de_test.escales)


def test_politique_invalide_signalee_base_chargee(base_de_test, tmp_path):
    from donnees.base.__main__ import PolitiqueInvalide, charger

    politique = tmp_path / "politique.sql"
    politique.write_text("CREATE POLICY cassee ON escales USING (colonne_inexistante = 1);\n", encoding="utf-8")
    with pytest.raises(PolitiqueInvalide, match="colonne_inexistante"):
        asyncio.run(charger(DSN_TEST, politique=politique))
    assert asyncio.run(_sous("pharos_agent", "SELECT count(*) FROM escales")) == len(base_de_test.escales)
