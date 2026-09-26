"""Vérificateur du LAB 5 — handles d'état, à travers le répartiteur à deux instances."""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from outils.client_test import ClientTest
from outils.verifier.commun import Echec, Verification
from pharos_docs import jetons

URL = "http://observateur:8201/mcp"
ESCALE, AUTRE = "ESC-2026-0412", "ESC-2026-0405"
RACINE = Path(__file__).resolve().parents[2]

v = Verification("LAB 5 — Handles d'état", URL, "make lab5-deux-instances")


def _texte(r) -> str:
    return "\n".join(getattr(b, "text", "") or "" for b in r.content)


def _donnees(r) -> dict:
    if isinstance(r.data, dict):
        return r.data
    try:
        return json.loads(_texte(r))
    except ValueError as exc:
        raise Echec(f"résultat non structuré : « {_texte(r)[:160]} » (rendre un dict, bloc 9.5).") from exc


def _cle() -> str:
    cle = os.environ.get("CLE_SERVEUR")
    if not cle:
        raise Echec("CLE_SERVEUR absente de l'environnement du vérificateur (compose.yaml, service atelier).")
    return cle


async def _ouvrir(c: ClientTest, escale: str) -> dict:
    if "ouvrir_dossier" not in {o.name for o in await c.outils()}:
        raise Echec("outil ouvrir_dossier absent du catalogue.")
    r = await c.appeler("ouvrir_dossier", {"escale_id": escale})
    if r.is_error:
        raise Echec(f"ouvrir_dossier({escale}) a échoué : « {_texte(r)[:200]} »")
    d = _donnees(r)
    if not str(d.get("handle", "")).startswith(jetons.PREFIXE):
        raise Echec("ouvrir_dossier doit rendre un champ « handle » produit par pharos_docs.jetons.signer (hdl_…).")
    sections = d.get("sections")
    if not sections or not all({"id", "titre", "pages"} <= set(s) for s in sections):
        raise Echec("ouvrir_dossier doit rendre « sections » : [{\"id\", \"titre\", \"pages\"}] (forme imposée, charge.md).")
    return d


def _section(d: dict, mot: str = "pénalités") -> dict:
    s = next((s for s in d["sections"] if mot in s["titre"].casefold()), None)
    if s is None:
        raise Echec(f"aucune section dont le titre contient « {mot} » dans {d.get('document_id', '?')}.")
    return s


def _alterer(jeton: str) -> str:
    i = len(jeton) - 3
    return jeton[:i] + ("A" if jeton[i] != "A" else "B") + jeton[i + 1:]


def _charge_sans_exp(jeton: str) -> dict:
    try:
        return {k: w for k, w in jetons.lire_charge(jeton).items() if k != "exp"}
    except jetons.JetonInvalide as exc:
        raise Echec("le handle n'a pas le format de pharos_docs.jetons (utiliser signer()).") from exc


def _refus_utile(r) -> str | None:
    t = _texte(r)
    if not r.is_error:
        return "accepté (isError attendu)"
    if t.startswith("Error calling tool") or "Traceback" in t:
        return "exception non rattrapée (lever ToolError)"
    if "ouvrir_dossier" not in t and "rouvr" not in t.casefold():
        return f"le message ne dit pas quoi faire (rouvrir le dossier) : « {t[:120]} »"
    return None


@v.constat("labs/lab5/charge.md est rempli, et la liste des champs exclus est justifiée.")
def _(ctx):
    return "Relire labs/lab5/charge.md : les trois exclusions (navire, texte de section, identité) sont-elles argumentées ?"


@v.critere("ouvrir_dossier rend un handle ; lire_section le consomme et en rend un nouveau.")
async def _(ctx):
    async with ClientTest(ctx.url) as c:
        d = await _ouvrir(c, ESCALE)
        section = _section(d)
        r = await c.appeler("lire_section", {"handle": d["handle"], "section": section["id"]})
    if r.is_error:
        raise Echec(f"lire_section a refusé un handle frais : « {_texte(r)[:200]} »")
    lu = _donnees(r)
    if not str(lu.get("handle", "")).startswith(jetons.PREFIXE) or "section" not in lu:
        raise Echec("lire_section doit rendre « section » et un nouveau « handle ».")
    ctx.cache["ouvert"] = d


@v.critere("Le handle ne contient ni donnée métier, ni donnée personnelle.")
async def _(ctx):
    d = ctx.cache.get("ouvert")
    if d is None:
        async with ClientTest(ctx.url) as c:
            d = await _ouvrir(c, ESCALE)
    handle = d["handle"]
    charge = _charge_sans_exp(handle)
    escales = yaml.safe_load((RACINE / "donnees" / "corpus" / "escales.yaml").read_text(encoding="utf-8"))["escales"]
    interdits = {str(e[k]) for e in escales for k in ("navire", "armateur", "agent", "imo") if e.get(k)}
    problemes = [f"« {x} » est dans la charge" for x in sorted(interdits) if x in json.dumps(charge, ensure_ascii=False)]
    problemes += [f"le champ {k} fait {len(w)} caractères : un texte n'a rien à faire dans la charge"
                  for k, w in charge.items() if isinstance(w, str) and len(w) > 64]
    if len(handle) >= 200:
        problemes.append(f"handle de {len(handle)} caractères : le modèle le recopie à chaque tour, le garder court")
    if problemes:
        raise Echec("\n".join(problemes))
    return f"charge : {json.dumps(charge, ensure_ascii=False)} ({len(handle)} caractères)"


@v.critere("Les trois refus produisent une erreur métier dont le modèle sait quoi faire.")
async def _(ctx):
    cle = _cle()
    async with ClientTest(ctx.url) as c:
        d = await _ouvrir(c, ESCALE)
        autre = await _ouvrir(c, AUTRE)
        section = _section(d)["id"]
        charge = _charge_sans_exp(d["handle"])
        cas = {
            "handle altéré d'un caractère": (_alterer(d["handle"]), section),
            "handle forgé avec une autre clé": (jetons.signer(charge, "une-autre-cle"), section),
            "handle expiré": (jetons.signer(charge, cle, duree_s=-60), section),
            f"handle de {ESCALE} sur une section de {AUTRE}": (d["handle"], _section(autre)["id"]),
        }
        problemes = []
        for nom, (handle, sec) in cas.items():
            defaut = _refus_utile(await c.appeler("lire_section", {"handle": handle, "section": sec}))
            if defaut:
                problemes.append(f"{nom} : {defaut}")
    if problemes:
        raise Echec("\n".join(problemes))


@v.constat("Le contexte final après reformatage est mesuré et consigné.")
def _(ctx):
    return "Compléter labs/lab5/mesures.md (make lab4-question QUESTION=\"…\" URL=http://observateur:8201/mcp)."


@v.critere("Critère décisif — deux requêtes portant le même handle, atterrissant sur deux instances différentes, "
           "se comportent identiquement ; et un handle altéré d'un seul caractère est refusé.")
async def _(ctx):
    async with ClientTest(ctx.url) as c:
        d = await _ouvrir(c, ESCALE)
        section = _section(d, "délais")["id"]
        r1 = await c.appeler("lire_section", {"handle": d["handle"], "section": section})
        r2 = await c.appeler("lire_section", {"handle": d["handle"], "section": section})
        altere = await c.appeler("lire_section", {"handle": _alterer(d["handle"]), "section": section})
        instances = c.instances()[-3:-1]
    if "?" in instances:
        raise Echec("pas d'en-tête X-Pharos-Instance : passer par le répartiteur (make lab5-deux-instances, port 8201).")
    if instances[0] == instances[1]:
        raise Echec(f"les deux lectures ont atterri sur la même instance ({instances[0]}).")
    if r1.is_error or r2.is_error or _donnees(r1).get("section") != _donnees(r2).get("section"):
        raise Echec(f"lectures différentes selon l'instance ({instances[0]} puis {instances[1]}) : un état vit en mémoire ?")
    if not altere.is_error:
        raise Echec("un handle altéré d'un caractère a été accepté.")
    return f"lectures servies par les instances {instances[0]} puis {instances[1]}, identiques"


@v.critere("Aucun outil verifier_handle n'est exposé (piège du brief).")
async def _(ctx):
    async with ClientTest(ctx.url) as c:
        noms = {o.name for o in await c.outils()}
    if any("verifier" in n and "handle" in n for n in noms):
        raise Echec("un outil de vérification de handle offre un oracle gratuit à un attaquant : le retirer.")
