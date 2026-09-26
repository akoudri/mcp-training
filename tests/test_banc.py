import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from outils import banc
from outils.banc import Question
from pharos.openrouter import Appel, ErreurModele, Reponse
from tests.aides import servir


def serveur() -> FastMCP:
    mcp = FastMCP("banc")

    @mcp.tool
    def lister_documents(escale_id: str) -> dict:
        """Liste les documents d'une escale."""
        return {"documents": []}

    @mcp.tool
    def rechercher_clause(escale_id: str, sujet: str) -> dict:
        """Recherche une clause."""
        if escale_id == "ESC-2026-9999":
            raise ToolError("Escale inconnue : ESC-2026-9999. Format attendu : ESC-AAAA-NNNN.")
        return {"texte": "…"}

    return mcp


def modele(script: dict):
    """script : texte de question → liste de choix successifs ; un choix = (outil, arguments) ou None."""
    vus: dict[str, int] = {}

    def completer(messages, outils, **_):
        assert messages[0]["role"] == "system" and "6 octobre 2026" in messages[0]["content"]
        assert outils, "le catalogue doit être transmis au modèle"
        q = messages[-1]["content"]
        i = vus.get(q, 0)
        vus[q] = i + 1
        choix = script[q][min(i, len(script[q]) - 1)]
        usage = {"prompt_tokens": 100, "completion_tokens": 10, "cost": 0.001}
        if choix is None:
            return Reponse({"role": "assistant", "content": "Je ne sais pas."}, [], usage)
        nom, args = choix
        return Reponse({"role": "assistant", "content": None}, [Appel("a1", nom, args)], usage)

    return completer


Q1 = Question(1, "Documents de ESC-2026-0412 ?", "lister_documents", {"escale_id": "ESC-2026-0412"})
Q2 = Question(2, "Pénalités du Vent d'Autan ?", "rechercher_clause", {"sujet": "penalites"}, constat=True)
Q5 = Question(5, "Pénalité de ESC-2026-9999 ?", "rechercher_clause", resultat_attendu="erreur_metier")


def test_charger_questions(tmp_path):
    f = tmp_path / "q.yaml"
    f.write_text("- question: A ?\n  attendu: x\n- question: B ?\n  attendu: y\n  constat: true\n"
                 "  arguments_attendus: {sujet: penalites}\n", encoding="utf-8")
    qs = banc.charger_questions(f)
    assert [q.numero for q in qs] == [1, 2]
    assert qs[1].constat and qs[1].arguments_attendus == {"sujet": "penalites"}



def test_charger_questions_avec_contexte(tmp_path):
    f = tmp_path / "q.yaml"
    f.write_text("- question: Et l'assurance ?\n  attendu: x\n  contexte:\n"
                 "    - {role: user, content: Question précédente}\n"
                 "    - {role: assistant, content: Réponse précédente}\n", encoding="utf-8")
    [q] = banc.charger_questions(f)
    assert q.contexte == ({"role": "user", "content": "Question précédente"},
                          {"role": "assistant", "content": "Réponse précédente"})


async def test_contexte_rejoue_avant_la_question():
    vus = []
    q = Question(1, "Et l'assurance ?", "rechercher_clause",
                 contexte=({"role": "user", "content": "Avant"}, {"role": "assistant", "content": "Réponse"}))

    def completer(messages, outils, **_):
        vus.append([m["content"] for m in messages])
        return Reponse({"role": "assistant", "content": None}, [Appel("a1", "rechercher_clause", {})], {})

    await banc.executer_banc(serveur(), [q], completer=completer)
    assert vus[0][1:] == ["Avant", "Réponse", "Et l'assurance ?"]


async def test_premier_appel_juge():
    script = {Q1.texte: [("lister_documents", {"escale_id": "ESC-2026-0412"})],
              Q2.texte: [("lister_documents", {"escale_id": "?"})],
              Q5.texte: [("rechercher_clause", {"escale_id": "ESC-2026-9999", "sujet": "penalites"})]}
    ex = await banc.executer_banc(serveur(), [Q1, Q2, Q5], completer=modele(script))
    assert [e.ok for e in ex] == [True, None, True]
    assert ex[2].est_erreur is True and "ESC-AAAA-NNNN" in ex[2].resultat
    assert banc.bilan(ex) == {1: (1, 1), 5: (1, 1)}
    texte = banc.formater(ex)
    assert "✅ lister_documents(escale_id=ESC-2026-0412)" in texte and "👁" in texte
    assert "isError" in texte and "Questions réussies" in texte and "0.0030" in texte


async def test_mauvais_arguments_et_aucun_appel():
    q = Question(1, "Q ?", "rechercher_clause", {"sujet": "penalites"})
    q2 = Question(2, "R ?", "lister_documents")
    script = {q.texte: [("rechercher_clause", {"escale_id": "E", "sujet": "delais"})], q2.texte: [None]}
    ex = await banc.executer_banc(serveur(), [q, q2], completer=modele(script))
    assert [e.ok for e in ex] == [False, False]
    assert "aucun appel" in banc.formater(ex)


async def test_trois_executions_majorite():
    script = {Q1.texte: [("lister_documents", {"escale_id": "ESC-2026-0412"}), None,
                         ("lister_documents", {"escale_id": "ESC-2026-0412"})]}
    ex = await banc.executer_banc(serveur(), [Q1], executions=3, completer=modele(script))
    assert banc.bilan(ex) == {1: (2, 3)} and banc.question_reussie(2, 3)
    assert not banc.question_reussie(1, 3)
    assert "2/3" in banc.formater(ex)


async def test_outil_inconnu_ne_plante_pas():
    q = Question(1, "Q ?", "lister_documents", resultat_attendu="erreur_metier")
    ex = await banc.executer_banc(serveur(), [q], completer=modele({q.texte: [("n_existe_pas", {})]}))
    assert ex[0].ok is False and ex[0].est_erreur is True


def test_sans_modele(monkeypatch, capsys):
    monkeypatch.setenv("SANS_MODELE", "1")
    assert banc.main(["http://127.0.0.1:1/mcp", "--questions", "absent.yaml"]) == 0
    assert "ignoré" in capsys.readouterr().out


def test_main_ecrit_la_sortie(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("SANS_MODELE", raising=False)
    f = tmp_path / "q.yaml"
    f.write_text(f"- question: '{Q1.texte}'\n  attendu: lister_documents\n", encoding="utf-8")
    monkeypatch.setattr(banc.openrouter, "completer", modele({Q1.texte: [("lister_documents", {"escale_id": "X"})]}))
    sortie = tmp_path / "avant.md"
    with servir(serveur().http_app(path="/mcp", json_response=True)) as base:
        assert banc.main([f"{base}/mcp", "--questions", str(f), "--sortie", str(sortie)]) == 0
    assert "✅ lister_documents" in sortie.read_text(encoding="utf-8")


def test_main_erreur_modele(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("SANS_MODELE", raising=False)
    f = tmp_path / "q.yaml"
    f.write_text("- question: Q ?\n  attendu: x\n", encoding="utf-8")

    def en_panne(*a, **k):
        raise ErreurModele("crédit épuisé sur cette clé : prévenir le formateur.")
    monkeypatch.setattr(banc.openrouter, "completer", en_panne)
    with servir(serveur().http_app(path="/mcp", json_response=True)) as base:
        assert banc.main([f"{base}/mcp", "--questions", str(f)]) == 2
    assert "crédit épuisé" in capsys.readouterr().out
