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

from app.i18n import t
from app.logic.repository import Repository

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

    def _columns(self):
        return [
            t("historic.col.position"),
            t("historic.col.code"),
            t("historic.col.material"),
            t("historic.col.datetime"),
            t("historic.col.movement"),
        ]

    def _kind_labels(self):
        return {
            "in": (t("historic.kind.in"), QColor("#1a7f37")),
            "out": (t("historic.kind.out"), QColor("#c62828")),
            "move_out": (t("historic.kind.move_out"), QColor("#b48c64")),
            "move_in": (t("historic.kind.move_in"), QColor("#78460f")),
        }

    def _build_ui(self):
        layout = QVBoxLayout(self)

        filters = QHBoxLayout()
        filters.addWidget(QLabel(t("historic.filter_label")))
        self.position_filter = QLineEdit()
        self.position_filter.setPlaceholderText(t("historic.filter_placeholder"))
        self.position_filter.textChanged.connect(self.refresh)
        filters.addWidget(self.position_filter)

        filters.addSpacing(16)
        filters.addWidget(QLabel(t("historic.sort_label")))
        self.sort_date_button = QPushButton(t("historic.sort_date"))
        self.sort_date_button.clicked.connect(lambda: self._set_order("date"))
        self.sort_position_button = QPushButton(t("historic.sort_position"))
        self.sort_position_button.clicked.connect(lambda: self._set_order("position"))
        filters.addWidget(self.sort_date_button)
        filters.addWidget(self.sort_position_button)

        self.refresh_button = QPushButton(t("historic.refresh"))
        self.refresh_button.clicked.connect(self.refresh)
        filters.addWidget(self.refresh_button)
        filters.addStretch()
        layout.addLayout(filters)

        columns = self._columns()
        self.table = QTableWidget(0, len(columns))
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels(columns)
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
        kind_labels = self._kind_labels()
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            label, color = kind_labels.get(row["kind"], (row["kind"], QColor(Qt.black)))
            values = [row["position"], row["material_code"] or "", row["material_desc"] or "", row["ts"], label]
            for c, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                item.setForeground(color)
                self.table.setItem(r, c, item)
