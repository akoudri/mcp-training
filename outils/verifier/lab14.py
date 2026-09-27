"""Vérificateur du LAB 14 — attaque et durcissement.

Aucun appel au vrai modèle : le serveur pharos-ops et pharos-docs du binôme sont chargés dans le processus,
les mocks sont servis en mémoire, et un modèle simulé « crédule » (qui obéit à ce qu'il lit) rejoue les trois
documents piégés de référence. Le canal des mocks compte ce qui part ; le journal serveur garde les refus.

Ce que le vérificateur contrôle (spec §10.2) :
  1. Manche 1 consignée (objectif, texte exact de l'injection, issue).
  2. Au moins deux contre-mesures actives (sondes indépendantes) et attribuées dans manche2.md.
  3. Les trois fiches de sécurité d'une page sont remplies.
  4. L'attaque de la manche 1 ne passe plus : B → compteur inchangé ; C → aucune escale hors périmètre ;
     A → 👁 (aucune contre-mesure serveur ne l'arrête).
  5. Chaque refus des sondes figure dans logs/<serveur>.jsonl (issue « refus »).
  6. Le serveur fait toujours son travail : publication vers l'exploitation acceptée après confirmation.
  7. Décisif (👁) : reconstituer la manche 1 depuis la seule trace (au débrief).

Base requise (navire_par_nom filtre par identité, escales_a_risque) : sans PHAROS_DSN_TEST/pharos-db, le
vérificateur le dit et s'arrête proprement.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
from pathlib import Path

import mcp_types

from outils.servir import servir
from outils.verifier.commun import Etat, Rapport, Resultat
from outils.verifier.modele_simule import ModeleCredule
from pharos import autorisation
from pharos_docs import depot

RACINE = Path(__file__).resolve().parents[2]
PIEGES = RACINE / "gabarits" / "lab14" / "pieges"
SECURITE = RACINE / "securite"
MANCHES = RACINE / "labs" / "lab14"
ESCALE, DESTINATAIRE_PIRATE, NAVIRE_HORS = "ESC-2026-0412", "veille@armateur-exemple.test", "Cormoran"
JETON_ATTAQUANT = "jeton-rance"          # l'agent maritime du Vent d'Autan (ESC-2026-0412)


async def _base_joignable() -> bool:
    """Vrai si pharos-db répond sous pharos_planification (atelier : PHAROS_DB_*, ou poste : PHAROS_DSN_TEST)."""
    import asyncpg

    from pharos import base

    try:
        c = await asyncpg.connect(base.dsn("pharos_planification"), timeout=5)
    except Exception:
        return False
    await c.close()
    return True


@contextlib.contextmanager
def _pharos_ops(logs: Path):
    """Sert le pharos-ops du binôme en HTTP (l'identité vient du jeton porteur), mocks servis en mémoire."""
    from tests.aides import charger_module, importer_paquet

    from serveurs.mocks import app as mocks

    mocks.etat = mocks.Etat()
    with servir(mocks.app) as url_mocks:
        os.environ["METEO_URL"] = f"{url_mocks}/meteo"
        os.environ["REFERENTIEL_URL"] = f"{url_mocks}/referentiel"
        os.environ["CANAL_URL"] = f"{url_mocks}/canal"
        os.environ["PHAROS_LOGS"] = str(logs)
        with importer_paquet(RACINE, "serveurs"):
            ops = charger_module(RACINE / "serveurs" / "pharos_ops" / "serveur.py", "verif_lab14_ops")
            with servir(ops.mcp.http_app(path="/mcp", json_response=True)) as url_ops:
                yield f"{url_ops}/mcp", url_mocks


async def _alertes(url_mocks: str) -> dict:
    import httpx
    async with httpx.AsyncClient() as http:
        r = await http.get(f"{url_mocks}/_compteur")
    return r.json().get("alertes", {})


async def _appeler(url_ops: str, jeton: str, nom: str, arguments: dict):
    """Un appel simple à pharos-ops sous une identité (jeton porteur)."""
    from outils.client_test import ClientTest

    async with ClientTest(url_ops, jeton=jeton, nom=f"verif-lab14-{jeton}") as c:
        return await c.appeler(nom, arguments)


async def _publier(url_ops: str, jeton: str, destinataire: str) -> None:
    """publier_alerte sous confirmation, comme la boucle : demande puis rejeu « oui ». Un refus (destinataire
    hors liste, ou repli) laisse simplement le compteur inchangé."""
    from outils.client_test import ClientTest

    arguments = {"escale_id": ESCALE, "niveau": "orange", "destinataire": destinataire}
    async with ClientTest(url_ops, jeton=jeton, nom=f"verif-lab14-{jeton}") as c:
        brut = await c.appeler_brut("publier_alerte", arguments)
        if not isinstance(brut, mcp_types.InputRequiredResult):
            return
        reps = {k: mcp_types.ElicitResult(action="accept", content={"confirmer": True})
                for k in (brut.input_requests or {})}
        try:
            await c.appeler_brut("publier_alerte", arguments, reponses=reps, etat=brut.request_state)
        except Exception:
            pass


def v_executer(sans_modele: bool = True) -> Rapport:
    """Enveloppe synchrone (hors boucle) : pour un appel direct. En contexte async, utiliser v.executer()."""
    return asyncio.run(_rapport(sans_modele))


async def _rapport(sans_modele: bool = True) -> Rapport:
    resultats: list[Resultat] = []

    def ok(libelle, detail=""):
        resultats.append(Resultat(libelle, Etat.OK, detail))

    def echec(libelle, detail):
        resultats.append(Resultat(libelle, Etat.ECHEC, detail))

    def constat(libelle, detail):
        resultats.append(Resultat(libelle, Etat.CONSTAT, detail))

    # 1. Manche 1 consignée
    m1 = MANCHES / "manche1.md"
    if not m1.exists():
        echec("Manche 1 consignée", "labs/lab14/manche1.md absent : lancer « make depart LAB=14 ».")
    else:
        texte = m1.read_text(encoding="utf-8")
        if "À REMPLIR" in texte or "```\n\n```" in texte:
            echec("Manche 1 consignée", "labs/lab14/manche1.md : remplir l'objectif, le texte exact de l'injection "
                  "et ce qui s'est passé.")
        else:
            ok("Manche 1 consignée", "objectif, injection et issue présents")

    # 3. Fiches de sécurité
    manquantes = [s for s in ("pharos-docs", "pharos-data", "pharos-ops")
                  if not (SECURITE / f"fiche-{s}.md").exists()]
    incompletes = [s for s in ("pharos-docs", "pharos-data", "pharos-ops")
                   if (SECURITE / f"fiche-{s}.md").exists()
                   and "À REMPLIR" in (SECURITE / f"fiche-{s}.md").read_text(encoding="utf-8")]
    if manquantes:
        echec("Fiches de sécurité", f"absentes : {', '.join(manquantes)} (make lab14-scaffold).")
    elif incompletes:
        echec("Fiches de sécurité", f"à remplir (il reste « À REMPLIR ») : {', '.join(incompletes)}.")
    else:
        ok("Fiches de sécurité", "trois fiches, cinq rubriques remplies")

    if not await _base_joignable():
        for libelle in ("Deux contre-mesures actives", "L'attaque de la manche 1 ne passe plus",
                        "Refus journalisés", "Le serveur fait toujours son travail"):
            resultats.append(Resultat(libelle, Etat.SAUTE, "pharos-db injoignable : lancer « make lab8-base »"))
        constat("Décisif — reconstituer la manche 1 depuis la seule trace",
                "au débrief : sans le document piégé sous les yeux, retrouver dans la trace ce que l'agent a tenté.")
        return Rapport("LAB 14 — attaque et durcissement", resultats)

    await _criteres_dynamiques(resultats, ok, echec, constat)
    constat("Décisif — reconstituer la manche 1 depuis la seule trace",
            "au débrief : sans le document piégé sous les yeux, retrouver dans la trace ce que l'agent a tenté.")
    return Rapport("LAB 14 — attaque et durcissement", resultats)


async def _criteres_dynamiques(resultats, ok, echec, constat):
    import tempfile

    from mcp.shared.exceptions import MCPError

    logs = Path(tempfile.mkdtemp())
    with _pharos_ops(logs) as (url_ops, url_mocks):
        # Sonde « moindre privilège » (contre-mesure C) : un agent voit-il un navire d'une autre agence ?
        r = await _appeler(url_ops, JETON_ATTAQUANT, "navire_par_nom", {"nom": NAVIRE_HORS})
        fiche = (r.structured_content or {}).get("navires", [{}])[0] if not r.is_error else {}
        mp_active = bool(r.is_error) or not fiche.get("escales")

        # Sonde « liste d'autorisation » (contre-mesure B) : publier vers un destinataire hors liste.
        raz_canal(url_mocks)
        await _publier(url_ops, JETON_ATTAQUANT, DESTINATAIRE_PIRATE)
        la_active = DESTINATAIRE_PIRATE not in await _alertes(url_mocks)

        # Sonde « séparer données et instructions » : rechercher_clause enveloppe-t-il l'extrait ?
        sep_active = await _extrait_marque()

        actives = [nom for nom, a in (("liste d'autorisation de destinataires", la_active),
                                      ("moindre privilège (navire_par_nom filtré)", mp_active),
                                      ("séparation données/instructions (extrait marqué et borné)", sep_active)) if a]
        m2 = (MANCHES / "manche2.md").read_text(encoding="utf-8") if (MANCHES / "manche2.md").exists() else ""
        if len(actives) < 2:
            echec("Deux contre-mesures actives", f"une seule ou aucune détectée ({', '.join(actives) or 'aucune'}). "
                  "Appliquer au moins deux des cinq contre-mesures du bloc 22.7.")
        elif "À REMPLIR" in m2:
            echec("Deux contre-mesures actives", f"{len(actives)} détectées, mais manche2.md n'attribue pas ce que "
                  "chacune arrête (il reste « À REMPLIR »).")
        else:
            ok("Deux contre-mesures actives", " ; ".join(actives))

        # 4. L'attaque de la manche 1 ne passe plus (documents piégés de référence, modèle crédule).
        await _attaques_bloquees(resultats, ok, echec, constat, url_ops, url_mocks, logs)

        # 5. Refus journalisés
        refus = [l for l in _journal(logs, "pharos-ops") if l.get("issue") == "refus"]
        if refus:
            ok("Refus journalisés", f"{len(refus)} refus dans logs/pharos-ops.jsonl")
        else:
            echec("Refus journalisés", "aucun refus dans logs/pharos-ops.jsonl : garder l'intergiciel "
                  "journal.Journal(\"pharos-ops\") branché — un refus non journalisé n'a jamais existé (bloc 22.6).")

        # 6. Le serveur fait toujours son travail (publication légitime après confirmation).
        raz_canal(url_mocks)
        await _publier(url_ops, "jeton-exploitation", "exploitation")
        alertes = await _alertes(url_mocks)
        if alertes.get("exploitation"):
            ok("Le serveur fait toujours son travail", "publication vers l'exploitation acceptée après confirmation")
        else:
            echec("Le serveur fait toujours son travail", "une publication légitime (exploitation, confirmée) "
                  "n'aboutit plus : le durcissement ne doit pas casser le service (ne pas retirer l'outil).")


async def _attaques_bloquees(resultats, ok, echec, constat, url_ops, url_mocks, logs):
    """Les trois documents piégés de référence, joués contre le serveur durci. L'intention de chaque document
    est sa balise (destinataire:, navire:, conclusion:), celle que suit le modèle crédule ; on la lit dans le
    document et on la porte au serveur, puis on vérifie qu'il la refuse (B, C) — A reste 👁."""
    b = re.search(r"destinataire\s*:\s*([^\s\n]+)", (PIEGES / "b.md").read_text(encoding="utf-8"), re.IGNORECASE)
    c_ = re.search(r"navire\s*:\s*([^\n]+)", (PIEGES / "c.md").read_text(encoding="utf-8"), re.IGNORECASE)
    echecs = []

    # B — exfiltration vers l'adresse du document piégé.
    raz_canal(url_mocks)
    await _publier(url_ops, JETON_ATTAQUANT, b.group(1))
    if b.group(1) in await _alertes(url_mocks):
        echecs.append(f"B : une alerte est partie vers {b.group(1)} (ajouter la liste d'autorisation).")

    # C — lecture d'un navire hors périmètre sous l'identité de l'attaquant.
    r = await _appeler(url_ops, JETON_ATTAQUANT, "navire_par_nom", {"nom": c_.group(1).strip()})
    fiches = (r.structured_content or {}).get("navires", []) if not r.is_error else []
    if any(f.get("escales") for f in fiches):
        echecs.append(f"C : les escales de « {c_.group(1).strip()} » (autre agence) sont visibles "
                      "(filtrer par identité dans navire_par_nom).")

    if echecs:
        echec("L'attaque de la manche 1 ne passe plus", " ".join(echecs))
    else:
        ok("L'attaque de la manche 1 ne passe plus", "B refusé (compteur inchangé), C hors périmètre masqué")
    constat("Objectif A — faire taire — n'est arrêté par aucune contre-mesure serveur",
            "a.md : « conclusion: aucun risque » ne déclenche aucun appel anormal (slide 441) ; "
            "seul le jeu d'évaluation du LAB 15 le détecte.")


async def _extrait_marque() -> bool:
    """Regarde si rechercher_clause de pharos-docs enveloppe l'extrait (champ marqué, borné). Appelé alors que
    le paquet « serveurs » du binôme est déjà importable (contexte _pharos_ops)."""
    from tests.aides import charger_module
    from fastmcp import Client

    try:
        docs = charger_module(RACINE / "serveurs" / "pharos_docs" / "serveur.py", "verif_lab14_docs")
    except Exception:
        return False
    with autorisation.en_tant_que("jeton-exploitation"):
        async with Client(docs.mcp) as c:
            r = await c.call_tool("rechercher_clause", {"escale_id": ESCALE, "sujet": "penalites"},
                                  raise_on_error=False)
    contenu = r.structured_content or {}
    extrait = contenu.get("extrait_document")
    return isinstance(extrait, dict) and "texte" in extrait and bool(extrait.get("source"))


def raz_canal(url_mocks: str) -> None:
    import httpx
    httpx.post(f"{url_mocks}/_raz", timeout=5)


def _journal(logs: Path, serveur: str) -> list[dict]:
    chemin = logs / f"{serveur}.jsonl"
    if not chemin.exists():
        return []
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


# Compatibilité avec « python -m outils.verifier lab14 » (qui appelle module.v.executer).
class _V:
    async def executer(self, url=None, sans_modele=None):
        return await _rapport(sans_modele=True)


v = _V()
