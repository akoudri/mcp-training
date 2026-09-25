"""Chargement validé de la source du corpus documentaire PHAROS."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml

DOSSIER = Path(__file__).resolve().parent / "corpus"
SUJETS = ("penalites", "delais", "manutention", "assurance")
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


@dataclass(frozen=True)
class DocSimple:
    document_id: str
    nb_pages: int


@dataclass(frozen=True)
class Contrat:
    document_id: str
    nb_pages: int
    signature: date
    prise_effet: date
    echeance: date
    sujets: list[str]
    valeurs: dict


@dataclass(frozen=True)
class Escale:
    escale_id: str
    navire: str
    imo: str
    quai: int
    debut: datetime
    fin: datetime
    armateur: str
    agent: str
    contrat: Contrat | None
    connaissements: list[DocSimple]
    avis_escale: DocSimple


@dataclass(frozen=True)
class Corpus:
    operateur: str
    escales: list[Escale] = field(default_factory=list)

    def escale(self, escale_id: str) -> Escale:
        for e in self.escales:
            if e.escale_id == escale_id:
                return e
        raise KeyError(escale_id)


def euros(montant: int) -> str:
    """1850 -> '1 850 €' (espace fine insécable remplacée par une espace simple pour l'extraction)."""
    return f"{montant:,}".replace(",", " ") + " €"


def date_longue(d: date) -> str:
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def _contrat(brut: dict | None) -> Contrat | None:
    if brut is None:
        return None
    inconnus = set(brut["sujets"]) - set(SUJETS)
    if inconnus:
        raise ValueError(f"sujets inconnus dans {brut['document_id']} : {inconnus}")
    return Contrat(
        document_id=brut["document_id"], nb_pages=int(brut["nb_pages"]),
        signature=brut["signature"], prise_effet=brut["prise_effet"], echeance=brut["echeance"],
        sujets=list(brut["sujets"]), valeurs=dict(brut["valeurs"]),
    )


def charger(chemin: Path = DOSSIER / "escales.yaml") -> Corpus:
    brut = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    escales = [
        Escale(
            escale_id=e["escale_id"], navire=e["navire"], imo=str(e["imo"]), quai=int(e["quai"]),
            debut=e["debut"], fin=e["fin"], armateur=e["armateur"], agent=e["agent"],
            contrat=_contrat(e.get("contrat")),
            connaissements=[DocSimple(**d) for d in e["connaissements"]],
            avis_escale=DocSimple(**e["avis_escale"]),
        )
        for e in brut["escales"]
    ]
    return Corpus(operateur=brut["operateur"], escales=escales)


def _blocs_du_gabarit() -> list[tuple[str, str | None, str]]:
    """[(titre, sujet ou None, corps)] dans l'ordre du gabarit."""
    blocs = re.split(r"^## ", (DOSSIER / "contrat.md").read_text(encoding="utf-8"), flags=re.M)
    resultat = []
    for bloc in blocs[1:]:
        titre, _, corps = bloc.partition("\n")
        sujet = None
        m = re.match(r"sujet: (\w+)\n", corps)
        if m:
            sujet, corps = m.group(1), corps[m.end():]
        resultat.append((titre.strip(), sujet, corps.strip()))
    return resultat


def articles_du_contrat(c: Corpus, e: Escale) -> list[tuple[str, str]]:
    if e.contrat is None:
        raise ValueError(f"{e.escale_id} n'a pas de contrat de manutention")
    v = dict(e.contrat.valeurs)
    champs = {
        "operateur": c.operateur, "armateur": e.armateur, "agent": e.agent,
        "navire": e.navire, "imo": e.imo,
        "signature_txt": date_longue(e.contrat.signature),
        "prise_effet_txt": date_longue(e.contrat.prise_effet),
        "echeance_txt": date_longue(e.contrat.echeance),
        **v,
    }
    for cle in ("montant_horaire", "plafond", "montant_garanti"):
        if cle in v:
            champs[f"{cle}_txt"] = euros(v[cle])
    articles = []
    for titre, sujet, corps in _blocs_du_gabarit():
        if sujet is not None and sujet not in e.contrat.sujets:
            continue
        articles.append((f"Article {len(articles) + 1} — {titre}", corps.format(**champs)))
    return articles
