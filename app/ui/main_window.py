"""Ventana principal: sustituye al libro Excel con pestañas por hoja."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
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

# Cada 4 horas, igual que IniciarBackupAutomatic en el original.
BACKUP_INTERVAL_MS = 4 * 60 * 60 * 1000


class MainWindow(QMainWindow):
    def __init__(self, repo: Repository, db_path: str):
        super().__init__()
        self.repo = repo
        self.db_path = db_path
        self.setWindowTitle("Sobrants — control de inventario")
        self.resize(1650, 900)

        self.board_tab = BoardTab(repo)
        self.historic_tab = HistoricTab(repo)
        self.materials_tab = MaterialsTab(repo)
        self.desmagatzem_tab = DesmagatzemTab(repo)

        self.board_tab.data_changed.connect(self.historic_tab.refresh)

        tabs = QTabWidget()
        tabs.addTab(self.board_tab, "Tablero")
        tabs.addTab(self.desmagatzem_tab, "Desmagatzem")
        tabs.addTab(self.historic_tab, "Histórico")
        tabs.addTab(self.materials_tab, "Materiales")
        self.setCentralWidget(tabs)
        tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs = tabs

        self._build_menu()
        self.statusBar().showMessage(f"Base de datos: {db_path}")

        self._backup_timer = QTimer(self)
        self._backup_timer.timeout.connect(self._auto_backup)
        self._backup_timer.start(BACKUP_INTERVAL_MS)

    def _on_tab_changed(self, index: int):
        widget = self._tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def _build_menu(self):
        menu = self.menuBar().addMenu("&Archivo")

        backup_action = menu.addAction("Copia de seguridad ahora")
        backup_action.triggered.connect(self._manual_backup)

        menu.addSeparator()

        export_board_action = menu.addAction("Exportar tablero a PDF…")
        export_board_action.triggered.connect(self._export_board)

        export_desmagatzem_action = menu.addAction("Exportar desmagatzem a PDF…")
        export_desmagatzem_action.triggered.connect(self._export_desmagatzem)

        report_action = menu.addAction("Informe de materiales tapados")
        report_action.triggered.connect(self._show_covered_report)

        menu.addSeparator()
        exit_action = menu.addAction("Salir")
        exit_action.triggered.connect(self.close)

    def _manual_backup(self):
        dest = create_backup(self.db_path)
        QMessageBox.information(self, "Copia de seguridad", f"Copia creada en:\n{dest}")

    def _auto_backup(self):
        try:
            create_backup(self.db_path)
            self.statusBar().showMessage(f"Base de datos: {self.db_path} — última copia: ahora", 5000)
        except OSError:
            pass  # backup silencioso; no se interrumpe el trabajo si falla

    def _export_board(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar tablero", "tablero.pdf", "PDF (*.pdf)")
        if not path:
            return
        export_board_pdf(self.repo, path)
        QMessageBox.information(self, "Exportado", f"Tablero exportado a:\n{path}")

    def _export_desmagatzem(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar desmagatzem", "desmagatzem.pdf", "PDF (*.pdf)")
        if not path:
            return
        export_desmagatzem_pdf(self.repo, path)
        QMessageBox.information(self, "Exportado", f"Desmagatzem exportado a:\n{path}")

    def _show_covered_report(self):
        text = covered_materials_report_text(self.repo)
        dialog = QWidget(self, flags=self.windowFlags())
        dialog.setWindowTitle("Materiales tapados")
        dialog.resize(700, 500)
        layout = QVBoxLayout(dialog)
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setPlainText(text)
        box.setFont(self.font())
        layout.addWidget(box)
        dialog.show()
        self._report_dialog = dialog  # evita que el GC lo cierre

    def closeEvent(self, event):
        try:
            create_backup(self.db_path)
        except OSError:
            pass
        super().closeEvent(event)
