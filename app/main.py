"""Punt d'entrada de l'aplicació."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app import i18n
from app.data.db import connect
from app.i18n import t
from app.logic.repository import Repository
from app.ui import dialogs
from app.ui.import_actions import import_from_excel


def _data_dir() -> Path:
    """Carpeta on viu la base de dades: al costat de l'executable (portàtil)."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parents[1]
    data_dir = base / "SobrantsData"
    data_dir.mkdir(exist_ok=True)
    return data_dir


def _ensure_database(data_dir: Path) -> Path:
    db_path = data_dir / "sobrants.db"
    if db_path.exists():
        return db_path

    # La importació és exactament la mateixa que la del menú
    # "Importar → Importar d'Excel" (`app.ui.import_actions`), no una còpia.
    if dialogs.confirm(None, t("startup.title"), t("startup.text")):
        if import_from_excel(None, db_path):
            return db_path

    # Sense importació: crea una base de dades buida amb l'esquema
    connect(db_path).close()
    return db_path


def _app_icon() -> QIcon:
    """Icona de l'app: el logotip (RIOU. Vidresif, sobre fons blanc) per a
    mides grans, i el favicon (marca "R.") per a mides petites (barra de
    tasques, títol de finestra), on el logotip sencer no es llegiria."""
    assets_dir = Path(__file__).with_name("assets")
    icon = QIcon()
    favicon_path = assets_dir / "favicon.png"
    logo_path = assets_dir / "app_icon.png"
    if favicon_path.exists():
        icon.addFile(str(favicon_path))
    if logo_path.exists():
        icon.addFile(str(logo_path))
    return icon


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Sobrants")
    app.setWindowIcon(_app_icon())
    style_path = Path(__file__).with_name("ui") / "style.qss"
    if style_path.exists():
        app.setStyleSheet(style_path.read_text(encoding="utf-8"))

    data_dir = _data_dir()
    i18n.init_settings_path(data_dir)
    db_path = _ensure_database(data_dir)

    conn = connect(db_path)
    repo = Repository(conn)

    from app.ui.main_window import MainWindow

    window = MainWindow(repo, str(db_path))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
