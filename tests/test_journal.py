import json

import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from labs.lab0.serveur.journal import JournalJSONL


async def json_rpc(request):
    corps = await request.json()
    return JSONResponse({"jsonrpc": "2.0", "id": corps["id"], "result": {"ok": True}})


async def sse(request):
    corps = await request.json()
    message = json.dumps({"jsonrpc": "2.0", "id": corps["id"], "result": {"flux": True}})
    return Response(f"event: message\ndata: {message}\n\n", media_type="text/event-stream")


def app_journalisee(chemin):
    return JournalJSONL(Starlette(routes=[Route("/mcp", json_rpc, methods=["POST"]),
                                          Route("/sse", sse, methods=["POST"])]), chemin=chemin)


async def test_journalise_requete_et_reponse(tmp_path):
    chemin = tmp_path / "logs" / "journal.jsonl"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_journalisee(chemin)), base_url="http://t") as c:
        await c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        await c.post("/sse", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call"})
    lignes = [json.loads(l) for l in chemin.read_text().splitlines()]
    assert [(l["sens"], l["message"]["id"]) for l in lignes] == [("recu", 1), ("emis", 1), ("recu", 2), ("emis", 2)]
    assert lignes[0]["message"]["method"] == "tools/list"
    assert lignes[3]["message"]["result"] == {"flux": True}
    assert lignes[0]["horodatage"].startswith("2026-10-06T")


async def test_corps_non_json_ignore_sans_planter(tmp_path):
    async def texte(request):
        await request.body()
        return Response("pas du json non plus", media_type="text/plain")
    chemin = tmp_path / "journal.jsonl"
    app = JournalJSONL(Starlette(routes=[Route("/brut", texte, methods=["POST"])]), chemin=chemin)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/brut", content=b"pas du json")
    assert r.status_code == 200
    assert not chemin.exists()
