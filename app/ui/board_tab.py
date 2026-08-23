"""Pestaña 'Tablero': equivalente a la hoja Hoja1 del Excel original."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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

BOARD_COLUMNS = ["Posición", "Nº material", "Material", "Medidas", "Notas", "Piezas"]
DETAIL_COLUMNS = ["Slot", "Nº material", "Material", "Medidas", "Notas", "Entrada"]


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

        self.table = QTableWidget(0, len(BOARD_COLUMNS))
        self.table.setHorizontalHeaderLabels(BOARD_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        left_layout.addWidget(self.table)

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
        splitter.setSizes([650, 400])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    # ------------------------------------------------------------------ #
    def refresh_board(self):
        board = self.repo.get_board()
        self.table.setRowCount(len(board))
        for r, row in enumerate(board):
            values = [
                row["position"],
                row["material_code"] if row["material_code"] is not None else "",
                row["material_desc"] or "",
                row["dimensions"] or "",
                row["notes"] or "",
                row["piece_count"],
            ]
            for c, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                item.setData(Qt.UserRole, row["position"])
                self.table.setItem(r, c, item)
        self._run_searches()
        if self.selected_position:
            self._select_position_row(self.selected_position)
            self._load_detail(self.selected_position)

    def _select_position_row(self, position: int):
        for r in range(self.table.rowCount()):
            if int(self.table.item(r, 0).text()) == position:
                self.table.selectRow(r)
                return

    def _on_row_selected(self):
        items = self.table.selectedItems()
        if not items:
            return
        position = int(items[0].text()) if items[0].column() == 0 else int(self.table.item(items[0].row(), 0).text())
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
    # Columna del tablero que se resalta por cada buscador (igual que el
    # original pintaba B/G/L para M20, C/H/M para M22, E/J/O para M24).
    _SEARCH_COLUMN = {"code": 1, "description": 2, "notes": 4}
    _SEARCH_COLOR = {
        "code": QColor("#ffe08a"),
        "description": QColor("#a8e6a1"),
        "notes": QColor("#9fd3ff"),
    }

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
        label.setText(f"{result['count']} coincidencia(s) · más antigua: pos. {oldest if oldest else '—'}")
        positions = {m["position"] for m in result["matches"]}
        self._highlight_column(positions, self._SEARCH_COLUMN[mode], self._SEARCH_COLOR[mode])

    def _clear_highlight(self):
        transparent = QColor(Qt.transparent)
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                self.table.item(r, c).setBackground(transparent)

    def _highlight_column(self, positions: set[int], column: int, color: QColor):
        for r in range(self.table.rowCount()):
            pos = int(self.table.item(r, 0).text())
            if pos in positions:
                self.table.item(r, column).setBackground(color)
