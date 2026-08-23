"""Pestanya 'Històric': equivalent a la fulla històric (auditoria, només lectura)."""
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

COLUMNS = ["Posició", "Núm. material", "Material", "Data/hora", "Moviment"]

# Mateixos colors que l'original: verd = entrada, vermell = sortida,
# marró clar/fosc = origen/destí d'un trasllat.
KIND_LABELS = {
    "in": ("Entrada", QColor("#1a7f37")),
    "out": ("Sortida", QColor("#c62828")),
    "move_out": ("Trasllat (origen)", QColor("#b48c64")),
    "move_in": ("Trasllat (destí)", QColor("#78460f")),
}

# Els botons d'ordre fan servir el mateix QPushButton blau per defecte quan
# estan actius; quan no ho estan, s'atenuen a gris per marcar quin és
# l'ordre vigent (equivalent al punt verd a A1/D1 de l'original).
ACTIVE_SORT_STYLE = ""
INACTIVE_SORT_STYLE = "background-color: #d8dae0; color: #444;"


class HistoricTab(QWidget):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.order_by = "date"  # equivalent a l'estat inicial de l'original (ordenat per data)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Filtrar per posició:"))
        self.position_filter = QLineEdit()
        self.position_filter.setPlaceholderText("p.ex. 12, o 'Desmagatzem'")
        self.position_filter.textChanged.connect(self.refresh)
        filters.addWidget(self.position_filter)

        filters.addSpacing(16)
        filters.addWidget(QLabel("Ordenar per:"))
        self.sort_date_button = QPushButton("Data")
        self.sort_date_button.clicked.connect(lambda: self._set_order("date"))
        self.sort_position_button = QPushButton("Posició")
        self.sort_position_button.clicked.connect(lambda: self._set_order("position"))
        filters.addWidget(self.sort_date_button)
        filters.addWidget(self.sort_position_button)

        self.refresh_button = QPushButton("Actualitzar")
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

        self._update_sort_buttons()

    def _set_order(self, order_by: str):
        self.order_by = order_by
        self._update_sort_buttons()
        self.refresh()

    def _update_sort_buttons(self):
        self.sort_date_button.setStyleSheet(
            ACTIVE_SORT_STYLE if self.order_by == "date" else INACTIVE_SORT_STYLE
        )
        self.sort_position_button.setStyleSheet(
            ACTIVE_SORT_STYLE if self.order_by == "position" else INACTIVE_SORT_STYLE
        )

    def refresh(self):
        position = self.position_filter.text().strip() or None
        rows = self.repo.get_historic(limit=1000, position=position, order_by=self.order_by)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            label, color = KIND_LABELS.get(row["kind"], (row["kind"], QColor(Qt.black)))
            values = [row["position"], row["material_code"] or "", row["material_desc"] or "", row["ts"], label]
            for c, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                item.setForeground(color)
                self.table.setItem(r, c, item)
