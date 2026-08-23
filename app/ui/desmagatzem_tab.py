"""Pestanya 'Desmagatzem': retirada de peces per carro/lot.

Els cercadors del Tauler (M20/M22/M24 a l'Excel original) també pintaven
les cel·les coincidents de la fulla desmagatzem amb el mateix color del
cercador (`BuscaCoincidenciesDesmagatzem_Q20/M22/M24`); aquí es reprodueix
exactament igual, reutilitzant els mateixos colors que `SearchPanel`
(`SEARCH_COLORS`) — mai es crea una paleta nova.

L'ordenació es fa clicant la capçalera de cada columna (mode natiu de
QTableWidget, alterna ascendent/descendent), no amb botons a part. Per
defecte surt ordenat per Data ascendent (la més antiga primer).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
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
from app.ui.search_panel import SEARCH_COLORS


class _NumericItem(QTableWidgetItem):
    """Perquè "Quantitat" i "Núm. material" s'ordenin numèricament en
    clicar la capçalera, no com a text (10 abans que 2)."""

    def __init__(self, text: str, sort_value: float):
        super().__init__(text)
        self._sort_value = sort_value

    def __lt__(self, other):
        if isinstance(other, _NumericItem):
            return self._sort_value < other._sort_value
        return super().__lt__(other)


def _numeric_item(value) -> QTableWidgetItem:
    try:
        return _NumericItem(str(value), float(value))
    except (TypeError, ValueError):
        return QTableWidgetItem(str(value))


class DesmagatzemTab(QWidget):
    # Columna de la taula (Quantitat, Núm., Material, Mides, Carro/lot, Data)
    # que ressalta cada cercador — igual que B/C/E a la fulla desmagatzem
    # original per a M20/M22/M24 respectivament.
    _SEARCH_COLUMN = {"code": 1, "description": 2, "notes": 4}
    _SEARCH_FIELD = {"code": "material_code", "description": "material_desc", "notes": "cart_ref"}
    _DATE_COL = 5

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._search_state: dict[str, str] = {}
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

    def _configure_column_widths(self):
        # Totes les columnes "Interactive" (redimensionables arrossegant la
        # vora), sense cap "Stretch": una columna en mode "Stretch" no es
        # pot redimensionar manualment (Qt en controla l'ample per omplir
        # l'espai sobrant), i totes s'han de poder canviar de mida.
        header = self.table.horizontalHeader()
        widths = [70, 80, 200, 90, 200, 150]  # Quantitat, Núm., Material, Mides, Notes, Data
        for col, width in enumerate(widths):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
            self.table.setColumnWidth(col, width)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 3, 9, 9)  # marge superior mínim, taula enganxada a les pestanyes

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

        columns = self._columns()
        self.table = QTableWidget(0, len(columns))
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels(columns)
        self._configure_column_widths()
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table)

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

    def refresh(self):
        # Desactivem l'ordenació mentre omplim la taula (si no, Qt reordena
        # fila a fila a cada setItem, molt lent i pot descol·locar dades).
        self.table.setSortingEnabled(False)
        rows = self.repo.list_desmagatzem()
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            quantity_item = _numeric_item(row["quantity"])
            quantity_item.setData(Qt.UserRole, row["id"])  # per retrobar la fila després d'ordenar
            self.table.setItem(r, 0, quantity_item)
            self.table.setItem(r, 1, _numeric_item(row["material_code"]))
            self.table.setItem(r, 2, QTableWidgetItem(row["material_desc"] or ""))
            self.table.setItem(r, 3, QTableWidgetItem(row["dimensions"] or ""))
            self.table.setItem(r, 4, QTableWidgetItem(row["cart_ref"] or ""))
            self.table.setItem(r, 5, QTableWidgetItem(row["ts"] or ""))
        self.table.setSortingEnabled(True)
        # Per defecte, ordenat per data ascendent (la més antiga primer).
        # L'usuari sempre pot canviar-ho clicant qualsevol altra capçalera.
        self.table.sortByColumn(self._DATE_COL, Qt.AscendingOrder)
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
        # Llegeix directament de la taula (no d'una llista a part), perquè
        # es mantingui correcte sigui quin sigui l'ordre de files actual.
        column = self._SEARCH_COLUMN[mode]
        self._clear_column(column)
        if not text.strip():
            return
        color = QColor(SEARCH_COLORS[mode])
        for r in range(self.table.rowCount()):
            item = self.table.item(r, column)
            if item is None or not item.text():
                continue
            value = item.text()
            hit = rules.matches_exact(value, text) if mode == "code" else rules.matches_partial(value, text)
            if hit:
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
        row = items[0].row()
        id_item = self.table.item(row, 0)
        return id_item.data(Qt.UserRole) if id_item is not None else None

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
