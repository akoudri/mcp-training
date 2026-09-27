"""Vérificateur du LAB 10 — pharos-ops v0 : trois outils, clé invisible, normalisation, plafond, réponse partielle,
et le critère décisif (la note produite en mode panne, relue sur fichier).

Aucun appel au modèle. Le vérificateur charge VOTRE serveur (serveurs/pharos_ops/serveur.py) dans son propre
processus, avec sa propre clé météo, reconnaissable ; il bascule les interrupteurs des mocks le temps de chaque
contrôle, puis remet leur configuration. La note du critère décisif est produite par « make lab10-note-panne ».
"""

from __future__ import annotations

import asyncio
import contextlib
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
# lat*/lon* par préfixe (mais pas « longueur* », qui commence aussi par « lon »), coord*/unite* par préfixe,
# le reste par nom exact — sans quoi un binôme peut glisser un « latitude_deg » ou un « lat_quai » sans être vu.
INTERDITS = re.compile(r"^(?:(?:lat|latitude|lon|lng|longitude)(?:[_\W].*)?|coord.*|unite.*"
                       r"|fuseau|tz|timezone|cle|key|apikey|api_key)$")
JEUDI = {"debut": "2026-10-08T14:00", "fin": "2026-10-08T17:00"}
SEMAINE = {"quais": [3], "debut": "2026-10-05T00:00", "fin": "2026-10-07T23:00"}     # 72 heures, à Paris
SEMAINE_GMT = datetime(2026, 10, 4, 22, tzinfo=timezone.utc)                         # sa première heure, en GMT
MENTEURS = ("Macareux", "Glénan", "Molène")
EXEMPTS = {"quai", "nombre", "total"}
# suffixes d'unité acceptés (nombres à virgule seulement — un entier n'a pas à en porter un : quai, pages, niveau…)
UNITES = ("_kt", "_kn", "_m", "_km", "_nm", "_ms", "_mm", "_cm", "_h", "_min", "_s", "_pct", "_deg", "_hpa", "_c",
          "_eur", "_t", "_kg")
DELAI_TOUR_S = float(os.environ.get("PHAROS_DELAI_S", "20"))
LENTEUR_S = 8.0                     # make lab10-mocks LENTEUR=8s
CLE = f"verif-{secrets.token_hex(6)}"


def _cle_salle_par_defaut() -> str:
    """La clé météo de la salle, lue dans l'environnement (METEO_CLE) — avant que « _serveur » ne le remplace
    par la clé du vérificateur. Si le formateur surcharge METEO_CLE (.env), la détection d'une clé en dur doit
    viser cette valeur-là, pas une constante codée en dur qui ne correspondrait plus à rien."""
    return os.environ.get("METEO_CLE", "meteo-salle-2026")


CLE_SALLE = _cle_salle_par_defaut()                 # valeur par défaut de METEO_CLE (bloc « commun/base.yaml »)
# une vraie clé après « apikey= » (la nôtre, ou celle de la salle) — pas un masquage (***, …, <masqué>, xxx…)
APIKEY = re.compile(r"apikey=([^&\s\"'()<>]+)", re.IGNORECASE)

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


def _apikeys_reelles(texte: str) -> bool:
    """Vrai si « apikey= » est suivi d'une vraie clé (la nôtre, ou celle de la salle) — pas un masquage."""
    return any(v in (CLE, CLE_SALLE) for v in APIKEY.findall(texte))


@contextlib.contextmanager
def _mode(**reglages):
    """« lab10.mode » ne lève qu'à l'entrée du « with » : l'entourer ici pour rendre un Echec, pas une exception
    brute, si les mocks deviennent injoignables pendant le contrôle."""
    try:
        with lab10.mode(**reglages):
            yield
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
    """Tout fichier sous logs/ (pas seulement les *.jsonl) : une fuite peut passer par un fichier de logging."""
    return {f: f.stat().st_size for f in journal.dossier().rglob("*") if f.is_file()} \
        if journal.dossier().is_dir() else {}


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
    fuites, cles_en_dur = [], []
    for libelle, reglages in (("nominal", {}), ("PANNE=meteo", {"panne": "meteo"}), ("QUOTA=1", {"quota": 1})):
        with _mode(**reglages):
            for nom, arguments in appels:
                texte = _texte(await _appeler(ctx, nom, arguments))
                if CLE in texte:
                    fuites.append(f"{nom} ({libelle})")
                if _apikeys_reelles(texte):
                    cles_en_dur.append(f"{nom} ({libelle})")
    if fuites:
        raise Echec(f"la clé apparaît dans ce que rend : {', '.join(fuites)}. Le message d'une erreur HTTP porte l'URL "
                    "complète, clé comprise : ne jamais le renvoyer tel quel (bloc 17.1).")
    boucle = _boucle()

    def _executer_boucle():
        # « autorisation.en_tant_que » repose sur un ContextVar : la boucle ouvre sa propre session (son propre
        # fil, sa propre boucle asyncio, dans pharos_client.transport.Session), donc l'identité doit être posée
        # ICI, dans le fil que « asyncio.to_thread » démarre pour exécuter la boucle — pas autour de l'« await »,
        # sans quoi un serveur qui exige « autorisation.identite() » dans chaque outil verrait « Identité
        # inconnue » au lieu du message de panne attendu.
        with autorisation.en_tant_que("jeton-exploitation"):
            return boucle.executer("Question simulée du LAB 10.", url=_serveur(ctx))

    with _mode(panne="meteo"):
        try:
            with ModeleSimule([[appel("a1", "meteo_creneau", {"quais": [3], **JEUDI})], "Réponse simulée."]):
                _, trace = await asyncio.to_thread(_executer_boucle)
        except NotImplementedError as exc:
            raise Echec("la boucle du LAB 4 n'est pas écrite : ce lab part de etat/da3-fin (make depart LAB=10).") from exc
        except Exception as exc:
            if hasattr(exc, "trace"):    # ArretBoucle (BudgetDepasse, EchecNonRecuperable…) : rien à voir avec la clé
                raise Echec(f"la boucle du LAB 4 s'est arrêtée pendant le contrôle : "
                            f"{exc.__class__.__name__}: {exc}") from exc
            raise
    trace_texte = " ".join(f"{e.arguments} {getattr(e, 'resultat', '')}" for e in trace)
    if CLE in trace_texte:
        raise Echec("la clé apparaît dans la trace de la boucle (résultat de meteo_creneau, météo en panne).")
    if _apikeys_reelles(trace_texte):
        cles_en_dur.append("trace de la boucle")
    nouveau = _nouveau(avant)
    if CLE in nouveau:
        raise Echec("la clé apparaît dans logs/ : le journal reçoit l'erreur brute — n'y consigner qu'un résumé "
                    "sans l'URL (journal.consigner_erreur d'une erreur que vous avez nettoyée).")
    if _apikeys_reelles(nouveau):
        cles_en_dur.append("logs/")
    if cles_en_dur:
        raise Echec(f"une vraie clé (pas un masquage) apparaît après « apikey= » dans : {', '.join(cles_en_dur)} — "
                    "une clé qui n'est pas celle de l'environnement (une clé en dur ?) fuite dans l'URL. Lire "
                    "METEO_CLE depuis l'environnement.")
    return "nominal, PANNE=meteo, QUOTA=1 : résultats, erreurs, trace de la boucle et journaux sans la clé ni « apikey= »"


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


def _absence(dictionnaire: dict, prefixe: str, *, sous_chaine: bool = False) -> str:
    """Comment une valeur manquante est rendue : 'absent', 'null', 'zéro', ou la valeur rendue.

    « sous_chaine » : cherche le repère n'importe où dans le nom du champ (utile pour la visibilité,
    dont le nom peut ne pas commencer par « visib », ex. « distance_visib_km » n'a pas de préfixe fixe)."""
    if sous_chaine:
        cles = [k for k in dictionnaire if prefixe in k.casefold()]
    else:
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


MARQUEURS_PREVISION = ("vent", "houle", "rafale", "visib")


def _ligne_prevision(d: dict) -> bool:
    """Une ligne de prévision : un dict-feuille (aucune valeur imbriquée — exclut l'enveloppe de meteo_creneau,
    qui porte resultats/incomplets, et le { quai, previsions } par quai, qui porte une liste), avec une valeur
    date-heure (n'importe quel nom de champ : « heure » n'est imposé par aucun brief) et au moins un champ météo
    reconnaissable (vent/houle/rafale/visib, contre un simple dict scalaire sans rapport, ex. un résumé quai/dates)."""
    if any(isinstance(w, (dict, list)) for w in d.values()):
        return False
    if not any(isinstance(w, str) and DATE_HEURE.match(w) for w in d.values()):
        return False
    return any(m in k.casefold() for k in d for m in MARQUEURS_PREVISION)


@v.critere("Normalisation : unités dans les noms, dates avec fuseau, une seule règle pour les absences.")
async def _(ctx):
    # I1 : ce critère joue toujours en mode nominal, quel que soit l'interrupteur laissé actif par le brief
    # (PANNE=meteo, QUOTA, LENTEUR…) — sans quoi un serveur juste échoue ici avec un message qui parle du
    # plafond au lieu de l'interrupteur resté actif.
    with _mode():
        rendus = {"meteo_creneau": await _appeler(ctx, "meteo_creneau", SEMAINE),
                  "meteo_alerte": await _appeler(ctx, "meteo_alerte", {"quai": 3, "horizon_h": 72}),
                  "navire_par_nom": await _appeler(ctx, "navire_par_nom", {"nom": "Vent d'Autan"})}
        for nom in MENTEURS:
            rendus[nom] = await _appeler(ctx, "navire_par_nom", {"nom": nom})
    erreurs = [f"{n} : {_texte(r)[:150]}" for n, r in rendus.items() if r.is_error or _json(r) is None]
    if erreurs:
        raise Echec("appels nominaux en échec, ou résultat qui n'est pas du JSON (le vérificateur fait une dizaine "
                    "d'appels par outil en moins d'une minute, dont un créneau de 72 h : un plafond plus strict "
                    "échoue ici) : " + " ; ".join(erreurs))
    sans_unite, sans_fuseau = set(), set()
    for r in rendus.values():
        for chemin, cle, valeur in _feuilles(_json(r)):
            if isinstance(valeur, float) and cle not in EXEMPTS and not cle.endswith("_id") \
                    and not cle.endswith(UNITES):
                sans_unite.add(cle)
            if isinstance(valeur, str) and DATE_HEURE.match(valeur):
                try:
                    lue = datetime.fromisoformat(valeur)
                except ValueError:
                    lue = None
                if lue is None or lue.tzinfo is None:
                    sans_fuseau.add(f"{cle} = {valeur}")
    if sans_unite:
        raise Echec(f"champs numériques à virgule sans unité reconnue dans le nom : {', '.join(sorted(sans_unite))} "
                    f"— suffixes acceptés : {', '.join(UNITES)} (jamais l'unité dans la valeur, bloc 16.2).")
    if sans_fuseau:
        raise Echec(f"dates sans fuseau : {', '.join(sorted(sans_fuseau)[:3])} — ISO 8601 avec décalage "
                    "(2026-10-08T14:00+02:00). Le référentiel rend l'heure locale sans fuseau, la météo l'heure GMT.")

    def _avec_decalage(valeur) -> bool:
        if not isinstance(valeur, str) or not DATE_HEURE.match(valeur):
            return False
        try:
            return datetime.fromisoformat(valeur).tzinfo is not None
        except ValueError:
            return False

    # M2 : navire_par_nom doit rendre les escales connues (§16, LAB 13 étape 3 ; LAB 10 ext. C) — un binôme qui
    # les retire pour éviter le contrôle des fuseaux ne doit pas passer ✅.
    fiche_vent = _fiche(rendus["navire_par_nom"], "Vent d'Autan")
    escale_0412 = next((e for e in (fiche_vent or {}).get("escales") or []
                        if isinstance(e, dict) and e.get("escale_id") == "ESC-2026-0412"), None)
    dates_escale = [e for c, e in (escale_0412 or {}).items() if c in ("debut", "fin") and e is not None]
    if not escale_0412 or not dates_escale or not all(_avec_decalage(d) for d in dates_escale):
        raise Echec("navire_par_nom (« Vent d'Autan ») ne rend pas l'escale connue ESC-2026-0412, avec une "
                    "date-heure et son décalage : navire_par_nom doit rendre les escales (le LAB 13 en a besoin).")
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
    # une ligne de prévision (voir _ligne_prevision) : ni le nom du champ d'horodatage ni celui du vent ne sont
    # imposés — seule l'enveloppe de meteo_creneau (resultats/incomplets/complet) est exclue, par sa forme.
    lignes = [d for d in _dictionnaires(_json(rendus["meteo_creneau"])) if _ligne_prevision(d)]
    if not lignes:
        # I3 : la spec et le brief laissent la forme de meteo_creneau ouverte — un serveur qui rend des
        # conditions agrégées (pas une ligne par heure) ne transforme aucune absence en zéro pour autant.
        # Sans ligne horaire à inspecter, ne pas accuser « une absence est devenue un nombre » : le dire à
        # constater (👁), pas en échec.
        return ("👁 aucune ligne de prévision horaire reconnue dans meteo_creneau (un objet par heure, avec son "
                "heure et vent/houle/visibilité) : la règle des absences côté météo n'a pas pu être contrôlée "
                "automatiquement — à relire à la main.")
    manquantes = [m for m in (_absence(d, "visib", sous_chaine=True) for d in lignes) if m not in ("nombre", "zéro")]
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
    reste = re.sub(r"429|too many requests|rate limit[^.]*|http|error|status|retry-after|retry|after|too|many"
                  r"|requests", "", texte, flags=re.IGNORECASE)
    if not re.search(r"[a-zà-ÿ]{4,}", reste, re.IGNORECASE):
        raise Echec(f"le refus se réduit au code du fournisseur : « {texte[:160]} ». Dire ce qui se passe et quand "
                    "réessayer (bloc 17.2).")
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
    sans_quai = [i for i in incomplets if not isinstance(i, dict) or not isinstance(i.get("quai"), int)]
    if sans_quai:
        raise Echec(f"incomplets = {incomplets} : une entrée sans « quai » entier (ou pas un objet) — "
                    "attendu les quais 5 et 7, chacun avec sa raison.")
    quais = sorted(i["quai"] for i in incomplets)
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
    # I2 : preuve de la panne météo, dans la trace — soit un appel en erreur (Erreur = oui), soit une réponse
    # partielle vide (tous les quais tombent : resultats vides, complet: false), suite logique de l'étape 4 sans
    # isError. « make lab10-note-panne » est la seule cible qui écrit ce fichier, toujours sous panne=meteo.
    lignes_meteo = [l for l in trace.splitlines() if l.strip().startswith("|") and re.search(r"meteo_(creneau|alerte)", l)]
    en_panne = any(re.search(r"\|\s*oui\s*\|", l) or re.search(r'"?complet"?\s*:\s*false', l, re.IGNORECASE)
                  for l in lignes_meteo)
    if not en_panne:
        raise Echec("la trace de la note ne montre aucun appel météo en erreur (ni une réponse partielle avec "
                    "complet: false) : la note n'a pas été produite en mode panne. Relancer « make lab10-note-panne ».")
    if not re.search(r"(?:non[\s-]+|pas\s+(?:(?:pu\s+)?être\s+|été\s+)?)évalué|indisponible", note, re.IGNORECASE):
        raise Echec("la note ne dit pas que la météo est non évaluée (ou indisponible) : le message de panne doit "
                    "dire ce qu'il ne faut pas conclure (bloc 17.3). Corriger, puis relancer make lab10-note-panne.")
    # houle : ne pas franchir un « . », « ; », « : », « ( », « ) », un saut de ligne, ou une virgule suivie d'une
    # espace (une virgule décimale, ex. « 13,2 », n'a pas d'espace derrière et reste dans la fenêtre puisqu'elle
    # n'apparaît que dans le groupe du nombre lui-même, jamais dans cette fenêtre qui le précède) — une clause qui
    # écarte la météo juste avant de citer le tirant d'eau (donnée réelle) ne doit pas être lue comme une houle
    # inventée ; lookahead plutôt que \b après « m » pour couvrir « mètres » (è n'est pas un caractère de mot ASCII).
    inventees = re.findall(r"\d+(?:[.,]\d+)?\s*(?:kt|kts|kn|nœuds?|noeuds?)\b"
                           r"|\d+(?:[.,]\d+)?\s*m(?:ètres?)?\s+de\s+houle"
                           r"|houle(?:(?!\.|;|:|\(|\)|\n|,\s)[\s\S]){0,30}?\d+(?:[.,]\d+)?\s*m(?:ètres?)?"
                           r"(?![a-zà-ÿ])", note, re.IGNORECASE)
    if inventees:
        raise Echec(f"la note donne une météo alors que le service était en panne : {', '.join(inventees)}. "
                    "C'est l'invention que le message de panne doit empêcher.")
    return "Relire la note entière (👁) : ce qu'elle conclut, et ce qu'elle refuse de conclure."
