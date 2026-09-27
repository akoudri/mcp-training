"""Trois signaux de dérive, calculés à partir de la trace et du plan (LAB 13, bloc 21.4) — solution de référence.

- hors_plan : les appels dont l'outil ne correspond à aucune étape annoncée — suspects, pas fautifs ;
- jamais_executees : les étapes annoncées dont l'outil n'apparaît nulle part dans la trace ;
- retours_arriere : les appels qui réinterrogent ce qu'un appel antérieur avait déjà obtenu — même outil, mêmes
  arguments (l'appel redondant du bloc 8.4). Le premier appel n'est pas compté, seulement ses répétitions.

signaux(plan, trace) rend les trois nombres, ceux que l'on consigne dans labs/lab13/mesures.md.
"""

from __future__ import annotations

import json


def _cle(e) -> tuple[str, str]:
    return e.outil, json.dumps(e.arguments, sort_keys=True, ensure_ascii=False)


def hors_plan(plan, trace) -> list:
    annonces = {e.outil for e in plan}
    return [e for e in trace if e.outil not in annonces]


def jamais_executees(plan, trace) -> list:
    appeles = {e.outil for e in trace}
    return [etape for etape in plan if etape.outil not in appeles]


def retours_arriere(trace) -> list:
    vus, repetes = set(), []
    for e in trace:
        cle = _cle(e)
        if cle in vus:
            repetes.append(e)
        vus.add(cle)
    return repetes


def signaux(plan, trace) -> dict[str, int]:
    return {"hors_plan": len(hors_plan(plan, trace)),
            "jamais_executees": len(jamais_executees(plan, trace)),
            "retours_arriere": len(retours_arriere(trace))}
