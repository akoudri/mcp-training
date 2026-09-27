"""Vérificateur du LAB 13 — l'agent PHAROS complet : noms, mesures, aucune collision, consigne, serveur dans la
trace, plan avant action, confirmation avant publication, réponse texte sans extension, signaux de dérive, et la
note de la dernière exécution réelle.

Aucun appel au modèle : la boucle du binôme est jouée avec un modèle simulé (le plan, puis des appels répartis sur
les trois serveurs), la décision sur le plan et la réponse à la confirmation sont scriptées. Les serveurs sont ceux
de labs/lab13/serveurs.json (make lab13-tout) ; le canal des mocks compte ce qui part. Le critère décisif relit
labs/lab13/execution.json, produite par make lab13-question (vrai modèle).
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import io
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

from mcp.client.session import ClientSession

from outils import lab10, lab12, lab13
from outils.client_test import ClientTest
from outils.verifier.commun import Echec, Verification
from outils.verifier.modele_simule import ModeleSimule, appel
from outils.verifier.note import sans_origine, verifier_note

RACINE = Path(__file__).resolve().parents[2]
CONFIG = RACINE / "labs" / "lab13" / "serveurs.json"
MESURES = RACINE / "labs" / "lab13" / "mesures.md"
CONSIGNE = RACINE / "client" / "pharos_client" / "consigne.md"
DERNIERE = RACINE / "labs" / "lab13" / "execution.json"
JETON = "jeton-exploitation"
QUESTION = "L'escale du Vent d'Autan de jeudi est-elle à risque ? Si oui, prépare la note d'alerte pour l'exploitant."
ATTENDUS = {"pharos-docs": ["rechercher_clause"],
            "pharos-data": ["escales_a_risque", "conflits_de_creneau", "requete_mouvements"],
            "pharos-ops": ["meteo_creneau", "navire_par_nom", "recalculer_plan_quai", "publier_alerte"]}
DESCRIPTION_NAVIRES = "Fiche d'un navire à partir de son nom"
PUBLICATION = {"escale_id": "ESC-2026-0412", "niveau": "orange", "destinataire": "exploitation",
               "note": "Note simulée du vérificateur."}
SCENARIO = [("navire_par_nom", {"nom": "Vent d'Autan"}),
            ("rechercher_clause", {"escale_id": "ESC-2026-0412", "sujet": "penalites"}),
            ("escales_a_risque", {"date": "2026-10-08"}),
            ("publier_alerte", PUBLICATION)]
VUE = "ui://pharos-ops/plan-quai"

v = Verification("LAB 13 — l'agent PHAROS complet", "http://observateur:8103/mcp",
                 "make lab8-base, make lab10-mocks, puis make lab13-tout")


def _serveurs() -> list[dict]:
    if not CONFIG.exists():
        raise Echec("labs/lab13/serveurs.json absent : lancer « make depart LAB=13 ».")
    return json.loads(CONFIG.read_text(encoding="utf-8"))["serveurs"]


async def _catalogues(ctx) -> dict[str, list]:
    if "catalogues" not in ctx.cache:
        os.environ.setdefault("PHAROS_JETON", JETON)
        try:
            ctx.cache["catalogues"] = await lab13.lister(_serveurs())
        except SystemExit as exc:
            raise Echec(str(exc)) from exc
    return ctx.cache["catalogues"]


def _modules():
    try:
        return (importlib.import_module("pharos_client.boucle"), importlib.import_module("pharos_client.entrees"),
                importlib.import_module("pharos_client.plan"))
    except ModuleNotFoundError as exc:
        raise Echec(f"{exc.name} introuvable : ce lab part de etat/sr3-fin (make depart LAB=13).") from exc


def _plan_json(noms: list[str]) -> str:
    return json.dumps([{"etape": i, "outil": n, "raison": "scénario du vérificateur"} for i, n in enumerate(noms, 1)])


@contextlib.contextmanager
def _chronologie():
    """Enregistre, dans l'ordre, chaque tools/call (nom, arguments) et ce que la boucle avait écrit avant."""
    evenements, original, sortie = [], ClientSession.call_tool, io.StringIO()

    async def enregistrer(self, name, arguments=None, *args, **kwargs):
        evenements.append({"nom": name, "arguments": dict(arguments or {}), "affiche_avant": sortie.getvalue()})
        return await original(self, name, arguments, *args, **kwargs)

    ClientSession.call_tool = enregistrer
    try:
        with contextlib.redirect_stdout(sortie):
            yield evenements, sortie
    finally:
        ClientSession.call_tool = original


async def _jouer(ctx, *, decision: str = "ok", confirmer: bool = False, scenario=SCENARIO) -> dict:
    """La boucle du binôme, modèle simulé : le plan, puis le scénario, puis une note. Rend ce qui s'est passé."""
    boucle, entrees, plan = _modules()
    demandes: list[dict] = []

    def repondre(demande):
        demandes.append(demande)
        props = (demande.get("schema") or {}).get("properties") or {}
        return {"action": "accept", "content": {k: confirmer for k, p in props.items() if p.get("type") == "boolean"}}

    tours = [_plan_json([n for n, _ in scenario])] + [[appel(f"a{i}", n, a)] for i, (n, a) in enumerate(scenario, 1)]
    anciens = entrees.demander_utilisateur, plan.valider_plan, os.environ.get("PHAROS_JETON")
    entrees.demander_utilisateur, plan.valider_plan = repondre, (lambda etapes: decision)
    os.environ["PHAROS_JETON"] = JETON
    simule = ModeleSimule([*tours, "Note simulée : fin du scénario."])
    try:
        with _chronologie() as (evenements, sortie), simule:
            execution = await asyncio.to_thread(boucle.executer, QUESTION, config=CONFIG)
    except NotImplementedError as exc:
        raise Echec(f"pas encore écrit : {exc}") from exc
    except TypeError as exc:
        raise Echec(f"la boucle ne prend pas encore config= ({exc}) : executer(question, *, config=…) → "
                    "Execution(plan, reponse, trace).") from exc
    except Exception as exc:
        if hasattr(exc, "trace"):
            raise Echec(f"la boucle s'est arrêtée : {exc}") from exc
        raise
    finally:
        entrees.demander_utilisateur, plan.valider_plan = anciens[0], anciens[1]
        if anciens[2] is None:
            os.environ.pop("PHAROS_JETON", None)
        else:
            os.environ["PHAROS_JETON"] = anciens[2]
    return {"execution": execution, "evenements": evenements, "sortie": sortie.getvalue(), "demandes": demandes,
            "recus": simule.recus}


async def _scenario_confirme(ctx) -> dict:
    if "confirme" not in ctx.cache:
        _raz()
        ctx.cache["confirme"] = await _jouer(ctx, confirmer=True)
        ctx.cache["confirme"]["parties"] = _compteur()
    return ctx.cache["confirme"]


def _raz() -> None:
    try:
        lab12.raz()
    except lab10.MocksInjoignables as exc:
        raise Echec(str(exc)) from exc


def _compteur() -> int:
    try:
        return sum(lab12.alertes().values())
    except lab10.MocksInjoignables as exc:
        raise Echec(str(exc)) from exc


def _cellules(titre: str) -> list[str]:
    ligne = next((l for l in MESURES.read_text(encoding="utf-8").splitlines() if l.startswith(f"| {titre}")), "")
    return [c.strip() for c in ligne.split("|")[2:-1]] if ligne.count("|") >= 3 else []


@v.critere("Les outils du brief sont au catalogue agrégé, et le module navires est branché sur pharos-data.")
async def _(ctx):
    catalogues = await _catalogues(ctx)
    manquants = [f"{o} ({s})" for s, noms in ATTENDUS.items() for o in noms
                 if o not in {t.name for t in catalogues.get(s, [])}]
    if manquants:
        raise Echec(f"absents : {', '.join(manquants)} — garder les noms du brief (le plan et le LAB 15 en dépendent) ; "
                    "vérifier labs/lab13/serveurs.json.")
    navires = [t.name for t in catalogues.get("pharos-data", []) if (t.description or "").startswith(DESCRIPTION_NAVIRES)]
    if not navires:
        raise Echec("le module navires n'est pas branché sur pharos-data : navires.enregistrer(mcp, emprunter) dans "
                    "serveurs/pharos_data/serveur.py (étape 1).")
    total = sum(len(o) for o in catalogues.values())
    return f"{total} outils sur {len(catalogues)} serveurs ; module navires : {navires[0]}"


@v.critere("Les mesures de l'étape 1 et les trois signaux sont consignés dans labs/lab13/mesures.md.")
def _(ctx):
    if not MESURES.exists():
        raise Echec("labs/lab13/mesures.md absent : lancer « make depart LAB=13 ».")
    lignes = ["Coût fixe du catalogue, un seul serveur", "Coût fixe du catalogue agrégé",
              "Nombre d'outils exposés au total", "Appels hors plan", "Étapes annoncées jamais exécutées",
              "Retours en arrière"]
    vides = [l for l in lignes if not any(re.search(r"\d", c) for c in _cellules(l))]
    if vides:
        raise Echec(f"à consigner (un nombre, même mauvais) : {', '.join(vides)}.")
    if "À RELEVER" in MESURES.read_text(encoding="utf-8"):
        raise Echec("il reste des « À RELEVER » dans labs/lab13/mesures.md.")


@v.critere("Aucune collision de noms sur le catalogue agrégé des trois serveurs.")
async def _(ctx):
    trouvees = lab13.collisions(await _catalogues(ctx))
    if trouvees:
        detail = "; ".join(f"{nom} ({', '.join(s)})" for nom, s in sorted(trouvees.items()))
        raise Echec(f"collision : {detail}. Préfixer par domaine côté serveur (bloc 21.1) — par exemple "
                    "navires.enregistrer(mcp, emprunter, nom_outil=\"data_navire_par_nom\").")


@v.critere("La consigne système de la boucle est celle de client/pharos_client/consigne.md.")
async def _(ctx):
    joue = await _scenario_confirme(ctx)
    if not CONSIGNE.exists():
        raise Echec("client/pharos_client/consigne.md absent : lancer « make depart LAB=13 ».")
    attendue = CONSIGNE.read_text(encoding="utf-8").strip()
    systeme = [m.get("content") or "" for m in joue["recus"][0] if m.get("role") == "system"]
    if not systeme or systeme[0].strip() != attendue:
        raise Echec("le premier message système envoyé au modèle n'est pas le contenu de consigne.md : lire la consigne "
                    "dans ce fichier (le LAB 15 en calcule l'empreinte pour savoir quand relancer l'évaluation).")


@v.critere("Chaque appel de la trace porte le nom du serveur qui l'a servi.")
async def _(ctx):
    execution = (await _scenario_confirme(ctx))["execution"]
    attendu = {"navire_par_nom": "pharos-ops", "rechercher_clause": "pharos-docs", "escales_a_risque": "pharos-data",
               "publier_alerte": "pharos-ops"}
    faux = [f"{e.outil} → « {e.serveur} » (attendu {attendu[e.outil]})" for e in execution.trace
            if e.outil in attendu and e.serveur != attendu[e.outil]]
    if not execution.trace:
        raise Echec("la trace est vide : le scénario (quatre appels sur trois serveurs) n'a pas été exécuté.")
    if faux:
        raise Echec(f"serveur absent ou faux dans la trace : {'; '.join(faux)} — le sixième champ (bloc 21.4) est le "
                    "nom du serveur de labs/lab13/serveurs.json.")
    return " · ".join(f"{e.outil} ← {e.serveur}" for e in execution.trace)


@v.critere("Le plan est affiché avant la première action, avec le serveur de chaque étape ; « non » n'exécute rien.")
async def _(ctx):
    joue = await _scenario_confirme(ctx)
    if not joue["evenements"]:
        raise Echec("aucun appel d'outil : la boucle n'a pas exécuté le plan accepté.")
    avant = joue["evenements"][0]["affiche_avant"]
    if "Plan annoncé" not in avant:
        raise Echec("le plan n'était pas affiché au moment du premier appel d'outil : plan.afficher_plan(etapes) "
                    "avant d'exécuter quoi que ce soit.")
    etapes = joue["execution"].plan
    if not etapes or any(e.serveur in ("", "?") for e in etapes):
        raise Echec(f"plan rendu sans serveur pour chaque étape : {etapes!r} — plan.lire_plan(texte, "
                    "catalogue.serveur_de).")
    refuse = await _jouer(ctx, decision="non")
    if refuse["evenements"]:
        raise Echec(f"plan refusé (« non ») et pourtant {len(refuse['evenements'])} appel(s) d'outil exécuté(s).")
    return f"{len(etapes)} étapes annoncées avant le premier appel ; « non » : aucun appel"


@v.critere("La confirmation du LAB 12 est déclenchée avant publication : « non » → rien ne part ; « oui » → une alerte.")
async def _(ctx):
    joue = await _scenario_confirme(ctx)
    if not joue["demandes"] or joue["parties"] != 1:
        raise Echec(f"« oui » : {joue['parties']} alerte(s) partie(s), {len(joue['demandes'])} demande(s) présentée(s) "
                    "— la boucle doit rejouer la demande de confirmation (LAB 12) sur la session de pharos-ops.")
    _raz()
    refuse = await _jouer(ctx, confirmer=False)
    if not refuse["demandes"]:
        raise Echec("aucune demande de confirmation présentée avant publier_alerte.")
    if _compteur():
        raise Echec("l'exploitant a répondu « non » et une alerte est partie.")
    return "« oui » : 1 ; « non » : 0"


@v.critere("La réponse texte existe pour un client sans extension ; la vue est déclarée (ressource ui://).")
async def _(ctx):
    url = next((s["url"] for s in _serveurs() if s["nom"] == "pharos-ops"), None)
    async with ClientTest(url, jeton=JETON, profil="sans_tasks", nom="verificateur-lab13-sans-extension") as c:
        outils = {o.name: o for o in await c.outils()}
        r = await c.appeler("recalculer_plan_quai", {"date": "2026-10-08", "quai": 3})
        ressources = {str(x.uri): x for x in await c.ressources()}
    texte = lab12._texte(r)
    if r.is_error or "ESC-2026-0412" not in texte:
        raise Echec(f"recalculer_plan_quai(quai=3), client sans extension : pas de réponse texte utilisable "
                    f"(« {texte[:200]} »). La vue ne remplace jamais la réponse.")
    meta = (getattr(outils.get("recalculer_plan_quai"), "meta", None) or {}).get("ui") or {}
    if meta.get("resourceUri") != VUE or VUE not in ressources:
        raise Echec(f"vue non déclarée : recalculer_plan_quai doit porter app=AppConfig(resource_uri=\"{VUE}\") et "
                    f"pharos-ops déclarer la ressource {VUE} (le gabarit serveurs/pharos_ops/vues/plan_quai.html). "
                    "Si le client de la salle ne rend pas les MCP Apps, voir le formateur (étape 4).")
    if "mcp-app" not in (ressources[VUE].mime_type or ""):
        raise Echec(f"{VUE} : type {ressources[VUE].mime_type}, attendu text/html;profile=mcp-app.")
    return f"texte : {len(texte)} caractères ; vue : {VUE}"


@v.constat("La vue du plan de quai s'affiche dans VS Code (si le client gère les MCP Apps).")
def _(ctx):
    return ("dans le chat de VS Code (agent pharos), demander le recalcul du plan de quai de jeudi pour le quai 3 : "
            "le diagramme doit apparaître sous la réponse texte.")


@v.critere("Les trois signaux de dérive sont justes sur une trace et un plan figés.")
def _(ctx):
    try:
        derive = importlib.import_module("pharos_client.derive")
    except ModuleNotFoundError as exc:
        raise Echec("pharos_client.derive introuvable : lancer « make depart LAB=13 ».") from exc
    plan = [SimpleNamespace(numero=i, outil=o, serveur="s", raison="") for i, o in
            enumerate(["navire_par_nom", "rechercher_clause", "meteo_creneau", "publier_alerte"], 1)]
    e = lambda tour, outil, **a: SimpleNamespace(tour=tour, outil=outil, arguments=a, serveur="s", resultat="")
    trace = [e(1, "navire_par_nom", nom="Vent d'Autan"), e(2, "requete_sql", sql="SELECT 1"),
             e(3, "rechercher_clause", escale_id="ESC-2026-0412", sujet="penalites"),
             e(4, "navire_par_nom", nom="Vent d'Autan"), e(5, "navire_par_nom", nom="Cormoran"),
             e(6, "rechercher_clause", escale_id="ESC-2026-0412", sujet="penalites")]
    try:
        obtenu = derive.signaux(plan, trace)
    except NotImplementedError as exc:
        raise Echec(f"pas encore écrit : {exc}") from exc
    attendu = {"hors_plan": 1, "jamais_executees": 2, "retours_arriere": 2}
    if obtenu != attendu:
        raise Echec(f"signaux : {obtenu}, attendus {attendu} — hors plan : requete_sql ; jamais exécutées : "
                    "meteo_creneau, publier_alerte ; retours en arrière : navire_par_nom(Vent d'Autan) et "
                    "rechercher_clause répétés à l'identique (le premier appel ne compte pas).")


@v.critere("Critère décisif (note) — la note de la dernière exécution réelle n'a aucune donnée sans origine.")
def _(ctx):
    if not DERNIERE.exists():
        raise Echec("aucune exécution réelle gardée : lancer « make lab13-question » (la question cible, vrai modèle), "
                    "puis relancer la vérification.")
    execution = json.loads(DERNIERE.read_text(encoding="utf-8"))
    if execution.get("arret"):
        raise Echec(f"la dernière exécution s'est arrêtée ({execution['arret']}) : pas de note.")
    if "Vent d'Autan" not in execution["question"]:
        raise Echec("la dernière exécution n'est pas la question cible : make lab13-question Q=1.")
    elements = verifier_note(execution["reponse"], execution["trace"], execution["question"])
    manquants = sans_origine(elements)
    if manquants:
        raise Echec(f"{len(manquants)} donnée(s) sans origine : {', '.join(e.texte for e in manquants)} "
                    "(make lab13-verifier-note pour le détail).")
    return f"{len(elements)} élément(s) vérifié(s), tous trouvés dans la trace ({len(execution['trace'])} appels)"


@v.constat("Critère décisif (trace) — au plus un appel superflu dans la trace de la question cible.")
def _(ctx):
    if not DERNIERE.exists():
        return "make lab13-question, puis relire l'arbre."
    trace = json.loads(DERNIERE.read_text(encoding="utf-8"))["trace"]
    return "trace : " + " · ".join(f"t{e['tour']} {e['serveur']} {e['outil']}" for e in trace)
