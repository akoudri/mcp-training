"""Lire un résultat du jeu d'évaluation et en tirer les taux (LAB 15) — fourni, utilisé par evaluation/rapport.py.

    resultat = charger(Path("sortie/lab15/20261006-101500.json"))   # ou dernier() : le plus récemment écrit de sortie/lab15/
    par_cas(resultat)        # {id: Taux(famille, reussites, executions, reussi)}
    par_famille(resultat)    # {famille: Taux} — exécutions réussies / exécutions, toutes celles de la famille
    print(tableau(resultat)) # le tableau par cas puis le taux par famille, lisible sans ouvrir une trace

Un résultat (écrit par le harnais) :
    {"horodatage", "modele", "empreintes": {base, catalogue, prompt, modele}, "fois",
     "cas": [{"id", "famille", "tolerance": "2/3", "reussites", "executions", "reussi",
              "detail": [{"reussite", "raisons", "outils", "reponse", "tokens", "cout", "duree_s", "arret"}]}],
     "cout_total", "tokens_total"}
Une référence (evaluation/reference.json, écrite par make lab15-referencer) a la même forme, réduite ; chaque cas
dit de quel résultat il vient (un jeu partiel complète la référence : « resultat » liste alors les sources) :
    {"modele", "empreintes", "resultat", "cas": [{"id", "famille", "tolerance", "reussites", "executions", "reussi",
                                                  "resultat"}]}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from outils.evaluation.cas import FAMILLES

SORTIE = Path("sortie/lab15")


@dataclass(frozen=True)
class Taux:
    famille: str
    reussites: int
    executions: int
    reussi: bool = True

    @property
    def valeur(self) -> float:
        return self.reussites / self.executions if self.executions else 0.0

    def __str__(self) -> str:
        return f"{self.reussites}/{self.executions}"


def charger(chemin: Path) -> dict:
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


def dernier(dossier: Path = SORTIE) -> Path:
    """Le résultat écrit le plus récemment (date de modification du fichier) : les noms suivent l'horloge fictive
    des serveurs, qui rejoue le même jour à chaque séance — l'ordre des noms n'est pas celui des lancements."""
    fichiers = sorted(Path(dossier).glob("*.json"), key=lambda f: (f.stat().st_mtime_ns, f.name))
    if not fichiers:
        raise FileNotFoundError(f"aucun résultat dans {dossier} : lancer d'abord « make lab15-lancer ».")
    return fichiers[-1]


def par_cas(resultat: dict) -> dict[str, Taux]:
    return {c["id"]: Taux(c["famille"], int(c["reussites"]), int(c["executions"]), bool(c["reussi"]))
            for c in resultat.get("cas", [])}


def par_famille(resultat: dict) -> dict[str, Taux]:
    taux = {}
    for famille in FAMILLES:
        cas = [t for t in par_cas(resultat).values() if t.famille == famille]
        if cas:
            taux[famille] = Taux(famille, sum(t.reussites for t in cas), sum(t.executions for t in cas),
                                 all(t.reussi for t in cas))
    return taux


def global_(resultat: dict) -> Taux:
    cas = list(par_cas(resultat).values())
    return Taux("global", sum(t.reussites for t in cas), sum(t.executions for t in cas), all(t.reussi for t in cas))


def _premiere_raison(c: dict) -> str:
    for d in c.get("detail", []):
        if d.get("raisons"):
            return d["raisons"][0]
    return ""


def tableau(resultat: dict) -> str:
    cas = resultat.get("cas", [])
    if not cas:
        return "Aucun cas dans ce résultat."
    largeur = max(len(c["id"]) for c in cas)
    lignes = [f"Jeu d'évaluation — modèle {resultat.get('modele', '?')}, {resultat.get('fois', '?')} exécution(s) "
              "par cas", "", f"  {'cas':<{largeur}}  {'famille':<9} taux  tolérance  première raison d'échec"]
    for c in sorted(cas, key=lambda c: (FAMILLES.index(c["famille"]), c["id"])):
        marque = "✅" if c["reussi"] else "❌"
        lignes.append(f"{marque} {c['id']:<{largeur}}  {c['famille']:<9} {c['reussites']}/{c['executions']}  "
                      f"{c.get('tolerance', ''):<9}  {_premiere_raison(c)}")
    lignes += ["", "Taux par famille (exécutions réussies / exécutions) :"]
    lignes += [f"  {f:<9} {t}  ({t.valeur:.0%})" for f, t in par_famille(resultat).items()]
    g = global_(resultat)
    lignes.append(f"  {'global':<9} {g}  ({g.valeur:.0%})")
    if resultat.get("cout_total") is not None:
        lignes.append(f"\nCoût : {resultat['cout_total']:.4f} $ · tokens : {resultat.get('tokens_total', '?')}")
    return "\n".join(lignes)


def reduire(resultat: dict, chemin: str = "") -> dict:
    """La référence tirée d'un résultat : taux par cas et empreintes, sans les réponses ni les traces."""
    return {"modele": resultat.get("modele"), "empreintes": resultat.get("empreintes", {}), "resultat": chemin,
            "cas": [{**{k: c[k] for k in ("id", "famille", "tolerance", "reussites", "executions", "reussi")},
                     "resultat": chemin} for c in resultat.get("cas", [])]}
