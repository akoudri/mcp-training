"""Horloge fictive de PHAROS.

Tout le parcours se déroule le mardi 6 octobre 2026, à Paris. Les réponses de
référence des labs en dépendent : aucun code ne lit l'horloge système directement.
"""

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSEAU = ZoneInfo("Europe/Paris")
DATE_FICTIVE = date(2026, 10, 6)


def aujourdhui() -> date:
    """Le jour fictif, ou celui de PHAROS_AUJOURDHUI (AAAA-MM-JJ) s'il est défini."""
    valeur = os.environ.get("PHAROS_AUJOURDHUI")
    return date.fromisoformat(valeur) if valeur else DATE_FICTIVE


def maintenant() -> datetime:
    """L'heure réelle à Paris, reportée sur le jour fictif."""
    reel = datetime.now(FUSEAU)
    return reel.replace(year=aujourdhui().year, month=aujourdhui().month, day=aujourdhui().day)
