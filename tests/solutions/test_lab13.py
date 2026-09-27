import contextlib
import json
import shutil
from pathlib import Path

import pytest

from outils.verifier.commun import Etat
from outils.labs import copier
from tests.aides import (DSN_TEST, RACINE_KIT, base_requise, charger_module, etat_complet, importer_client,
                         importer_paquet, servir)

pytestmark = pytest.mark.skipif(not Path("solutions/lab13").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")
CLE_ETAT = "pharos-salle-2026-cle-etat-mrtr-partagee"
SERVEURS = [("pharos-docs", "pharos_docs"), ("pharos-data", "pharos_data"), ("pharos-ops", "pharos_ops")]


@pytest.fixture(scope="module")
def etat(tmp_path_factory):
    return etat_complet(tmp_path_factory.mktemp("etat-lab13"), 13)


@contextlib.contextmanager
def trois_serveurs(etat: Path, config: Path):
    """Les trois serveurs de la solution, servis en HTTP dans le processus ; écrit la configuration qui les vise."""
    with importer_paquet(etat, "serveurs"):
        mcp = {nom: charger_module(etat / "serveurs" / module / "serveur.py", f"solution_lab13_{module}").mcp
               for nom, module in SERVEURS}
        with contextlib.ExitStack() as pile:
            urls = {nom: pile.enter_context(servir(m.http_app(path="/mcp", json_response=True))) + "/mcp"
                    for nom, m in mcp.items()}
            config.write_text(json.dumps({"serveurs": [
                {"nom": nom, "url": urls[nom], "jeton": "jeton-exploitation"} for nom, _ in SERVEURS]}),
                encoding="utf-8")
            yield urls


async def verifier(etat: Path, monkeypatch, tmp_path, mocks_servis):
    """Le vérificateur du LAB 13 sur un état (la base doit porter la politique de l'état)."""
    from donnees.base.__main__ import charger
    from outils.verifier import lab13

    await charger(DSN_TEST, politique=etat / "labs" / "lab9" / "politique.sql")
    monkeypatch.setenv("CLE_ETAT", CLE_ETAT)
    monkeypatch.setenv("CANAL_URL", f"{mocks_servis}/canal")
    for nom, valeur in (("RACINE", etat), ("CONFIG", tmp_path / "serveurs.json"),
                        ("MESURES", etat / "labs" / "lab13" / "mesures.md"),
                        ("CONSIGNE", etat / "client" / "pharos_client" / "consigne.md"),
                        ("DERNIERE", etat / "labs" / "lab13" / "execution.json")):
        monkeypatch.setattr(lab13, nom, valeur)
    try:
        with trois_serveurs(etat, tmp_path / "serveurs.json") as urls, importer_client(etat / "client"):
            rapport = await lab13.v.executer(url=urls["pharos-ops"], sans_modele=True)
    finally:
        await charger(DSN_TEST, politique=Path("/nulle-part.sql"))
    return rapport


def echecs(rapport) -> dict[str, str]:
    return {r.libelle: r.detail for r in rapport.resultats if r.etat is Etat.ECHEC}


@base_requise
async def test_la_solution_passe_son_verificateur(etat, base_de_test, mocks_servis, monkeypatch, tmp_path):
    rapport = await verifier(etat, monkeypatch, tmp_path, mocks_servis)
    assert echecs(rapport) == {}, rapport.texte()


@base_requise
async def test_le_gabarit_echoue(base_de_test, mocks_servis, monkeypatch, tmp_path):
    etat = etat_complet(tmp_path / "etat", 12)
    copier(RACINE_KIT / "gabarits" / "lab13", etat, ecraser=False)
    rapport = await verifier(etat, monkeypatch, tmp_path, mocks_servis)
    rates = " ".join(echecs(rapport))
    for debut in ("Les outils du brief", "Les mesures", "La consigne système", "Chaque appel de la trace",
                  "Le plan est affiché", "La confirmation", "La réponse texte", "Les trois signaux", "Critère décisif (note)"):
        assert debut in rates, rapport.texte()


REFUS = ('            if decision.casefold() in ("non", "n", "no"):\n'
         '                return plan.Execution(etapes, "Plan refusé par l\'exploitant : rien n\'a été exécuté.", trace)\n')

MUTATIONS = {
    "collision": ("serveurs/pharos_data/serveur.py", 'navires.enregistrer(mcp, emprunter, nom_outil="data_navire_par_nom")',
                  "navires.enregistrer(mcp, emprunter)", "Aucune collision", "navire_par_nom (pharos-data, pharos-ops)"),
    "plan_non_affiche": ("client/pharos_client/boucle.py", "    plan.afficher_plan(etapes)\n", "",
                         "Le plan est affiché", "n'était pas affiché"),
    "serveur_absent": ("client/pharos_client/boucle.py", 'serveur or "?"))', '""))',
                       "Chaque appel de la trace", "serveur absent ou faux"),
    "vue_non_declaree": ("serveurs/pharos_ops/serveur.py", "          app=AppConfig(resource_uri=VUE_PLAN_QUAI),\n", "",
                         "La réponse texte", "vue non déclarée"),
    "consigne_en_dur": ("client/pharos_client/boucle.py",
                        'CONSIGNE = Path(__file__).with_name("consigne.md").read_text(encoding="utf-8").strip()',
                        'CONSIGNE = "Tu es un assistant."', "La consigne système", "n'est pas le contenu de consigne.md"),
    "confirmation_par_la_boucle": ("client/pharos_client/boucle.py",
                                   "reponses = {cle: entrees.demander_utilisateur(demande) for cle, demande in "
                                   "resultat.demandes.items()}",
                                   'reponses = {cle: {"action": "accept", "content": {"confirmer": True}} '
                                   "for cle in resultat.demandes}",
                                   "La confirmation", "0 demande(s) présentée(s)"),
    "plan_ignore": ("client/pharos_client/boucle.py", REFUS, "", "Le plan est affiché", "et pourtant"),
}


@base_requise
@pytest.mark.parametrize("defaut", sorted(MUTATIONS))
async def test_chaque_defaut_est_vu(etat, defaut, base_de_test, mocks_servis, monkeypatch, tmp_path):
    fichier, avant, apres, critere, message = MUTATIONS[defaut]
    copie = tmp_path / "etat"
    shutil.copytree(etat, copie)
    chemin = copie / fichier
    texte = chemin.read_text(encoding="utf-8")
    assert avant in texte, f"mutation {defaut} : texte introuvable dans {fichier}"
    chemin.write_text(texte.replace(avant, apres), encoding="utf-8")
    rapport = await verifier(copie, monkeypatch, tmp_path, mocks_servis)
    rates = echecs(rapport)
    assert any(l.startswith(critere) and message in d for l, d in rates.items()), rapport.texte()


@base_requise
async def test_un_refus_leve_en_arret_a_trace_vide_est_accepte(etat, base_de_test, mocks_servis, monkeypatch, tmp_path):
    copie = tmp_path / "etat"
    shutil.copytree(etat, copie)
    chemin = copie / "client" / "pharos_client" / "boucle.py"
    texte = chemin.read_text(encoding="utf-8")
    assert REFUS in texte
    chemin.write_text(texte.replace(REFUS, '            if decision.casefold() in ("non", "n", "no"):\n'
                                           '                raise ArretBoucle("plan refusé par l\'exploitant", trace)\n'),
                      encoding="utf-8")
    rapport = await verifier(copie, monkeypatch, tmp_path, mocks_servis)
    assert not any(l.startswith("Le plan est affiché") for l in echecs(rapport)), rapport.texte()


def test_mesures_consignees(etat):
    texte = (etat / "labs" / "lab13" / "mesures.md").read_text(encoding="utf-8")
    assert "À RELEVER" not in texte and "PROVISOIRE" not in texte


def test_l_execution_gardee_est_la_question_cible_et_sa_note_est_sourcee(etat):
    from outils.verifier.note import sans_origine, verifier_note

    execution = json.loads((etat / "labs" / "lab13" / "execution.json").read_text(encoding="utf-8"))
    assert "Vent d'Autan" in execution["question"] and not execution.get("arret")
    assert sans_origine(verifier_note(execution["reponse"], execution["trace"], execution["question"])) == []


def jouets() -> list:
    """Deux serveurs jouets en mémoire, sans base : de quoi jouer la boucle de référence sur ses cas limites."""
    from fastmcp import FastMCP

    docs, ops = FastMCP("docs"), FastMCP("ops")

    @docs.tool
    def rechercher_clause(escale_id: str, sujet: str) -> dict:
        """Clause d'un contrat."""
        return {"texte": "Pénalité de 1 850 € par heure au-delà de 6 heures."}

    @ops.tool
    def navire_par_nom(nom: str) -> dict:
        """Fiche d'un navire."""
        return {"navire_id": "NAV-0007", "escales": [{"escale_id": "ESC-2026-0412"}]}

    return [("pharos-docs", docs), ("pharos-ops", ops)]


@contextlib.contextmanager
def boucle_de_reference(etat, monkeypatch, serveurs):
    with importer_client(etat / "client"):
        from pharos_client import agregation, boucle, plan
        monkeypatch.setattr(agregation, "lire_config", lambda _c: [agregation.Serveur(n, m) for n, m in serveurs])
        monkeypatch.setattr(plan, "valider_plan", lambda etapes: "ok")
        yield boucle


def test_un_plan_illisible_n_arrete_pas_l_execution(etat, monkeypatch, capsys):
    from outils.verifier.modele_simule import ModeleSimule, appel

    with boucle_de_reference(etat, monkeypatch, jouets()) as boucle, \
            ModeleSimule(["Je vais d'abord chercher le navire.", [appel("a1", "navire_par_nom", {"nom": "Vent"})], "Fini."]):
        execution = boucle.executer("Question ?", config="inutile.json")
    assert execution.plan == [] and [e.outil for e in execution.trace] == ["navire_par_nom"]
    assert "Plan illisible" in capsys.readouterr().out


def test_un_outil_inconnu_revient_au_modele_en_erreur(etat, monkeypatch):
    from outils.verifier.modele_simule import ModeleSimule, appel

    with boucle_de_reference(etat, monkeypatch, jouets()) as boucle, \
            ModeleSimule(['[{"etape": 1, "outil": "escales_du_jour", "raison": "?"}]',
                          [appel("a1", "escales_du_jour", {"date": "jeudi"})], "Fini."]) as simule:
        execution = boucle.executer("Question ?", config="inutile.json")
    enregistrement = execution.trace[0]
    assert (enregistrement.outil, enregistrement.serveur, enregistrement.erreur) == ("escales_du_jour", "?", True)
    assert execution.plan[0].serveur == "?"
    assert "Outil inconnu : escales_du_jour" in simule.recus[-1][-1]["content"]


def test_une_collision_arrete_la_boucle_en_la_nommant(etat, monkeypatch):
    from fastmcp import FastMCP

    autre = FastMCP("data")

    @autre.tool
    def navire_par_nom(nom: str) -> dict:
        """La même chose, ailleurs."""
        return {}

    with boucle_de_reference(etat, monkeypatch, [*jouets(), ("pharos-data", autre)]) as boucle:
        with pytest.raises(boucle.EchecNonRecuperable, match=r"navire_par_nom \(pharos-ops, pharos-data\)"):
            boucle.executer("Question ?", config="inutile.json")


def test_un_serveur_injoignable_arrete_la_boucle_sans_trace_python(etat, monkeypatch):
    with boucle_de_reference(etat, monkeypatch, [("pharos-ops", "http://127.0.0.1:1/mcp")]) as boucle:
        with pytest.raises(boucle.EchecNonRecuperable, match="serveur injoignable"):
            boucle.executer("Question ?", config="inutile.json")
