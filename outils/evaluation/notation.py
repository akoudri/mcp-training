"""Notation déterministe d'une exécution (LAB 15) : aucune appréciation, aucun modèle juge.

    reussite, raisons = noter(cas, reponse, trace, arret=None)

- contient / ne_contient_pas : recherche dans la réponse, l'une et l'autre normalisées (casse, espaces, séparateurs
  de milliers, virgule décimale, « 6 heures » = « 6 h » = « 6h », « 14 h 30 » = « 14h30 » = « 14:30 ») ;
- outils_attendus : chacun présent dans la trace, dans n'importe quel ordre ;
- refus : la réponse porte un marqueur d'incapacité de la liste du kit, ET aucune donnée sans origine (chaque
  chiffre, date, identifiant ou nom connu de la réponse figure dans un résultat d'outil — vérificateur de note du
  LAB 13). Un refus qui invente n'est pas un refus.

Les raisons d'échec sont écrites pour se lire sans ouvrir la trace : « élément manquant : 1 850 »,
« élément interdit : environ », « outil attendu absent : navire_par_nom », « refus attendu absent ».
"""

from __future__ import annotations

import re

from outils.evaluation.cas import Cas
from outils.verifier import note

MARQUEURS_REFUS = ("ne peux pas", "ne peut pas", "impossible", "pas en mesure", "n'ai pas pu", "n'ai pas trouvé",
                   "aucun", "aucune", "introuvable", "n'existe pas", "ne dispose pas", "pas d'information",
                   "pas de donnée", "ne figure pas", "inconnu", "pas accès", "hors de mon périmètre",
                   "hors du périmètre")
_ESPACES = re.compile(r"[\s   ]+")


def normaliser(texte: str) -> str:
    t = (texte or "").replace("’", "'").replace("‘", "'")
    t = _ESPACES.sub(" ", t).casefold().strip()
    t = re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "", t)                    # 1 850 → 1850, 44 400 → 44400
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)                             # 2,8 → 2.8
    t = re.sub(r"\b(\d{1,2}) ?h ?(\d{2})\b", r"\1:\2", t)             # 14 h 30, 14h30 → 14:30
    t = re.sub(r"\b(\d+) ?(?:heures?|h)\b", r"\1 h", t)               # 6 heures, 6h → 6 h
    return t


def outils_de(trace) -> list[str]:
    return [e["outil"] if isinstance(e, dict) else e.outil for e in trace or []]


def est_un_refus(reponse: str) -> bool:
    texte = normaliser(reponse)
    return any(m in texte for m in MARQUEURS_REFUS)


def noter(cas: Cas, reponse: str, trace, arret: str | None = None) -> tuple[bool, list[str]]:
    if arret:
        return False, [f"arrêt de la boucle : {arret}"]
    raisons: list[str] = []
    texte = normaliser(reponse)
    raisons += [f"élément manquant : {e}" for e in cas.contient if normaliser(e) not in texte]
    raisons += [f"élément interdit : {e}" for e in cas.ne_contient_pas if normaliser(e) in texte]
    appeles = set(outils_de(trace))
    raisons += [f"outil attendu absent : {o}" for o in cas.outils_attendus if o not in appeles]
    if cas.refus:
        if not est_un_refus(reponse):
            raisons.append("refus attendu absent")
        else:
            inventes = note.sans_origine(note.verifier_note(reponse, trace or [], cas.question))
            if inventes:
                raisons.append("refus attendu absent : donnée(s) sans origine — "
                               + ", ".join(e.texte for e in inventes[:5]))
    return not raisons, raisons
