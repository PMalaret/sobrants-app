"""Pestanya 'Materials': equivalent a la fulla Materials (catàleg, només lectura)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t
from app.logic.repository import Repository


class MaterialsTab(QWidget):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel(t("materials.search_label")))
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("materials.search_placeholder"))
        self.search.textChanged.connect(self.refresh)
        search_row.addWidget(self.search)
        layout.addLayout(search_row)

        columns = [t("materials.col.code"), t("materials.col.description")]
        self.table = QTableWidget(0, len(columns))
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table)

    def refresh(self):
        query = self.search.text().strip()
        rows = self.repo.search_materials(query, limit=500)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(str(row["code"])))
            self.table.setItem(r, 1, QTableWidgetItem(row["description"]))
