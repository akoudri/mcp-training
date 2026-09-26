import subprocess
from pathlib import Path

import pytest

from outils import depart as d
from outils.labs import copier


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def travail(tmp_path) -> Path:
    distant = tmp_path / "distant.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(distant))
    t = tmp_path / "travail"
    git(tmp_path, "init", "-q", "-b", "main", str(t))
    git(t, "config", "user.name", "essai")
    git(t, "config", "user.email", "essai@example.invalid")
    (t / ".gitignore").write_text(".env\n")
    g = t / "gabarits" / "lab01"
    (g / "serveurs" / "pharos_docs").mkdir(parents=True)
    (g / "serveurs" / "pharos_docs" / "serveur.py").write_text("# squelette\n")
    (g / "labs" / "lab1").mkdir(parents=True)
    (g / "labs" / "lab1" / "resultats.md").write_text("| Q | … |\n")
    (g / "__pycache__").mkdir()
    (g / "__pycache__" / "x.pyc").write_bytes(b"\0")
    git(t, "add", "-A")
    git(t, "commit", "-q", "-m", "kit")
    git(t, "remote", "add", "origin", str(distant))
    git(t, "push", "-q", "origin", "main", "main:etat/fa2-fin")
    (t / ".env").write_text("OPENROUTER_API_KEY=sk\nPHAROS_BINOME=3\n")
    return t


def test_depart_cree_branche_et_gabarits(travail):
    messages = d.depart(travail, 1)
    assert git(travail, "branch", "--show-current") == "binome-3-lab01"
    assert (travail / "serveurs" / "pharos_docs" / "serveur.py").read_text() == "# squelette\n"
    assert not (travail / "__pycache__").exists()
    assert any("créée depuis origin/etat/fa2-fin" in m for m in messages)
    assert subprocess.run(["git", "rev-parse", "--abbrev-ref", "@{upstream}"], cwd=travail,
                          capture_output=True).returncode != 0          # aucune branche amont


def test_arbre_modifie_refuse(travail):
    (travail / ".gitignore").write_text("autre\n")
    with pytest.raises(d.Refus, match="git add -A"):
        d.depart(travail, 1)


def test_fichier_non_suivi_refuse(travail):
    (travail / "brouillon.py").write_text("x = 1\n")
    with pytest.raises(d.Refus, match="brouillon.py"):
        d.depart(travail, 1)


def test_binome_absent(travail):
    (travail / ".env").write_text("OPENROUTER_API_KEY=sk\n")
    with pytest.raises(d.Refus, match="PHAROS_BINOME"):
        d.depart(travail, 1)


def test_gabarit_jamais_ecrase(travail):
    d.depart(travail, 1)
    serveur = travail / "serveurs" / "pharos_docs" / "serveur.py"
    serveur.write_text("# mon travail\n")
    messages = d.gabarits(travail, 1)
    assert serveur.read_text() == "# mon travail\n"
    assert any("serveurs/pharos_docs/serveur.py" in m and "laissé" in m for m in messages)


def test_branche_existante(travail):
    d.depart(travail, 1)
    git(travail, "add", "-A")
    git(travail, "commit", "-q", "-m", "LAB 1")
    git(travail, "switch", "-q", "main")
    messages = d.depart(travail, 1)
    assert git(travail, "branch", "--show-current") == "binome-3-lab01"
    assert any("existe déjà" in m for m in messages)
    assert git(travail, "log", "-1", "--format=%s") == "LAB 1"


def test_depart_depuis_tete_detachee(travail):
    git(travail, "switch", "-q", "--detach", "HEAD")
    d.depart(travail, 1)
    assert git(travail, "branch", "--show-current") == "binome-3-lab01"


def test_checkpoint_introuvable(travail):
    with pytest.raises(d.Refus, match="introuvable"):
        d.depart(travail, 2)


def test_lab_inconnu(travail):
    with pytest.raises(d.Refus, match="LAB 9"):
        d.depart(travail, 9)


def test_main_refus_code_1(travail, monkeypatch, capsys):
    monkeypatch.chdir(travail)
    (travail / ".env").write_text("")
    assert d.main(["1"]) == 1
    assert "Départ refusé" in capsys.readouterr().out


def test_copier_ne_signale_pas_un_fichier_identique(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("a")
    (tmp_path / "src" / "b.py").write_text("b")
    (tmp_path / "dst").mkdir()
    (tmp_path / "dst" / "a.py").write_text("a")
    (tmp_path / "dst" / "b.py").write_text("mon travail")
    copies, laisses = copier(tmp_path / "src", tmp_path / "dst", ecraser=False)
    assert copies == [] and [str(p) for p in laisses] == ["b.py"]


def test_copier_ignore_les_caches(tmp_path):
    (tmp_path / "src" / "__pycache__").mkdir(parents=True)
    (tmp_path / "src" / "__pycache__" / "a.pyc").write_bytes(b"")
    (tmp_path / "src" / "a.py").write_text("a")
    copies, laisses = copier(tmp_path / "src", tmp_path / "dst", ecraser=False)
    assert [str(p) for p in copies] == ["a.py"] and laisses == []
