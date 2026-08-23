"""Protecció simple per a accions administratives (de moment només "afegir
material nou" al catàleg). Una única contrasenya fixa n'hi ha prou per ara;
si en el futur cal alguna cosa més seriosa (usuaris, hash, etc.) només s'ha
de canviar `check_password` — la resta de l'app ja hi crida a través
d'aquesta funció, no compara la contrasenya directament enlloc.
"""
from __future__ import annotations

ADMIN_PASSWORD = "1234"


def check_password(value: str) -> bool:
    return value == ADMIN_PASSWORD
