"""Punto de entrada de la aplicación."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app.data.db import connect
from app.logic.repository import Repository


def _data_dir() -> Path:
    """Carpeta donde vive la base de datos: junto al ejecutable (portable)."""
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

    resp = QMessageBox.question(
        None,
        "Primer arranque",
        "No se ha encontrado ninguna base de datos todavía.\n\n"
        "¿Quieres importar los datos desde un archivo Excel "
        "(SobrantsV4.74.xlsm) existente?",
        QMessageBox.Yes | QMessageBox.No,
    )
    if resp == QMessageBox.Yes:
        excel_path, _ = QFileDialog.getOpenFileName(
            None, "Selecciona el Excel a importar", str(Path.home()), "Excel (*.xlsm *.xlsx)"
        )
        if excel_path:
            from app.migration.from_excel import migrate

            stats = migrate(excel_path, str(db_path))
            QMessageBox.information(
                None,
                "Importación completada",
                "Datos importados:\n" + "\n".join(f"  {k}: {v}" for k, v in stats.items()),
            )
            return db_path

    # Sin importación: crea una base de datos vacía con el esquema
    connect(db_path).close()
    return db_path


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Sobrants")
    style_path = Path(__file__).with_name("ui") / "style.qss"
    if style_path.exists():
        app.setStyleSheet(style_path.read_text(encoding="utf-8"))

    data_dir = _data_dir()
    db_path = _ensure_database(data_dir)

    conn = connect(db_path)
    repo = Repository(conn)

    from app.ui.main_window import MainWindow

    window = MainWindow(repo, str(db_path))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
