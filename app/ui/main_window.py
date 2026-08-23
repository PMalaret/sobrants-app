"""Finestra principal: substitueix el llibre Excel amb una pestanya per fulla."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup
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

from app import i18n
from app.backup import create_backup
from app.export import covered_materials_report_text, export_board_pdf, export_desmagatzem_pdf
from app.i18n import t
from app.logic.repository import Repository
from app.ui.board_tab import BoardTab
from app.ui.desmagatzem_tab import DesmagatzemTab
from app.ui.historic_tab import HistoricTab
from app.ui.materials_tab import MaterialsTab

# Cada 4 hores, igual que IniciarBackupAutomatic a l'original.
BACKUP_INTERVAL_MS = 4 * 60 * 60 * 1000

# Botons grans d'accions (icona + text + color), per a gent a qui li costi
# llegir un menú de text pla. (clau de traducció, emoji, color, mètode a cridar)
ACTION_BUTTONS = [
    ("action.backup", "💾", "#2f6fed", "_manual_backup"),
    ("action.export_board", "🗂️", "#1a9c6d", "_export_board"),
    ("action.export_desmagatzem", "📦", "#c9852b", "_export_desmagatzem"),
    ("action.covered", "⚠️", "#c62828", "_show_covered_report"),
]


class MainWindow(QMainWindow):
    def __init__(self, repo: Repository, db_path: str):
        super().__init__()
        self.repo = repo
        self.db_path = db_path
        self.resize(1500, 820)

        self._backup_timer = QTimer(self)
        self._backup_timer.timeout.connect(self._auto_backup)
        self._backup_timer.start(BACKUP_INTERVAL_MS)

        self._build_everything()

    # ------------------------------------------------------------------ #
    # Construcció completa de la UI. Es torna a cridar sencera quan canvia
    # l'idioma, perquè totes les cadenes es recalculen amb t() en construir
    # els widgets (més senzill i robust que retraduir widget per widget).
    # ------------------------------------------------------------------ #
    def _build_everything(self):
        self.setWindowTitle(t("app.title"))

        self.board_tab = BoardTab(self.repo)
        self.historic_tab = HistoricTab(self.repo)
        self.materials_tab = MaterialsTab(self.repo)
        self.desmagatzem_tab = DesmagatzemTab(self.repo)
        self.board_tab.data_changed.connect(self.historic_tab.refresh)
        # Els cercadors del Tauler també ressalten coincidències a
        # Desmagatzem amb el mateix color (igual que l'original).
        self.board_tab.search_dialog.search_changed.connect(self.desmagatzem_tab.apply_search_highlight)
        self.board_tab.search_dialog.cleared.connect(self.desmagatzem_tab.clear_search_highlight)

        tabs = QTabWidget()
        tabs.addTab(self.board_tab, t("tab.board"))
        tabs.addTab(self.desmagatzem_tab, t("tab.desmagatzem"))
        tabs.addTab(self.historic_tab, t("tab.historic"))
        tabs.addTab(self.materials_tab, t("tab.materials"))
        tabs.currentChanged.connect(self._on_tab_changed)
        tabs.setCornerWidget(self._build_action_bar(), Qt.TopRightCorner)
        self._tabs = tabs

        self.setCentralWidget(tabs)

        self.menuBar().clear()
        self._build_menu()

        status = self.statusBar()
        # netegem widgets permanents anteriors (si es reconstrueix per canvi d'idioma)
        for child in status.findChildren(QWidget):
            if getattr(child, "_sobrants_status_widget", False):
                status.removeWidget(child)
                child.deleteLater()
        legend = self.board_tab.build_legend_widget()
        legend._sobrants_status_widget = True
        status.addPermanentWidget(legend)
        status.showMessage(t("status.db", path=self.db_path))

    def _build_action_bar(self) -> QWidget:
        """Botons grans amb icona i color, a la mateixa alçada que les
        pestanyes i a la dreta (cantonada superior dreta del QTabWidget)."""
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        for label_key, emoji, color, slot_name in ACTION_BUTTONS:
            label = t(label_key).replace("\n", " ")
            button = QPushButton(f"{emoji}  {label}")
            button.setToolTip(label)
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-size: 12px;
                    font-weight: 600;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 10px;
                }}
                """
            )
            button.clicked.connect(getattr(self, slot_name))
            layout.addWidget(button)

        return bar

    def _on_tab_changed(self, index: int):
        widget = self._tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def _build_menu(self):
        menu = self.menuBar().addMenu(t("menu.file"))

        backup_action = menu.addAction(t("menu.backup_now"))
        backup_action.triggered.connect(self._manual_backup)

        menu.addSeparator()

        export_board_action = menu.addAction(t("menu.export_board"))
        export_board_action.triggered.connect(self._export_board)

        export_desmagatzem_action = menu.addAction(t("menu.export_desmagatzem"))
        export_desmagatzem_action.triggered.connect(self._export_desmagatzem)

        report_action = menu.addAction(t("menu.report_covered"))
        report_action.triggered.connect(self._show_covered_report)

        menu.addSeparator()
        exit_action = menu.addAction(t("menu.exit"))
        exit_action.triggered.connect(self.close)

        lang_menu = self.menuBar().addMenu(f"🌐 {t('app.language')}")
        group = QActionGroup(self)
        group.setExclusive(True)
        for code, name in i18n.LANGS.items():
            action = QAction(name, self, checkable=True)
            action.setChecked(i18n.get_language() == code)
            action.triggered.connect(lambda checked, c=code: self._change_language(c))
            group.addAction(action)
            lang_menu.addAction(action)

    def _change_language(self, lang: str):
        if lang == i18n.get_language():
            return
        i18n.set_language(lang)
        self._build_everything()

    def _manual_backup(self):
        dest = create_backup(self.db_path)
        QMessageBox.information(self, t("dialog.backup.title"), t("dialog.backup.text", path=dest))

    def _auto_backup(self):
        try:
            create_backup(self.db_path)
            self.statusBar().showMessage(t("status.db_backed_up", path=self.db_path), 5000)
        except OSError:
            pass  # backup silenciós; no s'interromp la feina si falla

    def _export_board(self):
        path, _ = QFileDialog.getSaveFileName(
            self, t("dialog.export_board.title"), t("dialog.export_board.filename"), "PDF (*.pdf)"
        )
        if not path:
            return
        export_board_pdf(self.repo, path)
        QMessageBox.information(self, t("dialog.exported.title"), t("dialog.export_board.done", path=path))

    def _export_desmagatzem(self):
        path, _ = QFileDialog.getSaveFileName(
            self, t("dialog.export_desmagatzem.title"), t("dialog.export_desmagatzem.filename"), "PDF (*.pdf)"
        )
        if not path:
            return
        export_desmagatzem_pdf(self.repo, path)
        QMessageBox.information(self, t("dialog.exported.title"), t("dialog.export_desmagatzem.done", path=path))

    def _show_covered_report(self):
        text = covered_materials_report_text(self.repo)
        dialog = QWidget(self, flags=self.windowFlags())
        dialog.setWindowTitle(t("dialog.covered.title"))
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
