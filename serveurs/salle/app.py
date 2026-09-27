"""Service de salle du LAB 14 (attaque et durcissement) — tourne sur le poste du formateur.

C'est le SEUL service joignable sur le réseau de salle (port 8300) ; les PHAROS des binômes restent
sur 127.0.0.1. Il tient l'anneau (qui attaque qui, par manche), reçoit les documents piégés déposés
par les attaquants, les remet aux cibles, et affiche un tableau de bord. Il n'exécute aucun agent : la
cible tire ses documents, pose la question à son propre PHAROS, et remonte l'issue ici.

L'anneau (N binômes, numérotés 1..N) :
  - manche 1 : le binôme b n'attaque que b+1 ;
  - manche 2 : dépôt fermé (durcissement) — chaque cible voit tous les documents qui l'ont visée ;
  - manche 3 : b attaque b+2.
Indices modulo N (b+1 et b+2 « bouclent » ; avec N ≤ 2, b+2 retombe sur b+1, signalé au tableau).

Un document est un Markdown UTF-8 dont les premières lignes peuvent porter un front-matter
« Titre: … » et « Escale: … » (les en-têtes HTTP n'acceptent que l'ASCII, d'où ce choix) ; à défaut,
titre « document-<n> » et escale ESC-2026-0412.

Routes :
  POST /depots/{cible}   attaquant : dépose un document (en-tête X-Jeton ; corps = Markdown, front-matter option.)
  GET  /depots/{moi}     cible : documents reçus (en-tête X-Jeton)
  POST /issues           cible : remonte l'issue d'une exécution (en-tête X-Jeton ; JSON)
  GET  /tableau          tous (HTML, sans jeton) : dépôts, issues, refus, par cible
  GET  /_etat            tous (JSON) : la même chose, pour les outils et les tests
  POST /_manche          formateur : {manche: 1|2|3}
  POST /_raz             formateur : vide dépôts, issues, refus (jetons et manche conservés)

L'état vit en mémoire ; un journal JSON est écrit sur disque (salle/journal.jsonl, git-ignoré). Tout
ce qui est tenté est consigné, refus compris : les échecs sont la moitié de l'information (règle 3).
"""

from __future__ import annotations

import html
import json
import os
import re
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.routing import Route

from pharos import horloge

TAILLE_MAX = 20_000                       # octets du corps d'un document
DEPOTS_MAX = 5                            # dépôts par binôme et par manche
CIBLE_PAR_MANCHE = {1: 1, 2: None, 3: 2}  # décalage attaquant → cible ; None : dépôt fermé
NOM = re.compile(r"[^A-Za-z0-9._-]+")
FRONT = re.compile(r"^(Titre|Escale)\s*:\s*(.+?)\s*$", re.IGNORECASE)


def _front_matter(corps: str) -> tuple[str, str]:
    """Lit « Titre: … » et « Escale: … » dans les premières lignes du document."""
    titre, escale = "", ""
    for ligne in corps.splitlines()[:5]:
        m = FRONT.match(ligne)
        if not m:
            continue
        if m.group(1).lower() == "titre":
            titre = m.group(2)
        else:
            escale = m.group(2)
    return titre, escale


@dataclass(frozen=True)
class Depot:
    auteur: int
    cible: int
    titre: str
    escale: str
    corps: str
    manche: int
    recu: str


@dataclass(frozen=True)
class Issue:
    binome: int
    objectif: str
    reussite: bool
    preuve: str
    manche: int
    recu: str


@dataclass(frozen=True)
class Refus:
    auteur: int | None
    cible: int | None
    motif: str
    manche: int
    recu: str


class Etat:
    def __init__(self, n: int = 0, jetons: dict[str, int] | None = None):
        self.n = n
        self.jetons: dict[str, int] = jetons or {}
        self.manche = 1
        self.raz()

    def raz(self) -> None:
        self.depots: list[Depot] = []
        self.issues: list[Issue] = []
        self.refus: list[Refus] = []

    def cible_de(self, binome: int) -> int | None:
        """La cible que « binome » doit attaquer à la manche en cours, ou None si le dépôt est fermé."""
        decalage = CIBLE_PAR_MANCHE[self.manche]
        if decalage is None:
            return None
        return (binome - 1 + decalage) % self.n + 1


etat = Etat()


def journal() -> Path:
    return Path(os.environ.get("SALLE_JOURNAL", Path(__file__).resolve().parents[2] / "salle" / "journal.jsonl"))


def _consigner(genre: str, **champs) -> None:
    chemin = journal()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    ligne = {"horodatage": horloge.maintenant().isoformat(timespec="seconds"), "genre": genre, **champs}
    with chemin.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False, default=str) + "\n")


def configurer(n: int) -> dict[str, int]:
    """Tire un jeton par binôme (1..n) plus un jeton formateur ; réinitialise tout l'état de salle."""
    global etat
    jetons = {secrets.token_hex(8): b for b in range(1, n + 1)}
    etat = Etat(n, jetons)
    etat.jeton_formateur = secrets.token_hex(8)
    return {**{j: b for j, b in jetons.items()}, etat.jeton_formateur: 0}


def _binome(requete: Request) -> int | None:
    return etat.jetons.get(requete.headers.get("X-Jeton", ""))


def _maintenant() -> str:
    return horloge.maintenant().isoformat(timespec="seconds")


def _refus(auteur, cible, motif, statut=403) -> JSONResponse:
    etat.refus.append(Refus(auteur, cible, motif, etat.manche, _maintenant()))
    _consigner("refus", auteur=auteur, cible=cible, motif=motif, manche=etat.manche)
    return JSONResponse({"refuse": True, "motif": motif}, status_code=statut)


async def deposer(requete: Request):
    binome = _binome(requete)
    cible = requete.path_params["cible"]
    if binome is None:
        return _refus(None, cible, "jeton absent ou inconnu", 401)
    if not (1 <= cible <= etat.n):
        return _refus(binome, cible, f"cible hors de l'anneau (1..{etat.n})", 404)
    attendue = etat.cible_de(binome)
    if attendue is None:
        return _refus(binome, cible, f"dépôt fermé à la manche {etat.manche} (durcissement)")
    if cible != attendue:
        return _refus(binome, cible, f"cible non désignée : à la manche {etat.manche}, le binôme {binome} "
                      f"attaque le binôme {attendue}")
    corps = (await requete.body()).decode("utf-8", "replace")
    if len(corps.encode("utf-8")) > TAILLE_MAX:
        return _refus(binome, cible, f"document trop gros (> {TAILLE_MAX} octets)", 413)
    deja = sum(1 for d in etat.depots if d.auteur == binome and d.manche == etat.manche)
    if deja >= DEPOTS_MAX:
        return _refus(binome, cible, f"quota de dépôts atteint ({DEPOTS_MAX} par manche)", 429)
    titre_lu, escale_lue = _front_matter(corps)
    escale = escale_lue or "ESC-2026-0412"
    titre = titre_lu or f"document-{deja + 1}"
    depot = Depot(binome, cible, titre, escale, corps, etat.manche, _maintenant())
    etat.depots.append(depot)
    _consigner("depot", auteur=binome, cible=cible, titre=titre, escale=escale, manche=etat.manche,
               octets=len(corps.encode("utf-8")))
    return JSONResponse({"depose": True, "cible": cible, "titre": titre, "escale": escale})


def _visibles(cible: int) -> list[Depot]:
    """Les documents qu'une cible peut voir : ceux qui la visent aux manches déjà jouées ou en cours."""
    return [d for d in etat.depots if d.cible == cible and d.manche <= etat.manche]


async def recevoir(requete: Request):
    binome = _binome(requete)
    moi = requete.path_params["moi"]
    if binome is None or binome != moi:
        return _refus(binome, moi, "un binôme ne lit que ses propres documents", 403)
    return JSONResponse({"binome": moi, "manche": etat.manche,
                         "documents": [asdict(d) for d in _visibles(moi)]})


async def remonter(requete: Request):
    binome = _binome(requete)
    if binome is None:
        return _refus(None, None, "jeton absent ou inconnu", 401)
    corps = await requete.json()
    objectif = str(corps.get("objectif", "?")).upper()[:1] or "?"
    issue = Issue(binome, objectif, bool(corps.get("reussite")), str(corps.get("preuve", ""))[:500],
                  etat.manche, _maintenant())
    etat.issues.append(issue)
    _consigner("issue", binome=binome, objectif=objectif, reussite=issue.reussite, manche=etat.manche)
    return JSONResponse({"recu": True})


def _etat_dict() -> dict:
    return {"n": etat.n, "manche": etat.manche,
            "depots": [asdict(d) for d in etat.depots], "issues": [asdict(i) for i in etat.issues],
            "refus": [asdict(r) for r in etat.refus]}


async def etat_json(requete: Request):
    return JSONResponse(_etat_dict())


async def configurer_route(requete: Request):
    corps = await requete.json()
    n = int(corps.get("n", 0))
    if not 1 <= n <= 50:
        return JSONResponse({"erreur": "n hors de 1..50"}, status_code=400)
    table = configurer(n)
    _consigner("config", n=n)
    return JSONResponse({"n": n, "jetons": table})


async def changer_manche(requete: Request):
    corps = await requete.json()
    manche = int(corps.get("manche", etat.manche))
    if manche not in CIBLE_PAR_MANCHE:
        return JSONResponse({"erreur": f"manche inconnue : {manche} (1, 2 ou 3)"}, status_code=400)
    etat.manche = manche
    _consigner("manche", manche=manche)
    return JSONResponse({"manche": manche, "depot_ouvert": CIBLE_PAR_MANCHE[manche] is not None})


async def raz(requete: Request):
    etat.raz()
    return JSONResponse({"raz": True})


def _tableau_html() -> str:
    lignes = [f"<h1>Salle PHAROS — LAB 14 · manche {etat.manche} · {etat.n} binômes</h1>"]
    ouvert = CIBLE_PAR_MANCHE[etat.manche]
    lignes.append(f"<p>Dépôt : {'fermé (manche 2)' if ouvert is None else f'le binôme b attaque b+{ouvert}'}."
                  " Le tableau ne voit que les tentatives connues.</p>")
    if etat.n and etat.n <= 2 and etat.manche == 3:
        lignes.append("<p><b>N ≤ 2 : à la manche 3, b+2 retombe sur b+1.</b></p>")
    for cible in range(1, etat.n + 1):
        depots = [d for d in etat.depots if d.cible == cible]
        issues = [i for i in etat.issues if i.binome == cible]
        refus = [r for r in etat.refus if r.cible == cible]
        lignes.append(f"<h2>Binôme {cible}</h2><ul>")
        for d in depots:
            lignes.append(f"<li>reçu de {d.auteur} (manche {d.manche}) : "
                          f"« {html.escape(d.titre)} » sur {html.escape(d.escale)}</li>")
        for i in issues:
            marque = "réussie" if i.reussite else "échouée"
            lignes.append(f"<li>issue {marque} — objectif {html.escape(i.objectif)} "
                          f"(manche {i.manche}) : {html.escape(i.preuve)}</li>")
        if refus:
            lignes.append(f"<li>{len(refus)} dépôt(s) refusé(s)</li>")
        if not (depots or issues or refus):
            lignes.append("<li>rien pour l'instant</li>")
        lignes.append("</ul>")
    return "<!doctype html><meta charset=utf-8><title>Salle PHAROS</title>" + "".join(lignes)


async def tableau(requete: Request):
    return HTMLResponse(_tableau_html())


async def sante(requete: Request):
    return PlainTextResponse("ok")


app = Starlette(routes=[
    Route("/depots/{cible:int}", deposer, methods=["POST"]),
    Route("/depots/{moi:int}", recevoir, methods=["GET"]),
    Route("/issues", remonter, methods=["POST"]),
    Route("/tableau", tableau, methods=["GET"]),
    Route("/_etat", etat_json, methods=["GET"]),
    Route("/_config", configurer_route, methods=["POST"]),
    Route("/_manche", changer_manche, methods=["POST"]),
    Route("/_raz", raz, methods=["POST"]),
    Route("/_sante", sante, methods=["GET"]),
])
