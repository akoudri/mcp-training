import subprocess
from pathlib import Path

import pytest

from outils import construire_etats as ce


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
    ecrire(r, "gabarits/lab01/labs/lab1/resultats.md", "grille\n")
    ecrire(r, "gabarits/lab04/client/pharos_client/boucle.py", "# squelette boucle\n")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "kit")
    git(r, "branch", "etat/fa2-fin")
    git(r, "switch", "-q", "-c", "solutions")
    ecrire(r, "solutions/lab01/serveurs/pharos_docs/serveur.py", "# solution 1\n")
    ecrire(r, "solutions/lab04/client/pharos_client/boucle.py", "# solution boucle\n")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "solutions")
    git(r, "switch", "-q", "main")
    return r


def fichier(r, ref, chemin):
    return subprocess.run(["git", "show", f"{ref}:{chemin}"], cwd=r, capture_output=True, text=True)


def test_etats_cumules(depot):
    base = git(depot, "rev-parse", "main")
    fa2 = git(depot, "rev-parse", "etat/fa2-fin")
    messages = ce.construire(depot, labs=[1, 4])
    assert fichier(depot, "etat/pr2-fin", "serveurs/pharos_docs/serveur.py").stdout == "# solution 1\n"
    assert fichier(depot, "etat/pr2-fin", "labs/lab1/resultats.md").stdout == "grille\n"
    assert fichier(depot, "etat/pr2-fin", "client/pharos_client/boucle.py").returncode != 0
    assert fichier(depot, "etat/or1-fin", "serveurs/pharos_docs/serveur.py").stdout == "# solution 1\n"
    assert fichier(depot, "etat/or1-fin", "client/pharos_client/boucle.py").stdout == "# solution boucle\n"
    assert fichier(depot, "etat/or1-fin", "solutions/lab01/serveurs/pharos_docs/serveur.py").returncode != 0
    assert git(depot, "rev-parse", "etat/or1-fin^") == base
    # etat/fa2-fin est avancé en avance rapide sur la base : ici la base n'a pas bougé depuis sa
    # création, donc il reste au même sha (pas un « jamais touché » : un avancement sans effet).
    assert git(depot, "rev-parse", "etat/fa2-fin") == fa2
    assert any("fa2-fin" in m for m in messages)
    assert any("LAB 2 : pas d'instantané" in m for m in messages)
    assert len(git(depot, "worktree", "list").splitlines()) == 1


def test_idempotent_et_prefixe(depot):
    ce.construire(depot, labs=[1], prefixe="essai/")
    ce.construire(depot, labs=[1], prefixe="essai/")
    assert fichier(depot, "essai/etat/pr2-fin", "serveurs/pharos_docs/serveur.py").stdout == "# solution 1\n"
    assert subprocess.run(["git", "rev-parse", "--verify", "--quiet", "etat/pr2-fin"], cwd=depot).returncode != 0


def test_depuis_une_branche_qui_contient_les_solutions(depot):
    ce.construire(depot, base="solutions", solutions="solutions", labs=[1], prefixe="essai/")
    assert fichier(depot, "essai/etat/pr2-fin", "solutions/lab01/serveurs/pharos_docs/serveur.py").returncode != 0


def test_refus_si_la_branche_cible_est_extraite(depot):
    git(depot, "switch", "-q", "-c", "etat/pr2-fin")
    with pytest.raises(ce.Refus, match="extraite"):
        ce.construire(depot, labs=[1])


def test_pousser(depot, tmp_path):
    distant = tmp_path / "distant.git"
    git(tmp_path, "init", "-q", "--bare", str(distant))
    git(depot, "remote", "add", "origin", str(distant))
    ce.construire(depot, labs=[1], pousser=True)
    assert git(distant, "rev-parse", "etat/pr2-fin") == git(depot, "rev-parse", "etat/pr2-fin")


def test_pousser_refuse_si_arbre_modifie(depot):
    (depot / "README.md").write_text("modifié\n")
    with pytest.raises(ce.Refus, match="modifications"):
        ce.construire(depot, labs=[1], pousser=True)


def test_fa2_fin_ancetre_avance_sur_la_base(depot):
    ecrire(depot, "AUTRE.md", "suite du kit\n")
    git(depot, "add", "-A")
    git(depot, "commit", "-q", "-m", "suite du kit")
    nouvelle_base = git(depot, "rev-parse", "main")
    messages = ce.construire(depot, labs=[1])
    assert git(depot, "rev-parse", "etat/fa2-fin") == nouvelle_base
    assert any("fa2-fin" in m and "avancé" in m for m in messages)


def test_fa2_fin_divergent_refuse(depot):
    git(depot, "switch", "-q", "etat/fa2-fin")
    ecrire(depot, "DIVERGENCE.md", "autre historique\n")
    git(depot, "add", "-A")
    git(depot, "commit", "-q", "-m", "divergence")
    git(depot, "switch", "-q", "main")
    avant = git(depot, "rev-parse", "etat/fa2-fin")
    with pytest.raises(ce.Refus, match="divergé"):
        ce.construire(depot, labs=[1])
    assert git(depot, "rev-parse", "etat/fa2-fin") == avant


def test_pousser_fa2_fin(depot, tmp_path):
    distant = tmp_path / "distant.git"
    git(tmp_path, "init", "-q", "--bare", str(distant))
    git(depot, "remote", "add", "origin", str(distant))
    ce.construire(depot, labs=[1], pousser=True)
    assert git(distant, "rev-parse", "etat/fa2-fin") == git(depot, "rev-parse", "etat/fa2-fin")


def test_pousser_refuse_si_le_distant_a_avance(depot, tmp_path):
    distant = tmp_path / "distant.git"
    git(tmp_path, "init", "-q", "--bare", str(distant))
    git(depot, "remote", "add", "origin", str(distant))
    ce.construire(depot, labs=[1], pousser=True)
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(distant), str(clone))
    git(clone, "config", "user.name", "concurrent")
    git(clone, "config", "user.email", "concurrent@example.invalid")
    git(clone, "switch", "-q", "etat/pr2-fin")
    ecrire(clone, "AILLEURS.md", "avance concurrente\n")
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", "avance concurrente")
    git(clone, "push", "-q", "origin", "etat/pr2-fin")
    with pytest.raises(ce.Refus, match="stale info|rejected"):
        ce.construire(depot, labs=[1], pousser=True)


def test_superposer(tmp_path):
    ecrire(tmp_path, "g/lab01/a.txt", "gabarit")
    ecrire(tmp_path, "g/lab01/b.txt", "gabarit b")
    ecrire(tmp_path, "s/lab01/a.txt", "solution")
    notes = ce.superposer(tmp_path / "d", tmp_path / "g", tmp_path / "s", 2)
    assert (tmp_path / "d" / "a.txt").read_text() == "solution"
    assert (tmp_path / "d" / "b.txt").read_text() == "gabarit b"
    assert notes == ["LAB 2 : pas d'instantané de solution — gabarits seuls."]
