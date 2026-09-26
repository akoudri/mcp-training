"""Jetons signés (« handles ») de PHAROS — fournis : la cryptographie n'est pas la leçon.

Format : hdl_<charge>.<signature>, chacun en base64url sans « = ».
La charge est signée, pas chiffrée : qui décode le jeton la lit, personne ne la modifie sans
la clé. Elle ne doit donc contenir aucune donnée sensible (LAB 5).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json

from pharos import horloge

PREFIXE = "hdl_"


class JetonInvalide(Exception):
    """Le jeton ne peut pas être accepté."""


class JetonAltere(JetonInvalide):
    """Format, préfixe ou signature incorrects : jeton modifié, forgé ou tronqué."""


class JetonExpire(JetonInvalide):
    """La date d'expiration du jeton est dépassée."""


def _b64(octets: bytes) -> str:
    return base64.urlsafe_b64encode(octets).rstrip(b"=").decode()


def _deb64(texte: str) -> bytes:
    return base64.urlsafe_b64decode(texte + "=" * (-len(texte) % 4))


def _signature(charge_b64: str, cle: str) -> str:
    return _b64(hmac.new(cle.encode(), charge_b64.encode(), hashlib.sha256).digest()[:16])


def _maintenant() -> int:
    return int(horloge.maintenant().timestamp())


def signer(charge: dict, cle: str, duree_s: int = 900) -> str:
    """Signe la charge et y ajoute « exp » (maintenant + duree_s, en secondes)."""
    if "exp" in charge:
        raise ValueError("« exp » est réservé : signer() le calcule à partir de duree_s.")
    if not cle:
        raise ValueError("clé de signature vide : définir CLE_SERVEUR.")
    corps = json.dumps({**charge, "exp": _maintenant() + duree_s},
                       separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    charge_b64 = _b64(corps.encode())
    return f"{PREFIXE}{charge_b64}.{_signature(charge_b64, cle)}"


def _decouper(jeton: object) -> tuple[str, str]:
    if not isinstance(jeton, str):
        raise JetonAltere("le jeton n'est pas une chaîne")
    jeton = jeton.strip()
    if not jeton.startswith(PREFIXE) or jeton.count(".") != 1:
        raise JetonAltere("format de jeton inattendu")
    charge_b64, signature = jeton[len(PREFIXE):].split(".")
    if not charge_b64 or not signature:
        raise JetonAltere("format de jeton inattendu")
    return charge_b64, signature


def _decoder(charge_b64: str) -> dict:
    try:
        charge = json.loads(_deb64(charge_b64))
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise JetonAltere("charge illisible") from exc
    if not isinstance(charge, dict):
        raise JetonAltere("charge illisible")
    return charge


def verifier(jeton: str, cle: str) -> dict:
    """Vérifie signature puis expiration ; rend la charge sans « exp »."""
    charge_b64, signature = _decouper(jeton)
    if not hmac.compare_digest(signature, _signature(charge_b64, cle)):
        raise JetonAltere("signature invalide")
    charge = _decoder(charge_b64)
    exp = charge.pop("exp", None)
    if not isinstance(exp, int) or exp <= _maintenant():
        raise JetonExpire("jeton expiré")
    return charge


def lire_charge(jeton: str) -> dict:
    """Décode la charge SANS la vérifier (diagnostic et vérificateurs uniquement)."""
    return _decoder(_decouper(jeton)[0])
