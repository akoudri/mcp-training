"""Kit du LAB 13 : squelettes du client (agrégation, plan, dérive), module navires, vue MCP App, outils du lab,
démarrage. Serveurs jouets en mémoire ; ni base, ni Docker, ni modèle."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastmcp import FastMCP

from outils import banc, lab13, labs
from outils.labs import copier
from tests.aides import RACINE_KIT, charger_module, importer_client

GABARITS = RACINE_KIT / "gabarits"


@pytest.fixture
def client_gabarit(tmp_path):
    """Le paquet pharos_client tel qu'un binôme le trouve au départ du LAB 13, gabarits seuls (sans solutions)."""
    for lab in ("lab04", "lab11", "lab12", "lab13"):
        copier(GABARITS / lab / "client", tmp_path / "client", ecraser=False)
    with importer_client(tmp_path / "client"):
        yield tmp_path / "client"


def outil(nom: str, description: str = "") -> SimpleNamespace:
    return SimpleNamespace(name=nom, description=description, input_schema={"type": "object", "properties": {}})


def test_le_depart_et_la_sortie_du_lab13():
    assert labs.DEPARTS[13] == "sr3-fin" and labs.SORTIES[13] == "or3-fin"
    assert labs.DEMARRAGE[13][-1] == "lab13-tout" and labs.PORTS_PRETS[13] == [8101, 8102, 8103]


def test_les_cibles_du_brief_existent():
    texte = (RACINE_KIT / "mk" / "lab13.mk").read_text(encoding="utf-8")
    for cible in ("lab13-tout", "lab13-scaffold", "lab13-catalogue", "lab13-question", "lab13-verifier-note",
                  "lab13-derive", "lab13-banc", "lab13-verifier"):
        assert f"\n{cible}:" in f"\n{texte}", cible


@pytest.mark.parametrize("module, fonctions", [
    ("agregation", ["collisions", "outils", "serveur_de", "session_de"]),
    ("derive", ["hors_plan", "jamais_executees", "retours_arriere"]),
])
def test_les_squelettes_disent_ce_qui_reste_a_ecrire(client_gabarit, module, fonctions):
    import importlib
    m = importlib.import_module(f"pharos_client.{module}")
    for nom in fonctions:
        if module == "agregation":
            appel = lambda: getattr(m.Catalogue([]), nom)(*(["x"] if nom in ("serveur_de", "session_de") else []))
        else:
            appel = lambda: getattr(m, nom)(*([[], []] if nom != "retours_arriere" else [[]]))
        with pytest.raises(NotImplementedError, match="LAB 13"):
            appel()


def test_le_plan_fourni_se_lit_et_s_affiche(client_gabarit):
    from pharos_client import plan
    texte = 'Voici le plan :\n```json\n[{"etape": 1, "outil": "navire_par_nom", "raison": "escale"},' \
            ' {"etape": 2, "outil": "inventé", "raison": "?"}]\n```'
    etapes = plan.lire_plan(texte, {"navire_par_nom": "pharos-ops"}.get)
    assert [(e.numero, e.outil, e.serveur) for e in etapes] == [(1, "navire_par_nom", "pharos-ops"), (2, "inventé", "?")]
    lignes = []
    assert "Plan annoncé" in plan.afficher_plan(etapes, lignes.append) and lignes
    with pytest.raises(plan.PlanIllisible):
        plan.lire_plan("Je vais d'abord regarder la météo.", {}.get)
    with pytest.raises(NotImplementedError, match="LAB 13"):
        plan.demander_plan([], [])


def test_la_decision_sur_le_plan_vaut_non_sans_terminal(client_gabarit, monkeypatch):
    from pharos_client import plan

    def sans_terminal(_):
        raise EOFError
    monkeypatch.setattr("builtins.input", sans_terminal)
    assert plan.valider_plan([]) == "non"


def test_la_configuration_fournie_vise_les_trois_serveurs(client_gabarit):
    from pharos_client import agregation
    serveurs = agregation.lire_config(GABARITS / "lab13" / "labs" / "lab13" / "serveurs.json")
    assert [(s.nom, s.url) for s in serveurs] == [("pharos-docs", "http://observateur:8101/mcp"),
                                                  ("pharos-data", "http://observateur:8102/mcp"),
                                                  ("pharos-ops", "http://observateur:8103/mcp")]


async def test_le_module_navires_s_enregistre_sous_le_nom_choisi():
    navires = charger_module(GABARITS / "lab13" / "serveurs" / "pharos_data" / "navires.py", "kit13_navires")
    for nom in ("navire_par_nom", "data_navire_par_nom"):
        mcp = FastMCP("jouet")
        navires.enregistrer(mcp, emprunter=None, nom_outil=nom)
        assert [t.name for t in await mcp.list_tools()] == [nom]


def test_la_vue_parle_le_protocole_des_mcp_apps():
    html = (GABARITS / "lab13" / "serveurs" / "pharos_ops" / "vues" / "plan_quai.html").read_text(encoding="utf-8")
    for fragment in ('"ui/initialize"', '"ui/notifications/initialized"', '"ui/notifications/tool-result"',
                     "structuredContent", "2026-01-26"):
        assert fragment in html, fragment


def test_collisions_et_rapport_du_catalogue():
    catalogues = {"pharos-docs": [outil("rechercher_clause", "Recherche une clause.")],
                  "pharos-data": [outil("escales_a_risque"), outil("navire_par_nom")],
                  "pharos-ops": [outil("navire_par_nom"), outil("publier_alerte")]}
    assert lab13.collisions(catalogues) == {"navire_par_nom": ["pharos-data", "pharos-ops"]}
    texte = lab13.rapport_catalogue(catalogues)
    assert "agrégé" in texte and "5 outil(s)" in texte and "navire_par_nom — pharos-data, pharos-ops" in texte
    ecrases = lab13.outils_ecrases(catalogues)
    assert [o["function"]["name"] for o in ecrases].count("navire_par_nom") == 1


def test_signaux_et_note_relisent_l_execution_gardee(tmp_path, monkeypatch, capsys):
    execution = {"question": "Q ?", "plan": [{"numero": 1, "outil": "a", "serveur": "s", "raison": ""}],
                 "reponse": "Houle de 2,8 m.", "arret": None,
                 "trace": [{"tour": 1, "outil": "a", "arguments": {}, "serveur": "s", "resultat": '{"houle_m": 2.8}'}]}
    fichier = tmp_path / "execution.json"
    fichier.write_text(json.dumps(execution), encoding="utf-8")
    monkeypatch.setattr(lab13, "DERNIERE", fichier)
    assert lab13.verifier_derniere_note() == 0
    assert "t1 s a" in capsys.readouterr().out


async def test_le_banc_accepte_un_catalogue_compose():
    vus = []

    def completer(messages, outils, **_):
        vus.append([o["function"]["name"] for o in outils])
        from pharos.openrouter import Appel, Reponse
        return Reponse({"role": "assistant"}, [Appel("1", "navire_par_nom", {})], {})

    questions = [banc.Question(1, "Quel navire ?", "navire_par_nom")]
    catalogue = lab13.outils_ecrases({"a": [outil("navire_par_nom")], "b": [outil("meteo_creneau")]})
    executions = await banc.executer_banc(None, questions, 2, completer=completer, outils=catalogue)
    assert [e.ok for e in executions] == [True, True] and vus[0] == ["navire_par_nom", "meteo_creneau"]
