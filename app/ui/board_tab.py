"""Pestaña 'Tablero': equivalente a la hoja Hoja1 del Excel original.

El tablero se reparte en 3 bloques de columnas lado a lado (posiciones
1-27, 28-54 y 55-61), igual que hacía Hoja1 (bloques A:E, F:J y K:O) para
que las 61 posiciones quepan a la vista sin necesidad de hacer scroll.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.logic.repository import DuplicateMaterialError, PositionFullError, Repository, RuleViolation

FIELD_LABELS = ["Posición", "Nº material", "Material", "Medidas", "Notas", "Piezas"]
DETAIL_COLUMNS = ["Slot", "Nº material", "Material", "Medidas", "Notas", "Entrada"]

# (posición inicial, nº de posiciones) de cada bloque de columnas, igual que
# los bloques A/F/K de Hoja1.
BLOCKS = [(1, 27), (28, 27), (55, 7)]
FIELDS_PER_BLOCK = len(FIELD_LABELS)
TABLE_ROWS = max(count for _start, count in BLOCKS)


def _position_to_cell(position: int) -> tuple[int, int]:
    """Posición -> (fila, columna del campo 'Posición' de su bloque)."""
    for block_idx, (start, count) in enumerate(BLOCKS):
        if start <= position < start + count:
            return position - start, block_idx * FIELDS_PER_BLOCK
    raise ValueError(f"Posición fuera de rango: {position}")


class BoardTab(QWidget):
    data_changed = Signal()

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.selected_position: int | None = None
        self._build_ui()
        self.refresh_board()

    # ------------------------------------------------------------------ #
    def _build_ui(self):
        splitter = QSplitter(Qt.Horizontal)

        # --- Panel izquierdo: tabla del tablero + buscadores ---
        left = QWidget()
        left_layout = QVBoxLayout(left)

        search_box = QGroupBox("Buscar")
        search_layout = QFormLayout(search_box)

        self.search_code = QLineEdit()
        self.search_code.setPlaceholderText("Nº de material exacto")
        self.search_code_result = QLabel("")
        row = QHBoxLayout()
        row.addWidget(self.search_code)
        row.addWidget(self.search_code_result)
        search_layout.addRow("Por nº (exacto):", row)

        self.search_desc = QLineEdit()
        self.search_desc.setPlaceholderText("Texto parcial en la descripción")
        self.search_desc_result = QLabel("")
        row2 = QHBoxLayout()
        row2.addWidget(self.search_desc)
        row2.addWidget(self.search_desc_result)
        search_layout.addRow("Por material (parcial):", row2)

        self.search_notes = QLineEdit()
        self.search_notes.setPlaceholderText("Texto parcial en notas")
        self.search_notes_result = QLabel("")
        row3 = QHBoxLayout()
        row3.addWidget(self.search_notes)
        row3.addWidget(self.search_notes_result)
        search_layout.addRow("Por notas (parcial):", row3)

        for edit in (self.search_code, self.search_desc, self.search_notes):
            edit.textChanged.connect(self._run_searches)

        left_layout.addWidget(search_box)

        self.table = QTableWidget(TABLE_ROWS, FIELDS_PER_BLOCK * len(BLOCKS))
        self.table.setHorizontalHeaderLabels(FIELD_LABELS * len(BLOCKS))
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_cell_selected)
        # Filas compactas y sin numeración de fila (ya está la columna
        # "Posición") para que las 61 posiciones quepan sin hacer scroll.
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.setStyleSheet("QTableWidget { font-size: 12px; }")
        # Alto mínimo para que quepan las 27 filas + cabecera sin scroll.
        self.table.setMinimumHeight(TABLE_ROWS * 20 + 30)
        self._configure_column_widths()
        left_layout.addWidget(self.table)
        left_layout.addWidget(self._build_legend())

        splitter.addWidget(left)

        # --- Panel derecho: detalle de la posición seleccionada ---
        right = QWidget()
        right_layout = QVBoxLayout(right)

        self.position_label = QLabel("Selecciona una posición")
        self.position_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        right_layout.addWidget(self.position_label)

        self.detail_table = QTableWidget(0, len(DETAIL_COLUMNS))
        self.detail_table.setHorizontalHeaderLabels(DETAIL_COLUMNS)
        self.detail_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.detail_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        right_layout.addWidget(self.detail_table)

        add_box = QGroupBox("Añadir pieza a esta posición")
        add_layout = QFormLayout(add_box)
        self.add_code = QSpinBox()
        self.add_code.setRange(0, 99999)
        self.add_dims = QLineEdit()
        self.add_notes = QLineEdit()
        add_layout.addRow("Nº material:", self.add_code)
        add_layout.addRow("Medidas:", self.add_dims)
        add_layout.addRow("Notas:", self.add_notes)
        self.add_button = QPushButton("Añadir pieza")
        self.add_button.clicked.connect(self._on_add_piece)
        add_layout.addRow(self.add_button)
        right_layout.addWidget(add_box)

        actions = QHBoxLayout()
        self.delete_button = QPushButton("Borrar última pieza")
        self.delete_button.clicked.connect(self._on_delete_last_piece)
        actions.addWidget(self.delete_button)

        self.move_target = QSpinBox()
        self.move_target.setRange(1, 61)
        self.move_button = QPushButton("Mover pieza visible a posición →")
        self.move_button.clicked.connect(self._on_move_piece)
        actions.addWidget(self.move_button)
        actions.addWidget(self.move_target)
        right_layout.addLayout(actions)

        splitter.addWidget(right)
        splitter.setSizes([1150, 420])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def _configure_column_widths(self):
        header = self.table.horizontalHeader()
        # Posición, Nº, Medidas, Notas, Piezas: ancho fijo y compacto.
        # Material: se estira para aprovechar el espacio sobrante.
        fixed_widths = [38, 55, None, 68, 55, 42]
        for block_idx in range(len(BLOCKS)):
            for field_idx, width in enumerate(fixed_widths):
                col = block_idx * FIELDS_PER_BLOCK + field_idx
                if width is None:
                    header.setSectionResizeMode(col, QHeaderView.Stretch)
                else:
                    header.setSectionResizeMode(col, QHeaderView.Fixed)
                    self.table.setColumnWidth(col, width)

    def _build_legend(self) -> QWidget:
        """Leyenda de la escala de color por ocupación (columna 'Posición')."""
        legend = QWidget()
        row = QHBoxLayout(legend)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Ocupación:"))
        steps = [
            ("#FFFFFF", "1 pieza"),
            ("#FFF2CC", "2"),
            ("#C6E0B4", "3"),
            ("#B4C6E7", "4"),
            ("#FF0000", "5 (llena)"),
        ]
        for color, text in steps:
            swatch = QLabel(f"  {text}  ")
            swatch.setStyleSheet(
                f"background-color: {color}; border: 1px solid #999; border-radius: 3px;"
                + ("color: white;" if color == "#FF0000" else "color: black;")
            )
            row.addWidget(swatch)
        row.addSpacing(16)
        warn = QLabel("Texto rojo = material distinto mezclado en la posición")
        warn.setStyleSheet("color: #c62828;")
        row.addWidget(warn)
        row.addStretch()
        return legend

    # ------------------------------------------------------------------ #
    def refresh_board(self):
        # Primero deja todas las celdas en blanco y no seleccionables (las
        # 20 filas del bloque de posiciones 55-61 sólo llegan hasta la 7).
        for r in range(TABLE_ROWS):
            for c in range(self.table.columnCount()):
                item = QTableWidgetItem("")
                item.setFlags(Qt.NoItemFlags)
                self.table.setItem(r, c, item)

        for entry in self.repo.get_board():
            row, col0 = _position_to_cell(entry["position"])
            values = [
                entry["position"],
                entry["material_code"] if entry["material_code"] is not None else "",
                entry["material_desc"] or "",
                entry["dimensions"] or "",
                entry["notes"] or "",
                entry["piece_count"],
            ]
            fill = QColor(entry["fill_color"])
            # El fondo rojo (posición llena) necesita texto blanco para
            # seguir siendo legible.
            fill_text_color = QColor(Qt.white) if entry["fill_color"] == "#FF0000" else QColor(Qt.black)

            for field_idx, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                item.setData(Qt.UserRole, entry["position"])
                if field_idx == 0:
                    item.setBackground(fill)
                    item.setForeground(fill_text_color)
                if entry["inconsistent"]:
                    if field_idx != 0:
                        item.setForeground(QColor("#c62828"))
                    item.setToolTip("Esta posición tiene más de un material distinto entre sus piezas.")
                elif field_idx == 2 and entry["material_desc"]:
                    item.setToolTip(entry["material_desc"])
                self.table.setItem(row, col0 + field_idx, item)

        self._run_searches()
        if self.selected_position:
            self._select_position_cell(self.selected_position)
            self._load_detail(self.selected_position)

    def _select_position_cell(self, position: int):
        row, col0 = _position_to_cell(position)
        self.table.setCurrentCell(row, col0)

    def _on_cell_selected(self):
        item = self.table.currentItem()
        if item is None:
            return
        position = item.data(Qt.UserRole)
        if position is None:
            return
        self.selected_position = position
        self._load_detail(position)

    def _load_detail(self, position: int):
        self.position_label.setText(f"Posición {position} — detalle (hasta 5 piezas)")
        detail = self.repo.get_position_detail(position)
        self.detail_table.setRowCount(len(detail))
        for r, p in enumerate(detail):
            values = [
                p["slot"],
                p["material_code"],
                p["material_desc"] or "",
                p["dimensions"] or "",
                p["notes"] or "",
                p["entered_at"] or "",
            ]
            for c, v in enumerate(values):
                self.detail_table.setItem(r, c, QTableWidgetItem(str(v)))

    # ------------------------------------------------------------------ #
    def _on_add_piece(self):
        if self.selected_position is None:
            QMessageBox.warning(self, "Sin posición", "Selecciona primero una posición en la tabla.")
            return
        position = self.selected_position
        code = self.add_code.value()
        dims = self.add_dims.text().strip()
        notes = self.add_notes.text().strip()

        try:
            self.repo.add_piece(position, code, dims, notes)
        except DuplicateMaterialError as exc:
            resp = QMessageBox.question(
                self,
                "Material duplicado",
                "Este material ya está en la(s) posición(es): "
                + ", ".join(str(p) for p in exc.positions)
                + "\n\n¿Confirmas añadirlo de todas formas?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if resp == QMessageBox.Yes:
                try:
                    self.repo.add_piece(position, code, dims, notes, confirm_duplicate=True)
                except RuleViolation as exc2:
                    QMessageBox.critical(self, "Error", str(exc2))
                    return
            else:
                return
        except (PositionFullError, RuleViolation) as exc:
            QMessageBox.critical(self, "No se puede añadir", str(exc))
            return

        self.add_code.setValue(0)
        self.add_dims.clear()
        self.add_notes.clear()
        self.refresh_board()
        self.data_changed.emit()

    def _on_delete_last_piece(self):
        if self.selected_position is None:
            return
        detail = self.repo.get_position_detail(self.selected_position)
        if not detail:
            QMessageBox.information(self, "Sin piezas", "Esta posición está vacía.")
            return
        last = max(detail, key=lambda p: p["slot"])
        resp = QMessageBox.question(
            self,
            "Confirmar borrado",
            f"¿Estás seguro de que quieres borrar la posición {self.selected_position}?\n\n"
            f"Nº {last['material_code']} — {last['material_desc']}",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        try:
            self.repo.delete_piece(self.selected_position, last["slot"])
        except RuleViolation as exc:
            QMessageBox.critical(self, "No se puede borrar", str(exc))
            return
        self.refresh_board()
        self.data_changed.emit()

    def _on_move_piece(self):
        if self.selected_position is None:
            return
        target = self.move_target.value()
        try:
            result = self.repo.move_piece(self.selected_position, target)
        except RuleViolation as exc:
            QMessageBox.critical(self, "No se puede mover", str(exc))
            return
        QMessageBox.information(
            self,
            "Pieza movida",
            f"Material {result['piece']['material_code']} — {result['piece']['material_desc']}\n"
            f"trasladado de la posición {self.selected_position} a la {target}.",
        )
        self.refresh_board()
        self.data_changed.emit()

    # ------------------------------------------------------------------ #
    # Campo del tablero que se resalta por cada buscador (igual que el
    # original pintaba B/G/L para M20, C/H/M para M22, E/J/O para M24).
    _SEARCH_FIELD = {"code": 1, "description": 2, "notes": 4}
    _SEARCH_COLOR = {
        "code": QColor("#ffe08a"),
        "description": QColor("#a8e6a1"),
        "notes": QColor("#9fd3ff"),
    }
    # Columnas que llevan el color fijo de ocupación (una por bloque); nunca
    # se tocan al pintar/limpiar resaltados de búsqueda.
    _POSITION_COLUMNS = {block_idx * FIELDS_PER_BLOCK for block_idx in range(len(BLOCKS))}

    def _run_searches(self):
        self._clear_highlight()
        self._run_one_search(self.search_code, "code", self.search_code_result)
        self._run_one_search(self.search_desc, "description", self.search_desc_result)
        self._run_one_search(self.search_notes, "notes", self.search_notes_result)

    def _run_one_search(self, edit: QLineEdit, mode: str, label: QLabel):
        query = edit.text()
        if not query.strip():
            label.setText("")
            return
        result = self.repo.search(query, mode=mode)
        oldest = result["oldest_position"]
        text = f"{result['count']} coincidencia(s) · más antigua: pos. {oldest if oldest else '—'}"
        if result["desmagatzem_qty"]:
            text += f" · {result['desmagatzem_qty']} ud(s) en Desmagatzem"
        label.setText(text)
        positions = {m["position"] for m in result["matches"]}
        self._highlight_field(positions, self._SEARCH_FIELD[mode], self._SEARCH_COLOR[mode])

    def _clear_highlight(self):
        transparent = QColor(Qt.transparent)
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                if c in self._POSITION_COLUMNS:
                    continue
                item = self.table.item(r, c)
                if item is not None:
                    item.setBackground(transparent)

    def _highlight_field(self, positions: set[int], field_idx: int, color: QColor):
        for pos in positions:
            row, col0 = _position_to_cell(pos)
            item = self.table.item(row, col0 + field_idx)
            if item is not None:
                item.setBackground(color)
