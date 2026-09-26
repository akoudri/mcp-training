"""make lab3-cout-surensemble — ce que coûte, en tokens, de renvoyer les deux formes de résultat (extension C du LAB 3).

Joue le scénario 2026-07-28 contre le serveur, puis compte, pour chaque résultat d'outil, les tokens
du contenu textuel seul et ceux du sur-ensemble (texte + structuredContent).
Usage : python -m outils.cout_surensemble URL
"""

from __future__ import annotations

import asyncio
import json
import sys

from outils.scenario_legacy import attendre, derouler
from outils.tokens_catalogue import ENCODAGE


def _t(valeur) -> int:
    return len(ENCODAGE.encode(json.dumps(valeur, ensure_ascii=False)))


def mesurer_resultats(resultats: list[tuple[str, dict]]) -> list[dict]:
    """[(outil, result JSON-RPC)] → une ligne par résultat réussi : tokens du texte seul et du sur-ensemble."""
    lignes = []
    for outil, r in resultats:
        if r.get("isError") or "content" not in r:
            continue
        texte = _t(r["content"])
        lignes.append({"outil": outil, "texte": texte,
                       "surensemble": texte + (_t(r["structuredContent"]) if "structuredContent" in r else 0)})
    return lignes


def tableau(lignes: list[dict]) -> str:
    sortie = ["| Outil | Texte seul | Texte + structuredContent | Surcoût |", "|---|---:|---:|---:|"]
    for l in lignes:
        sortie.append(f"| {l['outil']} | {l['texte']} | {l['surensemble']} | {l['surensemble'] - l['texte']:+d} |")
    texte, total = sum(l["texte"] for l in lignes), sum(l["surensemble"] for l in lignes)
    if texte:
        sortie += ["", f"Sur ce scénario : {total - texte} tokens de plus ({(total - texte) / texte:.0%}), payés par "
                   "tous les clients, y compris ceux qui ont migré et n'ont besoin que d'une forme."]
    return "\n".join(sortie)


async def _principal(url: str) -> int:
    d = await derouler(url, "2026-07-28")
    if d.erreur:
        print(f"Scénario interrompu : {d.erreur}")
    resultats = []
    for e in d.appels():
        try:
            resultats.append((json.loads(e.corps_requete)["params"]["name"], json.loads(e.corps_reponse)["result"]))
        except (ValueError, KeyError):
            continue
    print(tableau(mesurer_resultats(resultats)))
    return 0


def main(argv: list[str]) -> int:
    url = argv[0] if argv else "http://observateur:8204/mcp"
    attendre(url, conseil="lancer make lab3-deux-instances")
    return asyncio.run(_principal(url))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
