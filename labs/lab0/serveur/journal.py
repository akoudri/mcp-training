"""Journal brut du trafic JSON-RPC, une ligne JSON par message (extension C du LAB 0)."""

from __future__ import annotations

import json
from pathlib import Path

from pharos import horloge


class JournalJSONL:
    def __init__(self, app, chemin: Path):
        self.app = app
        self.chemin = Path(chemin)

    def _ecrire(self, sens: str, brut: bytes) -> None:
        textes = []
        if brut.lstrip().startswith((b"{", b"[")):
            textes.append(brut.decode("utf-8", "replace"))
        else:
            textes += [l[5:].strip() for l in brut.decode("utf-8", "replace").splitlines() if l.startswith("data:")]
        for texte in textes:
            try:
                message = json.loads(texte)
            except json.JSONDecodeError:
                continue
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            with self.chemin.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"horodatage": horloge.maintenant().isoformat(), "sens": sens,
                                    "message": message}, ensure_ascii=False) + "\n")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        recu, emis = bytearray(), bytearray()

        async def recevoir():
            message = await receive()
            if message["type"] == "http.request":
                recu.extend(message.get("body", b""))
                if not message.get("more_body"):
                    self._ecrire("recu", bytes(recu))
            return message

        async def envoyer(message):
            if message["type"] == "http.response.body":
                emis.extend(message.get("body", b""))
                if not message.get("more_body"):
                    self._ecrire("emis", bytes(emis))
            await send(message)

        await self.app(scope, recevoir, envoyer)
