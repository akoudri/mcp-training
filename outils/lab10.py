"""Outils du LAB 10 : interrupteurs des mocks, compteur d'appels, note produite en mode panne.

python -m outils.lab10 mocks [--panne meteo] [--lenteur 8s] [--lenteur-quais 5,7] [--quota 5]   (make lab10-mocks)
python -m outils.lab10 appels                                                                  (make lab10-appels)
python -m outils.lab10 note-panne                                                              (make lab10-note-panne)

Le pilotage des mocks (lire_config, regler, compteur…) sert aussi aux vérificateurs des LAB 10 à 12.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import re
import sys
import time
from pathlib import Path

import httpx

URL_MOCKS = os.environ.get("PHAROS_MOCKS_URL", "http://mocks:8000")
URL_OPS = "http://observateur:8103/mcp"
RACINE = Path(__file__).resolve().parents[1]
NOTE = RACINE / "labs" / "lab10" / "note-panne.md"
QUESTION = "L'escale du Vent d'Autan de jeudi présente-t-elle un risque ?"


class MocksInjoignables(Exception):
    """Le service mocks ne répond pas ; le message dit quoi lancer."""


def _requete(methode: str, chemin: str, url: str | None = None, **options) -> dict:
    try:
        reponse = httpx.request(methode, f"{url or URL_MOCKS}{chemin}", timeout=10, **options)
        reponse.raise_for_status()
    except httpx.HTTPError as exc:
        raise MocksInjoignables(f"mocks injoignables ({exc.__class__.__name__}) : lancer « make lab10-mocks ».") from exc
    return reponse.json()


def attendre(url: str | None = None, delai_s: float = 30) -> None:
    fin = time.monotonic() + delai_s
    while True:
        try:
            _requete("GET", "/_sante", url)
            return
        except MocksInjoignables:
            if time.monotonic() > fin:
                raise
            time.sleep(0.5)


def lire_config(url: str | None = None) -> dict:
    return _requete("GET", "/_config", url)


def regler(url: str | None = None, **reglages) -> dict:
    """Remplace toute la configuration des mocks (réglage absent : valeur nominale)."""
    return _requete("POST", "/_config", url, json=reglages)


def ajouter_cle(cle: str, url: str | None = None) -> None:
    _requete("POST", "/_cles", url, json={"cle": cle})


def compteur(url: str | None = None) -> dict:
    return _requete("GET", "/_compteur", url)


@contextlib.contextmanager
def mode(url: str | None = None, **reglages):
    """Règle les mocks le temps d'un bloc, puis remet la configuration d'avant."""
    avant = lire_config(url)
    regler(url, **reglages)
    try:
        yield
    finally:
        regler(url, **avant)


def decrire(config: dict) -> str:
    morceaux = []
    if config.get("panne"):
        morceaux.append(f"panne de « {config['panne']} » (503)")
    if config.get("lenteur_s"):
        quais = ", ".join(str(q) for q in config["lenteur_quais"])
        morceaux.append(f"lenteur de {config['lenteur_s']:g} s sur la météo des quais {quais}")
    if config.get("quota"):
        morceaux.append(f"quota de {config['quota']} appels météo par fenêtre glissante de 60 s, puis 429")
    return " · ".join(morceaux) or "mode nominal"


def _secondes(texte: str) -> float:
    m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*s?\s*", texte)
    if not m:
        raise argparse.ArgumentTypeError(f"durée illisible : « {texte} » (exemple : LENTEUR=8s)")
    return float(m.group(1).replace(",", "."))


def _quais(texte: str) -> list[int]:
    try:
        quais = [int(q) for q in texte.split(",") if q.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(f"quais illisibles : « {texte} » (exemple : LENTEUR_QUAIS=5,7)") from None
    if not quais or any(q not in range(1, 8) for q in quais):
        raise argparse.ArgumentTypeError(f"quais de 1 à 7 attendus : « {texte} »")
    return quais


def mocks(a) -> int:
    attendre()
    reglages = {"panne": a.panne, "lenteur_s": a.lenteur, "quota": a.quota}
    if a.lenteur_quais:
        reglages["lenteur_quais"] = a.lenteur_quais
    config = regler(**reglages)
    print(f"Mocks (http://mocks:8000) : {decrire(config)}.")
    print("Compteurs et canal conservés ; « make lab10-mocks » sans variable revient au mode nominal.")
    return 0


def appels(a) -> int:
    c = compteur()
    print("Appels réellement reçus par les mocks, depuis leur démarrage :\n")
    for route, n in sorted(c["routes"].items()) or [("(aucun)", 0)]:
        print(f"  {route:<32} {n:>5}")
    if c["alertes"]:
        print("\nAlertes reçues par le canal, par destinataire :")
        for destinataire, n in sorted(c["alertes"].items()):
            print(f"  {destinataire:<32} {n:>5}")
    return 0


def _cellule(texte: str, n: int = 160) -> str:
    texte = " ".join(str(texte).split()).replace("|", "\\|")
    return texte if len(texte) <= n else texte[:n] + "…"


def ecrire_note(chemin: Path, question: str, note: str, trace: list, arret: str | None = None) -> None:
    lignes = ["# LAB 10 — note produite en mode panne", "",
              "Produite par `make lab10-note-panne` : météo en panne (503), votre boucle du LAB 4, le vrai modèle, "
              "contre pharos-ops. Relue par `make lab10-verifier` (critère décisif), sans rappeler le modèle.", "",
              f"Question : {question}", "", "## Note de l'agent", "",
              note.strip() or f"(aucune note : la boucle s'est arrêtée — {arret})", "", "## Trace", "",
              "| Tour | Outil | Arguments | Erreur | Résultat (début) |", "|---|---|---|---|---|"]
    for e in trace:
        lignes.append(f"| {e.tour} | {e.outil} | {_cellule(e.arguments, 80)} | {'oui' if e.erreur else 'non'} "
                      f"| {_cellule(getattr(e, 'resultat', ''))} |")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def note_panne(a) -> int:
    try:
        from pharos_client.boucle import ArretBoucle, executer
    except ModuleNotFoundError:
        print("client/pharos_client introuvable : ce lab part de etat/da3-fin (make depart LAB=10).")
        return 1
    attendre()
    with mode(panne="meteo"):
        print(f"Météo en panne. Question posée à votre boucle, contre pharos-ops :\n  {QUESTION}\n")
        try:
            note, trace, arret = *executer(QUESTION, url=a.url), None
        except ArretBoucle as exc:
            note, trace, arret = "", exc.trace, str(exc)
    if arret and not trace:
        print(f"Arrêt avant tout appel d'outil : {arret}\n{NOTE.relative_to(RACINE)} n'est pas modifié.")
        return 1
    ecrire_note(NOTE, QUESTION, note, trace, arret)
    if arret:
        # M6 : la boucle s'est arrêtée après au moins un appel — la trace reste informative, donc la note est
        # écrite quand même, mais le code de retour et le message doivent dire qu'elle est incomplète : sans
        # cela, le binôme croit que le modèle a conclu (aucune note) alors que la boucle a été coupée.
        print(f"Arrêt avant conclusion : {arret}\n{NOTE.relative_to(RACINE)} écrit, mais la note est incomplète "
              "(la boucle s'est arrêtée avant de conclure) ; la relire, puis make lab10-verifier.")
        return 1
    print(note or f"Arrêt : {arret}")
    print(f"\n→ {NOTE.relative_to(RACINE)} écrit ; le relire, puis make lab10-verifier.")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m outils.lab10")
    sous = p.add_subparsers(dest="commande", required=True)
    m = sous.add_parser("mocks")
    m.add_argument("--panne", choices=["meteo", "referentiel"])
    m.add_argument("--lenteur", type=_secondes, default=0.0)
    m.add_argument("--lenteur-quais", type=_quais)
    m.add_argument("--quota", type=int)
    sous.add_parser("appels")
    n = sous.add_parser("note-panne")
    n.add_argument("--url", default=URL_OPS)
    a = p.parse_args(argv)
    try:
        return {"mocks": mocks, "appels": appels, "note-panne": note_panne}[a.commande](a)
    except MocksInjoignables as exc:
        print(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
