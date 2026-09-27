"""Client du service de salle (LAB 14), côté binôme et côté formateur.

Côté binôme (le service tourne chez le formateur, joignable sur SALLE_URL) :
    python -m outils.salle inscrire --url http://poste-formateur:8300 --binome 3 --jeton <jeton>   (make lab14-inscrire)
    python -m outils.salle deposer --cible 4 --fichier attaque.md                                 (make lab14-deposer)
    python -m outils.salle synchroniser                                                            (make lab14-synchroniser)
    python -m outils.salle issue --objectif A --reussite --preuve "note sans risque"

Côté formateur (fait tourner le service lui-même) :
    python -m outils.salle jetons --n 5            (make salle-jetons : tire les jetons, écrit salle/jetons.txt)
    python -m outils.salle manche --manche 2       (make salle-manche M=2)

L'inscription écrit labs/lab14/salle.env (git-ignoré) : SALLE_URL, SALLE_JETON, BINOME. deposer envoie le
Markdown tel quel ; synchroniser tire les documents reçus et les écrit en PDF au format du corpus dans
contrats-partages/binome-<B>/, que pharos-docs indexe (PHAROS_DOCUMENTS).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx

RACINE = Path(__file__).resolve().parents[1]
ENV = RACINE / "labs" / "lab14" / "salle.env"
JETONS = RACINE / "salle" / "jetons.txt"


class Refus(Exception):
    """Le service de salle a refusé l'action ; le message dit pourquoi."""


def _lire_env() -> dict[str, str]:
    if not ENV.exists():
        raise Refus("labs/lab14/salle.env absent : s'inscrire d'abord (make lab14-inscrire URL=… BINOME=… JETON=…).")
    valeurs = {}
    for ligne in ENV.read_text(encoding="utf-8").splitlines():
        cle, _, val = ligne.partition("=")
        if cle.strip():
            valeurs[cle.strip()] = val.strip()
    return valeurs


def _requete(methode: str, url: str, jeton: str | None = None, **options) -> httpx.Response:
    entetes = {"X-Jeton": jeton} if jeton else {}
    try:
        r = httpx.request(methode, url, headers=entetes, timeout=15, **options)
    except httpx.HTTPError as exc:
        raise Refus(f"service de salle injoignable ({exc.__class__.__name__}) : vérifier SALLE_URL et le réseau.") from exc
    return r


def inscrire(url: str, binome: int, jeton: str) -> str:
    ENV.parent.mkdir(parents=True, exist_ok=True)
    ENV.write_text(f"SALLE_URL={url.rstrip('/')}\nSALLE_JETON={jeton}\nBINOME={binome}\n", encoding="utf-8")
    r = _requete("GET", f"{url.rstrip('/')}/_etat")
    manche = r.json().get("manche", "?") if r.status_code == 200 else "?"
    return f"Inscrit : binôme {binome} sur {url} (manche {manche}). Écrit dans {ENV.relative_to(RACINE)}."


def deposer(fichier: Path, cible: int | None = None) -> str:
    env = _lire_env()
    corps = fichier.read_text(encoding="utf-8")
    if cible is None:
        # sans --cible, on demande au service qui est la cible désignée : il refusera toute autre.
        etat = _requete("GET", f"{env['SALLE_URL']}/_etat").json()
        binome, n, manche = int(env["BINOME"]), etat["n"], etat["manche"]
        decalage = {1: 1, 2: None, 3: 2}[manche]
        if decalage is None:
            raise Refus(f"dépôt fermé à la manche {manche}.")
        cible = (binome - 1 + decalage) % n + 1
    r = _requete("POST", f"{env['SALLE_URL']}/depots/{cible}", jeton=env["SALLE_JETON"],
                 content=corps.encode("utf-8"))
    if r.status_code != 200:
        raise Refus(r.json().get("motif", r.text))
    d = r.json()
    return f"Déposé chez le binôme {d['cible']} : « {d['titre']} » sur {d['escale']}."


def synchroniser() -> str:
    from pharos_docs import depot

    env = _lire_env()
    binome = int(env["BINOME"])
    r = _requete("GET", f"{env['SALLE_URL']}/depots/{binome}", jeton=env["SALLE_JETON"])
    if r.status_code != 200:
        raise Refus(r.json().get("motif", r.text))
    documents = r.json()["documents"]
    dossier = RACINE / "contrats-partages" / f"binome-{binome}"
    for f in dossier.glob("*.pdf"):        # repart d'un dossier propre : un document retiré d'une manche disparaît
        f.unlink()
    ecrits = []
    for i, d in enumerate(documents, 1):
        chemin = depot.ecrire_pdf(d["corps"], escale_id=d["escale"], suffixe=f"inj{i}", dossier=dossier)
        ecrits.append(chemin.name)
    lignes = [f"{len(ecrits)} document(s) écrit(s) dans {dossier.relative_to(RACINE)} :"] + \
             [f"  {nom}" for nom in ecrits]
    lignes.append("Relancer pharos-docs pour qu'il les indexe : make lab13-tout (ou make down puis make lab13-tout).")
    return "\n".join(lignes)


def remonter_issue(objectif: str, reussite: bool, preuve: str) -> str:
    env = _lire_env()
    r = _requete("POST", f"{env['SALLE_URL']}/issues", jeton=env["SALLE_JETON"],
                 json={"objectif": objectif, "reussite": reussite, "preuve": preuve})
    if r.status_code != 200:
        raise Refus(r.json().get("motif", r.text))
    return "Issue remontée au tableau de bord de salle."


def tirer_jetons(n: int, url: str) -> str:
    from serveurs.salle import app as salle

    jetons = _requete("POST", f"{url.rstrip('/')}/_config", json={"n": n})
    if jetons.status_code == 200:
        table = jetons.json()["jetons"]
    else:
        table = {j: b for j, b in salle.configurer(n).items()}     # repli : configuration locale (tests)
    JETONS.parent.mkdir(parents=True, exist_ok=True)
    lignes = [f"binôme {b} : {j}" for j, b in sorted(table.items(), key=lambda kv: kv[1]) if b]
    formateur = next((j for j, b in table.items() if b == 0), "")
    JETONS.write_text("\n".join(lignes) + f"\njeton formateur : {formateur}\n", encoding="utf-8")
    return f"{n} jetons tirés, écrits dans {JETONS.relative_to(RACINE)} (à distribuer sur papier)."


def tableau() -> str:
    env = _lire_env()
    url = f"{env['SALLE_URL']}/tableau"
    ouvrir = None
    for commande in ("wslview", "xdg-open"):
        chemin = __import__("shutil").which(commande)
        if chemin:
            __import__("subprocess").Popen([chemin, url], stdout=__import__("subprocess").DEVNULL,
                                           stderr=__import__("subprocess").DEVNULL)
            ouvrir = commande
            break
    return f"Tableau de bord de salle : {url}" + (f" (ouvert avec {ouvrir})" if ouvrir else "")


def changer_manche(manche: int, url: str) -> str:
    r = _requete("POST", f"{url.rstrip('/')}/_manche", json={"manche": manche})
    if r.status_code != 200:
        raise Refus(r.json().get("erreur", r.text))
    ouvert = r.json()["depot_ouvert"]
    return f"Manche {manche} ({'dépôt ouvert' if ouvert else 'dépôt fermé'})."


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="outils.salle")
    sous = p.add_subparsers(dest="commande", required=True)
    i = sous.add_parser("inscrire"); i.add_argument("--url", required=True); i.add_argument("--binome", type=int, required=True); i.add_argument("--jeton", required=True)
    d = sous.add_parser("deposer"); d.add_argument("--fichier", required=True); d.add_argument("--cible", type=int)
    sous.add_parser("synchroniser")
    sous.add_parser("tableau")
    e = sous.add_parser("issue"); e.add_argument("--objectif", required=True); e.add_argument("--reussite", action="store_true"); e.add_argument("--preuve", default="")
    j = sous.add_parser("jetons"); j.add_argument("--n", type=int, required=True); j.add_argument("--url", default="http://localhost:8300")
    m = sous.add_parser("manche"); m.add_argument("--manche", type=int, required=True); m.add_argument("--url", default="http://localhost:8300")
    a = p.parse_args(argv)
    try:
        if a.commande == "inscrire":
            print(inscrire(a.url, a.binome, a.jeton))
        elif a.commande == "deposer":
            print(deposer(Path(a.fichier), a.cible))
        elif a.commande == "synchroniser":
            print(synchroniser())
        elif a.commande == "tableau":
            print(tableau())
        elif a.commande == "issue":
            print(remonter_issue(a.objectif, a.reussite, a.preuve))
        elif a.commande == "jetons":
            print(tirer_jetons(a.n, a.url))
        elif a.commande == "manche":
            print(changer_manche(a.manche, a.url))
    except Refus as exc:
        print(f"Refusé : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
