"""Vérificateur du LAB 1 — pharos-docs v0. Critères du brief, dans l'ordre."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from outils import banc
from outils.client_test import ClientTest
from outils.verifier.commun import Echec, Verification

URL = "http://observateur:8101/mcp"
OUTILS = {"lister_documents", "rechercher_clause", "extraire_dates_contractuelles"}
SUJETS = {"penalites", "delais", "manutention", "assurance"}
RACINE = Path(__file__).resolve().parents[2]
QUESTIONS = RACINE / "outils" / "questions" / "lab1.yaml"
LIMITE = 4000
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]

v = Verification("LAB 1 — pharos-docs v0", URL, "make lab1-up")


def _texte(resultat) -> str:
    return "\n".join(getattr(b, "text", "") or "" for b in resultat.content)


def _non_rattrapee(texte: str) -> bool:
    return "Traceback" in texte or texte.startswith("Error calling tool")


def _normaliser_espaces(texte: str) -> str:
    """Un saut de ligne réel ou échappé (« \\n » littéral) devient un espace ; les espaces sont ramassés."""
    return re.sub(r"\s+", " ", texte.replace("\\n", " ").replace("\n", " ")).strip()


def _formes_date(d) -> list[str]:
    """Formes acceptées pour une date de contrat : ISO, « D mois AAAA » (« 1er » pour le 1er), JJ/MM/AAAA."""
    mois = MOIS[d.month - 1]
    formes = [d.isoformat(), f"{d.day} {mois} {d.year}", f"{d.day:02d}/{d.month:02d}/{d.year}"]
    if d.day == 1:
        formes.append(f"1er {mois} {d.year}")
    return formes


async def _outils(ctx) -> dict:
    if "outils" not in ctx.cache:
        async with ClientTest(ctx.url) as c:
            ctx.cache["outils"] = {o.name: o for o in await c.outils()}
    return ctx.cache["outils"]


async def _appeler(ctx, nom: str, arguments: dict):
    async with ClientTest(ctx.url) as c:
        return await c.appeler(nom, arguments)


def _propriete(schema: dict, nom: str) -> dict:
    """Propriété d'un schéma d'entrée, $ref résolu (un Enum Python produit un $ref vers $defs)."""
    prop = (schema or {}).get("properties", {}).get(nom, {})
    ref = prop.get("$ref") or next((x.get("$ref") for x in prop.get("allOf", []) if "$ref" in x), None)
    if ref:
        return {**schema.get("$defs", {}).get(ref.rsplit("/", 1)[-1], {}), **{k: w for k, w in prop.items() if k != "$ref"}}
    return prop


@v.critere("Les trois outils apparaissent dans tools/list, avec leurs schémas.")
async def _(ctx):
    outils = await _outils(ctx)
    noms = set(outils)
    if noms != OUTILS:
        lignes = [f"outils attendus, et rien d'autre : {', '.join(sorted(OUTILS))}"]
        if OUTILS - noms:
            lignes.append(f"manquants : {', '.join(sorted(OUTILS - noms))}")
        if noms - OUTILS:
            lignes.append(f"en trop : {', '.join(sorted(noms - OUTILS))}")
        raise Echec("\n".join(lignes))
    problemes = []
    for nom, o in sorted(outils.items()):
        if not (o.description or "").strip():
            problemes.append(f"{nom} : pas de description")
        description = _propriete(o.input_schema, "escale_id").get("description", "")
        if not description:
            problemes.append(f"{nom} : escale_id sans description (le modèle ne devinera pas ESC-AAAA-NNNN)")
        elif "ESC-" not in description:
            problemes.append(f"{nom} : la description de escale_id ne donne pas le format ESC-AAAA-NNNN")
    if problemes:
        raise Echec("\n".join(problemes))


@v.critere("sujet est une énumération ; une valeur hors énumération est refusée avant d'atteindre le code métier.")
async def _(ctx):
    outil = (await _outils(ctx)).get("rechercher_clause")
    if outil is None:
        raise Echec("rechercher_clause est absent.")
    sujet = _propriete(outil.input_schema, "sujet")
    if set(sujet.get("enum") or []) != SUJETS:
        raise Echec(f"sujet doit être une énumération de {', '.join(sorted(SUJETS))} "
                    f"(trouvé : {sujet.get('enum') or sujet.get('type', 'absent')}). Typer avec Literal[...].")
    r = await _appeler(ctx, "rechercher_clause", {"escale_id": "ESC-2026-0412", "sujet": "retards"})
    if not r.is_error or "validation" not in _texte(r).lower():
        raise Echec("sujet=\"retards\" doit être refusé par la validation du schéma, avant le code métier.")


@v.critere("Les trois erreurs métier disent quoi faire au tour suivant (étape 2).")
async def _(ctx):
    cas = [
        ({"escale_id": "ESC-2026-9999", "sujet": "penalites"}, "escale inconnue",
         lambda t: ("format" in t.lower() or "ESC-AAAA-NNNN" in t) and "lister_documents" in t,
         "le format attendu (ESC-AAAA-NNNN) et le nom de l'outil lister_documents"),
        ({"escale_id": "ESC-2026-0406", "sujet": "penalites"}, "aucun contrat (ESC-2026-0406)",
         lambda t: "BL-0406" in t or "AE-0406" in t or "connaissement" in t.lower() or "avis" in t.lower(),
         "ce qui existe à la place (connaissements BL-0406-…, avis d'escale AE-0406, ou juste le type de document)"),
        ({"escale_id": "ESC-2026-0408", "sujet": "assurance"}, "sujet absent (ESC-2026-0408, assurance)",
         lambda t: "penalites" in t.lower() or "pénalités" in t.lower(),
         "les sujets effectivement présents dans ce contrat"),
    ]
    problemes = []
    for arguments, nom, correct, attendu in cas:
        r = await _appeler(ctx, "rechercher_clause", arguments)
        t = _texte(r)
        if not r.is_error:
            problemes.append(f"{nom} : un résultat isError est attendu (raise ToolError), pas un succès")
        elif _non_rattrapee(t):
            problemes.append(f"{nom} : exception non rattrapée — lever ToolError avec un message métier")
        elif not correct(t):
            problemes.append(f"{nom} : le message doit contenir {attendu}. Reçu : « {t[:160]} »")
    if problemes:
        raise Echec("\n".join(problemes))


@v.critere("Les dates du contrat de ESC-2026-0412 sont justes : signature, prise d'effet, échéance.")
async def _(ctx):
    escales = yaml.safe_load((RACINE / "donnees" / "corpus" / "escales.yaml").read_text(encoding="utf-8"))["escales"]
    contrat = next(e for e in escales if e["escale_id"] == "ESC-2026-0412")["contrat"]
    r = await _appeler(ctx, "extraire_dates_contractuelles", {"escale_id": "ESC-2026-0412"})
    t = _normaliser_espaces(_texte(r))
    manquantes = []
    for champ in ("signature", "prise_effet", "echeance"):
        d = contrat[champ]
        if not any(forme in t for forme in _formes_date(d)):
            manquantes.append(f"{champ} ({d.isoformat()})")
    if r.is_error or manquantes:
        raise Echec(f"dates attendues absentes : {', '.join(manquantes) or '—'}. Reçu : « {t[:200]} »")


NOTE_Q4 = ("Question 4 consignée sans verdict : elle dépend du contexte de la question 3 (« ce contrat »), "
           "absent du protocole mono-tour du banc.")


@v.critere("Les questions 1, 3 et 4 déclenchent le bon outil sans reformulation humaine.", modele=True)
async def _(ctx):
    executions = await banc.executer_banc(ctx.url, banc.charger_questions(QUESTIONS), executions=1, executer=True)
    ctx.cache["banc"] = executions
    table = banc.formater(executions, "Premier appel des cinq questions")
    detail = f"{NOTE_Q4}\n{table}"
    ratees = [n for n in (1, 3) if not all(e.ok for e in executions if e.question.numero == n)]
    if ratees:
        raise Echec(f"questions ratées : {', '.join(map(str, ratees))}\n{detail}")
    return detail


@v.critere("La question 5 produit une erreur métier lisible : aucune trace de pile, aucun plantage du serveur.")
async def _(ctx):
    r = await _appeler(ctx, "rechercher_clause", {"escale_id": "ESC-2026-9999", "sujet": "penalites"})
    t = _texte(r)
    if not r.is_error:
        raise Echec("ESC-2026-9999 doit produire une erreur métier (isError).")
    if _non_rattrapee(t):
        raise Echec(f"exception non rattrapée : « {t[:160]} ». Lever ToolError avec un message métier.")
    async with ClientTest(ctx.url) as c:
        await c.outils()                                           # le serveur répond toujours
    return f"message renvoyé : « {t[:200]} »"


@v.constat("La question 5 : le modèle reformule ou propose une alternative.")
def _(ctx):
    return "Poser la question 5 dans VS Code (mode PHAROS) et noter dans labs/lab1/resultats.md ce que le modèle en fait."


@v.critere("Aucun outil ne renvoie le texte intégral d'un document.")
async def _(ctx):
    appels = [("lister_documents", {"escale_id": "ESC-2026-0412"}),
              ("extraire_dates_contractuelles", {"escale_id": "ESC-2026-0412"})]
    appels += [("rechercher_clause", {"escale_id": "ESC-2026-0412", "sujet": s}) for s in sorted(SUJETS)]
    trop = []
    for nom, arguments in appels:
        n = len(_texte(await _appeler(ctx, nom, arguments)))
        if n > LIMITE:
            trop.append(f"{nom} {arguments.get('sujet', '')} : {n} caractères")
    if trop:
        raise Echec(f"au-delà de {LIMITE} caractères, c'est un document, pas un extrait :\n" + "\n".join(trop))


@v.constat("Le résultat de la question 2 est consigné tel quel, y compris s'il est mauvais.")
def _(ctx):
    executions = ctx.cache.get("banc", [])
    vu2 = next((e for e in executions if e.question.numero == 2), None)
    vu4 = next((e for e in executions if e.question.numero == 4), None)
    consigne = "Consigner dans labs/lab1/resultats.md ce que le modèle a fait pour la question 2."
    if vu2 is None:
        return consigne
    detail = consigne + f"\nBanc : premier appel {vu2.outil or 'aucun'}({vu2.arguments})."
    if vu4 is not None:
        detail += f"\nBanc (Q4) : premier appel {vu4.outil or 'aucun'}({vu4.arguments})."
    return detail
