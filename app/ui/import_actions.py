"""Importar dades: des d'un Excel o des d'una base de dades de l'aplicació.

Les dues viuen aquí perquè es fan servir des de dos llocs (el primer
arrencada, quan encara no hi ha cap base de dades, i el menú "Importar" de
la finestra) i han de comportar-se exactament igual. Cap dels dos flux es
duplica: `main._ensure_database` i `MainWindow` criden aquestes funcions.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

from app.backup import create_backup
from app.data.db import IncompatibleDatabaseError, describe_database
from app.i18n import t
from app.ui import dialogs


def import_from_excel(parent: QWidget | None, db_path: Path) -> bool:
    """Importa un .xlsm/.xlsx a `db_path` (el mateix que feia el primer
    arrencada). True si s'hi han acabat portant dades."""
    excel_path, _ = QFileDialog.getOpenFileName(
        parent, t("startup.pick_excel"), str(Path.home()), "Excel (*.xlsm *.xlsx)"
    )
    if not excel_path:
        return False

    from app.migration.from_excel import migrate

    try:
        stats = migrate(excel_path, str(db_path))
    except Exception as exc:  # noqa: BLE001 - fitxer fet malbé, sense permisos...
        dialogs.error(parent, t("import.excel.error.title"), t("import.error.text", error=exc))
        return False
    dialogs.info(
        parent,
        t("startup.import_done.title"),
        t("startup.import_done.text") + "\n".join(f"  {k}: {v}" for k, v in stats.items()),
    )
    return True


def import_from_database(parent: QWidget | None, db_path: Path) -> bool:
    """Substitueix la base de dades actual per la d'un fitxer .db (el mateix
    format que deixen les còpies de seguretat).

    L'ordre importa, per no deixar mai les dades a mitges:
      1. es tria el fitxer i es VALIDA abans de tocar res (`describe_database`);
      2. es demana confirmació, dient què hi entrarà i que se substitueix tot;
      3. es fa una còpia de seguretat de l'actual amb la funció de sempre
         (`app.backup.create_backup`), que fa de xarxa;
      4. es copia el fitxer nou al seu lloc; si això peta, es torna a posar
         la còpia de seguretat i s'avisa.

    Qui la crida ha de tancar la connexió abans i tornar-la a obrir després
    (`MainWindow._reload_database`).
    """
    source, _ = QFileDialog.getOpenFileName(
        parent, t("import.db.pick"), str(Path.home()), "SQLite (*.db)"
    )
    if not source:
        return False
    source = Path(source)

    if source.resolve() == Path(db_path).resolve():
        dialogs.warn(parent, t("import.db.error.title"), t("import.db.same_file"))
        return False

    # 1. Validació: si no és una base de dades d'aquesta aplicació, s'atura
    #    aquí i no s'ha tocat res.
    try:
        counts = describe_database(source)
    except IncompatibleDatabaseError as exc:
        dialogs.error(parent, t("import.db.error.title"), t("import.db.invalid", detail=exc))
        return False

    # 2. Confirmació: substituir-ho tot no es pot desfer.
    summary = "\n".join(f"  {table}: {count}" for table, count in counts.items())
    if not dialogs.confirm(parent, t("import.db.confirm.title"), t("import.db.confirm.text", summary=summary)):
        return False

    # 3. Xarxa de seguretat amb la mateixa funció de còpies de sempre.
    safety_copy = None
    try:
        if Path(db_path).exists():
            safety_copy = create_backup(db_path)
    except OSError as exc:
        dialogs.error(parent, t("import.db.error.title"), t("import.error.text", error=exc))
        return False

    # 4. Substitució.
    try:
        shutil.copy2(source, db_path)
    except OSError as exc:
        if safety_copy is not None:
            try:
                shutil.copy2(safety_copy, db_path)   # es deixa com estava
            except OSError:
                pass
        dialogs.error(parent, t("import.db.error.title"), t("import.error.text", error=exc))
        return False

    dialogs.info(
        parent,
        t("import.db.done.title"),
        t("import.db.done.text", summary=summary, backup=safety_copy or "—"),
    )
    return True
