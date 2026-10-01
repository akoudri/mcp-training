"""Harnais du jeu d'évaluation (LAB 15) — fourni : fige le contexte, fait tourner l'agent du binôme, note, écrit.

    probleme = contexte_fige(cas, aujourdhui=…, base=…, racine=…)   # [] si tout concorde, sinon pourquoi refuser
    resultat = lancer(cas, fois=3, parallele=3)                       # le résultat (dict), voir outils.evaluation.resultats

Pour chaque cas, avant d'exécuter : la date du cas est celle de l'horloge des serveurs, l'empreinte de la base est
celle du cas, l'identité est connue ; aucun document du LAB 14 n'est encore indexé par pharos-docs (il supplanterait
le contrat de l'escale dans tous les cas). Puis, pour chaque exécution : le jeton de l'identité, le plan accepté
(« ok »), la confirmation répondue selon le cas (défaut : refuser — le jeu ne publie jamais), les mocks en mode
nominal ; un cas de sécurité charge son document piégé (contrats-partages/evaluation/) le temps de ses exécutions,
seul — aucun autre cas ne tourne pendant ce temps. Un appel de recalculer_plan_quai sans quai (la journée entière,
lente) n'est pas exécuté : le modèle reçoit un refus, et l'exécution le signale dans ses avertissements.

L'agent est celui du binôme : pharos_client.boucle.executer (LAB 13), appelé tel quel. Trois cas tournent en
parallèle, chacun dans son processus (identité, réponses et compteurs propres) ; les cas de sécurité ensuite, un à
un. Les tokens et le coût viennent de l'usage rendu par OpenRouter à chaque appel au modèle.
"""

from __future__ import annotations

import contextlib
import importlib
import inspect
import io
import multiprocessing
import os
import re
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path

from outils.evaluation.cas import Cas
from outils.evaluation.notation import noter, outils_de

RACINE = Path(__file__).resolve().parents[2]
CONFIG = RACINE / "labs" / "lab13" / "serveurs.json"
DOSSIER_EVALUATION = Path("contrats-partages") / "evaluation"
ESCALE_PAR_DEFAUT = "ESC-2026-0412"
_ESCALE = re.compile(r"^Escale\s*:\s*(ESC-\d{4}-\d{4})\s*$", re.IGNORECASE | re.MULTILINE)
REFUS_JOURNEE = ("Le jeu d'évaluation n'exécute pas recalculer_plan_quai sur la journée entière (trop lent) : "
                 "préciser le quai.")


def contexte_fige(cas: list[Cas], *, aujourdhui: str, base: str, racine: Path = RACINE) -> list[str]:
    """Ce qui empêche de comparer deux exécutions : chaque écart est une raison de ne pas lancer."""
    problemes = []
    for c in cas:
        if c.contexte.date != aujourdhui:
            problemes.append(f"{c.id} : date {c.contexte.date}, mais l'horloge des serveurs est au {aujourdhui}.")
        if c.contexte.base != base:
            problemes.append(f"{c.id} : empreinte de base {c.contexte.base}, mais la base actuelle est {base} "
                             "(make lab8-base recharge la base de salle ; make lab15-empreinte l'affiche).")
    restes = sorted(p.relative_to(racine) for p in (racine / "contrats-partages").glob("binome-*/*.pdf"))
    if restes:
        problemes.append("documents du LAB 14 encore indexés par pharos-docs — ils supplantent le contrat de "
                         f"l'escale dans tous les cas : {', '.join(map(str, restes))}. Les mettre de côté, par "
                         "exemple : mkdir -p sortie/lab14 && mv contrats-partages/binome-* sortie/lab14/")
    return problemes


def escale_du_document(markdown: str) -> str:
    m = _ESCALE.search(markdown)
    return m.group(1) if m else ESCALE_PAR_DEFAUT


@contextlib.contextmanager
def document_charge(cas: Cas, racine: Path = RACINE):
    """Le document piégé d'un cas de sécurité, en PDF au format du corpus, le temps du bloc — puis retiré."""
    if not cas.document:
        yield None
        return
    from pharos_docs import depot

    markdown = (racine / cas.document).read_text(encoding="utf-8")
    chemin = depot.ecrire_pdf(markdown, escale_id=escale_du_document(markdown), suffixe="inj1",
                              dossier=racine / DOSSIER_EVALUATION)
    try:
        yield chemin
    finally:
        chemin.unlink(missing_ok=True)


def _repondre(confirmation: str):
    accepter = confirmation == "accepter"

    def repondre(demande: dict) -> dict:
        proprietes = (demande.get("schema") or {}).get("properties") or {}
        return {"action": "accept",
                "content": {champ: accepter for champ, p in proprietes.items() if p.get("type") == "boolean"}}
    return repondre


def _prend_config(executer) -> bool:
    try:
        parametres = inspect.signature(executer).parameters
    except (TypeError, ValueError):
        return False
    return "config" in parametres or any(p.kind is p.VAR_KEYWORD for p in parametres.values())


def executer_une(cas: Cas, config: Path | None = CONFIG) -> dict:
    """Une exécution de l'agent du binôme sur un cas, notée. Ne lève jamais : un échec est un résultat."""
    boucle = importlib.import_module("pharos_client.boucle")
    entrees = importlib.import_module("pharos_client.entrees")
    plan = importlib.import_module("pharos_client.plan")
    modele = importlib.import_module("pharos_client.modele")
    from pharos_client.transport import Resultat

    compteur = {"entree": 0, "sortie": 0, "cout": 0.0}
    avertissements: list[str] = []
    completer, appeler_brut = modele.completer, entrees.appeler_brut

    def completer_compte(*args, **kwargs):
        reponse = completer(*args, **kwargs)
        usage = reponse.usage or {}
        compteur["entree"] += int(usage.get("prompt_tokens") or 0)
        compteur["sortie"] += int(usage.get("completion_tokens") or 0)
        compteur["cout"] += float(usage.get("cost") or 0)
        return reponse

    def appeler_garde(session, nom, arguments, **options):
        if nom == "recalculer_plan_quai" and arguments.get("quai") in (None, ""):
            avertissements.append("recalculer_plan_quai demandé sur la journée entière : non exécuté")
            return Resultat(REFUS_JOURNEE, True, len(REFUS_JOURNEE.encode("utf-8")))
        return appeler_brut(session, nom, arguments, **options)

    anciens = (plan.valider_plan, plan.afficher_plan, entrees.demander_utilisateur, os.environ.get("PHAROS_JETON"))
    plan.valider_plan, plan.afficher_plan = (lambda etapes: "ok"), (lambda etapes, sortie=print: "")
    entrees.demander_utilisateur = _repondre(cas.contexte.confirmation)
    modele.completer, entrees.appeler_brut = completer_compte, appeler_garde
    os.environ["PHAROS_JETON"] = cas.contexte.jeton
    debut = time.monotonic()
    reponse, trace, arret = "", [], None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            options = {"config": config} if config is not None and _prend_config(boucle.executer) else {}
            execution = boucle.executer(cas.question, **options)
        reponse, trace = execution.reponse or "", list(execution.trace)
    except boucle.ArretBoucle as exc:
        arret, trace = str(exc), list(exc.trace or [])
    except Exception as exc:             # l'agent du binôme peut planter : c'est un échec du cas, pas du harnais
        arret = f"{exc.__class__.__name__} : {exc}"
    finally:
        plan.valider_plan, plan.afficher_plan, entrees.demander_utilisateur = anciens[:3]
        modele.completer, entrees.appeler_brut = completer, appeler_brut
        if anciens[3] is None:
            os.environ.pop("PHAROS_JETON", None)
        else:
            os.environ["PHAROS_JETON"] = anciens[3]
    reussite, raisons = noter(cas, reponse, trace, arret)
    return {"reussite": reussite, "raisons": raisons, "outils": outils_de(trace), "reponse": reponse,
            "tokens": {"entree": compteur["entree"], "sortie": compteur["sortie"]},
            "cout": round(compteur["cout"], 6), "duree_s": round(time.monotonic() - debut, 1), "arret": arret,
            "avertissements": avertissements,
            "trace": [asdict(e) if hasattr(e, "__dataclass_fields__") else dict(e) for e in trace]}


def executer_cas(cas: Cas, fois: int, racine: Path = RACINE) -> dict:
    """Les « fois » exécutions d'un cas, puis son taux : réussi si la tolérance est atteinte."""
    with document_charge(cas, racine):
        detail = [executer_une(cas, racine / "labs" / "lab13" / "serveurs.json") for _ in range(fois)]
    reussites = sum(d["reussite"] for d in detail)
    return {"id": cas.id, "famille": cas.famille, "question": cas.question,
            "tolerance": f"{cas.tolerance[0]}/{cas.tolerance[1]}", "reussites": reussites, "executions": fois,
            "reussi": cas.reussi(reussites, fois), "detail": detail}


def lancer(cas: list[Cas], *, fois: int = 3, parallele: int = 3, racine: Path = RACINE,
           afficher=print) -> list[dict]:
    """Tous les cas : les cas ordinaires « parallele » à la fois (un processus chacun), puis les cas de sécurité, un
    à un, seuls. parallele=1 : tout dans ce processus (tests, modèle simulé)."""
    ordinaires = [c for c in cas if not c.document]
    a_part = [c for c in cas if c.document]
    resultats: dict[str, dict] = {}

    def fini(r: dict) -> None:
        resultats[r["id"]] = r
        afficher(f"  {'✅' if r['reussi'] else '❌'} {r['id']} ({r['famille']}) : {r['reussites']}/{r['executions']}")

    if parallele > 1 and len(ordinaires) > 1:
        with ProcessPoolExecutor(max_workers=parallele, mp_context=multiprocessing.get_context("spawn")) as pool:
            for r in pool.map(executer_cas, ordinaires, [fois] * len(ordinaires), [racine] * len(ordinaires)):
                fini(r)
    else:
        for c in ordinaires:
            fini(executer_cas(c, fois, racine))
    for c in a_part:
        fini(executer_cas(c, fois, racine))
    return [resultats[c.id] for c in cas]


def assembler(cas_resultats: list[dict], *, fois: int, modele: str, empreintes: dict, horodatage: str) -> dict:
    details = [d for c in cas_resultats for d in c["detail"]]
    return {"horodatage": horodatage, "modele": modele, "empreintes": empreintes, "fois": fois,
            "cas": cas_resultats, "cout_total": round(sum(d["cout"] for d in details), 6),
            "tokens_total": sum(d["tokens"]["entree"] + d["tokens"]["sortie"] for d in details)}
