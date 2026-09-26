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
