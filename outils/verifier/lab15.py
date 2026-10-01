"""Vérificateur du LAB 15 — le jeu d'évaluation.

Aucun appel au modèle : le jeu lui-même n'est jamais lancé ici. Ce que le vérificateur contrôle (spec §10.3) :
  1. Dix cas, quota 4/3/2/1, chacun au format et avec son contexte figé — date de l'horloge des serveurs, identité
     connue, empreinte égale à celle de la base de salle.
  2. Le taux de référence consigné (labs/lab15/reference.md : modèle, global, par famille) et evaluation/reference.json.
  3. Un cas instable consigné comme tel (hors sécurité), et son taux de référence est bien 1/3 ou 2/3.
  4. La chaîne d'évaluation est séparée de la chaîne rapide, avec ses trois déclencheurs et le tag.
  5. « Rien à lancer » : sans changement, la chaîne sort en vert sans exécuter le jeu.
  6. Décisif : evaluation/rapport.py sur deux résultats figés du kit (sain, régressé) — code 0 puis 1, et la sortie du
     second nomme les cas fautifs et leur famille.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

from outils.evaluation import cas as cas_mod
from outils.evaluation import chaine, resultats
from outils.verifier.commun import Echec, Verification

RACINE = Path(__file__).resolve().parents[2]
EXEMPLES = Path(__file__).resolve().parents[1] / "evaluation" / "exemples"
CONFIG = RACINE / "labs" / "lab13" / "serveurs.json"
FAUTIFS = ("penalites-vent-autan", "quai-et-vent-vent-autan", "conflit-cormoran-jeudi")   # multi, dans regresse.json
JETON = "jeton-exploitation"

v = Verification("LAB 15 — le jeu d'évaluation", "http://observateur:8103/mcp",
                 "make lab8-base, make lab10-mocks, puis make lab13-tout")


def _chemins() -> dict[str, Path]:
    return {"cas": RACINE / "evaluation" / "cas", "reference_md": RACINE / "labs" / "lab15" / "reference.md",
            "reference": RACINE / "evaluation" / "reference.json", "rapport": RACINE / "evaluation" / "rapport.py",
            "evaluation": RACINE / ".ci" / "evaluation.yaml", "rapide": RACINE / ".ci" / "rapide.yaml",
            "consigne": RACINE / "client" / "pharos_client" / "consigne.md"}


def _reference_json() -> dict:
    chemin = _chemins()["reference"]
    if not chemin.exists():
        raise Echec("evaluation/reference.json absent : make lab15-referencer après le premier jeu complet.")
    try:
        reference = json.loads(chemin.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise Echec(f"evaluation/reference.json illisible ({exc}) : le régénérer par make lab15-referencer.") from exc
    if not reference.get("cas"):
        raise Echec("evaluation/reference.json est vide : make lab15-lancer, puis make lab15-referencer.")
    return reference


def _reference_md() -> str:
    chemin = _chemins()["reference_md"]
    if not chemin.exists():
        raise Echec("labs/lab15/reference.md absent : make lab15-scaffold.")
    return chemin.read_text(encoding="utf-8")


@v.critere("Dix cas, quota 4/3/2/1, chacun avec son contexte figé (date, identité, empreinte de la base de salle).")
async def dix_cas(ctx):
    from pharos import base, empreintes, horloge

    try:
        cas = cas_mod.charger(_chemins()["cas"], RACINE)
    except cas_mod.CasInvalide as exc:
        raise Echec(str(exc)) from exc
    manques = cas_mod.quota(cas)
    if manques:
        raise Echec(f"{len(cas)} cas dans evaluation/cas/ — quota non respecté : " + " · ".join(manques) + ".")
    try:
        empreinte = await empreintes.empreinte_base(base.dsn(base.ADMIN))
    except Exception as exc:
        raise Echec(f"base injoignable ({exc.__class__.__name__}) : make lab8-base.") from exc
    jour = horloge.aujourdhui().isoformat()
    ecarts = [f"{c.id} : " + ", ".join(e for e in (f"date {c.contexte.date} ≠ {jour}" if c.contexte.date != jour
                                                      else "", f"base {c.contexte.base} ≠ {empreinte}"
                                                      if c.contexte.base != empreinte else "") if e)
              for c in cas if c.contexte.date != jour or c.contexte.base != empreinte]
    if ecarts:
        raise Echec("contexte non figé sur l'état de salle (make lab15-empreinte) :\n" + "\n".join(ecarts))
    return " · ".join(f"{f} {sum(c.famille == f for c in cas)}" for f in cas_mod.FAMILLES)


@v.critere("Le taux de référence est consigné, global et par famille, sur trois exécutions par cas.")
def taux_de_reference(ctx):
    reference = _reference_json()
    texte = _reference_md()
    courtes = [c["id"] for c in reference["cas"] if int(c["executions"]) < 3]
    if courtes:
        raise Echec(f"référence prise sur moins de trois exécutions pour : {', '.join(courtes)} (make lab15-lancer "
                    "FOIS=3, puis make lab15-referencer).")
    if "…" in texte.split("## Cas instables")[0]:
        raise Echec("labs/lab15/reference.md : le tableau de l'agent sain n'est pas rempli (« … »).")
    if not re.search(r"(?<![\w/.-])(?=[\w.-]*[A-Za-z])[\w.-]+/[\w.:-]*[A-Za-z][\w.:-]*", texte.split("\n## ")[0]):
        raise Echec("labs/lab15/reference.md : nommer le modèle et sa version épinglée (bloc 10.2), ex. "
                    "google/gemini-3.6-flash.")
    globale = str(resultats.global_(reference))
    familles = resultats.par_famille(reference)
    sain = texte.split("## Agent sain", 1)[1].split("\n## ", 1)[0] if "## Agent sain" in texte else ""
    jeton = lambda t: rf"(?<![\d/]){re.escape(str(t))}(?![\d/])"
    absents = [f"{f} {t}" for f, t in familles.items() if not re.search(rf"{f}\D[^\n]*{jeton(t)}", sain)]
    if not re.search(jeton(globale), sain) or absents:
        raise Echec("labs/lab15/reference.md ne reprend pas les taux de evaluation/reference.json : "
                    f"global {globale}" + (f", {', '.join(absents)}" if absents else "") + ".")
    return f"global {globale} · " + " · ".join(f"{f} {t}" for f, t in familles.items())


@v.critere("Au moins un cas instable est consigné comme instable (hors sécurité), et non corrigé.")
def cas_instable(ctx):
    reference = _reference_json()
    texte = _reference_md()
    partie = texte.split("## Cas instables", 1)[1].split("\n## ", 1)[0] if "## Cas instables" in texte else texte
    taux = resultats.par_cas(reference)
    nommes = [i for i in taux if re.search(rf"\b{re.escape(i)}\b", partie)]
    if not nommes:
        raise Echec("aucun cas instable consigné dans labs/lab15/reference.md (section « Cas instables ») : un jeu "
                    "sans cas instable a probablement été corrigé jusqu'à passer.")
    vrais = [i for i in nommes if taux[i].famille != "securite" and 0 < taux[i].reussites < taux[i].executions]
    if not vrais:
        raise Echec(f"cas consigné(s) comme instable(s) : {', '.join(nommes)} — mais leur taux de référence n'est "
                    "ni 1/3 ni 2/3 (ou c'est un cas de sécurité, qui exige 3/3).")
    return ", ".join(f"{i} {taux[i]}" for i in vrais)


def _declencheurs(flux) -> dict:
    """Lit les déclencheurs d'un workflow ; toute forme inattendue (liste, `push: [...]`, valeur non texte) est
    traitée comme absente plutôt que de faire planter le vérificateur."""
    flux = flux if isinstance(flux, dict) else {}
    on = flux.get("on", flux.get(True))
    on = on if isinstance(on, dict) else {}
    push = on.get("push") if isinstance(on.get("push"), dict) else {}

    def textes(valeur) -> list[str]:
        return [x for x in valeur if isinstance(x, str)] if isinstance(valeur, list) else []

    dispatch = on.get("workflow_dispatch")
    entrees = dispatch.get("inputs") if isinstance(dispatch, dict) else None
    return {"paths": textes(push.get("paths")), "tags": textes(push.get("tags")),
            "manuel": "workflow_dispatch" in on, "entrees": entrees if isinstance(entrees, dict) else {}}


@v.critere("La chaîne d'évaluation est séparée de la chaîne rapide, avec ses propres déclencheurs.")
def chaine_separee(ctx):
    chemins = _chemins()
    if not chemins["evaluation"].exists():
        raise Echec(".ci/evaluation.yaml absent : make lab15-scaffold, puis le compléter (étape 4).")
    texte = chemins["evaluation"].read_text(encoding="utf-8")
    try:
        flux = yaml.safe_load(texte) or {}
    except yaml.YAMLError as exc:
        raise Echec(f".ci/evaluation.yaml illisible ({exc}).") from exc
    d = _declencheurs(flux)
    manques = []
    if not any("consigne.md" in p for p in d["paths"]):
        manques.append("on.push.paths : le prompt système (client/pharos_client/consigne.md)")
    if not any(p.startswith("serveurs") for p in d["paths"]):
        manques.append("on.push.paths : les serveurs (le catalogue)")
    if not any(str(t).startswith("v") for t in d["tags"]):
        manques.append("on.push.tags : la publication (v*)")
    if not d["manuel"] or not d["entrees"]:
        manques.append("workflow_dispatch avec une entrée (le modèle)")
    if "lab15-chaine" not in texte:
        manques.append("un job qui lance make lab15-chaine")
    if "secrets.OPENROUTER_API_KEY" not in texte:
        manques.append("la clé depuis les secrets (secrets.OPENROUTER_API_KEY)")
    if manques:
        raise Echec(".ci/evaluation.yaml — il manque : " + " ; ".join(manques) + ".")
    rapide = chemins["rapide"].read_text(encoding="utf-8") if chemins["rapide"].exists() else ""
    if rapide.strip() == texte.strip() or re.search(r"lab15|evaluation\.yaml|lab15-chaine", rapide):
        raise Echec("la chaîne rapide (.ci/rapide.yaml) ne doit ni être la chaîne d'évaluation ni l'appeler : elle "
                    "passerait de quelques secondes à plusieurs minutes.")
    return "consigne.md, serveurs, tag v*, lancement manuel (modèle) → make lab15-chaine"


@v.critere("« Rien à lancer » : sans changement de modèle, de catalogue ni de prompt, la chaîne reste verte sans jouer.")
async def rien_a_lancer(ctx):
    from outils import lab13
    from pharos import empreintes

    reference = _reference_json()
    if not CONFIG.exists():
        raise Echec("labs/lab13/serveurs.json absent : make depart LAB=15.")
    serveurs = [{**s, "jeton": s.get("jeton") or JETON} for s in json.loads(CONFIG.read_text(encoding="utf-8"))["serveurs"]]
    try:
        catalogues = await lab13.lister(serveurs)
    except SystemExit as exc:
        raise Echec(str(exc)) from exc
    courantes = {"catalogue": empreintes.empreinte_catalogue(catalogues),
                 "prompt": empreintes.empreinte_prompt(_chemins()["consigne"]), "modele": empreintes.empreinte_modele()}
    a_lancer, motifs = chaine.decider(reference, courantes, publication=False)
    if a_lancer:
        raise Echec("la chaîne relancerait le jeu : " + " ; ".join(motifs) + " — régression encore posée (make "
                    "lab15-regression-retirer) ou référence à refaire (make lab15-referencer).")
    return "aucun déclencheur n'a bougé : rien à lancer"


def _rapport(resultat: Path) -> subprocess.CompletedProcess:
    rapport = _chemins()["rapport"]
    if not rapport.exists():
        raise Echec("evaluation/rapport.py absent : make lab15-scaffold.")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(str(p) for p in (RACINE / "src", RACINE, RACINE / "client"))}
    return subprocess.run([sys.executable, str(rapport), str(resultat), "--reference", str(EXEMPLES / "reference.json")],
                          cwd=RACINE, env=env, capture_output=True, text=True, timeout=60)


@v.critere("Critère décisif — vert sur l'agent sain, rouge sur l'agent régressé, et le rapport désigne les cas fautifs.")
def decisif(ctx):
    sain = _rapport(EXEMPLES / "sain.json")
    if sain.returncode != 0:
        dernieres = "\n".join((sain.stdout + sain.stderr).strip().splitlines()[-4:])
        raise Echec(f"agent sain (outils/evaluation/exemples/sain.json) : code {sain.returncode}, 0 attendu.\n{dernieres}")
    if "RÉGRESSION" in sain.stdout:
        raise Echec("agent sain : le rapport annonce une RÉGRESSION — un cas instable (2/3 → 3/3, ou 3/3 → 2/3 "
                    "toujours dans la tolérance) n'est pas fautif.")
    regresse = _rapport(EXEMPLES / "regresse.json")
    if regresse.returncode != 1:
        dernieres = "\n".join((regresse.stdout + regresse.stderr).strip().splitlines()[-4:])
        raise Echec(f"agent régressé (regresse.json) : code {regresse.returncode}, 1 attendu.\n{dernieres}")
    absents = [i for i in FAUTIFS if not re.search(rf"RÉGRESSION\s+{re.escape(i)}\s+\(multi\)", regresse.stdout)]
    if absents:
        raise Echec("agent régressé : le rapport ne nomme pas " + ", ".join(absents) + " — une ligne « RÉGRESSION "
                    "<id> (<famille>) : <avant> → <après> » par cas fautif.")
    return "sain → 0 ; régressé → 1, cas fautifs nommés (famille multi)"

