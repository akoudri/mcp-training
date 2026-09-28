import os
import shutil
from pathlib import Path

import pytest

from outils.labs import copier
from outils.verifier.commun import Etat
from tests.aides import DSN_TEST, RACINE_KIT, base_requise, etat_complet, importer_paquet

pytestmark = pytest.mark.skipif(not Path("solutions/lab14").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")


def _viser(lab14, etat: Path) -> None:
    lab14.RACINE = etat
    lab14.SECURITE = etat / "securite"
    lab14.MANCHES = etat / "labs" / "lab14"
    lab14.PIEGES = etat / "gabarits" / "lab14" / "pieges"


async def _executer(etat: Path, monkeypatch):
    from donnees.base.__main__ import charger
    from outils.verifier import lab14

    await charger(DSN_TEST, politique=etat / "labs" / "lab9" / "politique.sql")
    for cle, val in (("CLE_ETAT", "pharos-salle-2026-cle-etat-mrtr-partagee"), ("METEO_CLE", "meteo-salle-2026"),
                     ("CLE_SERVEUR", "pharos-salle-2026")):
        monkeypatch.setenv(cle, val)
    _viser(lab14, etat)
    return await lab14.v.executer(sans_modele=True)


def echecs(rapport) -> dict[str, str]:
    return {r.libelle: r.detail for r in rapport.resultats if r.etat is Etat.ECHEC}


@pytest.fixture(scope="module")
def etat_solution(tmp_path_factory):
    etat = etat_complet(tmp_path_factory.mktemp("etat-lab14"), 14)
    copier(RACINE_KIT / "gabarits" / "lab14" / "pieges", etat / "gabarits" / "lab14" / "pieges", ecraser=True)
    return etat


@base_requise
async def test_la_solution_passe_son_verificateur(etat_solution, base_de_test, monkeypatch):
    rapport = await _executer(etat_solution, monkeypatch)
    assert echecs(rapport) == {}, rapport.texte()


@base_requise
async def test_le_gabarit_echoue(base_de_test, monkeypatch, tmp_path):
    etat = etat_complet(tmp_path / "etat", 13)
    copier(RACINE_KIT / "gabarits" / "lab14", etat, ecraser=False)
    rapport = await _executer(etat, monkeypatch)
    rates = " ".join(echecs(rapport))
    for debut in ("Manche 1 consignée", "Fiches de sécurité", "Deux contre-mesures actives",
                  "L'attaque de la manche 1 ne passe plus"):
        assert debut in rates, rapport.texte()


MUTATIONS = {
    "sans_allowlist": ("serveurs/pharos_ops/serveur.py",
                       'if destinataire not in DESTINATAIRES:', 'if False and destinataire not in DESTINATAIRES:',
                       "L'attaque de la manche 1 ne passe plus", "B :"),
    "sans_moindre_privilege": ("serveurs/pharos_ops/serveur.py",
                               'if identite.profil == "agent" and identite.agent_id:',
                               'if False and identite.profil == "agent" and identite.agent_id:',
                               "L'attaque de la manche 1 ne passe plus", "C :"),
    "fiche_vide": ("securite/fiche-pharos-ops.md", "| **Propriétaire** |", "| **Propriétaire** À REMPLIR |",
                   "Fiches de sécurité", "À REMPLIR"),
    "manche1_vide": ("labs/lab14/manche1.md", "**Objectif choisi** : B", "**Objectif choisi** : À REMPLIR",
                     "Manche 1 consignée", "remplir"),
}


@base_requise
@pytest.mark.parametrize("defaut", sorted(MUTATIONS))
async def test_chaque_defaut_est_vu(etat_solution, defaut, base_de_test, monkeypatch, tmp_path):
    fichier, avant, apres, critere, message = MUTATIONS[defaut]
    copie = tmp_path / "etat"
    shutil.copytree(etat_solution, copie)
    chemin = copie / fichier
    texte = chemin.read_text(encoding="utf-8")
    assert avant in texte, f"mutation {defaut} : « {avant} » introuvable dans {fichier}"
    chemin.write_text(texte.replace(avant, apres), encoding="utf-8")
    rapport = await _executer(copie, monkeypatch)
    rates = echecs(rapport)
    assert any(l.startswith(critere) and message in d for l, d in rates.items()), rapport.texte()


def test_fiches_et_manches_de_la_solution_sont_remplies(etat_solution):
    for s in ("pharos-docs", "pharos-data", "pharos-ops"):
        assert "À REMPLIR" not in (etat_solution / "securite" / f"fiche-{s}.md").read_text(encoding="utf-8")
    for m in ("manche1", "manche2", "manche3"):
        assert "À REMPLIR" not in (etat_solution / "labs" / "lab14" / f"{m}.md").read_text(encoding="utf-8")


def test_le_contrat_depose_supplante_le_contrat_de_base(etat_solution, monkeypatch):
    """LAB 14 : le contrat déposé dans le dépôt partagé (document_id « -inj ») doit l'emporter sur le
    contrat de base — c'est le vecteur d'attaque. Sans dépôt, le contrat de base reste rendu (no-op)."""
    with importer_paquet(etat_solution, "serveurs"):
        from pharos_docs import extraction
        from serveurs.pharos_docs.serveur import _contrat

        base = extraction.Document("CM-0412", "contrat_manutention", "ESC-2026-0412", 3)
        depose = extraction.Document("CM-0412-inj1", "contrat_manutention", "ESC-2026-0412", 1)

        monkeypatch.setattr(extraction, "documents_de_escale", lambda escale_id: [base, depose])
        assert _contrat("ESC-2026-0412").document_id == "CM-0412-inj1"

        monkeypatch.setattr(extraction, "documents_de_escale", lambda escale_id: [base])
        assert _contrat("ESC-2026-0412").document_id == "CM-0412"
