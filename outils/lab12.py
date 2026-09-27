"""Outils du LAB 12 : le canal d'alertes (remise à zéro, compteur) et les clients de test de publier_alerte.

python -m outils.lab12 canal                                   (make lab12-canal : remet le canal à zéro)
python -m outils.lab12 compteur                                (make lab12-compteur)
python -m outils.lab12 clients [--sans-elicitation] [--defaut] [--url …] (make lab12-clients [URL=…])

Les clients visent pharos-ops sur 8103, une instance (étapes 1 à 4) ; à l'étape 5, URL=http://observateur:8203/mcp
vise le répartiteur des deux instances.

Le compteur du canal est la seule vérité du lab : une alerte comptée est partie.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import mcp_types

from outils import lab10
from outils.client_test import ClientTest, ServeurInjoignable

URL = "http://observateur:8103/mcp"
LANCER = ("« make lab10-up » (pharos-ops, 8103 : étapes 1 à 4) ou « make lab12-deux-instances » "
          "(répartiteur, 8203 : étape 5)")
OUTIL = "publier_alerte"
ARGUMENTS = {"escale_id": "ESC-2026-0412", "niveau": "orange", "destinataire": "exploitation",
             "note": "Escale du Vent d'Autan à risque jeudi : tirant d'eau et coup de vent."}


def raz(url: str | None = None) -> None:
    lab10._requete("POST", "/_raz", url)


def alertes(url: str | None = None) -> dict[str, int]:
    return lab10.compteur(url)["alertes"]


def canal(a) -> int:
    lab10.attendre()
    raz()
    print("Canal d'alertes remis à zéro (compteurs des mocks compris). make lab12-compteur : ce qui part.")
    return 0


def compteur(a) -> int:
    parties = alertes()
    total = sum(parties.values())
    print(f"Alertes réellement parties : {total}")
    for destinataire, n in sorted(parties.items()):
        print(f"  {destinataire:<32} {n:>4}")
    if total:
        print("\nDernières reçues (corps compris) :")
        for a in lab10._requete("GET", "/_journal")["alertes"][-5:]:
            print(f"  {a['alerte_id']} {a['recue']} → {a['destinataire']} : {a['escale_id']} {a['niveau']} {a.get('note') or ''}")
    return 0


def _texte(resultat) -> str:
    texte = "\n".join(getattr(b, "text", "") or "" for b in resultat.content)
    if not texte and getattr(resultat, "structured_content", None) is not None:
        texte = json.dumps(resultat.structured_content, ensure_ascii=False)
    return texte


async def _clients(url: str, jeton: str, profil: str) -> int:
    avant = sum(alertes().values())
    async with ClientTest(url, jeton=jeton, profil=profil, nom=f"pharos-lab12-{profil}") as c:
        await c.joindre(LANCER)
        print(f"Client « {profil} » — déclare : {c.declare()}")
        print(f"Appel : {OUTIL}({', '.join(f'{k}={v!r}' for k, v in ARGUMENTS.items())})\n")
        if profil == "defaut":                     # le client répond seul, sans rien demander (extension C)
            r = await c.appeler(OUTIL, ARGUMENTS)
            print(("Résultat — ERREUR (isError) :\n" if r.is_error else "Résultat :\n") + _texte(r))
        else:
            brut = await c.appeler_brut(OUTIL, ARGUMENTS)
            if isinstance(brut, mcp_types.InputRequiredResult):
                print("Réponse : input_required — une demande d'entrée, à rejouer (le client de test ne rejoue pas).")
                for cle, requete in (brut.input_requests or {}).items():
                    params = requete.params
                    print(f"  [{cle}] {params.message}\n        schéma : {json.dumps(params.requested_schema, ensure_ascii=False)}")
                print(f"  requestState ({len(brut.request_state or '')} caractères) : {(brut.request_state or '')[:48]}…")
            else:
                print(("Réponse — ERREUR (isError) :\n" if brut.is_error else "Réponse :\n") + _texte(brut))
    apres = sum(alertes().values())
    print(f"\nCompteur du canal : {avant} → {apres}")
    return 0


def clients(a) -> int:
    profil = "sans_elicitation" if a.sans_elicitation else "defaut" if a.defaut else "complet"
    return asyncio.run(_clients(a.url, a.jeton, profil))


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m outils.lab12")
    sous = p.add_subparsers(dest="commande", required=True)
    sous.add_parser("canal")
    sous.add_parser("compteur")
    c = sous.add_parser("clients")
    c.add_argument("--sans-elicitation", action="store_true")
    c.add_argument("--defaut", action="store_true")
    c.add_argument("--url", default=URL)
    c.add_argument("--jeton", default=os.environ.get("PHAROS_JETON") or "jeton-exploitation")
    a = p.parse_args(argv)
    try:
        return {"canal": canal, "compteur": compteur, "clients": clients}[a.commande](a)
    except (lab10.MocksInjoignables, ServeurInjoignable) as exc:
        print(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
