"""Vérificateur du LAB 9 : sur un serveur jouet dont on active les défauts un par un, et sur la politique en base."""

import asyncio
from pathlib import Path

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from donnees.base import generer
from outils.verifier.commun import Etat
from pharos import autorisation, journal
from tests.aides import DSN_TEST, base_requise, servir

pytestmark = base_requise
REFUS = "Requête refusée. Seules des lectures SELECT sur escales, mouvements, navires et quais sont possibles."
POLITIQUE_ESCALES = """
ALTER TABLE escales ENABLE ROW LEVEL SECURITY;
ALTER TABLE mouvements ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS e ON escales;
CREATE POLICY e ON escales FOR SELECT TO pharos_exploitation USING (true);
DROP POLICY IF EXISTS em ON mouvements;
CREATE POLICY em ON mouvements FOR SELECT TO pharos_exploitation USING (true);
DROP POLICY IF EXISTS a ON escales;
CREATE POLICY a ON escales FOR SELECT TO pharos_agent
    USING (navire_id IN (SELECT navire_id FROM navires WHERE agent_id = {agent}));
"""
DYNAMIQUE = "current_setting('pharos.agent', true)"
MOUVEMENTS_FILTRES = """
DROP POLICY IF EXISTS am ON mouvements;
CREATE POLICY am ON mouvements FOR SELECT TO pharos_agent USING (escale_id IN (SELECT escale_id FROM escales));
"""
POLITIQUE_AGENT = POLITIQUE_ESCALES.format(agent=DYNAMIQUE) + MOUVEMENTS_FILTRES
# Deux politiques fautives que seul le critère décisif peut voir : un agent écrit en dur, des mouvements non filtrés.
POLITIQUE_EN_DUR = POLITIQUE_ESCALES.format(agent="'AG-IROISE'") + MOUVEMENTS_FILTRES
POLITIQUE_MOUVEMENTS_OUVERTS = POLITIQUE_ESCALES.format(agent=DYNAMIQUE) + """
DROP POLICY IF EXISTS am ON mouvements;
CREATE POLICY am ON mouvements FOR SELECT TO pharos_agent USING (true);
"""
QUAI_3_JEUDI = {None: ["ESC-2026-0412", "ESC-2026-0413"], "AG-RANCE": ["ESC-2026-0412"], "AG-IROISE": ["ESC-2026-0413"]}


def jouet(*, parametre_identite=False, sans_auth=False, fuite=False, fuite_rance=False,
          sans_journal=False) -> FastMCP:
    d = generer.generer()
    [a, b, m] = d.conflits_jeudi[0]
    [c, e, n] = d.conflits_jeudi[1]
    mcp = FastMCP("jouet", auth=None if sans_auth else autorisation.verificateur(),
                  middleware=[] if sans_journal else [journal.Journal("pharos-data")])

    def agent():
        return autorisation.identite().agent_id

    @mcp.tool
    def escales_a_risque(date: str) -> dict:
        """Risques."""
        vent = {"escale_id": "ESC-2026-0412", "criteres": [
            {"critere": "tirant_eau", "detail": {"tirant_eau_m": 12.9, "quai_max_m": 13.5, "marge_m": 1.0}},
            {"critere": "conflit_creneau", "detail": {"escale_id": "ESC-2026-0413", "chevauchement_min": 60}}]}
        return {"definition_version": "2.0", "escales": [] if agent() == "AG-IROISE" else [vent]}

    @mcp.tool
    def conflits_de_creneau(date: str) -> dict:
        """Conflits."""
        if agent() is not None:
            return {"conflits": []}
        return {"conflits": [{"escales": [a, b], "chevauchement_min": m}, {"escales": [c, e], "chevauchement_min": n}]}

    @mcp.tool
    def requete_mouvements(date_debut: str, date_fin: str, quai: int | None = None) -> dict:
        """Mouvements."""
        if quai is None:          # comme pharos-data : sans quai, une semaine dépasse le plafond de 200 lignes
            raise ToolError("754 mouvements correspondent : au-delà du plafond de 200 lignes, rien n'est rendu.")
        if fuite_rance:           # un filtre d'outil oublié : un mouvement de l'escale de Rance au quai 3, jeudi
            return {"mouvements": [{"mouvement_id": "MVT-000001", "escale_id": "ESC-2026-0412"}]}
        return {"mouvements": []}

    if parametre_identite:
        @mcp.tool
        def escales_de(agent_id: str) -> list:
            """Escales d'un agent."""
            return []

    @mcp.tool
    def requete_sql(sql: str) -> dict:
        """SQL."""
        from outils.verifier import lab9

        if sql == lab9.QUAI_3_JEUDI:
            return {"lignes": [{"escale_id": e} for e in QUAI_3_JEUDI[agent()]]}
        if sql == "SELECT escale_id FROM escales":
            return {"lignes": [{"escale_id": "ESC-2026-0413"}]}
        if fuite and "armateur" in sql:
            raise ToolError('column "e.armateur" does not exist')
        raise ToolError(REFUS)

    return mcp


@pytest.fixture
def racine(tmp_path, monkeypatch):
    """Une racine de binôme dont tests/pharos_data contient un test de cloisonnement qui passe."""
    from outils.verifier import lab9

    (tmp_path / "tests" / "pharos_data").mkdir(parents=True)
    (tmp_path / "tests" / "pharos_data" / "test_c.py").write_text("def test_cloisonnement():\n    assert True\n")
    monkeypatch.setattr(lab9, "RACINE", tmp_path)
    monkeypatch.setenv("PHAROS_LOGS", str(tmp_path / "logs"))
    return tmp_path


def _politique(tmp_path, sql: str | None):
    from donnees.base.__main__ import charger

    chemin = tmp_path / "politique.sql"
    if sql is not None:
        chemin.write_text(sql, encoding="utf-8")
    asyncio.run(charger(DSN_TEST, politique=chemin))


@pytest.fixture
def politique(base_de_test, tmp_path):
    _politique(tmp_path, POLITIQUE_AGENT)
    yield
    _politique(tmp_path / "rien", None)


async def _rapport(mcp):
    from outils.verifier import lab9

    with servir(mcp.http_app(path="/mcp", json_response=True)) as url:
        return await lab9.v.executer(url=f"{url}/mcp", sans_modele=True)


def _echecs(rapport) -> dict[str, str]:
    return {r.libelle: r.detail for r in rapport.resultats if r.etat is Etat.ECHEC}


async def test_jouet_correct(politique, racine):
    rapport = await _rapport(jouet())
    assert _echecs(rapport) == {}, rapport.texte()


async def test_identite_en_parametre_et_serveur_sans_jeton(politique, racine):
    echecs = _echecs(await _rapport(jouet(parametre_identite=True)))
    assert any("escales_de(agent_id)" in d for d in echecs.values()), echecs
    echecs = _echecs(await _rapport(jouet(sans_auth=True)))
    assert any("401 attendu" in d for d in echecs.values()), echecs


async def test_message_qui_fuit(politique, racine):
    echecs = _echecs(await _rapport(jouet(fuite=True)))
    [detail] = [d for l, d in echecs.items() if "contournements" in l]
    assert "armateur" in detail and "does not exist" in detail


async def test_protection_absente_de_la_base(base_de_test, racine, tmp_path):
    try:
        await asyncio.to_thread(_politique, tmp_path, "SELECT 1;")      # aucune RLS : l'agent voit tout
        echecs = _echecs(await _rapport(jouet()))
        [detail] = [d for l, d in echecs.items() if "décisif" in l]
        assert "hors de son périmètre" in detail
        await asyncio.to_thread(_politique, tmp_path, "ALTER TABLE escales ENABLE ROW LEVEL SECURITY;")  # sans agent
        echecs = _echecs(await _rapport(jouet()))
        [detail] = [d for l, d in echecs.items() if "décisif" in l]
        assert "ne rend aucune escale" in detail
    finally:
        await asyncio.to_thread(_politique, tmp_path / "rien", None)


async def test_fuite_d_une_escale_de_rance_vers_iroise(politique, racine):
    echecs = _echecs(await _rapport(jouet(fuite_rance=True)))
    [detail] = [d for l, d in echecs.items() if "ne voit aucune escale de Rance" in l]
    assert "ESC-2026-0412 (requete_mouvements)" in detail


@pytest.mark.parametrize(("sql", "attendu"), [(POLITIQUE_EN_DUR, "jamais un agent écrit en dur"),
                                              (POLITIQUE_MOUVEMENTS_OUVERTS, "la table mouvements")],
                         ids=["agent_en_dur", "mouvements_ouverts"])
async def test_politique_fautive_vue_par_le_critere_decisif(base_de_test, racine, tmp_path, sql, attendu):
    try:
        await asyncio.to_thread(_politique, tmp_path, sql)
        echecs = _echecs(await _rapport(jouet()))
        [detail] = [d for l, d in echecs.items() if "décisif" in l]
        assert attendu in detail
    finally:
        await asyncio.to_thread(_politique, tmp_path / "rien", None)


async def test_refus_absents_du_journal_malgre_un_historique(politique, racine):
    """Des refus d'une séance précédente dans logs/pharos-data.jsonl ne comptent pas pour ce serveur-ci."""
    import json

    (racine / "logs").mkdir()
    ancien = json.dumps({"outil": "requete_sql", "issue": "refus"}) + "\n"
    (racine / "logs" / "pharos-data.jsonl").write_text(ancien * 50, encoding="utf-8")
    echecs = _echecs(await _rapport(jouet(sans_journal=True)))
    [detail] = [d for l, d in echecs.items() if "contournements" in l]
    assert "logs/pharos-data.jsonl" in detail


async def test_suite_absente(politique, racine):
    import shutil

    shutil.rmtree(racine / "tests")
    echecs = _echecs(await _rapport(jouet()))
    assert any("tests/pharos_data absent" in d for d in echecs.values()), echecs


def test_gabarit_politique_sans_agent_et_perimetre_a_ecrire():
    texte = Path("gabarits/lab09/labs/lab9/politique.sql").read_text(encoding="utf-8")
    assert "pharos.agent" in texte and "À ÉCRIRE" in texte
    assert "CREATE POLICY agent_escales" not in texte.replace("-- CREATE POLICY agent_escales", "")
