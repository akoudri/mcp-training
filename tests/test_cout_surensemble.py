from outils import cout_surensemble


def test_surcout_du_surensemble():
    texte = [{"type": "text", "text": '{"quai": 3}'}]
    lignes = cout_surensemble.mesurer_resultats([
        ("etat_escale", {"content": texte, "structuredContent": {"quai": 3}, "isError": False}),
        ("page_suivante", {"content": texte, "isError": False}),
        ("lister_mouvements", {"content": texte, "isError": True}),
    ])
    assert [l["outil"] for l in lignes] == ["etat_escale", "page_suivante"]
    assert lignes[0]["surensemble"] > lignes[0]["texte"] and lignes[1]["surensemble"] == lignes[1]["texte"]
    assert "tokens de plus" in cout_surensemble.tableau(lignes)


def test_main_attend_avec_le_conseil_du_lab3(monkeypatch):
    appels = {}
    monkeypatch.setattr(cout_surensemble, "attendre", lambda url, **kw: appels.update(kw))

    def _faux_run(coro):
        coro.close()
        return 0

    monkeypatch.setattr(cout_surensemble.asyncio, "run", _faux_run)
    cout_surensemble.main([])
    assert appels.get("conseil") == "lancer make lab3-deux-instances"
