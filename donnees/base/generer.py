"""Contenu de la base PHAROS (LAB 8 et suivants), généré en mémoire, de façon déterministe.

Rien d'autre que ce code n'est versionné : deux appels à generer() rendent exactement les mêmes lignes.
Les invariants qui font les labs (vérité de la question de référence, piège du fuseau, jeudi 8 octobre,
plafond de 200 lignes) sont des tests du kit (tests/test_base_donnees.py).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

import yaml

from donnees import corpus
from pharos import horloge

FUSEAU = horloge.FUSEAU
DOSSIER = Path(__file__).resolve().parent
LEGACY = DOSSIER.parent / "legacy" / "mouvements.yaml"
DEBUT = datetime(2026, 9, 1, tzinfo=FUSEAU)
FIN = datetime(2026, 10, 10, tzinfo=FUSEAU)
AGENTS = {"AG-RANCE": "Agence Maritime Rance", "AG-IROISE": "Consignation Iroise"}
TYPES = ("20", "40", "refrigere")
SENS = ("embarquement", "debarquement")
# Marge de sécurité du critère tirant d'eau (définition 2.0 d'escales_a_risque, slide 274) : valeur de salle.
MARGE_TIRANT_EAU_M = 1.0
# Question de référence du LAB 8 : semaine calendaire précédant le mardi 6 octobre, heure de Paris.
SEMAINE_REFERENCE = (datetime(2026, 9, 28, tzinfo=FUSEAU), datetime(2026, 10, 5, tzinfo=FUSEAU))
# Aucun mouvement généré dans ces deux fenêtres : seuls les trois mouvements pièges y tombent, et le
# même calcul en UTC donne exactement la vérité moins un.
FENETRES_PIEGE = [(SEMAINE_REFERENCE[0], SEMAINE_REFERENCE[0] + timedelta(hours=2)),
                  (SEMAINE_REFERENCE[1], SEMAINE_REFERENCE[1] + timedelta(hours=2))]
JEUDI = date(2026, 10, 8)

NOMS_FLOTTE = ["Goéland", "Cormoran", "Fou de Bassan", "Macareux", "Sterne", "Pétrel", "Fulmar", "Guillemot",
               "Mouette", "Puffin", "Aber Wrac'h", "Pointe du Raz", "Glénan", "Molène", "Bréhat", "Groix",
               "Houat", "Hoëdic", "Iroise Trader", "Rance Carrier", "Crozon", "Camaret", "Douarnenez", "Audierne"]
PAVILLONS = ("FR", "MT", "PA", "LR", "BS", "PT")


@dataclass(frozen=True)
class Navire:
    navire_id: str
    nom: str
    imo: str
    longueur_m: float
    tirant_eau_max_m: float
    pavillon: str
    agent_id: str


@dataclass(frozen=True)
class Quai:
    quai: int
    longueur_m: float
    tirant_eau_max_m: float
    equipements: tuple[str, ...]
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Escale:
    escale_id: str
    navire_id: str
    quai: int
    debut: datetime
    fin: datetime
    statut: str
    tirant_eau_m: float
    tarif_negocie: float


@dataclass(frozen=True)
class Mouvement:
    mouvement_id: str
    escale_id: str
    conteneur_id: str
    sens: str
    horodatage: datetime
    type_conteneur: str


@dataclass(frozen=True)
class Tarif:
    navire_id: str
    grille: str
    montant: float


@dataclass
class Donnees:
    agents: dict[str, str]
    navires: list[Navire]
    quais: list[Quai]
    escales: list[Escale]
    mouvements: list[Mouvement]
    legacy: list[Mouvement]
    tarifs: list[Tarif]
    conflits_jeudi: list[tuple[str, str, int]] = field(default_factory=list)   # (escale, escale, minutes)


def quais() -> list[Quai]:
    brut = yaml.safe_load((DOSSIER / "quais.yaml").read_text(encoding="utf-8"))["quais"]
    return [Quai(q["quai"], float(q["longueur_m"]), float(q["tirant_eau_max_m"]), tuple(q["equipements"]),
                 float(q["latitude"]), float(q["longitude"])) for q in brut]


def _h(jour: date, heures: float) -> datetime:
    return datetime.combine(jour, time(0), FUSEAU) + timedelta(minutes=round(heures * 60))


def statut(debut: datetime, fin: datetime) -> str:
    """Statut au regard de l'horloge fictive (midi du jour fictif, pour rester déterministe)."""
    reference = datetime.combine(horloge.aujourdhui(), time(12), FUSEAU)
    if fin <= reference:
        return "terminee"
    return "accostee" if debut <= reference else "prevue"


def _navires(escales_corpus) -> list[Navire]:
    alea = random.Random("navires")
    navires, vus = [], {}
    agents = {nom: ident for ident, nom in AGENTS.items()}
    for e in escales_corpus:
        if e.navire in vus:
            continue
        ident = f"NAV-{len(navires) + 1:04d}"
        vus[e.navire] = ident
        navires.append(Navire(ident, e.navire, e.imo, float(alea.randrange(150, 300, 5)),
                              round(e.tirant_eau_m + alea.choice((0.3, 0.5, 0.8)), 1),
                              alea.choice(PAVILLONS), agents[e.agent]))
    for i, nom in enumerate(NOMS_FLOTTE):
        ident = f"NAV-{len(navires) + 1:04d}"
        navires.append(Navire(ident, nom, str(9_300_000 + alea.randrange(10_000, 99_999)),
                              float(alea.randrange(90, 260, 5)), round(alea.uniform(6.5, 14.0), 1),
                              alea.choice(PAVILLONS), ("AG-RANCE", "AG-IROISE")[i % 2]))
    return navires


def _tirant(alea: random.Random, navire: Navire, quai: Quai) -> float:
    plafond = min(navire.tirant_eau_max_m, quai.tirant_eau_max_m - MARGE_TIRANT_EAU_M - 0.2)
    return round(max(5.0, plafond - alea.uniform(0, 1.5)), 1)


def _compatibles(flotte: list[Navire], quai: Quai) -> list[Navire]:
    """Navires de la flotte qui tiennent au quai avec la marge (ceux du corpus gardent leurs propres escales)."""
    return [n for n in flotte if n.longueur_m <= quai.longueur_m and n.tirant_eau_max_m >= 5.0]


def _chevauche(debut, fin, fenetres) -> bool:
    return any(debut < f and d < fin for d, f in fenetres)


def generer() -> Donnees:
    source = corpus.charger()
    navires = _navires(source.escales)
    flotte = navires[len({e.navire for e in source.escales}):]      # après les navires du corpus (_navires)
    par_nom = {n.nom: n for n in navires}
    les_quais = quais()
    par_quai = {q.quai: q for q in les_quais}
    alea = random.Random("escales")
    fixes: list[tuple] = []           # (escale_id ou None, navire, quai, debut, fin, tirant)

    for e in source.escales:
        fixes.append((e.escale_id, par_nom[e.navire], e.quai, e.debut, e.fin, e.tirant_eau_m))
    iroise_q3 = next(n for n in _compatibles(flotte, par_quai[3]) if n.agent_id == "AG-IROISE")
    # Conflit de créneau du Vent d'Autan (ESC-2026-0412, quai 3, jeudi 6 h – 20 h) : 60 minutes.
    fixes.append(("ESC-2026-0413", iroise_q3, 3, _h(JEUDI, 19), _h(JEUDI, 29), None))
    # Les deux escales du quai 3 qui portent les mouvements pièges de la semaine de référence.
    piege_a = (None, flotte[1], 3, _h(date(2026, 9, 27), 20), _h(date(2026, 9, 28), 9), None)
    piege_b = (None, flotte[3], 3, _h(date(2026, 10, 4), 22), _h(date(2026, 10, 5), 8), None)
    fixes += [piege_a, piege_b]

    # Jeudi 8 octobre : 22 escales courtes sur les quais 5, 6 et 7, dont un conflit de 45 min au quai 5.
    jeudi = {5: [(0.5, 3), (4, 3), (7.5, 2.5), (10, 3), (12.25, 2.5), (15.5, 3), (19, 2.5), (22, 3.5)],
             6: [(1, 3), (5, 3), (9, 2.5), (12.5, 3), (16, 2.5), (19, 2), (21.5, 3)],
             7: [(0, 4), (5, 3.5), (9.5, 3), (13.5, 3), (17, 3), (20.5, 2.5), (23.5, 4)]}
    for q, creneaux in jeudi.items():
        candidats = _compatibles(flotte, par_quai[q])
        for debut_h, duree_h in creneaux:
            fixes.append((None, alea.choice(candidats), q, _h(JEUDI, debut_h), _h(JEUDI, debut_h + duree_h), None))

    # Historique : sur chaque quai, une suite d'escales sans chevauchement, qui contourne les escales
    # fixes. Les quais 1 à 4 ne reçoivent rien à partir du 5 octobre (le LAB 6 lit le même planning
    # que le corpus), les quais 5 à 7 rien le jeudi (décrit ci-dessus).
    generees = []
    for q in les_quais:
        bloque = [(d, f) for _, _, quai, d, f, _ in fixes if quai == q.quai]
        if q.quai <= 4:
            bloque.append((datetime(2026, 10, 5, tzinfo=FUSEAU), FIN))
        else:
            bloque.append((_h(JEUDI, 0) - timedelta(hours=2), _h(JEUDI, 30)))
        curseur = DEBUT + timedelta(hours=alea.uniform(0, 6))
        candidats = _compatibles(flotte, q)
        while curseur < FIN:
            duree = timedelta(hours=alea.choice((6, 8, 10, 12, 14, 18, 20)))
            if not _chevauche(curseur, curseur + duree + timedelta(hours=1), bloque) and curseur + duree <= FIN:
                generees.append((None, alea.choice(candidats), q.quai, curseur, curseur + duree, None))
                curseur += duree
            curseur += timedelta(hours=alea.choice((1, 2, 3, 4, 6, 8)))

    annulables = {id(g) for g in generees}          # jamais une escale fixe
    tout = sorted(fixes + generees, key=lambda x: (x[3], x[2]))
    escales, numero = [], 1000
    for x in tout:
        ident, navire, q, debut, fin, tirant = x
        if ident is None:
            numero += 1
            ident = f"ESC-2026-{numero}"
        annulee = id(x) in annulables and fin < datetime(2026, 10, 1, tzinfo=FUSEAU) and alea.random() < 0.03
        escales.append(Escale(ident, navire.navire_id, q, debut, fin,
                              "annulee" if annulee else statut(debut, fin),
                              tirant if tirant is not None else _tirant(alea, navire, par_quai[q]),
                              float(alea.randrange(8_000, 60_000, 100))))

    mouvements = _mouvements(escales, piege_a, piege_b)
    return Donnees(dict(AGENTS), navires, les_quais, escales, mouvements, _legacy(mouvements),
                   _tarifs(navires), _conflits(escales, JEUDI))


def _mouvements(escales: list[Escale], piege_a, piege_b) -> list[Mouvement]:
    legacy = yaml.safe_load(LEGACY.read_text(encoding="utf-8"))["mouvements"]
    alea = random.Random("mouvements")
    bruts = []            # (escale_id, conteneur, sens, horodatage, type)
    for e in escales:
        if e.escale_id in legacy:
            for m in legacy[e.escale_id]:
                bruts.append((e.escale_id, m["conteneur"], "debarquement" if m["sens"] == "débarquement" else m["sens"],
                              datetime.fromisoformat(m["heure"]), "refrigere" if m["type"] == "reefer" else m["type"]))
            continue
        if e.statut == "annulee":
            continue
        duree_min = (e.fin - e.debut).total_seconds() / 60
        nombre = alea.randrange(4, 13) if duree_min <= 300 else alea.randrange(8, 37)
        for _ in range(nombre):
            while True:
                instant = e.debut + timedelta(minutes=15 + int(alea.uniform(0, duree_min - 30)) // 5 * 5)
                if not _chevauche(instant, instant + timedelta(minutes=1), FENETRES_PIEGE):
                    break
            bruts.append((e.escale_id, f"{alea.choice(('PHRU', 'MSKU', 'CMAU', 'TGHU'))}{alea.randrange(10**6, 10**7)}",
                          alea.choice(SENS), instant, alea.choices(TYPES, weights=(5, 4, 1))[0]))
    # Les trois mouvements pièges : réfrigérés, quai 3, près des bornes de la semaine de référence.
    ids = {(e.debut, e.quai): e.escale_id for e in escales}
    a, b = ids[(piege_a[3], 3)], ids[(piege_b[3], 3)]
    for escale_id, instant, conteneur in [(a, _h(date(2026, 9, 28), 0.5), "TGHU7310052"),
                                          (a, _h(date(2026, 9, 28), 1.25), "PHRU4408816"),
                                          (b, _h(date(2026, 10, 5), 1.5), "MSKU9012277")]:
        bruts.append((escale_id, conteneur, "debarquement", instant, "refrigere"))
    bruts.sort(key=lambda m: (m[3], m[0], m[1]))
    return [Mouvement(f"MVT-{i:06d}", *m) for i, m in enumerate(bruts, 1)]


def _legacy(mouvements: list[Mouvement]) -> list[Mouvement]:
    """Doublons de reprise de 2019 : les mouvements de septembre, plus 15 % recopiés."""
    alea = random.Random("legacy")
    septembre = [m for m in mouvements if m.horodatage.month == 9]
    lignes = septembre + alea.sample(septembre, round(len(septembre) * 0.15))
    return [Mouvement(f"HDR-{i:06d}", m.escale_id, m.conteneur_id, m.sens, m.horodatage, m.type_conteneur)
            for i, m in enumerate(lignes, 1)]


def _tarifs(navires: list[Navire]) -> list[Tarif]:
    alea = random.Random("tarifs")
    return [Tarif(n.navire_id, alea.choice(("standard", "negocie", "premium")), float(alea.randrange(2_000, 9_000, 50)))
            for n in navires]


def _conflits(escales: list[Escale], jour: date) -> list[tuple[str, str, int]]:
    """Paires d'escales du même quai dont les intervalles se chevauchent et touchent le jour."""
    debut, fin = _h(jour, 0), _h(jour, 24)
    du_jour = sorted((e for e in escales if e.debut < fin and debut < e.fin and e.statut != "annulee"),
                     key=lambda e: (e.quai, e.debut))
    paires = []
    for i, e in enumerate(du_jour):
        for f in du_jour[i + 1:]:
            if f.quai == e.quai and f.debut < e.fin:
                paires.append((e.escale_id, f.escale_id, int((min(e.fin, f.fin) - f.debut).total_seconds() // 60)))
    return paires


def compter(d: Donnees, debut: datetime, fin: datetime, quai: int | None = None,
            type_conteneur: str | None = None, sens: str | None = None) -> int:
    """Nombre de mouvements dans [debut, fin[ — la vérité, calculée sans la base."""
    quai_de = {e.escale_id: e.quai for e in d.escales}
    return sum(1 for m in d.mouvements
               if debut <= m.horodatage < fin and (quai is None or quai_de[m.escale_id] == quai)
               and (type_conteneur is None or m.type_conteneur == type_conteneur)
               and (sens is None or m.sens == sens))
