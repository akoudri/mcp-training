"""Vérificateur de note (LAB 13) : chaque chiffre, chaque date et chaque nom de la note a-t-il une origine dans la trace ?

    elements = verifier_note(note, trace, question)     # trace : Enregistrement, ou dict (labs/lab13/execution.json)
    print(formater(elements))                           # élément → origine (t3 pharos-docs rechercher_clause), ou « sans origine »

Ce qui est extrait de la note, puis cherché dans les résultats d'outils de la trace, sous forme normalisée :
- les identifiants (ESC-AAAA-NNNN, NAV-NNNN, CM-NNNN…) ;
- les dates (« 8 octobre », « jeudi 8 octobre 2026 », « 08/10/2026 », « 2026-10-08 ») ;
- les heures (« 14 h », « 14 h 30 », « 14:00 ») : origine si l'heure figure dans la trace, ou si le nombre y figure
  (« 6 h » peut être une durée : la franchise de « 6 heures ») ;
- les nombres (« 1 850 », « 2,8 », « 34 kt ») : 1 850 et 1850 sont le même nombre ; un nombre obtenu par une seule
  opération (×, +, −) sur deux nombres rendus par le MÊME appel d'outil est accepté, et l'opération est dite
  (la marge 13,5 − 12,9) — pas au-delà : plus on accepte de combinaisons, plus une invention passe par hasard ;
- les noms propres d'une liste connue du kit (navires, armateurs, agents). Un nom hors liste n'est pas vérifié.

Ne sont pas vérifiés : ce qui figure déjà dans la question, les numéros d'étape (« étape 3 », « 3. » en début de
ligne), les nombres 0 et 1 isolés. Aucun appel au modèle.
"""

from __future__ import annotations

import itertools
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MOIS = {m: i for i, m in enumerate(["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                                    "septembre", "octobre", "novembre", "décembre"], start=1)}
ANNEE_PAR_DEFAUT = 2026
ESPACES = "    "

_IDENTIFIANT = re.compile(r"\b(?:ESC-\d{4}-\d{4}|NAV-\d{4}|CM-\d{4}|BL-\d{4}-\d+|AE-\d{4}|AG-[A-Z]+)\b")
_DATE_TEXTE = re.compile(r"\b(\d{1,2})(?:er)?[" + ESPACES + r"]+(" + "|".join(MOIS) + r")(?:[" + ESPACES + r"]+(\d{4}))?\b",
                         re.IGNORECASE)
_DATE_NUM = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})")
_HEURE = re.compile(r"(?<![\d,.])(\d{1,2})(?:[" + ESPACES + r"]?h(?:eures?)?(?:[" + ESPACES + r"]?(\d{2}))?\b|:(\d{2})\b)",
                    re.IGNORECASE)
_NOMBRE = re.compile(r"(?<![\w.,])(\d{1,3}(?:[" + ESPACES + r"]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)(?![\w]*-\d)")
_ETAPE = re.compile(r"(?:\b[ée]tapes?[" + ESPACES + r"]+\d+|^[" + ESPACES + r"]*\d+[.)])", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class Element:
    texte: str
    genre: str            # identifiant | date | heure | nombre | nom
    origine: str | None   # « t3 pharos-docs rechercher_clause », « calcul : 1850 × 4 », ou None : sans origine


def _champ(e, nom: str, defaut=""):
    return e.get(nom, defaut) if isinstance(e, dict) else getattr(e, nom, defaut)


def _source(e) -> str:
    serveur = str(_champ(e, "serveur") or "").strip()
    return f"t{_champ(e, 'tour', '?')} {serveur + ' ' if serveur else ''}{_champ(e, 'outil')}".strip()


def nombre(texte: str) -> float:
    """« 1 850 » → 1850.0 ; « 2,8 » → 2.8."""
    return float(re.sub(f"[{ESPACES}]", "", texte).replace(",", "."))


def _cle(valeur: float) -> float:
    return round(valeur, 2)


@lru_cache(maxsize=1)
def noms_connus() -> tuple[str, ...]:
    """Navires (référentiel), armateurs et agents (corpus), opérateur : la liste de noms que la note peut citer."""
    import yaml
    noms: set[str] = set()
    navires = RACINE / "donnees" / "referentiel" / "navires.yaml"
    if navires.exists():
        noms |= {n["nom"] for n in yaml.safe_load(navires.read_text(encoding="utf-8"))["navires"]}
    corpus = RACINE / "donnees" / "corpus" / "escales.yaml"
    if corpus.exists():
        for e in yaml.safe_load(corpus.read_text(encoding="utf-8"))["escales"]:
            noms |= {e.get("navire", ""), e.get("armateur", ""), e.get("agent", "")}
    noms |= {"Agence Maritime Rance", "Consignation Iroise"}
    return tuple(sorted((n for n in noms if n), key=len, reverse=True))


class _Index:
    """Ce que la trace contient, sous forme normalisée, avec la source de chaque valeur (premier appel qui la rend)."""

    def __init__(self, trace):
        self.textes: list[tuple[str, str]] = []
        self.nombres: dict[float, str] = {}
        self.dates: dict[str, str] = {}
        self.heures: dict[str, str] = {}
        self.par_appel: list[tuple[list[float], str]] = []
        for e in trace:
            texte = str(_champ(e, "resultat") or "")
            source = _source(e)
            self.textes.append((texte, source))
            for a, m, j in _DATE_ISO.findall(texte):
                self.dates.setdefault(f"{a}-{m}-{j}", source)
            for h, mi in re.findall(r"T(\d{2}):(\d{2})", texte):
                self.heures.setdefault(f"{int(h):02d}:{mi}", source)
            for element in _elements_de(texte, sans_dates=True):
                if element[0] == "heure":
                    self.heures.setdefault(element[1], source)
            valeurs = [_cle(nombre(brut)) for brut in _NOMBRE.findall(_masquer(texte))]
            for valeur in valeurs:
                self.nombres.setdefault(valeur, source)
            self.par_appel.append((sorted(set(v for v in valeurs if v != 0))[:200], source))

    def cherche_texte(self, fragment: str) -> str | None:
        f = fragment.casefold()
        return next((s for t, s in self.textes if f in t.casefold()), None)

    def calcul(self, cible: float) -> str | None:
        for valeurs, source in self.par_appel:
            for a, b in itertools.combinations_with_replacement(valeurs, 2):
                for resultat, signe in ((a * b, "×"), (a + b, "+"), (b - a, "−")):
                    if _cle(resultat) == cible:
                        x, y = (b, a) if signe == "−" else (a, b)
                        return f"calcul : {x:g} {signe} {y:g} ({source})"
        return None


def _masquer(texte: str) -> str:
    """Retire du texte les identifiants et les dates ISO, pour que leurs chiffres ne passent pas pour des nombres."""
    texte = _IDENTIFIANT.sub(" ", texte)
    texte = re.sub(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:\d{2}|Z)?)?", " ", texte)
    return texte


def _elements_de(texte: str, sans_dates: bool = False) -> list[tuple[str, str, str]]:
    """(genre, valeur normalisée, texte d'origine), dans l'ordre : identifiants, dates, heures, nombres."""
    trouves: list[tuple[str, str, str]] = []
    reste = texte
    for m in _IDENTIFIANT.finditer(reste):
        trouves.append(("identifiant", m.group(0), m.group(0)))
    reste = _IDENTIFIANT.sub(" ", reste)
    if not sans_dates:
        for m in _DATE_ISO.finditer(reste):
            trouves.append(("date", m.group(0)[:10], m.group(0)[:10]))
        reste = re.sub(r"\d{4}-\d{2}-\d{2}(?:T[\d:+\-]+)?", " ", reste)
        for m in _DATE_TEXTE.finditer(reste):
            jour, mois, annee = int(m.group(1)), MOIS[m.group(2).casefold()], int(m.group(3) or ANNEE_PAR_DEFAUT)
            trouves.append(("date", f"{annee:04d}-{mois:02d}-{jour:02d}", m.group(0)))
        reste = _DATE_TEXTE.sub(" ", reste)
        for m in _DATE_NUM.finditer(reste):
            trouves.append(("date", f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}", m.group(0)))
        reste = _DATE_NUM.sub(" ", reste)
    for m in _HEURE.finditer(reste):
        h = int(m.group(1))
        if h > 24:
            continue
        minutes = m.group(2) or m.group(3) or "00"
        trouves.append(("heure", f"{h:02d}:{minutes}", m.group(0).strip()))
    reste = _HEURE.sub(lambda m: " " if int(m.group(1)) <= 24 else m.group(0), reste)
    for m in _NOMBRE.finditer(reste):
        trouves.append(("nombre", str(_cle(nombre(m.group(1)))), m.group(1)))
    return trouves


def verifier_note(note: str, trace, question: str = "") -> list[Element]:
    index = _Index(trace)
    deja = {(g, v) for g, v, _ in _elements_de(question)}
    elements: list[Element] = []
    vus: set[tuple[str, str]] = set()
    note_sans_etapes = _ETAPE.sub(" ", note)
    for nom in noms_connus():
        if nom.casefold() in note_sans_etapes.casefold() and nom.casefold() not in question.casefold():
            elements.append(Element(nom, "nom", index.cherche_texte(nom)))
            note_sans_etapes = re.sub(re.escape(nom), " ", note_sans_etapes, flags=re.IGNORECASE)
    for genre, valeur, texte in _elements_de(note_sans_etapes):
        if (genre, valeur) in deja or (genre, valeur) in vus:
            continue
        vus.add((genre, valeur))
        if genre == "identifiant":
            origine = index.cherche_texte(valeur)
        elif genre == "date":
            origine = index.dates.get(valeur)
        elif genre == "heure":
            origine = index.heures.get(valeur) or index.nombres.get(_cle(float(valeur[:2]))) \
                if valeur.endswith(":00") else index.heures.get(valeur)
        else:
            cible = float(valeur)
            if cible in (0, 1):
                continue
            origine = index.nombres.get(cible) or index.calcul(cible)
        elements.append(Element(texte, genre, origine))
    return elements


def sans_origine(elements: list[Element]) -> list[Element]:
    return [e for e in elements if e.origine is None]


def formater(elements: list[Element]) -> str:
    if not elements:
        return "Aucun chiffre, aucune date ni aucun nom connu dans la note : rien à vérifier."
    largeur = max(len(e.texte) for e in elements)
    lignes = [f"  {'✅' if e.origine else '❌'} {e.texte:<{largeur}}  {e.genre:<11} "
              f"{e.origine or 'SANS ORIGINE dans la trace'}" for e in elements]
    manquants = sans_origine(elements)
    lignes += ["", f"{len(elements)} élément(s) vérifié(s), {len(manquants)} sans origine."
               + ("" if not manquants else " Une donnée sans origine a été inventée, ou mal recopiée : la retrouver "
                  "dans la trace, ou la retirer de la note.")
               + " Les noms hors de la liste du kit ne sont pas vérifiés."]
    return "\n".join(lignes)


def lire_execution(chemin: Path) -> dict:
    """labs/lab13/execution.json : {"question", "plan", "reponse", "trace": [enregistrements]}."""
    return json.loads(chemin.read_text(encoding="utf-8"))
