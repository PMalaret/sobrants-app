"""Copias de seguridad automáticas (equivalente a CrearBackup/IniciarBackupAutomatic).

En el Excel original se guardaba una copia del libro cada 4 horas en una
carpeta "Backups" junto al fichero, conservando sólo las 10 más recientes.
Aquí se replica igual mediante una copia del fichero SQLite.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

KEEP_BACKUPS = 10


def create_backup(db_path: str | Path, backups_dir: str | Path | None = None) -> Path:
    db_path = Path(db_path)
    backups_dir = Path(backups_dir) if backups_dir else db_path.parent / "Backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backups_dir / f"Backup_{stamp}.db"
    shutil.copy2(db_path, dest)

    rotate_backups(backups_dir, keep=KEEP_BACKUPS)
    return dest


def rotate_backups(backups_dir: str | Path, keep: int = KEEP_BACKUPS) -> None:
    backups_dir = Path(backups_dir)
    files = sorted(backups_dir.glob("Backup_*.db"), key=lambda p: p.stat().st_mtime)
    excess = len(files) - keep
    for f in files[:max(excess, 0)]:
        f.unlink(missing_ok=True)
