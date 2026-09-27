"""Trois signaux de dérive, calculés à partir de la trace et du plan (LAB 13, bloc 21.4) — SQUELETTE : les trois
fonctions sont à écrire (étape 5) ; signaux() est fourni.

- hors_plan : les appels dont l'outil ne correspond à aucune étape annoncée — suspects, pas fautifs ;
- jamais_executees : les étapes annoncées dont l'outil n'apparaît nulle part dans la trace ;
- retours_arriere : les appels qui réinterrogent ce qu'un appel antérieur avait déjà obtenu — même outil, mêmes
  arguments (l'appel redondant du bloc 8.4). Le premier appel n'est pas compté, seulement ses répétitions.

signaux(plan, trace) rend les trois nombres, ceux que l'on consigne dans labs/lab13/mesures.md.
"""

from __future__ import annotations


def hors_plan(plan, trace) -> list:
    raise NotImplementedError("derive.hors_plan : à écrire (LAB 13, étape 5).")


def jamais_executees(plan, trace) -> list:
    raise NotImplementedError("derive.jamais_executees : à écrire (LAB 13, étape 5).")


def retours_arriere(trace) -> list:
    raise NotImplementedError("derive.retours_arriere : à écrire (LAB 13, étape 5).")


def signaux(plan, trace) -> dict[str, int]:
    return {"hors_plan": len(hors_plan(plan, trace)),
            "jamais_executees": len(jamais_executees(plan, trace)),
            "retours_arriere": len(retours_arriere(trace))}
