"""Preferències de l'aplicació, a `SobrantsData/settings.json`.

Un sol fitxer per a tot el que s'ha de recordar entre arrencades (idioma,
contrasenya, cada quantes hores es fa una còpia de seguretat). Cada
escriptura és llegir-modificar-desar: mai es rescriu el fitxer sencer amb
una sola clau, així dos ajustos diferents no s'esborren l'un a l'altre.

És el mateix fitxer que ja feia servir l'idioma (`app.i18n`), que ara hi
passa per aquí; qui l'inicialitza segueix sent `main` en arrencar.
"""
from __future__ import annotations

import json
from pathlib import Path

_path: Path | None = None


def init(data_dir: str | Path) -> None:
    """Crida's una vegada a l'arrencada amb la carpeta de dades de l'app."""
    global _path
    _path = Path(data_dir) / "settings.json"


def path() -> Path | None:
    return _path


def load() -> dict:
    """Tot el contingut del fitxer (diccionari buit si encara no existeix o
    si té alguna cosa que no es pot llegir: mai peta per un fitxer tocat)."""
    if _path is None or not _path.exists():
        return {}
    try:
        data = json.loads(_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def get(key: str, default=None):
    return load().get(key, default)


def set_value(key: str, value) -> None:
    if _path is None:
        return
    data = load()
    data[key] = value
    try:
        _path.parent.mkdir(parents=True, exist_ok=True)
        _path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass  # no poder desar una preferència no ha d'aturar l'aplicació
