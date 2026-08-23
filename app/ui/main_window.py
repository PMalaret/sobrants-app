"""Finestra principal: substitueix el llibre Excel amb una pestanya per fulla."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.backup import create_backup
from app.export import covered_materials_report_text, export_board_pdf, export_desmagatzem_pdf
from app.logic.repository import Repository
from app.ui.board_tab import BoardTab
from app.ui.desmagatzem_tab import DesmagatzemTab
from app.ui.historic_tab import HistoricTab
from app.ui.materials_tab import MaterialsTab

# Cada 4 hores, igual que IniciarBackupAutomatic a l'original.
BACKUP_INTERVAL_MS = 4 * 60 * 60 * 1000

# Botons grans d'accions (icona + text + color), per a gent a qui li costi
# llegir un menú de text pla. (etiqueta, emoji, color, mètode a cridar)
ACTION_BUTTONS = [
    ("Còpia de\nseguretat", "💾", "#2f6fed", "_manual_backup"),
    ("Exportar\ntauler a PDF", "🗂️", "#1a9c6d", "_export_board"),
    ("Exportar\ndesmagatzem a PDF", "📦", "#c9852b", "_export_desmagatzem"),
    ("Materials\ntapats", "⚠️", "#c62828", "_show_covered_report"),
]


class MainWindow(QMainWindow):
    def __init__(self, repo: Repository, db_path: str):
        super().__init__()
        self.repo = repo
        self.db_path = db_path
        self.setWindowTitle("Sobrants — control d'inventari")
        self.resize(1500, 920)

        self.board_tab = BoardTab(repo)
        self.historic_tab = HistoricTab(repo)
        self.materials_tab = MaterialsTab(repo)
        self.desmagatzem_tab = DesmagatzemTab(repo)

        self.board_tab.data_changed.connect(self.historic_tab.refresh)

        tabs = QTabWidget()
        tabs.addTab(self.board_tab, "Tauler")
        tabs.addTab(self.desmagatzem_tab, "Desmagatzem")
        tabs.addTab(self.historic_tab, "Històric")
        tabs.addTab(self.materials_tab, "Materials")
        tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs = tabs

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(self._build_action_bar())
        central_layout.addWidget(tabs)
        self.setCentralWidget(central)

        self._build_menu()
        self.statusBar().showMessage(f"Base de dades: {db_path}")

        self._backup_timer = QTimer(self)
        self._backup_timer.timeout.connect(self._auto_backup)
        self._backup_timer.start(BACKUP_INTERVAL_MS)

    def _build_action_bar(self) -> QWidget:
        """Franja de botons grans amb icona i color, alternativa visual al
        menú de text per a operaris a qui els costi llegir."""
        bar = QWidget()
        bar.setStyleSheet("background-color: #eef0f3; border-bottom: 1px solid #d0d3d9;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        for label, emoji, color, slot_name in ACTION_BUTTONS:
            button = QPushButton(f"{emoji}\n{label}")
            button.setMinimumSize(120, 60)
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-size: 13px;
                    font-weight: 600;
                    border: none;
                    border-radius: 8px;
                    padding: 6px;
                }}
                QPushButton:hover {{ background-color: {color}; opacity: 0.9; }}
                """
            )
            button.clicked.connect(getattr(self, slot_name))
            layout.addWidget(button)

        layout.addStretch()
        return bar

    def _on_tab_changed(self, index: int):
        widget = self._tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def _build_menu(self):
        menu = self.menuBar().addMenu("&Fitxer")

        backup_action = menu.addAction("Còpia de seguretat ara")
        backup_action.triggered.connect(self._manual_backup)

        menu.addSeparator()

        export_board_action = menu.addAction("Exportar tauler a PDF…")
        export_board_action.triggered.connect(self._export_board)

        export_desmagatzem_action = menu.addAction("Exportar desmagatzem a PDF…")
        export_desmagatzem_action.triggered.connect(self._export_desmagatzem)

        report_action = menu.addAction("Informe de materials tapats")
        report_action.triggered.connect(self._show_covered_report)

        menu.addSeparator()
        exit_action = menu.addAction("Sortir")
        exit_action.triggered.connect(self.close)

    def _manual_backup(self):
        dest = create_backup(self.db_path)
        QMessageBox.information(self, "Còpia de seguretat", f"Còpia creada a:\n{dest}")

    def _auto_backup(self):
        try:
            create_backup(self.db_path)
            self.statusBar().showMessage(f"Base de dades: {self.db_path} — última còpia: ara", 5000)
        except OSError:
            pass  # backup silenciós; no s'interromp la feina si falla

    def _export_board(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar tauler", "tauler.pdf", "PDF (*.pdf)")
        if not path:
            return
        export_board_pdf(self.repo, path)
        QMessageBox.information(self, "Exportat", f"Tauler exportat a:\n{path}")

    def _export_desmagatzem(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar desmagatzem", "desmagatzem.pdf", "PDF (*.pdf)")
        if not path:
            return
        export_desmagatzem_pdf(self.repo, path)
        QMessageBox.information(self, "Exportat", f"Desmagatzem exportat a:\n{path}")

    def _show_covered_report(self):
        text = covered_materials_report_text(self.repo)
        dialog = QWidget(self, flags=self.windowFlags())
        dialog.setWindowTitle("Materials tapats")
        dialog.resize(700, 500)
        layout = QVBoxLayout(dialog)
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setPlainText(text)
        box.setFont(self.font())
        layout.addWidget(box)
        dialog.show()
        self._report_dialog = dialog  # evita que el GC el tanqui

    def closeEvent(self, event):
        try:
            create_backup(self.db_path)
        except OSError:
            pass
        super().closeEvent(event)
