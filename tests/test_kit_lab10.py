"""Kit du LAB 10 : gabarit de pharos-ops (trois outils bruts, clé hors des paramètres), cibles et démarrage."""

import re
from pathlib import Path

import httpx
import pytest
from fastmcp import Client

from outils import labs
from serveurs.mocks import app as mocks
from tests.aides import charger_module, client_minimal, importer_client


async def test_gabarit_trois_outils_bruts():
    serveur = charger_module(Path("gabarits/lab10/serveurs/pharos_ops/serveur.py"), "gabarit_lab10")
    async with Client(serveur.mcp) as c:
        outils = {o.name: o for o in await c.list_tools()}
    assert set(outils) == {"meteo_creneau", "meteo_alerte", "navire_par_nom"}
    assert set(outils["meteo_creneau"].input_schema["properties"]) == {"quais", "debut", "fin"}
    assert set(outils["meteo_alerte"].input_schema["properties"]) == {"quai", "horizon_h"}
    assert set(outils["navire_par_nom"].input_schema["properties"]) == {"nom"}
    assert serveur.POSITIONS[3] == (48.3799, -4.4839) and len(serveur.POSITIONS) == 7


def test_gabarit_sans_cle_ni_solution():
    texte = Path("gabarits/lab10/serveurs/pharos_ops/serveur.py").read_text(encoding="utf-8")
    assert "meteo-salle-2026" not in texte and "METEO_CLE" not in texte     # la clé : pharos.meteo, l'environnement
    assert "incomplets" not in texte.split('"""', 2)[2]                     # étape 4 : à écrire


def test_depart_et_cibles_du_lab10():
    assert (labs.DEPARTS[10], labs.SORTIES[10]) == ("da3-fin", "is2-fin")
    assert labs.DEMARRAGE[10] == ["lab10-mocks", "lab10-up"] and labs.PORTS_PRETS[10] == [8103]
    cibles = set(re.findall(r"^([a-z0-9-]+):", Path("mk/lab10.mk").read_text(encoding="utf-8"), re.MULTILINE))
    assert {"lab10-mocks", "lab10-appels", "lab10-scaffold", "lab10-up", "lab10-note-panne", "lab10-verifier"} <= cibles


def test_variables_de_salle_pour_tous_les_services_python():
    for fichier in ("compose.yaml", "compose/commun/base.yaml"):
        texte = Path(fichier).read_text(encoding="utf-8")
        for variable in ("METEO_URL", "METEO_CLE", "REFERENTIEL_URL", "CANAL_URL"):
            assert f"{variable}:" in texte, (fichier, variable)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    return client_minimal(tmp_path_factory.mktemp("client"))


def test_outils_lab10_decrire_et_durees():
    from outils import lab10

    assert lab10.decrire(mocks.DEFAUTS) == "mode nominal"
    assert "lenteur de 8 s sur la météo des quais 5, 7" in lab10.decrire({**mocks.DEFAUTS, "lenteur_s": 8.0})
    assert lab10._secondes("8s") == lab10._secondes("8") == 8.0 and lab10._quais("5,7") == [5, 7]


def test_ecrire_note(tmp_path, client):
    from outils import lab10

    with importer_client(client):
        from pharos_client.trace import Enregistrement

        trace = [Enregistrement("c", 1, "meteo_creneau", {"quais": [3]}, 1.0, 10, 100, True, "Service | indisponible")]
    lab10.ecrire_note(tmp_path / "n.md", "Q ?", "Météo non évaluée.", trace)
    texte = (tmp_path / "n.md").read_text(encoding="utf-8")
    assert "## Note de l'agent\n\nMétéo non évaluée." in texte and "| 1 | meteo_creneau |" in texte
    assert "Service \\| indisponible" in texte and "| oui |" in texte


def test_note_panne_n_ecrase_rien_si_la_boucle_s_arrete_avant_tout_appel(mocks_servis, client, tmp_path, monkeypatch,
                                                                           capsys):
    from outils import lab10

    monkeypatch.setattr(lab10, "NOTE", tmp_path / "labs" / "lab10" / "note-panne.md")
    monkeypatch.setattr(lab10, "RACINE", tmp_path)
    with importer_client(client):
        from pharos_client import boucle

        class ArretBoucle(Exception):
            def __init__(self, message, trace):
                super().__init__(message)
                self.trace = trace

        def arret(question, **_):
            raise ArretBoucle("modèle indisponible : clé OpenRouter absente", [])

        monkeypatch.setattr(boucle, "ArretBoucle", ArretBoucle, raising=False)   # la boucle minimale n'en a pas
        monkeypatch.setattr(boucle, "executer", arret)
        assert lab10.main(["note-panne"]) == 1
    assert not lab10.NOTE.exists() and "n'est pas modifié" in capsys.readouterr().out
    assert httpx.get(f"{mocks_servis}/_config").json() == mocks.DEFAUTS           # panne levée à la sortie
