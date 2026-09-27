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
