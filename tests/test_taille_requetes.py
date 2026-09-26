from outils import taille_requetes
from tests.aides import servir


async def test_avant_apres():
    with servir(taille_requetes.serveur_de_reference().http_app(path="/mcp", json_response=True)) as base:
        avant = await taille_requetes.mesurer(f"{base}/mcp", "2025-11-25", tours=3)
        apres = await taille_requetes.mesurer(f"{base}/mcp", "2026-07-28", tours=3)
    assert avant["requetes_poignee"] == 3 and avant["poignee"] > 0
    assert apres["requetes_poignee"] == 0 and apres["poignee"] == 0
    assert apres["par_appel"] > avant["par_appel"]           # la révision voyage dans chaque requête
    texte = taille_requetes.tableau(avant, apres)
    assert "Poignée de main" in texte and "économisés" in texte
