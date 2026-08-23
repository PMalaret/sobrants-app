"""Pestaña 'Histórico': equivalente a la hoja històric (auditoría, sólo lectura)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.logic.repository import Repository

COLUMNS = ["Posición", "Nº material", "Material", "Fecha/hora", "Movimiento"]

# Mismos colores que el original: verde = entrada, rojo = salida,
# marrón claro/oscuro = origen/destino de un traslado.
KIND_LABELS = {
    "in": ("Entrada", QColor("#1a7f37")),
    "out": ("Salida", QColor("#c62828")),
    "move_out": ("Traslado (origen)", QColor("#b48c64")),
    "move_in": ("Traslado (destino)", QColor("#78460f")),
}


class HistoricTab(QWidget):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Filtrar por posición:"))
        self.position_filter = QLineEdit()
        self.position_filter.setPlaceholderText("p.ej. 12, o 'Desmagatzem'")
        self.position_filter.textChanged.connect(self.refresh)
        filters.addWidget(self.position_filter)
        self.refresh_button = QPushButton("Actualizar")
        self.refresh_button.clicked.connect(self.refresh)
        filters.addWidget(self.refresh_button)
        filters.addStretch()
        layout.addLayout(filters)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table)

    def refresh(self):
        position = self.position_filter.text().strip() or None
        rows = self.repo.get_historic(limit=1000, position=position)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            label, color = KIND_LABELS.get(row["kind"], (row["kind"], QColor(Qt.black)))
            values = [row["position"], row["material_code"] or "", row["material_desc"] or "", row["ts"], label]
            for c, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                item.setForeground(color)
                self.table.setItem(r, c, item)
