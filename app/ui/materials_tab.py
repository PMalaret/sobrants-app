"""Pestaña 'Materiales': equivalente a la hoja Materials (catálogo, sólo lectura)."""
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

from app.logic.repository import Repository

COLUMNS = ["Nº material", "Descripción"]


class MaterialsTab(QWidget):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Buscar:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Nº o parte de la descripción")
        self.search.textChanged.connect(self.refresh)
        search_row.addWidget(self.search)
        layout.addLayout(search_row)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels(COLUMNS)
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
