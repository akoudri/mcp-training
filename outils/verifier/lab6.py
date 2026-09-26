"""Vérificateur du LAB 6 — réécriture de catalogue. Critères du brief, dans l'ordre.

N'appelle jamais le modèle : les deux mesures sont celles que le binôme a consignées avec
make lab6-mesurer ; le vérificateur les relit et les confronte au catalogue actuel.
"""

from __future__ import annotations

from pathlib import Path

from outils import banc
from outils.client_test import ClientTest
from outils.mesure_quai import (QUESTIONS as FICHIER_QUESTIONS, Mesure, SchemasModifies, charger_empreinte,
                                correspondance, empreinte_schemas, lire_mesure)
from outils.verifier.commun import Echec, Verification

URL = "http://observateur:8105/mcp"
RACINE = Path(__file__).resolve().parents[2]      # l'arbre du binôme (labs/lab6/) ; remplacé par les tests
QUESTIONS = 5
EXECUTIONS = 3
ANTI_PATRONS = ("texte libre en entrée", "identifiant que le modèle ne peut pas connaître",
                "erreur qui ne dit rien", "deux descriptions interchangeables",
                "description qui décrit l'implémentation", "outil qui renvoie un document entier")

v = Verification("LAB 6 — réécriture de catalogue", URL, "make lab6-quai")


def _chemin(nom: str) -> Path:
    return RACINE / "labs" / "lab6" / nom


def _mesure(ctx, nom: str) -> Mesure:
    if nom in ctx.cache:
        return ctx.cache[nom]
    chemin = _chemin(nom)
    if not chemin.is_file():
        raise Echec(f"labs/lab6/{nom} absent : lancer « make lab6-mesurer SORTIE=labs/lab6/{nom} ».")
    try:
        mesure = lire_mesure(chemin.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise Echec(f"labs/lab6/{nom} illisible ({exc}) : le régénérer avec « make lab6-mesurer SORTIE=labs/lab6/{nom} », "
                    "sans le retoucher à la main.") from None
    numeros = [l.numero for l in mesure.lignes]
    if numeros != list(range(1, QUESTIONS + 1)):
        raise Echec(f"labs/lab6/{nom} : {len(numeros)} question(s), les cinq du brief sont attendues.")
    incompletes = [l.numero for l in mesure.lignes if l.executions != EXECUTIONS]
    if incompletes:
        raise Echec(f"labs/lab6/{nom} : trois exécutions par question sont attendues "
                    f"(questions {', '.join(map(str, incompletes))}).")
    ctx.cache[nom] = mesure
    return mesure


async def _noms(ctx) -> dict[str, str]:
    """Nom d'origine → nom actuel. Echec si les schémas ou le nombre d'outils ont changé."""
    if "noms" not in ctx.cache:
        async with ClientTest(ctx.url) as c:
            actuels = empreinte_schemas(await c.outils())
        try:
            ctx.cache["noms"] = correspondance(actuels, charger_empreinte())
        except SchemasModifies as exc:
            raise Echec(str(exc)) from None
    return ctx.cache["noms"]


def _attendus(mesure: Mesure) -> list[str]:
    return [l.attendu for l in mesure.lignes]


def _origine() -> list[str]:
    return [q.attendu for q in banc.charger_questions(FICHIER_QUESTIONS)]


def _avant_valide(ctx) -> Mesure:
    """La mesure avant.md, si c'est bien une mesure initiale (sur le catalogue fourni, avant toute réécriture) ;
    sinon échec sans reprendre le diagnostic (déjà fait par le premier critère, en détail)."""
    avant = _mesure(ctx, "avant.md")
    if _attendus(avant) != _origine():
        raise Echec("avant.md n'est pas une mesure initiale valable : corriger d'abord le premier critère.")
    return avant


@v.critere("`avant.md` est consigné : cinq questions, trois exécutions chacune.")
def _(ctx):
    avant = _mesure(ctx, "avant.md")
    if _attendus(avant) != _origine():
        raise Echec("avant.md n'a pas été mesuré sur le catalogue fourni (les outils attendus portent déjà d'autres "
                    "noms) : la mesure initiale se fait avant toute réécriture. Pour le refaire : mettre la "
                    "réécriture de côté (« git stash »), relancer « make lab6-mesurer SORTIE=labs/lab6/avant.md », "
                    "puis « git stash pop » — ou « git checkout -- labs/lab6/avant.md » s'il avait été commité.")
    return f"{len(avant.reussies)}/{QUESTIONS} questions réussies avant réécriture (modèle {avant.modele})."


@v.constat("Chaque échec initial est rattaché à un anti-patron nommé du bloc 10.6.")
def _(ctx):
    try:
        avant = _mesure(ctx, "avant.md")
    except Echec:
        avant = None
    ratees: list[int] = []
    if avant:
        ratees = [l.numero for l in avant.lignes if l.numero not in avant.reussies]
    consigne = "Dans labs/lab6/diagnostic.md, une ligne par question ratée, avec l'un des six anti-patrons : " \
               + " ; ".join(ANTI_PATRONS) + "."
    return consigne + (f"\nQuestions ratées dans avant.md : {', '.join(map(str, ratees))}." if ratees else "")


@v.critere("La réécriture ne touche ni les schémas ni le nombre d'outils.")
async def _(ctx):
    noms = await _noms(ctx)
    renommes = [f"{a} → {n}" for a, n in noms.items() if a != n]
    return "Six outils, schémas d'origine. " + ("Renommés : " + ", ".join(renommes) if renommes else "Aucun outil renommé.")


@v.critere("`apres.md` est consigné, selon le même protocole.")
async def _(ctx):
    apres = _mesure(ctx, "apres.md")
    noms = await _noms(ctx)
    attendus = [noms[a] for a in _origine()]
    if _attendus(apres) != attendus:
        raise Echec("apres.md ne correspond pas au catalogue actuel (outils attendus : "
                    f"{', '.join(attendus)}) : relancer « make lab6-mesurer SORTIE=labs/lab6/apres.md » après la réécriture.")
    avant = ctx.cache.get("avant.md")
    if avant and avant.modele != apres.modele:
        raise Echec(f"avant.md et apres.md n'ont pas été mesurés avec le même modèle ({avant.modele}, {apres.modele}).")
    return f"{len(apres.reussies)}/{QUESTIONS} questions réussies après réécriture."


@v.critere("Critère décisif — le taux progresse d'au moins deux questions sur cinq.")
def _(ctx):
    avant, apres = _avant_valide(ctx), _mesure(ctx, "apres.md")
    gagnees = sorted(apres.reussies - avant.reussies)
    perdues = sorted(avant.reussies - apres.reussies)
    ecart = len(apres.reussies) - len(avant.reussies)
    detail = (f"{len(avant.reussies)}/5 → {len(apres.reussies)}/5 ; gagnées : {', '.join(map(str, gagnees)) or 'aucune'}"
              + (f" ; perdues : {', '.join(map(str, perdues))}" if perdues else ""))
    ctx.cache["gagnees"] = gagnees
    if ecart < 2:
        ratees_avant = QUESTIONS - len(avant.reussies)
        if len(apres.reussies) == QUESTIONS and ratees_avant <= 1:
            raise Echec(detail + f". 5/5 atteint : la mesure initiale n'a raté que {ratees_avant} question(s), "
                        "l'écart de deux est impossible sur ce passage (variance du modèle) — le signaler au "
                        "formateur, qui décide ; ne pas remesurer avant.md après la réécriture.")
        raise Echec(detail + ". Reprendre le diagnostic des questions encore ratées : l'élément « quand l'appeler » "
                    "(bloc 10.2) est le plus souvent absent.")
    return detail


@v.constat("… et chaque gain est attribué à une modification précise et nommée.")
def _(ctx):
    gagnees = ctx.cache.get("gagnees") or []
    return ("Dans labs/lab6/attribution.md, une ligne par question gagnée"
            + (f" ({', '.join(map(str, gagnees))})" if gagnees else "")
            + " : « +1 sur la question N, grâce à … ». Un gain non attribué est du bruit.")
