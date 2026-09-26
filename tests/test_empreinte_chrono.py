import json
import sys

from outils import chrono, empreinte
from tests.aides import serveur_demo


async def test_empreinte_triee_et_serialisable():
    e = await empreinte.empreinte_de(serveur_demo())
    assert [x["name"] for x in e] == ["echec", "etat"]
    assert set(e[1]) == {"name", "description", "inputSchema"}
    assert json.loads(empreinte.serialiser(e)) == e


def test_chrono(capsys):
    assert chrono.main([sys.executable, "-c", "pass"]) == 0
    assert "Durée :" in capsys.readouterr().out
    assert chrono.main([sys.executable, "-c", "raise SystemExit(3)"]) == 3
