"""Contrasenyes de les accions protegides de l'aplicació.

N'hi ha DUES, independents (encara que totes dues comencin valent "1234"):

  - `ADMIN`  (contrasenya administrador) -> còpies de seguretat (fer-ne una
             ara, canviar cada quantes hores es fan soles) i netejar
             l'històric.
  - `WORKER` (contrasenya treballador)   -> afegir i esborrar materials.

Són coses diferents a posta: netejar l'històric és una feina
d'administració, no de treball diari, i per això va amb la d'administrador
i no amb la de materials.

Canviar-ne una no toca l'altra: es desen com a dues credencials separades.
Tota l'aplicació hi passa per `check_password(valor, scope)` i les canvia
amb `set_password(nova, scope)`; enlloc no es compara cap contrasenya
directament.

Com es desen: mai en clar. A `settings.json` hi va, per a cadascuna, un
PBKDF2-HMAC-SHA256 amb sal aleatòria (`hashlib`, biblioteca estàndard: cap
dependència nova), del qual no es pot recuperar la contrasenya. Mentre no
se n'hagi desat cap val la inicial `DEFAULT_PASSWORD` ("1234"), l'únic
valor en clar del codi i només com a punt de partida.
"""
from __future__ import annotations

import hashlib
import hmac
import os

from app import settings

# Contrasenya d'una instal·lació nova, mentre no se n'hagi desat cap.
DEFAULT_PASSWORD = "1234"

# Les dues contrasenyes (el valor és la clau amb què es desen).
ADMIN = "password_admin"
WORKER = "password_worker"
SCOPES = (ADMIN, WORKER)

# Claus de versions anteriors, perquè qui ja hagués canviat una contrasenya
# no la perdi: primer es mira la seva pròpia, després la que feia la mateixa
# feina abans i, si no n'hi ha cap, val la inicial. En canviar-la, es desa
# amb la clau nova.
_LEGACY_KEYS = {
    # abans: "password_backup" (còpies) i "password_materials" (materials
    # i netejar); i encara més enrere, "password" per a tot.
    ADMIN: ("password_backup", "password"),
    WORKER: ("password_materials", "password"),
}

# Cost del PBKDF2. Es desa amb el hash, així es pot apujar més endavant
# sense invalidar les contrasenyes ja guardades.
_ITERATIONS = 200_000
_SALT_BYTES = 16


def _derive(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, iterations)


def _stored(scope: str) -> dict | None:
    """El hash desat per a aquesta contrasenya, el de l'antiga clau única
    si encara no n'hi ha de pròpia, o None si val la inicial."""
    if scope not in SCOPES:
        raise ValueError(f"Contrasenya desconeguda: {scope}")
    value = settings.get(scope)
    if isinstance(value, dict):
        return value
    for legacy in _LEGACY_KEYS[scope]:
        value = settings.get(legacy)
        if isinstance(value, dict):
            return value
    return None


def is_default_password(scope: str) -> bool:
    """True mentre aquesta contrasenya encara sigui la inicial."""
    return _stored(scope) is None


def check_password(value: str, scope: str) -> bool:
    stored = _stored(scope)
    if stored is None:
        return hmac.compare_digest(value or "", DEFAULT_PASSWORD)
    try:
        salt = bytes.fromhex(stored["salt"])
        expected = bytes.fromhex(stored["hash"])
        iterations = int(stored["iterations"])
    except (KeyError, TypeError, ValueError):
        # Preferències tocades a mà o corruptes: es torna a la inicial en
        # lloc de deixar l'aplicació bloquejada per sempre.
        return hmac.compare_digest(value or "", DEFAULT_PASSWORD)
    return hmac.compare_digest(_derive(value, salt, iterations), expected)


def set_password(new_password: str, scope: str) -> None:
    """Desa una de les dues contrasenyes (només el hash), sense tocar
    l'altra. No hi ha cap requisit de forma: qualsevol text val."""
    if scope not in SCOPES:
        raise ValueError(f"Contrasenya desconeguda: {scope}")
    salt = os.urandom(_SALT_BYTES)
    settings.set_value(
        scope,
        {
            "salt": salt.hex(),
            "hash": _derive(new_password, salt, _ITERATIONS).hex(),
            "iterations": _ITERATIONS,
        },
    )
