"""Pestaña 'Desmagatzem': retirada de piezas por carro/lote."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.logic.repository import Repository, RuleViolation

COLUMNS = ["Cantidad", "Nº material", "Material", "Medidas", "Carro/lote", "Fecha/hora"]

CONFIRM_TEXT = {
    "increase": "¿Confirmas aumentar la cantidad? Se registrará en el histórico.",
    "decrease": "¿Confirmas disminuir la cantidad? Se registrará en el histórico.",
    "delete": "La cantidad queda en 0: ¿confirmas borrar la línea? Se registrará la baja en el histórico.",
}


class DesmagatzemTab(QWidget):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form_box = QGroupBox("Nueva retirada")
        form = QFormLayout(form_box)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Nº de material (usa '1' para material no registrado)")
        self.custom_text_input = QLineEdit()
        self.custom_text_input.setPlaceholderText("Sólo si el nº es 1: describe el material")
        self.qty_input = QSpinBox()
        self.qty_input.setRange(0, 20)
        self.dims_input = QLineEdit()
        self.cart_input = QLineEdit()
        self.cart_input.setPlaceholderText("p.ej. carro 88000")

        form.addRow("Nº material:", self.code_input)
        form.addRow("Material (si nº = 1):", self.custom_text_input)
        form.addRow("Cantidad:", self.qty_input)
        form.addRow("Medidas:", self.dims_input)
        form.addRow("Carro/lote:", self.cart_input)

        self.add_button = QPushButton("Registrar retirada")
        self.add_button.clicked.connect(self._on_add_row)
        form.addRow(self.add_button)
        layout.addWidget(form_box)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table)

        qty_row = QHBoxLayout()
        qty_row.addWidget(self._label("Nueva cantidad para la fila seleccionada:"))
        self.new_qty_input = QSpinBox()
        self.new_qty_input.setRange(0, 20)
        qty_row.addWidget(self.new_qty_input)
        self.update_qty_button = QPushButton("Aplicar cambio de cantidad")
        self.update_qty_button.clicked.connect(self._on_update_qty)
        qty_row.addWidget(self.update_qty_button)
        qty_row.addStretch()
        layout.addLayout(qty_row)

    @staticmethod
    def _label(text):
        from PySide6.QtWidgets import QLabel

        return QLabel(text)

    def refresh(self):
        rows = self.repo.list_desmagatzem()
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

    def _selected_row_id(self) -> int | None:
        items = self.table.selectedItems()
        if not items:
            return None
        return self._row_ids[items[0].row()]

    def _on_add_row(self):
        code = self.code_input.text().strip()
        if not code:
            QMessageBox.warning(self, "Falta el nº de material", "Indica el nº de material.")
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
            QMessageBox.critical(self, "No se puede registrar", str(exc))
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
            QMessageBox.warning(self, "Sin selección", "Selecciona primero una línea de la tabla.")
            return
        new_qty = self.new_qty_input.value()

        # Averigua qué tipo de cambio será, para pedir la confirmación adecuada
        # (igual que el MsgBox Sí/No de ActualitzaHistorialQuantitat).
        current = next(r for r in self.repo.list_desmagatzem() if r["id"] == row_id)
        from app.logic.rules import quantity_change_kind

        change = quantity_change_kind(current["quantity"], new_qty)
        if change is None:
            return
        resp = QMessageBox.question(
            self, "Confirmar", CONFIRM_TEXT[change], QMessageBox.Yes | QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return
        try:
            self.repo.update_desmagatzem_quantity(row_id, new_qty)
        except RuleViolation as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.refresh()
