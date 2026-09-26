"""Créneaux d'accostage par quai et fenêtres de marée, pour pharos-quai (LAB 6).

Générés une fois, de façon déterministe, et versionnés dans creneaux.yaml :
    python -m donnees.quai.creneaux
Un créneau de deux heures est réservé à une escale s'il chevauche son intervalle [début, fin] au même
quai ; les autres sont libres. Le test du kit vérifie que le fichier versionné est celui que ce script produit.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from donnees import corpus

FICHIER = Path(__file__).resolve().parent / "creneaux.yaml"
JOURS = (date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8))
QUAIS = (1, 2, 3, 4)
FUSEAU = ZoneInfo("Europe/Paris")
DUREE_H = 2
# Fenêtres de pleine mer, heure de Paris : les seuls moments où un navire au-delà du seuil de tirant
# d'eau (quais.yaml) peut accoster.
MAREES = {
    "2026-10-06": [["03:10", "06:10"], ["15:30", "18:30"]],
    "2026-10-07": [["03:50", "06:50"], ["16:10", "19:10"]],
    "2026-10-08": [["04:30", "07:30"], ["16:50", "19:50"]],
}


def _creneaux(jour: date, quai: int, escales: list[corpus.Escale]) -> list[dict]:
    lignes = []
    for h in range(0, 24, DUREE_H):
        debut = datetime.combine(jour, time(h), FUSEAU)
        fin = debut + timedelta(hours=DUREE_H)
        occupant = next((e.escale_id for e in escales if e.quai == quai and e.debut < fin and debut < e.fin), None)
        lignes.append({"debut": f"{h:02d}:00", "fin": f"{h + DUREE_H:02d}:00", "escale_id": occupant})
    return lignes


def generer() -> dict:
    escales = corpus.charger().escales
    return {"marees": MAREES,
            "creneaux": {j.isoformat(): {q: _creneaux(j, q, escales) for q in QUAIS} for j in JOURS}}


def ecrire(chemin: Path = FICHIER) -> None:
    entete = "# Généré par « python -m donnees.quai.creneaux » — ne pas modifier à la main.\n"
    chemin.write_text(entete + yaml.safe_dump(generer(), allow_unicode=True, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    ecrire()
