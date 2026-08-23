"""Pestanya 'Desmagatzem': retirada de peces per carro/lot.

Els cercadors del Tauler (M20/M22/M24 a l'Excel original) també pintaven
les cel·les coincidents de la fulla desmagatzem amb el mateix color del
cercador (`BuscaCoincidenciesDesmagatzem_Q20/M22/M24`); aquí es reprodueix
exactament igual, reutilitzant els mateixos colors que `SearchDialog`
(`SEARCH_COLORS`) — mai es crea una paleta nova.
"""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t
from app.logic import rules
from app.logic.repository import Repository, RuleViolation
from app.logic.rules import quantity_change_kind
from app.ui.search_dialog import SEARCH_COLORS

# Mateix patró que a HistoricTab: el botó d'ordre actiu es queda amb
# l'estil blau per defecte, l'inactiu s'atenua a gris.
ACTIVE_SORT_STYLE = ""
INACTIVE_SORT_STYLE = "background-color: #d8dae0; color: #444;"


class DesmagatzemTab(QWidget):
    # Columna de la taula (Quantitat, Núm., Material, Mides, Carro/lot, Data)
    # que ressalta cada cercador — igual que B/C/E a la fulla desmagatzem
    # original per a M20/M22/M24 respectivament.
    _SEARCH_COLUMN = {"code": 1, "description": 2, "notes": 4}
    _SEARCH_FIELD = {"code": "material_code", "description": "material_desc", "notes": "cart_ref"}

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._search_state: dict[str, str] = {}
        self.order_by = "date"  # per defecte: per data/hora ascendent
        self._build_ui()
        self.refresh()

    def _columns(self):
        return [
            t("desmagatzem.col.quantity"),
            t("desmagatzem.col.code"),
            t("desmagatzem.col.material"),
            t("desmagatzem.col.dimensions"),
            t("desmagatzem.col.cart"),
            t("desmagatzem.col.datetime"),
        ]

    def _confirm_text(self):
        return {
            "increase": t("desmagatzem.confirm.increase"),
            "decrease": t("desmagatzem.confirm.decrease"),
            "delete": t("desmagatzem.confirm.delete"),
        }

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form_box = QGroupBox(t("desmagatzem.form_title"))
        form = QFormLayout(form_box)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText(t("desmagatzem.code_placeholder"))
        self.custom_text_input = QLineEdit()
        self.custom_text_input.setPlaceholderText(t("desmagatzem.custom_placeholder"))
        self.qty_input = QSpinBox()
        self.qty_input.setRange(0, 20)
        self.dims_input = QLineEdit()
        self.cart_input = QLineEdit()
        self.cart_input.setPlaceholderText(t("desmagatzem.cart_placeholder"))

        form.addRow(t("desmagatzem.field.code"), self.code_input)
        form.addRow(t("desmagatzem.field.custom"), self.custom_text_input)
        form.addRow(t("desmagatzem.field.quantity"), self.qty_input)
        form.addRow(t("desmagatzem.field.dimensions"), self.dims_input)
        form.addRow(t("desmagatzem.field.cart"), self.cart_input)

        self.add_button = QPushButton(t("desmagatzem.add_button"))
        self.add_button.clicked.connect(self._on_add_row)
        form.addRow(self.add_button)
        layout.addWidget(form_box)

        sort_row = QHBoxLayout()
        sort_row.addWidget(QLabel(t("historic.sort_label")))
        self.sort_date_button = QPushButton(t("historic.sort_date"))
        self.sort_date_button.clicked.connect(lambda: self._set_order("date"))
        self.sort_order_button = QPushButton(t("desmagatzem.sort_order"))
        self.sort_order_button.clicked.connect(lambda: self._set_order("order"))
        sort_row.addWidget(self.sort_date_button)
        sort_row.addWidget(self.sort_order_button)
        sort_row.addStretch()
        layout.addLayout(sort_row)

        columns = self._columns()
        self.table = QTableWidget(0, len(columns))
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table)

        self._update_sort_buttons()

        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel(t("desmagatzem.new_qty_label")))
        self.new_qty_input = QSpinBox()
        self.new_qty_input.setRange(0, 20)
        qty_row.addWidget(self.new_qty_input)
        self.update_qty_button = QPushButton(t("desmagatzem.apply_qty"))
        self.update_qty_button.clicked.connect(self._on_update_qty)
        qty_row.addWidget(self.update_qty_button)
        qty_row.addStretch()
        layout.addLayout(qty_row)

    def _set_order(self, order_by: str):
        self.order_by = order_by
        self._update_sort_buttons()
        self.refresh()

    def _update_sort_buttons(self):
        self.sort_date_button.setStyleSheet(ACTIVE_SORT_STYLE if self.order_by == "date" else INACTIVE_SORT_STYLE)
        self.sort_order_button.setStyleSheet(ACTIVE_SORT_STYLE if self.order_by == "order" else INACTIVE_SORT_STYLE)

    def refresh(self):
        rows = self.repo.list_desmagatzem(order_by=self.order_by)
        self._rows = rows
        self._row_ids = [r["id"] for r in rows]
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                row["quantity"],
                row["material_code"],
                row["material_desc"] or "",
                row["dimensions"] or "",
                row["cart_ref"] or "",
                row["ts"] or "",
            ]
            for c, v in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))
        self._reapply_highlights()

    # ------------------------------------------------------------------ #
    # Ressaltat creuat amb els cercadors del Tauler (mateixos colors)
    # ------------------------------------------------------------------ #
    def apply_search_highlight(self, mode: str, text: str):
        self._search_state[mode] = text
        self._highlight_mode(mode, text)

    def clear_search_highlight(self):
        self._search_state = {}
        for mode in self._SEARCH_COLUMN:
            self._clear_column(self._SEARCH_COLUMN[mode])

    def _reapply_highlights(self):
        for mode, text in self._search_state.items():
            self._highlight_mode(mode, text)

    def _highlight_mode(self, mode: str, text: str):
        column = self._SEARCH_COLUMN[mode]
        self._clear_column(column)
        if not text.strip():
            return
        color = QColor(SEARCH_COLORS[mode])
        field = self._SEARCH_FIELD[mode]
        for r, row in enumerate(getattr(self, "_rows", [])):
            value = row[field]
            if value is None:
                continue
            hit = rules.matches_exact(str(value), text) if mode == "code" else rules.matches_partial(str(value), text)
            if hit:
                item = self.table.item(r, column)
                if item is not None:
                    item.setBackground(color)

    def _clear_column(self, column: int):
        transparent = QColor(0, 0, 0, 0)
        for r in range(self.table.rowCount()):
            item = self.table.item(r, column)
            if item is not None:
                item.setBackground(transparent)

    def _selected_row_id(self) -> int | None:
        items = self.table.selectedItems()
        if not items:
            return None
        return self._row_ids[items[0].row()]

    def _on_add_row(self):
        code = self.code_input.text().strip()
        if not code:
            QMessageBox.warning(self, t("desmagatzem.missing_code.title"), t("desmagatzem.missing_code.text"))
            return
        custom_text = self.custom_text_input.text().strip() or None
        try:
            self.repo.add_desmagatzem_row(
                material_code=code,
                quantity=self.qty_input.value(),
                dimensions=self.dims_input.text().strip(),
                cart_ref=self.cart_input.text().strip(),
                custom_text=custom_text,
            )
        except RuleViolation as exc:
            QMessageBox.critical(self, t("desmagatzem.cannot_register"), str(exc))
            return
        self.code_input.clear()
        self.custom_text_input.clear()
        self.qty_input.setValue(0)
        self.dims_input.clear()
        self.cart_input.clear()
        self.refresh()

    def _on_update_qty(self):
        row_id = self._selected_row_id()
        if row_id is None:
            QMessageBox.warning(self, t("desmagatzem.no_selection.title"), t("desmagatzem.no_selection.text"))
            return
        new_qty = self.new_qty_input.value()

        # Esbrina quin tipus de canvi serà, per demanar la confirmació
        # adequada (igual que el MsgBox Sí/No d'ActualitzaHistorialQuantitat).
        current = next(r for r in self.repo.list_desmagatzem() if r["id"] == row_id)
        change = quantity_change_kind(current["quantity"], new_qty)
        if change is None:
            return
        resp = QMessageBox.question(
            self, t("common.confirm"), self._confirm_text()[change], QMessageBox.Yes | QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return
        try:
            self.repo.update_desmagatzem_quantity(row_id, new_qty)
        except RuleViolation as exc:
            QMessageBox.critical(self, t("common.error"), str(exc))
            return
        self.refresh()
