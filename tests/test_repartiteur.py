import asyncio
import time

import httpx
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, StreamingResponse
from starlette.routing import Route

from outils.repartiteur import creer_repartiteur
from tests.aides import servir


def amont(nom: str) -> Starlette:
    async def repondre(requete):
        entetes = {}
        if not requete.headers.get("mcp-session-id"):
            entetes["Mcp-Session-Id"] = f"s-{nom}"
        return PlainTextResponse(f"{nom}:{requete.url.path}:{(await requete.body()).decode()}", headers=entetes)

    async def flux(requete):
        async def evenements():
            yield b"data: 1\n\n"
            await asyncio.sleep(2)
            yield b"data: 2\n\n"
        return StreamingResponse(evenements(), media_type="text/event-stream")

    return Starlette(routes=[Route("/flux", flux), Route("/{chemin:path}", repondre, methods=["GET", "POST", "DELETE"])])


def test_alternance_stricte_sur_une_meme_connexion():
    with servir(amont("a")) as a, servir(amont("b")) as b, servir(creer_repartiteur(a, b)) as r:
        with httpx.Client() as http:            # une seule connexion keep-alive
            reponses = [http.post(f"{r}/mcp", content=f"n{i}") for i in range(4)]
    assert [x.headers["x-pharos-instance"] for x in reponses] == ["a", "b", "a", "b"]
    assert reponses[1].text == "b:/mcp:n1"


def test_affinite_par_session():
    with servir(amont("a")) as a, servir(amont("b")) as b, servir(creer_repartiteur(a, b, affinite=True)) as r:
        with httpx.Client() as http:
            premiere = http.post(f"{r}/mcp")
            session = premiere.headers["mcp-session-id"]
            suivantes = [http.post(f"{r}/mcp", headers={"Mcp-Session-Id": session}) for _ in range(3)]
    instance = premiere.headers["x-pharos-instance"]
    assert all(x.headers["x-pharos-instance"] == instance for x in suivantes)


def test_sans_affinite_la_session_est_ignoree():
    with servir(amont("a")) as a, servir(amont("b")) as b, servir(creer_repartiteur(a, b)) as r:
        with httpx.Client() as http:
            http.post(f"{r}/mcp")
            suivantes = [http.post(f"{r}/mcp", headers={"Mcp-Session-Id": "s-a"}) for _ in range(2)]
    assert [x.headers["x-pharos-instance"] for x in suivantes] == ["b", "a"]


def test_instance_injoignable_502():
    with servir(amont("a")) as a, servir(creer_repartiteur(a, "http://127.0.0.1:1")) as r:
        with httpx.Client() as http:
            http.post(f"{r}/mcp")
            panne = http.post(f"{r}/mcp")
    assert panne.status_code == 502 and "instance b injoignable" in panne.text
    assert panne.headers["x-pharos-instance"] == "b"


def test_instance_hors_service_502_apres_delai_connexion():
    # Adresse non routable (RFC 5737-like, réservée aux tests réseau) : la connexion ne sera ni
    # acceptée ni refusée, elle doit expirer sur le délai de connexion (5 s) et rendre le 502.
    debut = time.monotonic()
    with servir(amont("a")) as a, httpx.Client() as http:
        r = creer_repartiteur(a, "http://10.255.255.1:9")
        with servir(r) as base:
            http.post(f"{base}/mcp")
            panne = http.post(f"{base}/mcp", timeout=7)
    delai = time.monotonic() - debut
    assert panne.status_code == 502 and "instance b injoignable" in panne.text
    assert panne.headers["x-pharos-instance"] == "b"
    assert delai < 7


def test_flux_relaye_sans_tampon():
    with servir(amont("a")) as a, servir(amont("b")) as b, servir(creer_repartiteur(a, b)) as r:
        debut = time.monotonic()
        with httpx.Client(timeout=10) as http, http.stream("GET", f"{r}/flux") as flux:
            premiere = next(flux.iter_lines())
            delai = time.monotonic() - debut
    assert premiere == "data: 1" and delai < 1.5
