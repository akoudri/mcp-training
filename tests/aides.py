"""Aides partagées par les tests du kit."""

from __future__ import annotations

import contextlib
import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from outils.construire_etats import superposer
from outils.servir import servir  # noqa: F401  (réexporté pour les tests)

RACINE_KIT = Path(__file__).resolve().parents[1]


def serveur_legacy_d_origine() -> bool:
    """Vrai si serveurs/pharos_legacy/serveur.py est le serveur d'origine (2025-11-25), faux sur un état de lab migré.

    Lu comme du texte, sans l'importer : un serveur en cours d'écriture (erreur de syntaxe) ne doit pas
    empêcher la collecte de toute la suite."""
    chemin = RACINE_KIT / "serveurs" / "pharos_legacy" / "serveur.py"
    try:
        return 'REVISION = "2025-11-25"' in chemin.read_text(encoding="utf-8")
    except OSError:
        return False


origine_seulement = pytest.mark.skipif(not serveur_legacy_d_origine(),
                                       reason="état de lab : serveurs/pharos_legacy/serveur.py est migré")


def serveur_quai_d_origine() -> bool:
    """Vrai si serveurs/pharos_quai/serveur.py porte le catalogue fourni, faux sur un état de lab réécrit (lu comme du texte)."""
    chemin = RACINE_KIT / "serveurs" / "pharos_quai" / "serveur.py"
    try:
        return 'description="Informations."' in chemin.read_text(encoding="utf-8")
    except OSError:
        return False


quai_d_origine = pytest.mark.skipif(not serveur_quai_d_origine(),
                                    reason="état de lab : le catalogue de serveurs/pharos_quai/serveur.py est réécrit")


def charger_module(chemin: Path, nom: str):
    """Importe un fichier Python sous un nom unique (gabarits et solutions ne sont pas des paquets du kit)."""
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    spec.loader.exec_module(module)
    return module


def _purger(prefixe: str) -> None:
    for nom in [n for n in sys.modules if n == prefixe or n.startswith(prefixe + ".")]:
        del sys.modules[nom]


@contextlib.contextmanager
def importer_paquet(dossier: Path, *paquets: str):
    """Rend importables, depuis « dossier », les paquets nommés (purgés de sys.modules avant et après)."""
    for paquet in paquets:
        _purger(paquet)
    sys.path.insert(0, str(dossier))
    try:
        yield
    finally:
        sys.path.remove(str(dossier))
        for paquet in paquets:
            _purger(paquet)


def importer_client(dossier: Path):
    """Rend importable le paquet pharos_client situé dans « dossier »."""
    return importer_paquet(dossier, "pharos_client")


@contextlib.contextmanager
def sans_paquet(*paquets: str):
    """Retire de sys.path toute entrée qui expose un des paquets nommés, et les purge de sys.modules ;
    restaure les deux à la sortie. Sert à isoler un test d'un paquet déjà présent par ailleurs (ex.
    client/pharos_client, présent sur etat/or1-fin et les états suivants, via le « pythonpath » de pytest)."""
    for paquet in paquets:
        _purger(paquet)
    chemin_original = list(sys.path)
    sys.path[:] = [p for p in sys.path if not any((Path(p) / paquet).is_dir() for paquet in paquets)]
    try:
        yield
    finally:
        sys.path[:] = chemin_original
        for paquet in paquets:
            _purger(paquet)


def serveur_demo() -> FastMCP:
    mcp = FastMCP("demo")

    @mcp.tool
    def etat(escale_id: str) -> dict:
        """Donne l'état d'une escale."""
        if escale_id != "ESC-2026-0412":
            raise ToolError("Escale inconnue.")
        return {"escale_id": escale_id, "quai": 3}

    @mcp.tool
    def echec() -> dict:
        """Échoue toujours."""
        raise RuntimeError("panne interne")

    return mcp


BOUCLE_MINIMALE = '''"""Boucle minimale pour les tests du kit : un tour d'outils, puis la réponse."""
import uuid

from pharos_client import modele
from pharos_client.trace import Enregistrement, borner
from pharos_client.transport import Session


def executer(question, *, url, **_):
    correlation, trace = uuid.uuid4().hex[:12], []
    messages = [{"role": "user", "content": question}]
    with Session(url) as s:
        outils = s.lister_outils()
        for tour in range(1, 5):
            r = modele.completer(messages, outils)
            messages.append(r.message)
            if not r.appels:
                return r.message.get("content") or "", trace
            for a in r.appels:
                res = s.appeler(a.nom, a.arguments, correlation=correlation)
                trace.append(Enregistrement(correlation, tour, a.nom, a.arguments, 0.0, res.octets, 1,
                                            res.est_erreur, borner(res.texte), s.url))
                messages.append({"role": "tool", "tool_call_id": a.id, "content": res.texte})
    return "", trace
'''


def client_minimal(dossier: Path) -> Path:
    """Le client du gabarit du LAB 4, avec une boucle minimale (sur main, aucune solution du LAB 4 n'est présente)."""
    shutil.copytree(RACINE_KIT / "gabarits" / "lab04" / "client", dossier, dirs_exist_ok=True)
    (dossier / "pharos_client" / "boucle.py").write_text(BOUCLE_MINIMALE, encoding="utf-8")
    return dossier


def etat_complet(destination: Path, lab: int) -> Path:
    """Copie du kit (comme une branche etat/*) avec gabarits et solutions superposés jusqu'au lab."""
    shutil.copytree(RACINE_KIT, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns(
        ".git", ".venv", "solutions", "__pycache__", ".pytest_cache", "logs", "sortie", ".superpowers", ".env"))
    superposer(destination, RACINE_KIT / "gabarits", RACINE_KIT / "solutions", lab)
    return destination


DSN_TEST = os.environ.get("PHAROS_DSN_TEST")
# Les tests sur la base la RECHARGENT : ils ne tournent que si PHAROS_DSN_TEST est défini (CI, poste du formateur :
# PHAROS_DSN_TEST=postgresql://postgres:pharos-salle-2026@127.0.0.1:5433/pharos), jamais par défaut.
base_requise = pytest.mark.skipif(not DSN_TEST, reason="PHAROS_DSN_TEST absent : tests sur la base sautés "
                                                       "(ils rechargent pharos-db)")


def un_cas(**champs):
    """Un cas d'évaluation (LAB 15) en mémoire, sans fichier : les champs donnés remplacent ceux par défaut."""
    from outils.evaluation import cas as cas_mod

    base = dict(id="c", famille="simple", contexte=cas_mod.Contexte("2026-10-06", "exploitation", "bb49a8976abecad4"),
                question="Quelle pénalité ?")
    return cas_mod.Cas(**{**base, **champs})
