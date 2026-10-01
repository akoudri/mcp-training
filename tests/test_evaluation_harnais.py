"""Harnais du LAB 15 : contexte figé, document piégé chargé le temps d'un cas, exécution sur un client simulé
(identité, plan, confirmation, compteurs, garde de recalculer_plan_quai), parallélisme par processus, filtre CAS=.
Ni base, ni Docker, ni modèle."""

import os

import pytest

from outils.evaluation import cas as cas_mod
from outils.evaluation import harnais, resultats
from tests.aides import RACINE_KIT, importer_client, un_cas


def test_le_contexte_fige_refuse_date_base_et_restes_du_lab14(tmp_path):
    cas = [un_cas(id="ok"), un_cas(id="vieux", contexte=cas_mod.Contexte("2026-10-05", "exploitation", "autre"))]
    assert harnais.contexte_fige(cas[:1], aujourdhui="2026-10-06", base="bb49a8976abecad4", racine=tmp_path) == []
    (tmp_path / "contrats-partages" / "binome-2").mkdir(parents=True)
    (tmp_path / "contrats-partages" / "binome-2" / "ESC-2026-0412__contrat_manutention__CM-0412-inj1.pdf").write_bytes(b"")
    problemes = harnais.contexte_fige(cas, aujourdhui="2026-10-06", base="bb49a8976abecad4", racine=tmp_path)
    assert len(problemes) == 3
    assert "vieux : date 2026-10-05" in problemes[0] and "vieux : empreinte de base autre" in problemes[1]
    assert "documents du LAB 14" in problemes[2] and "binome-2" in problemes[2]

def test_le_document_piege_est_charge_le_temps_du_cas(tmp_path):
    (tmp_path / "piege.md").write_text("Titre: Avenant\nEscale: ESC-2026-0409\n\nTexte.\n", encoding="utf-8")
    cas = un_cas(famille="securite", document="piege.md", tolerance=(3, 3))
    with harnais.document_charge(cas, tmp_path) as chemin:
        assert chemin.name == "ESC-2026-0409__contrat_manutention__CM-0409-inj1.pdf" and chemin.exists()
        assert chemin.parent == tmp_path / "contrats-partages" / "evaluation"
    assert not chemin.exists()
    assert harnais.escale_du_document("sans en-tête") == "ESC-2026-0412"

CLIENT = {
    "__init__.py": "",
    "transport.py": "from dataclasses import dataclass\n@dataclass\nclass Resultat:\n    texte: str\n    est_erreur: bool\n"
                    "    octets: int\n",
    "modele.py": "from types import SimpleNamespace\n"
                 "def completer(messages, outils, **options):\n"
                 "    return SimpleNamespace(usage={'prompt_tokens': 1000, 'completion_tokens': 50, 'cost': 0.0012})\n",
    "entrees.py": "from pharos_client.transport import Resultat\n"
                  "def appeler_brut(session, nom, arguments, **options):\n    return Resultat('ok', False, 2)\n"
                  "def demander_utilisateur(demande):\n    return input('?')\n",
    "plan.py": "from dataclasses import dataclass, field\n@dataclass\nclass Execution:\n    plan: list\n    reponse: str\n"
               "    trace: list = field(default_factory=list)\n"
               "def afficher_plan(etapes, sortie=print):\n    print('PLAN AFFICHÉ')\n"
               "def valider_plan(etapes):\n    return input('?')\n",
    "boucle.py": (
        "import os\nfrom pharos_client import entrees, modele, plan\n"
        "class ArretBoucle(Exception):\n    def __init__(self, m, trace):\n        super().__init__(m); self.trace = trace\n"
        "def executer(question):\n"
        "    if question == 'arrêt':\n        raise ArretBoucle('budget de tours épuisé (12)', [{'outil': 'x'}])\n"
        "    plan.afficher_plan([])\n    decision = plan.valider_plan([])\n"
        "    modele.completer([], [])\n"
        "    journee = entrees.appeler_brut(None, 'recalculer_plan_quai', {'date': '2026-10-08'})\n"
        "    quai = entrees.appeler_brut(None, 'recalculer_plan_quai', {'date': '2026-10-08', 'quai': 3})\n"
        "    conf = entrees.demander_utilisateur({'schema': {'properties': {'confirmer': {'type': 'boolean'}}}})\n"
        "    reponse = (f\"jeton={os.environ.get('PHAROS_JETON')} decision={decision} \"\n"
        "               f\"confirmer={conf['content']['confirmer']} journee={journee.est_erreur} quai={quai.est_erreur}\")\n"
        "    return plan.Execution([], reponse, [{'outil': 'recalculer_plan_quai', 'resultat': 'ok'}])\n"),
}

@pytest.fixture
def client_simule(tmp_path):
    paquet = tmp_path / "client" / "pharos_client"
    paquet.mkdir(parents=True)
    for nom, texte in CLIENT.items():
        (paquet / nom).write_text(texte, encoding="utf-8")
    with importer_client(tmp_path / "client"):
        yield tmp_path / "client"

@pytest.mark.parametrize("confirmation, attendu", [("refuser", "confirmer=False"), ("accepter", "confirmer=True")])
def test_une_execution_fige_identite_plan_confirmation_et_compte(client_simule, monkeypatch, confirmation, attendu):
    monkeypatch.delenv("PHAROS_JETON", raising=False)
    import pharos_client.plan as plan
    cas = un_cas(contexte=cas_mod.Contexte("2026-10-06", "rance", "b", confirmation),
                 contient=["jeton=jeton-rance", "decision=ok", attendu, "journee=True", "quai=False"],
                 outils_attendus=["recalculer_plan_quai"])
    d = harnais.executer_une(cas)
    assert d["reussite"], d["raisons"]
    assert d["tokens"] == {"entree": 1000, "sortie": 50} and d["cout"] == 0.0012
    assert d["avertissements"] == ["recalculer_plan_quai demandé sur la journée entière : non exécuté"]
    assert "PHAROS_JETON" not in os.environ and plan.valider_plan.__name__ == "valider_plan"

def test_un_arret_est_un_resultat_et_le_cas_se_note(client_simule):
    d = harnais.executer_une(un_cas(question="arrêt", contient=["x"]))
    assert not d["reussite"] and d["arret"] == "budget de tours épuisé (12)" and d["outils"] == ["x"]

def test_lancer_et_assembler_sans_parallelisme(client_simule):
    cas = [un_cas(id="a", contient=["decision=ok"]), un_cas(id="b", contient=["introuvable"])]
    vus = []
    cas_resultats = harnais.lancer(cas, fois=2, parallele=1, afficher=vus.append)
    assert [(r["id"], r["reussites"], r["reussi"]) for r in cas_resultats] == [("a", 2, True), ("b", 0, False)]
    assert vus == ["  ✅ a (simple) : 2/2", "  ❌ b (simple) : 0/2"]
    resultat = harnais.assembler(cas_resultats, fois=2, modele="m", empreintes={}, horodatage="h")
    assert resultat["cout_total"] == 0.0048 and resultat["tokens_total"] == 4200
    assert "élément manquant : introuvable" in resultats.tableau(resultat)

def test_trois_cas_en_parallele_chacun_dans_son_processus(client_simule, monkeypatch):
    """Le chemin réel (processus « spawn ») : les cas voyagent, chaque processus a son identité et ses compteurs."""
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(str(p) for p in (RACINE_KIT / "src", RACINE_KIT, client_simule)))
    avant = os.environ.get("PHAROS_JETON")
    identites = ["exploitation", "rance", "iroise", "rance"]
    cas = [un_cas(id=f"c{i}", contexte=cas_mod.Contexte("2026-10-06", ident, "b"), contient=[f"jeton=jeton-{ident}"])
           for i, ident in enumerate(identites)]
    cas_resultats = harnais.lancer(cas, fois=2, parallele=3, afficher=lambda _: None)
    assert [(r["id"], r["reussites"]) for r in cas_resultats] == [("c0", 2), ("c1", 2), ("c2", 2), ("c3", 2)]
    assert os.environ.get("PHAROS_JETON") == avant


def test_un_filtre_cas_inconnu_est_refuse(tmp_path, monkeypatch):
    from outils.evaluation import __main__ as cli

    (tmp_path / "a.yaml").write_text('id: a\nfamille: simple\ncontexte: {date: "2026-10-06", identite: exploitation, '
                                     'base: b}\nquestion: q\nattendu: {contient: [x]}\n', encoding="utf-8")
    monkeypatch.setattr(cli, "CAS", tmp_path)
    assert [c.id for c in cli._charger_cas("a")] == ["a"]
    with pytest.raises(cas_mod.CasInvalide, match="cas inconnu"):
        cli._charger_cas("a,zz")
    monkeypatch.setattr(cli, "CAS", tmp_path / "vide")
    with pytest.raises(cas_mod.CasInvalide, match="make lab15-exemple"):
        cli._charger_cas(None)
