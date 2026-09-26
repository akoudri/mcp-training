"""Tests sans Docker de outils.essayer : la partie git (construire, worktree, nettoyage) est
réelle ; les cibles make (up, démarrage, verifier, down) sont remplacées par des no-op."""

import subprocess
from pathlib import Path

import pytest

from outils import essayer as es


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def ecrire(racine: Path, chemin: str, texte: str) -> None:
    f = racine / chemin
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(texte)


@pytest.fixture
def depot(tmp_path) -> Path:
    r = tmp_path / "kit"
    git(tmp_path, "init", "-q", "-b", "main", str(r))
    git(r, "config", "user.name", "essai")
    git(r, "config", "user.email", "essai@example.invalid")
    ecrire(r, "README.md", "kit\n")
    ecrire(r, "gabarits/lab01/serveurs/pharos_docs/serveur.py", "# squelette\n")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "kit")
    git(r, "branch", "etat/fa2-fin")
    git(r, "switch", "-q", "-c", "solutions")
    ecrire(r, "solutions/lab01/serveurs/pharos_docs/serveur.py", "# solution 1\n")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "solutions")
    git(r, "switch", "-q", "main")
    return r


class _SubprocessSansDocker:
    """Laisse passer git tel quel ; « exécute » make sans rien lancer (pas de Docker en test)."""

    def run(self, cmd, *args, **kwargs):
        if cmd and cmd[0] == "make":
            return subprocess.CompletedProcess(cmd, 0)
        return subprocess.run(cmd, *args, **kwargs)


def branches_essai(racine: Path) -> str:
    return subprocess.run(["git", "branch", "--list", "essai/*"], cwd=racine,
                          capture_output=True, text=True).stdout.strip()


def test_essayer_nettoie_aussi_essai_etat_fa2_fin(depot, monkeypatch):
    """essayer() supprime, en plus du worktree et de essai/etat/<sortie>, la branche locale
    essai/etat/fa2-fin créée par construire() avec le préfixe essai/ : pas de branche essai/*
    résiduelle après un essai."""
    monkeypatch.setattr(es, "subprocess", _SubprocessSansDocker())
    monkeypatch.setattr(es, "attendre", lambda ports, delai=90: None)
    es.essayer(depot, 1)
    assert branches_essai(depot) == ""
