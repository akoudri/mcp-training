"""Outils du LAB 15 — le jeu d'évaluation, dans le conteneur atelier.

python -m outils.evaluation empreinte                       (make lab15-empreinte)   le contexte à figer dans un cas
python -m outils.evaluation lancer [--cas a,b] [--fois 3]   (make lab15-lancer)      le jeu : cas × exécutions
python -m outils.evaluation referencer [--resultat P]       (make lab15-referencer)  fige un résultat comme référence
python -m outils.evaluation chaine [--publication]          (make lab15-chaine)      relance si un déclencheur a bougé

Les cas sont dans evaluation/cas/ ; chaque lancement écrit sortie/lab15/<horodatage>.json. Le rapport et sa
comparaison à la référence sont evaluation/rapport.py (make lab15-rapport), écrit par le binôme.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from outils.evaluation import cas as cas_mod
from outils.evaluation import chaine, harnais, resultats

RACINE = Path(__file__).resolve().parents[2]
CAS = RACINE / "evaluation" / "cas"
REFERENCE = RACINE / "evaluation" / "reference.json"
RAPPORT = RACINE / "evaluation" / "rapport.py"
CONSIGNE = RACINE / "client" / "pharos_client" / "consigne.md"
SORTIE = RACINE / "sortie" / "lab15"
JETON_CATALOGUE = "jeton-exploitation"


def base_courante() -> str:
    from pharos import base, empreintes

    return asyncio.run(empreintes.empreinte_base(base.dsn(base.ADMIN)))


def empreintes_courantes() -> dict:
    """Catalogue agrégé (labs/lab13/serveurs.json), prompt système et modèle : les trois déclencheurs."""
    from outils import lab13
    from pharos import empreintes

    serveurs = [{**s, "jeton": s.get("jeton") or JETON_CATALOGUE} for s in lab13.lire_serveurs()]
    catalogues = asyncio.run(lab13.lister(serveurs))
    if not CONSIGNE.exists():
        raise SystemExit(f"{CONSIGNE.relative_to(RACINE)} absent : ce lab part de etat/sg1-fin (make depart LAB=15).")
    return {"catalogue": empreintes.empreinte_catalogue(catalogues), "prompt": empreintes.empreinte_prompt(CONSIGNE),
            "modele": empreintes.empreinte_modele()}


def afficher_empreinte() -> int:
    from pharos import horloge

    courantes = empreintes_courantes()
    print("Contexte à figer dans chaque cas (contexte: {date, identite, base, confirmation}) :")
    print(f"  date        {horloge.aujourdhui().isoformat()}   (l'horloge des serveurs)")
    print(f"  identite    {' | '.join(cas_mod.IDENTITES)}")
    print(f"  base        {base_courante()}   (la base de salle, make lab8-base)")
    print("  confirmation refuser (défaut) | accepter")
    print("\nDéclencheurs de la chaîne (comparés à evaluation/reference.json) :")
    for cle, valeur in courantes.items():
        print(f"  {cle:<11} {valeur}")
    return 0


def _charger_cas(filtre: str | None) -> list[cas_mod.Cas]:
    cas = cas_mod.charger(CAS, RACINE)
    if filtre:
        voulus = {c.strip() for c in filtre.split(",") if c.strip()}
        inconnus = voulus - {c.id for c in cas}
        if inconnus:
            raise cas_mod.CasInvalide(f"cas inconnu(s) : {', '.join(sorted(inconnus))}.")
        cas = [c for c in cas if c.id in voulus]
    if not cas:
        raise cas_mod.CasInvalide("aucun cas dans evaluation/cas/ : make lab15-exemple montre le format.")
    return cas


def lancer(filtre: str | None = None, fois: int = 3) -> Path | None:
    from outils import lab10
    from pharos import horloge

    try:
        cas = _charger_cas(filtre)
    except cas_mod.CasInvalide as exc:
        print(f"Cas refusé — {exc}")
        return None
    if not filtre and cas_mod.quota(cas):
        print("Quota non respecté (le jeu tourne quand même) : " + " · ".join(cas_mod.quota(cas)))
    problemes = harnais.contexte_fige(cas, aujourdhui=horloge.aujourdhui().isoformat(), base=base_courante(),
                                      racine=RACINE)
    if problemes:
        print("Contexte non figé : le jeu ne tourne pas.\n" + "\n".join(f"  - {p}" for p in problemes))
        return None
    try:
        lab10.regler()                          # mocks en mode nominal : ni panne, ni lenteur, ni quota
    except lab10.MocksInjoignables as exc:
        print(f"{exc} — ou make lab13-tout.")
        return None
    empreintes = {"base": cas[0].contexte.base, **empreintes_courantes()}
    print(f"{len(cas)} cas × {fois} exécution(s), modèle {empreintes['modele']} — trois cas à la fois, la "
          "confirmation refusée sauf mention contraire :")
    cas_resultats = harnais.lancer(cas, fois=fois)
    horodatage = horloge.maintenant().strftime("%Y%m%d-%H%M%S")
    resultat = harnais.assembler(cas_resultats, fois=fois, modele=empreintes["modele"], empreintes=empreintes,
                                 horodatage=horodatage)
    SORTIE.mkdir(parents=True, exist_ok=True)
    chemin = SORTIE / f"{horodatage}.json"
    chemin.write_text(json.dumps(resultat, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\n" + resultats.tableau(resultat))
    print(f"\nRésultat : {chemin.relative_to(RACINE)} — make lab15-rapport le compare à la référence.")
    return chemin


def referencer(chemin: str | None) -> int:
    source = Path(chemin) if chemin else resultats.dernier(SORTIE)
    resultat = resultats.charger(source)
    REFERENCE.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE.write_text(json.dumps(resultats.reduire(resultat, source.name), ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    print(f"Référence figée depuis {source.name} : {REFERENCE.relative_to(RACINE)} — le commiter avec "
          "labs/lab15/reference.md.")
    print(resultats.tableau(resultat))
    return 0


def executer_chaine(publication: bool) -> int:
    reference = json.loads(REFERENCE.read_text(encoding="utf-8") or "{}") if REFERENCE.exists() else {}
    a_lancer, motifs = chaine.decider(reference, empreintes_courantes(), publication)
    if not a_lancer:
        print("Rien à lancer : ni le modèle, ni le catalogue, ni le prompt système n'ont changé, et rien n'est "
              "publié.")
        return 0
    print("Le jeu tourne : " + " ; ".join(motifs) + ".")
    chemin = lancer()
    if chemin is None:
        return 1
    return subprocess.run([sys.executable, str(RAPPORT), str(chemin)], cwd=RACINE).returncode


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="outils.evaluation")
    sous = p.add_subparsers(dest="commande", required=True)
    sous.add_parser("empreinte")
    l = sous.add_parser("lancer")
    l.add_argument("--cas")
    l.add_argument("--fois", type=int, default=3)
    r = sous.add_parser("referencer")
    r.add_argument("--resultat")
    c = sous.add_parser("chaine")
    c.add_argument("--publication", action="store_true")
    a = p.parse_args(argv)
    if a.commande == "empreinte":
        return afficher_empreinte()
    if a.commande == "referencer":
        return referencer(a.resultat)
    if a.commande == "chaine":
        return executer_chaine(a.publication)
    if os.environ.get("SANS_MODELE") == "1":
        print("Jeu ignoré (SANS_MODELE=1) : aucun appel au modèle.")
        return 0
    return 0 if lancer(a.cas, a.fois) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
