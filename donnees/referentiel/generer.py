"""Contenu du référentiel navires, dérivé de la base PHAROS (donnees.base.generer) : mêmes navires, mêmes escales.

Le fichier navires.yaml est versionné pour être lisible ; un test du kit impose qu'il soit exactement ce que
rend ce module. Le référentiel « ment » comme une vraie API tierce (LAB 10) : trois navires ont une
longueur absente, nulle (null) ou à zéro, et l'un d'eux un tirant d'eau maximal à zéro — alors que la
documentation (docs/api/referentiel.yaml) annonce ces champs obligatoires. Ce n'est jamais le Vent d'Autan.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from donnees.base import generer

FICHIER = Path(__file__).resolve().parent / "navires.yaml"
ABSENT = object()
# Nom du navire → champs qui mentent (ABSENT : la clé manque).
MENTEURS = {"Macareux": {"longueur_m": ABSENT},
            "Glénan": {"longueur_m": None},
            "Molène": {"longueur_m": 0, "tirant_eau_max_m": 0}}
ENTETE = ("# Référentiel navires — contenu du mock (LAB 10). GÉNÉRÉ par « python -m donnees.referentiel » depuis\n"
          "# la base PHAROS : ne pas modifier à la main. Heures locales du port, sans fuseau (comme l'API réelle).\n")


def _heure(instant) -> str:
    return instant.astimezone(generer.FUSEAU).replace(tzinfo=None).isoformat(timespec="minutes")


def navires(donnees: generer.Donnees | None = None) -> list[dict]:
    """Les fiches du référentiel, dans l'ordre des identifiants ; escales annulées exclues."""
    d = donnees or generer.generer()
    fiches = []
    for n in sorted(d.navires, key=lambda n: n.navire_id):
        fiche = {"navire_id": n.navire_id, "nom": n.nom, "imo": n.imo, "longueur_m": n.longueur_m,
                 "tirant_eau_max_m": n.tirant_eau_max_m, "pavillon": n.pavillon,
                 "escales": [{"escale_id": e.escale_id, "quai": e.quai, "debut": _heure(e.debut), "fin": _heure(e.fin)}
                             for e in sorted(d.escales, key=lambda e: e.debut)
                             if e.navire_id == n.navire_id and e.statut != "annulee"]}
        for champ, valeur in MENTEURS.get(n.nom, {}).items():
            if valeur is ABSENT:
                del fiche[champ]
            else:
                fiche[champ] = valeur
        fiches.append(fiche)
    return fiches


def rendre(donnees: generer.Donnees | None = None) -> str:
    return ENTETE + yaml.safe_dump({"navires": navires(donnees)}, allow_unicode=True, sort_keys=False, width=120)


def charger() -> list[dict]:
    return yaml.safe_load(FICHIER.read_text(encoding="utf-8"))["navires"]
