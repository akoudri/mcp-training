"""Vérificateur du LAB 10 — pharos-ops v0 : trois outils, clé invisible, normalisation, plafond, réponse partielle,
et le critère décisif (la note produite en mode panne, relue sur fichier).

Aucun appel au modèle. Le vérificateur charge VOTRE serveur (serveurs/pharos_ops/serveur.py) dans son propre
processus, avec sa propre clé météo, reconnaissable ; il bascule les interrupteurs des mocks le temps de chaque
contrôle, puis remet leur configuration. La note du critère décisif est produite par « make lab10-note-panne ».
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import os
import re
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastmcp import Client

from outils import lab10
from outils.verifier.commun import Echec, Verification
from outils.verifier.modele_simule import ModeleSimule, appel
from pharos import autorisation, journal
from serveurs.mocks.app import prevision

URL = "http://observateur:8103/mcp"
RACINE = Path(__file__).resolve().parents[2]
NOTE = RACINE / "labs" / "lab10" / "note-panne.md"
OUTILS = ("meteo_creneau", "meteo_alerte", "navire_par_nom")
INTERDITS = re.compile(r"^(lat|latitude|lon|lng|longitude|coord.*|fuseau|tz|timezone|unite.*|cle|key|apikey|api_key)$")
JEUDI = {"debut": "2026-10-08T14:00", "fin": "2026-10-08T17:00"}
SEMAINE = {"quais": [3], "debut": "2026-10-05T00:00", "fin": "2026-10-07T23:00"}     # 72 heures, à Paris
SEMAINE_GMT = datetime(2026, 10, 4, 22, tzinfo=timezone.utc)                         # sa première heure, en GMT
MENTEURS = ("Macareux", "Glénan", "Molène")
EXEMPTS = {"quai", "nombre", "total"}
UNITES = ("_kt", "_m", "_km", "_nm", "_h", "_min", "_s", "_pct", "_deg", "_hpa", "_c", "_eur")
DELAI_TOUR_S = float(os.environ.get("PHAROS_DELAI_S", "20"))
LENTEUR_S = 8.0                     # make lab10-mocks LENTEUR=8s
CLE = f"verif-{secrets.token_hex(6)}"

v = Verification("LAB 10 — pharos-ops v0", URL, "make lab10-mocks puis make lab10-up")


def charger_serveur():
    """Le serveur du binôme, importé sous un nom propre au vérificateur, avec la clé du vérificateur."""
    chemin = RACINE / "serveurs" / "pharos_ops" / "serveur.py"
    if not chemin.exists():
        raise Echec("serveurs/pharos_ops/serveur.py absent : lancer « make depart LAB=10 ».")
    spec = importlib.util.spec_from_file_location("verification_lab10_serveur", chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise Echec(f"serveurs/pharos_ops/serveur.py ne se charge pas : {exc.__class__.__name__}: {exc}") from exc
    return module.mcp


def _serveur(ctx):
    if "mocks_injoignables" in ctx.cache:            # une seule attente, pas une par critère
        raise Echec(ctx.cache["mocks_injoignables"])
    if "mcp" not in ctx.cache:
        try:
            lab10.attendre(delai_s=5)
            lab10.ajouter_cle(CLE)
        except lab10.MocksInjoignables as exc:
            ctx.cache["mocks_injoignables"] = str(exc)
            raise Echec(str(exc)) from exc
        os.environ["METEO_CLE"] = CLE
        ctx.cache["mcp"] = charger_serveur()
    return ctx.cache["mcp"]


def _texte(resultat) -> str:
    texte = "\n".join(getattr(b, "text", "") or "" for b in resultat.content)
    if not texte and resultat.structured_content is not None:
        texte = json.dumps(resultat.structured_content, ensure_ascii=False)
    return texte


def _json(resultat):
    if resultat.structured_content is not None:
        return resultat.structured_content
    try:
        return json.loads(_texte(resultat))
    except ValueError:
        return None


async def _appeler(ctx, nom: str, arguments: dict):
    with autorisation.en_tant_que("jeton-exploitation"):
        async with Client(_serveur(ctx)) as c:
            return await c.call_tool(nom, arguments, raise_on_error=False)


def _mode(**reglages):
    try:
        return lab10.mode(**reglages)
    except lab10.MocksInjoignables as exc:
        raise Echec(str(exc)) from exc


@v.critere("Les trois outils du brief sont au catalogue : meteo_creneau, meteo_alerte, navire_par_nom.")
async def _(ctx):
    async with Client(_serveur(ctx)) as c:
        noms = {o.name for o in await c.list_tools()}
    manquants = [n for n in OUTILS if n not in noms]
    if manquants:
        raise Echec(f"{', '.join(manquants)} introuvable(s) (catalogue : {', '.join(sorted(noms)) or 'vide'}) : garder "
                    "les noms du brief — le plan du LAB 13 et la régression du LAB 15 les appellent ainsi.")


@v.critere("Trois outils, et aucun paramètre que le modèle devrait deviner (coordonnées, fuseau, unité, clé).")
async def _(ctx):
    async with Client(_serveur(ctx)) as c:
        outils = await c.list_tools()
    if len(outils) != 3:
        raise Echec(f"{len(outils)} outils ({', '.join(o.name for o in outils)}) : trois questions métier, trois outils "
                    "(bloc 16.1) — pas un outil par variable météo.")
    fautifs = [f"{o.name}({p})" for o in outils for p in (o.input_schema or {}).get("properties", {})
               if INTERDITS.match(p.casefold())]
    if fautifs:
        raise Echec(f"paramètres à retirer : {', '.join(fautifs)}. Le quai suffit : le serveur connaît sa position, "
                    "son fuseau et ses unités ; la clé est lue dans l'environnement.")


def _journaux() -> dict[Path, int]:
    return {f: f.stat().st_size for f in journal.dossier().glob("*.jsonl")} if journal.dossier().is_dir() else {}


def _nouveau(avant: dict[Path, int]) -> str:
    morceaux = []
    for f, taille in _journaux().items():
        with f.open("rb") as flux:
            flux.seek(avant.get(f, 0))
            morceaux.append(flux.read().decode("utf-8", "replace"))
    return "\n".join(morceaux)


def _boucle():
    try:
        return importlib.import_module("pharos_client.boucle")
    except ModuleNotFoundError as exc:
        raise Echec("pharos_client introuvable : ce lab part de etat/da3-fin (make depart LAB=10).") from exc


@v.critere("La clé n'apparaît ni en résultat, ni en message d'erreur, ni au journal, ni dans la trace de la boucle.")
async def _(ctx):
    avant = _journaux()
    appels = [("meteo_creneau", {"quais": [3], **JEUDI}), ("meteo_alerte", {"quai": 3, "horizon_h": 24}),
              ("navire_par_nom", {"nom": "Vent d'Autan"})]
    fuites = []
    for libelle, reglages in (("nominal", {}), ("PANNE=meteo", {"panne": "meteo"}), ("QUOTA=1", {"quota": 1})):
        with _mode(**reglages):
            for nom, arguments in appels:
                if CLE in _texte(await _appeler(ctx, nom, arguments)):
                    fuites.append(f"{nom} ({libelle})")
    if fuites:
        raise Echec(f"la clé apparaît dans ce que rend : {', '.join(fuites)}. Le message d'une erreur HTTP porte l'URL "
                    "complète, clé comprise : ne jamais le renvoyer tel quel (bloc 17.1).")
    boucle = _boucle()
    with _mode(panne="meteo"):
        try:
            with ModeleSimule([[appel("a1", "meteo_creneau", {"quais": [3], **JEUDI})], "Réponse simulée."]):
                _, trace = await asyncio.to_thread(boucle.executer, "Question simulée du LAB 10.", url=_serveur(ctx))
        except NotImplementedError as exc:
            raise Echec("la boucle du LAB 4 n'est pas écrite : ce lab part de etat/da3-fin (make depart LAB=10).") from exc
    if any(CLE in f"{e.arguments} {getattr(e, 'resultat', '')}" for e in trace):
        raise Echec("la clé apparaît dans la trace de la boucle (résultat de meteo_creneau, météo en panne).")
    if CLE in _nouveau(avant):
        raise Echec("la clé apparaît dans logs/ : le journal reçoit l'erreur brute — n'y consigner qu'un résumé "
                    "sans l'URL (journal.consigner_erreur d'une erreur que vous avez nettoyée).")
    return "nominal, PANNE=meteo, QUOTA=1 : résultats, erreurs, trace de la boucle et journaux sans la clé"


def _feuilles(valeur, chemin=""):
    """(chemin, clé, valeur) de chaque champ scalaire de dictionnaire, en profondeur."""
    if isinstance(valeur, dict):
        for k, w in valeur.items():
            if isinstance(w, (dict, list)):
                yield from _feuilles(w, f"{chemin}.{k}")
            else:
                yield f"{chemin}.{k}", k, w
    elif isinstance(valeur, list):
        for w in valeur:
            yield from _feuilles(w, chemin)


def _dictionnaires(valeur):
    if isinstance(valeur, dict):
        yield valeur
        for w in valeur.values():
            yield from _dictionnaires(w)
    elif isinstance(valeur, list):
        for w in valeur:
            yield from _dictionnaires(w)


DATE_HEURE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


def _absence(dictionnaire: dict, prefixe: str) -> str:
    """Comment une valeur manquante est rendue : 'absent', 'null', 'zéro', ou la valeur rendue."""
    cles = [k for k in dictionnaire if k.casefold().startswith(prefixe)]
    if not cles:
        return "absent"
    valeur = dictionnaire[cles[0]]
    if valeur is None:
        return "null"
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return "zéro" if valeur == 0 else "nombre"
    return f"« {valeur} »"


def _fiche(resultat, nom: str) -> dict | None:
    return next((d for d in _dictionnaires(_json(resultat)) if d.get("nom") == nom), None)


@v.critere("Normalisation : unités dans les noms, dates avec fuseau, une seule règle pour les absences.")
async def _(ctx):
    rendus = {"meteo_creneau": await _appeler(ctx, "meteo_creneau", SEMAINE),
              "meteo_alerte": await _appeler(ctx, "meteo_alerte", {"quai": 3, "horizon_h": 72}),
              "navire_par_nom": await _appeler(ctx, "navire_par_nom", {"nom": "Vent d'Autan"})}
    for nom in MENTEURS:
        rendus[nom] = await _appeler(ctx, "navire_par_nom", {"nom": nom})
    erreurs = [f"{n} : {_texte(r)[:150]}" for n, r in rendus.items() if r.is_error or _json(r) is None]
    if erreurs:
        raise Echec("appels nominaux en échec, ou résultat qui n'est pas du JSON : " + " ; ".join(erreurs))
    sans_unite, sans_fuseau = set(), set()
    for r in rendus.values():
        for chemin, cle, valeur in _feuilles(_json(r)):
            if isinstance(valeur, (int, float)) and not isinstance(valeur, bool) \
                    and cle not in EXEMPTS and not cle.endswith("_id") and not cle.endswith(UNITES):
                sans_unite.add(cle)
            if isinstance(valeur, str) and DATE_HEURE.match(valeur):
                try:
                    lue = datetime.fromisoformat(valeur)
                except ValueError:
                    lue = None
                if lue is None or lue.tzinfo is None:
                    sans_fuseau.add(f"{cle} = {valeur}")
    if sans_unite:
        raise Echec(f"champs numériques sans unité dans le nom : {', '.join(sorted(sans_unite))} "
                    "(vent_kt, houle_m, visibilite_km… — jamais l'unité dans la valeur, bloc 16.2).")
    if sans_fuseau:
        raise Echec(f"dates sans fuseau : {', '.join(sorted(sans_fuseau)[:3])} — ISO 8601 avec décalage "
                    "(2026-10-08T14:00+02:00). Le référentiel rend l'heure locale sans fuseau, la météo l'heure GMT.")
    fiches = {nom: _fiche(rendus[nom], nom) for nom in MENTEURS}
    if not all(fiches.values()):
        raise Echec(f"navire_par_nom ne rend pas la fiche de {', '.join(n for n, f in fiches.items() if not f)}.")
    longueurs = {nom: _absence(f, "longueur") for nom, f in fiches.items()}
    if len(set(longueurs.values())) != 1 or set(longueurs.values()) & {"zéro", "nombre"}:
        raise Echec("longueur absente, null et 0 : les trois cas doivent être rendus de la même façon, et jamais "
                    "comme un nombre (" + ", ".join(f"{n} → {r}" for n, r in longueurs.items()) + ").")
    regle = longueurs["Macareux"]
    tirant = _absence(fiches["Molène"], "tirant")
    if tirant != regle:
        raise Echec(f"tirant d'eau maximal à 0 (Molène) rendu {tirant}, longueur absente rendue {regle} : "
                    "une seule règle pour les absences. Un zéro fausse tout calcul de tirant d'eau.")
    attendues = sum(prevision(3, SEMAINE_GMT + timedelta(hours=i))["visibility"] is None for i in range(72))
    lignes = [d for d in _dictionnaires(_json(rendus["meteo_creneau"])) if any(k.startswith("vent") for k in d)]
    manquantes = [m for m in (_absence(d, "visib") for d in lignes) if m not in ("nombre", "zéro")]
    if len(manquantes) < attendues:
        raise Echec(f"sur la semaine demandée, la météo omet la visibilité {attendues} fois, votre sortie "
                    f"{len(manquantes)} : une absence est devenue un nombre (souvent 0).")
    if set(manquantes) - {regle}:
        raise Echec(f"absences de la météo rendues {', '.join(sorted(set(manquantes)))}, celles du référentiel "
                    f"{regle} : une seule règle, sur les deux API.")
    return f"absences rendues {regle} sur les deux API"


@v.critere("Au-delà du quota, un refus en erreur métier, qui ne se réduit pas à « 429 ».")
async def _(ctx):
    with _mode(quota=1):
        await _appeler(ctx, "meteo_alerte", {"quai": 1, "horizon_h": 24})
        r = await _appeler(ctx, "meteo_alerte", {"quai": 2, "horizon_h": 24})
    texte = _texte(r)
    if not r.is_error:
        raise Echec("QUOTA=1 : le second appel n'est pas une erreur (isError). Au-delà du quota, rendre un refus.")
    reste = re.sub(r"429|too many requests|rate limit[^.]*|http", "", texte, flags=re.IGNORECASE)
    if len(re.findall(r"[a-zA-Zà-ÿ]", reste)) < 40:
        raise Echec(f"le refus se réduit au code du fournisseur : « {texte[:160]} ». Dire ce qui se passe, quand "
                    "réessayer, et comment consommer moins (bloc 17.2).")
    ctx.cache["refus_quota"] = texte
    return f"« {texte[:220]} »"


@v.constat("Le refus au quota indique comment consommer moins.")
def _(ctx):
    texte = ctx.cache.get("refus_quota")
    return f"Relire : « {texte} »" if texte else "Relire le refus obtenu avec make lab10-mocks QUOTA=5."


@v.critere("Réponse partielle : cinq quais, deux trop lents — trois résultats, incomplets, complet: false.")
async def _(ctx):
    with _mode(lenteur_s=LENTEUR_S, lenteur_quais=[5, 7]):
        debut = time.monotonic()
        r = await _appeler(ctx, "meteo_creneau", {"quais": [1, 3, 4, 5, 7], **JEUDI})
        duree = time.monotonic() - debut
    corps = _json(r)
    if r.is_error or not isinstance(corps, dict):
        raise Echec(f"meteo_creneau sur cinq quais, deux lents : erreur au lieu d'une réponse partielle — "
                    f"« {_texte(r)[:200]} »")
    if duree >= DELAI_TOUR_S:
        raise Echec(f"réponse en {duree:.0f} s : au-delà du budget de tour ({DELAI_TOUR_S:.0f} s), la boucle coupe "
                    "avant vous. Un délai par quai, et les quais en parallèle.")
    if corps.get("complet") is not False:
        raise Echec(f"complet vaut {corps.get('complet')!r} : il doit valoir false quand des quais manquent (bloc 17.3).")
    incomplets = corps.get("incomplets") or []
    quais = sorted(i.get("quai") for i in incomplets if isinstance(i, dict))
    if quais != [5, 7] or not all(str(i.get("raison") or "").strip() for i in incomplets):
        raise Echec(f"incomplets = {incomplets} : attendu les quais 5 et 7, chacun avec sa raison.")
    resultats = corps.get("resultats")
    if not isinstance(resultats, list) or len(resultats) != 3:
        raise Echec(f"resultats : {len(resultats) if isinstance(resultats, list) else resultats!r} au lieu des trois "
                    "quais qui ont répondu.")
    return f"réponse en {duree:.1f} s ; incomplets : {incomplets}"


@v.critere("Critère décisif — en panne, la note de l'agent signale la météo non évaluée, sans météo inventée.")
def _(ctx):
    if not NOTE.exists():
        raise Echec("labs/lab10/note-panne.md absent : lancer « make lab10-note-panne » (vrai modèle, météo en panne).")
    texte = NOTE.read_text(encoding="utf-8")
    note = texte.split("## Note de l'agent", 1)[-1].split("## Trace", 1)[0]
    trace = texte.split("## Trace", 1)[-1]
    if not re.search(r"\|\s*meteo_(creneau|alerte)\s*\|[^\n]*\|\s*oui\s*\|", trace):
        raise Echec("la trace de la note ne montre aucun appel météo en erreur : la note n'a pas été produite en "
                    "mode panne. Relancer « make lab10-note-panne ».")
    if not re.search(r"(non|pas)\s+(été\s+)?évalué|indisponible", note, re.IGNORECASE):
        raise Echec("la note ne dit pas que la météo est non évaluée (ou indisponible) : le message de panne doit "
                    "dire ce qu'il ne faut pas conclure (bloc 17.3). Corriger, puis relancer make lab10-note-panne.")
    inventees = re.findall(r"\d+(?:[.,]\d+)?\s*(?:kt|kts|nœuds?|noeuds?)\b|\d+(?:[.,]\d+)?\s*m(?:ètres?)?\s+de\s+houle"
                           r"|houle[^.\n]{0,30}?\d+(?:[.,]\d+)?\s*m\b", note, re.IGNORECASE)
    if inventees:
        raise Echec(f"la note donne une météo alors que le service était en panne : {', '.join(inventees)}. "
                    "C'est l'invention que le message de panne doit empêcher.")
    return "Relire la note entière (👁) : ce qu'elle conclut, et ce qu'elle refuse de conclure."
