"""Vérificateur du LAB 8 : sur le gabarit, et sur un serveur jouet dont on active les défauts un par un."""

from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

import asyncpg
import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from outils.construire_etats import superposer
from outils.verifier.commun import Etat
from pharos import base
from tests.aides import base_requise, charger_module, client_minimal, importer_client, servir

pytestmark = base_requise


def jouet(*, utc=False, pool_par_appel=False, sans_plafond=False, schema="Fuseau Europe/Paris ; tirants en mètres.",
          sans_sql=False) -> FastMCP:
    etat = {}
    parametres = {"dsn": base.dsn("pharos_app"), "server_settings": {"application_name": "pharos-data"}}

    @asynccontextmanager
    async def cycle(serveur):
        if not pool_par_appel:
            etat["pool"] = await asyncpg.create_pool(min_size=1, max_size=2, **parametres)
        yield {}
        if "pool" in etat:
            await etat.pop("pool").close()

    mcp = FastMCP("jouet", lifespan=cycle)

    @mcp.resource("pharos://schema/mouvements")
    def dictionnaire() -> str:
        return schema

    @mcp.tool
    async def requete_mouvements(date_debut: date, date_fin: date, quai: int | None = None,
                                 type_conteneur: str | None = None, sens: str | None = None) -> dict:
        """Mouvements."""
        borne = "$%d::date" if utc else "($%d::date::timestamp AT TIME ZONE 'Europe/Paris')"
        sql = (f"SELECT count(*) FROM mouvements m JOIN escales e USING (escale_id) WHERE m.horodatage >= {borne % 1} "
               f"AND m.horodatage < {borne % 2} AND ($3::int IS NULL OR e.quai = $3) "
               f"AND ($4::text IS NULL OR m.type_conteneur = $4)")
        args = [date_debut, date_fin + timedelta(days=1), quai, type_conteneur]
        pool = etat.get("pool") or await asyncpg.create_pool(min_size=1, max_size=1, **parametres)
        try:
            async with pool.acquire() as cx, cx.transaction():
                await cx.execute("SET LOCAL ROLE pharos_exploitation")
                n = await cx.fetchval(sql, *args)
        finally:
            if pool_par_appel:
                await pool.close()
        if n > 200 and not sans_plafond:
            raise ToolError(f"{n} lignes, plafond 200 : préciser un quai ou réduire la période.")
        return {"nombre": n} if sans_sql else {"nombre": n, "sql": sql, "parametres": [str(a) for a in args]}

    return mcp


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    return client_minimal(tmp_path_factory.mktemp("client"))


@pytest.fixture
def mesures(tmp_path, monkeypatch):
    from outils.verifier import lab8

    chemin = tmp_path / "mesures.md"
    chemin.write_text("| Réponse obtenue | 16 |\n", encoding="utf-8")
    monkeypatch.setattr(lab8, "MESURES", chemin)
    return chemin


async def _rapport(mcp, dossier_client):
    from outils.verifier import lab8

    with importer_client(dossier_client), servir(mcp.http_app(path="/mcp", json_response=True)) as url:
        return await lab8.v.executer(url=f"{url}/mcp", sans_modele=True)


def _echecs(rapport) -> list[str]:
    return [r.libelle for r in rapport.resultats if r.etat is Etat.ECHEC]


async def test_jouet_correct(base_de_test, mesures, client):
    rapport = await _rapport(jouet(), client)
    assert _echecs(rapport) == [], rapport.texte()


async def test_bornes_en_utc(base_de_test, mesures, client):
    rapport = await _rapport(jouet(utc=True), client)
    echecs = {r.libelle: r.detail for r in rapport.resultats if r.etat is Etat.ECHEC}
    exacte = next(d for libelle, d in echecs.items() if "exacte" in libelle)
    assert "bornes en UTC" in exacte, rapport.texte()
    assert all("exacte" in l or "plafond" in l for l in echecs)       # le compte de septembre est faux aussi


async def test_pool_par_appel(base_de_test, mesures, client):
    rapport = await _rapport(jouet(pool_par_appel=True), client)
    assert [e for e in _echecs(rapport) if "pool" in e], rapport.texte()


async def test_sans_plafond_ni_sql(base_de_test, mesures, client):
    rapport = await _rapport(jouet(sans_plafond=True, sans_sql=True), client)
    echecs = _echecs(rapport)
    assert any("plafond" in e for e in echecs) and any("décisif" in e for e in echecs), rapport.texte()


async def test_schema_sans_fuseau_et_table_cachee(base_de_test, mesures, client):
    rapport = await _rapport(jouet(schema="Voir aussi esc_hdr_legacy."), client)
    echecs = _echecs(rapport)
    assert any("schéma" in e for e in echecs) and any("esc_hdr_legacy" in e for e in echecs), rapport.texte()


async def test_mesure_non_consignee(base_de_test, mesures, client):
    mesures.write_text("| Réponse obtenue | |\n", encoding="utf-8")
    rapport = await _rapport(jouet(), client)
    echecs = [r for r in rapport.resultats if r.etat is Etat.ECHEC]
    assert len(echecs) == 1 and "consigner" in echecs[0].detail, rapport.texte()


async def test_gabarit_tout_rouge_sauf_le_nom(base_de_test, tmp_path, mesures):
    superposer(tmp_path, Path("gabarits"), Path("/nulle-part"), 8)
    serveur = charger_module(tmp_path / "serveurs" / "pharos_data" / "serveur.py", "gabarit_lab8_serveur")
    rapport = await _rapport(serveur.mcp, tmp_path / "client")
    ok = [r.libelle for r in rapport.resultats if r.etat is Etat.OK]
    assert ok == ["requete_mouvements est au catalogue, sous le nom du brief.",
                  "esc_hdr_legacy n'apparaît nulle part dans ce qui est exposé."], rapport.texte()


async def test_serveur_absent():
    from outils.verifier import lab8

    rapport = await lab8.v.executer(url="http://127.0.0.1:1/mcp", sans_modele=True)
    assert "make lab8-base puis make lab8-up" in rapport.texte()
