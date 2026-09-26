from pathlib import Path

from outils.verifier.commun import Etat
from tests.aides import importer_client, sans_paquet, serveur_demo, servir


async def test_le_squelette_ne_passe_pas():
    with importer_client(Path("gabarits/lab04/client")):
        from outils.verifier import lab4
        with servir(serveur_demo().http_app(path="/mcp", json_response=True)) as base:
            rapport = await lab4.v.executer(url=f"{base}/mcp", sans_modele=True)
    echecs = [r for r in rapport.resultats if r.etat is Etat.ECHEC]
    assert echecs and all("pas encore écrite" in r.detail for r in echecs)
    assert rapport.code_sortie == 1


async def test_sans_pharos_client():
    """Indépendant de l'état : pharos_client peut être réellement importable (etat/or1-fin et
    suivants, via client/ sur le pythonpath de pytest) — on le masque explicitement ici."""
    with sans_paquet("pharos_client"):
        from outils.verifier import lab4
        with servir(serveur_demo().http_app(path="/mcp", json_response=True)) as base:
            rapport = await lab4.v.executer(url=f"{base}/mcp", sans_modele=True)
    assert any("make depart LAB=4" in r.detail for r in rapport.resultats)


def test_normaliser_nombre_espace_insecable():
    """Espace fine insécable (U+202F, utilisée par le français pour les milliers) et
    espace insécable normale (U+00A0) : toutes deux ramenées à une espace normale."""
    from outils.verifier import lab4

    fine = chr(0x202F)   # espace fine insécable
    normale = chr(0x00A0)  # espace insécable normale
    assert lab4._normaliser_nombre(f"1{fine}850 € par heure.") == "1 850 € par heure."
    assert lab4._normaliser_nombre(f"1{normale}850 € par heure.") == "1 850 € par heure."
    assert lab4._normaliser_nombre("1 850 € par heure.") == "1 850 € par heure."


async def test_guard_import_direct_du_completer(tmp_path):
    """Une boucle qui importe modele.completer directement (au lieu de passer par l'attribut du
    module) contourne le modèle simulé : le vérificateur doit le signaler, pas planter ou l'accepter."""
    paquet = tmp_path / "pharos_client"
    paquet.mkdir()
    (paquet / "__init__.py").write_text("", encoding="utf-8")
    (paquet / "modele.py").write_text(
        "from pharos.openrouter import Appel, ErreurModele, Reponse, completer, estimer_tokens\n"
        "__all__ = ['Appel', 'ErreurModele', 'Reponse', 'completer', 'estimer_tokens']\n",
        encoding="utf-8",
    )
    (paquet / "trace.py").write_text(
        "from dataclasses import dataclass\n\n"
        "@dataclass(frozen=True)\n"
        "class Enregistrement:\n"
        "    correlation: str\n"
        "    tour: int\n"
        "    outil: str\n"
        "    arguments: dict\n"
        "    duree_ms: float\n"
        "    octets: int\n"
        "    tokens_cumules: int\n"
        "    erreur: bool = False\n",
        encoding="utf-8",
    )
    (paquet / "boucle.py").write_text(
        "from pharos_client.modele import completer  # import direct : c'est ce qu'il ne faut pas faire\n\n"
        "class ArretBoucle(Exception):\n"
        "    def __init__(self, message, trace):\n"
        "        super().__init__(message)\n"
        "        self.trace = trace\n\n"
        "class BudgetDepasse(ArretBoucle):\n"
        "    pass\n\n"
        "class EchecNonRecuperable(ArretBoucle):\n"
        "    pass\n\n"
        "def executer(question, *, url=None, max_tours=8, max_tokens=30_000):\n"
        "    completer([], [])  # appelle la fonction importée directement, pas modele.completer\n"
        "    return 'réponse', []\n",
        encoding="utf-8",
    )
    with importer_client(tmp_path):
        from outils.verifier import lab4
        with servir(serveur_demo().http_app(path="/mcp", json_response=True)) as base:
            rapport = await lab4.v.executer(url=f"{base}/mcp", sans_modele=True)
    echecs = [r for r in rapport.resultats if r.etat is Etat.ECHEC]
    assert echecs and all("import direct" in r.detail for r in echecs)
