"""Cloisonnement de pharos-data : deux identités, une question, deux résultats attendus — et l'exploitation voit tout.

Sans modèle, en transport mémoire, contre pharos-db ; sous les rôles applicatifs, comme le serveur en salle.
"""

QUESTION = {"date": "2026-10-08"}          # « quai 3 jeudi, toutes compagnies confondues »


async def _escales_quai_3(client) -> set[str]:
    r = await client.call_tool("requete_sql", {"sql": "SELECT escale_id FROM escales WHERE quai = 3 "
                                                      "AND debut < '2026-10-09 00:00+02' AND fin > '2026-10-08 00:00+02'"})
    return {ligne["escale_id"] for ligne in r.structured_content["lignes"]}


async def test_cloisonnement_deux_agents_et_l_exploitation(client_en_tant_que):
    async with client_en_tant_que("jeton-rance") as c:
        rance = await _escales_quai_3(c)
    async with client_en_tant_que("jeton-iroise") as c:
        iroise = await _escales_quai_3(c)
    async with client_en_tant_que("jeton-exploitation") as c:
        tout = await _escales_quai_3(c)
    assert rance == {"ESC-2026-0412"} and iroise == {"ESC-2026-0413"}
    assert tout == rance | iroise


async def test_cloisonnement_des_outils_metier(client_en_tant_que):
    async with client_en_tant_que("jeton-iroise") as c:
        risques = (await c.call_tool("escales_a_risque", QUESTION)).structured_content
        conflits = (await c.call_tool("conflits_de_creneau", QUESTION)).structured_content
    vus = {e["escale_id"] for e in risques["escales"]} | {x for c in conflits["conflits"] for x in c["escales"]}
    assert "ESC-2026-0412" not in vus                   # l'escale de Rance n'existe pas pour Iroise


async def test_contournement_refuse_sans_rien_reveler(client_en_tant_que):
    async with client_en_tant_que("jeton-rance") as c:
        r = await c.call_tool_mcp("requete_sql", {"sql": "SELECT e.tarif_negocie FROM escales e"})
    assert r.is_error and "tarif_negocie" not in r.content[0].text


# Correctif Task 11 (round 1) : fonctions non blanchies et détournement de la variable de session pharos.agent
# — au-delà des trois contournements ci-dessus (labs/lab9/contournements.md), quatre sondes qui passaient les
# quatre étages avant le correctif (liste blanche de fonctions à l'étage 2, transaction en lecture seule,
# set_config réservé à pharos_app).
CONTOURNEMENTS_AVANCES = {
    "variable_de_session": "SELECT e.escale_id FROM (SELECT set_config('pharos.agent','AG-RANCE',true) AS s) AS z, "
                          "escales e WHERE e.quai = 3 AND e.debut < '2026-10-09 00:00+02' AND e.fin > '2026-10-08 00:00+02'",
    "fonction_xml_tarifs": "SELECT query_to_xml('select grille, montant from tarifs limit 2' || "
                          "left(set_config('role','pharos_exploitation',true),0), true, true, '') AS x",
    "fonction_xml_tarif_negocie": "SELECT query_to_xml('select escale_id, tarif_negocie from escales limit 2', "
                                 "true, true, '') AS x",
    "fonction_xml_catalogue": "SELECT query_to_xml('select string_agg(table_name, '','') t from "
                             "information_schema.tables where table_schema = ''public''', true, true, '') AS x",
    "to_regclass": "SELECT to_regclass('esc_hdr_legacy')::text AS x",
    "ecriture_lo": "SELECT lo_from_bytea(0, 'x'::bytea) AS x",
    # Correctif Task 11 (round 2) : la conversion (CAST/::) vers un type système (reg*, oid) fait du CAST un
    # oracle du catalogue — existence d'une table, d'un rôle, d'une fonction, jusqu'à l'énumération par OID.
    "regclass_existence": "SELECT 'esc_hdr_legacy'::regclass::text AS x",
    "regclass_par_oid": "SELECT CAST(36907 AS regclass)::text AS x",          # OID littéral : refusé avant exécution
    "regrole_existence": "SELECT 'pharos_app'::regrole::text AS x",
    "regproc_existence": "SELECT 'query_to_xml'::regproc::text AS x",
    "regclass_vers_oid": "SELECT 'escales'::regclass::oid::int AS x",
}
INTERDITS_AVANCES = ("ESC-2026-0412", "montant", "tarif_negocie", "information_schema", "esc_hdr_legacy",
                     "tarifs", "pharos_app")


async def test_requete_sql_contournements_avances(client_en_tant_que):
    async with client_en_tant_que("jeton-iroise") as c:
        for sql in CONTOURNEMENTS_AVANCES.values():
            r = await c.call_tool_mcp("requete_sql", {"sql": sql})
            texte = r.content[0].text
            assert r.is_error, f"{sql!r} n'a pas été refusée : {texte}"
            assert not any(motif in texte for motif in INTERDITS_AVANCES), f"{sql!r} a révélé : {texte}"


async def test_requete_sql_conversions_de_type_autorisees(client_en_tant_que):
    """Contrepreuve du correctif round 2 : une conversion vers un type de donnée ordinaire (pas un type
    système) continue de fonctionner — la restriction porte sur le type cible, pas sur CAST/:: en général."""
    async with client_en_tant_que("jeton-iroise") as c:
        r = await c.call_tool("requete_sql", {"sql": "SELECT CAST(quai AS text) AS q, count(*) AS n "
                                                      "FROM escales GROUP BY quai"})
        assert r.structured_content["nombre"] > 0
        r = await c.call_tool("requete_sql", {"sql": "SELECT debut::date AS jour FROM escales"})
        assert r.structured_content["nombre"] > 0
