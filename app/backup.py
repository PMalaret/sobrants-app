"""Còpies de seguretat automàtiques (equivalent a CrearBackup/IniciarBackupAutomatic).

A l'Excel original es desava una còpia del llibre cada 4 hores en una
carpeta "Backups" al costat del fitxer, conservant només les 10 més
recents. Aquí es replica igual mitjançant una còpia del fitxer SQLite.
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
