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


# Au-delà des trois contournements du brief (labs/lab9/contournements.md) : des requêtes qui passeraient une
# liste blanche de tables et de colonnes vérifiée nom par nom — fonctions qui exécutent un second SELECT ou
# écrivent, variable de session pharos.agent, conversions vers les types du catalogue, référence de ligne
# entière. Chacune doit être refusée sans rien révéler.
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
    # La conversion (CAST/::) vers un type système (reg*, oid) fait du CAST un oracle du catalogue —
    # existence d'une table, d'un rôle, d'une fonction, jusqu'à l'énumération par OID.
    "regclass_existence": "SELECT 'esc_hdr_legacy'::regclass::text AS x",
    "regclass_par_oid": "SELECT CAST(36907 AS regclass)::text AS x",          # OID littéral : refusé avant exécution
    "regrole_existence": "SELECT 'pharos_app'::regrole::text AS x",
    "regproc_existence": "SELECT 'query_to_xml'::regproc::text AS x",
    "regclass_vers_oid": "SELECT 'escales'::regclass::oid::int AS x",
    # Un alias de table nommé comme une colonne autorisée d'une AUTRE table : pour PostgreSQL, « nom » n'étant
    # la colonne d'aucune table de la requête, c'est la ligne entière de l'escale — tarif_negocie compris.
    "ligne_entiere_escale": "SELECT nom::text FROM escales nom WHERE navire_id IN (SELECT navire_id FROM navires)",
    "ligne_entiere_navire": "SELECT quai::text FROM navires quai WHERE navire_id IN (SELECT navire_id FROM escales)",
    # Colonne cachée lue là où sqlglot ne la rattache à aucune table (HAVING), ou renommée par position.
    "colonne_cachee_having": "SELECT quai FROM escales GROUP BY quai HAVING max(tarif_negocie) > 50000",
    "colonnes_renommees": "SELECT h FROM escales AS e(a, b, c, d, f, g, i, h)",
    # Un alias de sortie repris hors de l'ORDER BY final : PostgreSQL y lit la colonne d'entrée du même nom.
    "alias_masquant_une_colonne": "SELECT quai AS tarif_negocie, count(*) OVER (ORDER BY tarif_negocie) AS n "
                                  "FROM escales",
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
            # Le refus dit aussi ce qui est possible : le modèle peut se corriger.
            assert "Fonctions possibles" in texte and "Conversions possibles" in texte, texte


async def test_requete_sql_conversions_de_type_autorisees(client_en_tant_que):
    """Contrepreuve : une conversion vers un type de donnée ordinaire (pas un type système) continue de
    fonctionner — la restriction porte sur le type cible, pas sur CAST/:: en général."""
    async with client_en_tant_que("jeton-iroise") as c:
        r = await c.call_tool("requete_sql", {"sql": "SELECT CAST(quai AS text) AS q, count(*) AS n "
                                                      "FROM escales GROUP BY quai"})
        assert r.structured_content["nombre"] > 0
        r = await c.call_tool("requete_sql", {"sql": "SELECT debut::date AS jour FROM escales"})
        assert r.structured_content["nombre"] > 0


REQUETES_LEGITIMES = {
    "jointure_using": "SELECT e.escale_id, nom FROM escales e JOIN navires USING (navire_id)",
    "tri_par_alias": "SELECT quai, count(*) AS n FROM escales GROUP BY quai ORDER BY n DESC",
    "exists": "SELECT n.nom FROM navires n WHERE EXISTS "
              "(SELECT 1 FROM escales e WHERE e.navire_id = n.navire_id AND e.quai = 3)",
    "sous_requete": "SELECT x FROM (SELECT quai AS x FROM escales) s",
    "date_trunc": "SELECT date_trunc('day', debut) AS jour, count(*) AS n FROM escales GROUP BY 1",
}


async def test_requete_sql_requetes_legitimes(client_en_tant_que):
    """Contrepreuve de la résolution des colonnes : jointures, alias de sortie en ORDER BY, EXISTS,
    sous-requêtes et agrégats restent permis."""
    async with client_en_tant_que("jeton-iroise") as c:
        for sql in REQUETES_LEGITIMES.values():
            r = await c.call_tool_mcp("requete_sql", {"sql": sql})
            assert not r.is_error, f"{sql!r} refusée : {r.content[0].text}"
            assert r.structured_content["nombre"] > 0, sql
