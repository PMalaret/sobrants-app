"""Pestanya 'Tauler': equivalent a la fulla Hoja1 de l'Excel original.

El tauler es reparteix en 3 blocs de columnes un al costat de l'altre
(posicions 1-27, 28-54 i 55-61), igual que feia Hoja1 (blocs A:E, F:J i
K:O), perquè les 61 posicions es vegin totes alhora sense fer scroll i
la taula ocupi tot l'ample disponible.

La cerca i el detall d'una posició (abans panells fixos) ara són un botó
+ diàleg, per deixar tot l'ample per a la taula.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.logic.repository import Repository
from app.ui.position_dialog import PositionDialog
from app.ui.search_dialog import SearchDialog

FIELD_LABELS = ["Posició", "Núm. material", "Material", "Mides", "Notes", "Peces"]

# (posició inicial, nombre de posicions) de cada bloc de columnes, igual que
# els blocs A/F/K de Hoja1.
BLOCKS = [(1, 27), (28, 27), (55, 7)]
FIELDS_PER_BLOCK = len(FIELD_LABELS)
TABLE_ROWS = max(count for _start, count in BLOCKS)


def _position_to_cell(position: int) -> tuple[int, int]:
    """Posició -> (fila, columna del camp 'Posició' del seu bloc)."""
    for block_idx, (start, count) in enumerate(BLOCKS):
        if start <= position < start + count:
            return position - start, block_idx * FIELDS_PER_BLOCK
    raise ValueError(f"Posició fora de rang: {position}")


class BoardTab(QWidget):
    data_changed = Signal()

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build_ui()
        self.refresh_board()

    # ------------------------------------------------------------------ #
    def _build_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.search_button = QPushButton("🔍 Cercar…")
        self.search_button.clicked.connect(self._open_search_dialog)
        toolbar.addWidget(self.search_button)
        self.clear_search_button = QPushButton("Netejar cerca")
        self.clear_search_button.clicked.connect(self._clear_search)
        self.clear_search_button.setEnabled(False)
        toolbar.addWidget(self.clear_search_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Doble clic sobre una posició per veure'n el detall, afegir o moure peces"))
        layout.addLayout(toolbar)

        self.table = QTableWidget(TABLE_ROWS, FIELDS_PER_BLOCK * len(BLOCKS))
        self.table.setHorizontalHeaderLabels(FIELD_LABELS * len(BLOCKS))
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        # Files compactes i sense numeració de fila (ja hi ha la columna
        # "Posició") perquè les 61 posicions càpiguen sense fer scroll.
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setStyleSheet("QTableWidget { font-size: 13px; }")
        self.table.setMinimumHeight(TABLE_ROWS * 22 + 32)
        self._configure_column_widths()
        layout.addWidget(self.table)
        layout.addWidget(self._build_legend())

        self._search_dialog = SearchDialog(self)
        self._search_dialog.search_changed.connect(self._on_search_changed)
        self._search_dialog.cleared.connect(self._on_search_cleared)
        self._search_state: dict[str, str] = {}

    def _configure_column_widths(self):
        header = self.table.horizontalHeader()
        # Posició, Núm., Mides, Notes, Peces: ample fix i compacte.
        # Material: s'estira per aprofitar l'espai sobrant de la pantalla.
        fixed_widths = [46, 62, None, 80, 65, 48]
        for block_idx in range(len(BLOCKS)):
            for field_idx, width in enumerate(fixed_widths):
                col = block_idx * FIELDS_PER_BLOCK + field_idx
                if width is None:
                    header.setSectionResizeMode(col, QHeaderView.Stretch)
                else:
                    header.setSectionResizeMode(col, QHeaderView.Fixed)
                    self.table.setColumnWidth(col, width)

    def _build_legend(self) -> QWidget:
        """Llegenda de l'escala de color per ocupació (columna 'Posició')."""
        legend = QWidget()
        row = QHBoxLayout(legend)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Ocupació:"))
        steps = [
            ("#FFFFFF", "1 peça"),
            ("#FFF2CC", "2"),
            ("#C6E0B4", "3"),
            ("#B4C6E7", "4"),
            ("#FF0000", "5 (plena)"),
        ]
        for color, text in steps:
            swatch = QLabel(f"  {text}  ")
            swatch.setStyleSheet(
                f"background-color: {color}; border: 1px solid #999; border-radius: 3px;"
                + ("color: white;" if color == "#FF0000" else "color: black;")
            )
            row.addWidget(swatch)
        row.addSpacing(16)
        warn = QLabel("Text vermell = material diferent barrejat a la posició")
        warn.setStyleSheet("color: #c62828;")
        row.addWidget(warn)
        row.addStretch()
        return legend

    # ------------------------------------------------------------------ #
    def refresh_board(self):
        # Primer deixa totes les cel·les en blanc i no seleccionables (el
        # bloc de posicions 55-61 només arriba fins a la fila 7).
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
            # El fons vermell (posició plena) necessita text blanc per
            # seguir sent llegible.
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
                    item.setToolTip("Aquesta posició té més d'un material diferent entre les seves peces.")
                elif field_idx == 2 and entry["material_desc"]:
                    item.setToolTip(entry["material_desc"])
                self.table.setItem(row, col0 + field_idx, item)

        self._reapply_all_highlights()

    def _on_cell_double_clicked(self, row: int, column: int):
        item = self.table.item(row, column)
        if item is None:
            return
        position = item.data(Qt.UserRole)
        if position is None:
            return
        dialog = PositionDialog(self.repo, position, self)
        dialog.changed.connect(self._on_position_changed)
        dialog.exec()

    def _on_position_changed(self):
        self.refresh_board()
        self.data_changed.emit()

    # ------------------------------------------------------------------ #
    # Cerca (diàleg)
    # ------------------------------------------------------------------ #
    def _open_search_dialog(self):
        self._search_dialog.show_and_focus()

    def _on_search_changed(self, mode: str, text: str):
        self._search_state[mode] = text
        self.clear_search_button.setEnabled(any(v.strip() for v in self._search_state.values()))
        self._run_search(mode, text)

    def _on_search_cleared(self):
        self._search_state = {}
        self.clear_search_button.setEnabled(False)
        self._reapply_all_highlights()

    def _clear_search(self):
        self._search_dialog.clear_all()

    def _reapply_all_highlights(self):
        self._clear_highlight()
        for mode, text in self._search_state.items():
            self._run_search(mode, text, update_label=False)

    def _run_search(self, mode: str, text: str, update_label: bool = True):
        self._clear_field_highlight(mode)
        if not text.strip():
            if update_label:
                self._search_dialog.set_result_text(mode, "")
            return
        result = self.repo.search(text, mode=mode)
        oldest = result["oldest_position"]
        label = f"{result['count']} coincidència(es) · més antiga: posc. {oldest if oldest else '—'}"
        if result["desmagatzem_qty"]:
            label += f" · {result['desmagatzem_qty']} ud(s) a Desmagatzem"
        if update_label:
            self._search_dialog.set_result_text(mode, label)
        positions = {m["position"] for m in result["matches"]}
        self._highlight_field(positions, self._SEARCH_FIELD[mode], self._SEARCH_COLOR[mode])

    # Camp del tauler que es ressalta per a cada cercador (igual que
    # l'original pintava B/G/L per M20, C/H/M per M22, E/J/O per M24).
    _SEARCH_FIELD = {"code": 1, "description": 2, "notes": 4}
    _SEARCH_COLOR = {
        "code": QColor("#ffe08a"),
        "description": QColor("#a8e6a1"),
        "notes": QColor("#9fd3ff"),
    }
    # Columnes amb el color fix d'ocupació (una per bloc); mai es toquen en
    # pintar/netejar ressaltats de cerca.
    _POSITION_COLUMNS = {block_idx * FIELDS_PER_BLOCK for block_idx in range(len(BLOCKS))}

    def _clear_highlight(self):
        transparent = QColor(Qt.transparent)
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                if c in self._POSITION_COLUMNS:
                    continue
                item = self.table.item(r, c)
                if item is not None:
                    item.setBackground(transparent)

    def _clear_field_highlight(self, mode: str):
        field_idx = self._SEARCH_FIELD[mode]
        transparent = QColor(Qt.transparent)
        for block_idx in range(len(BLOCKS)):
            col = block_idx * FIELDS_PER_BLOCK + field_idx
            for r in range(self.table.rowCount()):
                item = self.table.item(r, col)
                if item is not None:
                    item.setBackground(transparent)

    def _highlight_field(self, positions: set[int], field_idx: int, color: QColor):
        for pos in positions:
            row, col0 = _position_to_cell(pos)
            item = self.table.item(row, col0 + field_idx)
            if item is not None:
                item.setBackground(color)
