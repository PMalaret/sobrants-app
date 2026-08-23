"""Pestanya 'Tauler': equivalent a la fulla Hoja1 de l'Excel original.

El tauler es reparteix en 3 blocs de columnes un al costat de l'altre
(posicions 1-27, 28-54 i 55-61), igual que feia Hoja1 (blocs A:E, F:J i
K:O), perquè les 61 posicions es vegin totes alhora sense fer scroll i
la taula ocupi tot l'ample disponible.

El tauler SEMPRE té exactament 61 posicions (mai més, mai menys): el 3r
bloc (posicions 55-61) només fa servir 7 de les 27 files, així que la
resta d'aquell bloc (a la dreta de tot) queda en blanc. Aquest espai és
on s'incrusta el panell de detall de la posició seleccionada
(`PositionPanel`), amb `setSpan`/`setCellWidget` — DINS de la pròpia
taula, no en una fila a part. Així la taula no canvia mai de mida (no
guanya files buides) i les 61 posicions sempre es veuen senceres. La
llegenda de colors viu a la barra d'estat de la finestra
(`build_legend_widget`), per no robar espai vertical a la taula.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t
from app.logic.repository import Repository
from app.ui.position_panel import PositionPanel
from app.ui.search_dialog import SearchDialog

# (posició inicial, nombre de posicions) de cada bloc de columnes, igual que
# els blocs A/F/K de Hoja1.
BLOCKS = [(1, 27), (28, 27), (55, 7)]
FIELDS_PER_BLOCK = 5
TABLE_ROWS = max(count for _start, count in BLOCKS)

# El panell de detall de posició s'incrusta dins l'espai en blanc del 3r
# bloc (posicions 55-61: només 7 de les 27 files fan servei).
PANEL_BLOCK_IDX = 2
PANEL_COL0 = PANEL_BLOCK_IDX * FIELDS_PER_BLOCK
PANEL_ROW0 = BLOCKS[PANEL_BLOCK_IDX][1]  # primera fila lliure d'aquell bloc (7)
PANEL_ROW_COUNT = TABLE_ROWS - PANEL_ROW0


def _position_to_cell(position: int) -> tuple[int, int]:
    """Posició -> (fila, columna del camp 'Posició' del seu bloc)."""
    for block_idx, (start, count) in enumerate(BLOCKS):
        if start <= position < start + count:
            return position - start, block_idx * FIELDS_PER_BLOCK
    raise ValueError(f"Posició fora de rang: {position}")


class _BoardGridDelegate(QStyledItemDelegate):
    """Vores extra per llegir la graella d'un cop d'ull:
    - Vora esquerra més gruixuda a la columna "Posició" de cada bloc (marca
      on comença cada bloc de 5 camps).
    - Vora inferior una mica gruixuda (menys que l'anterior) cada 5 files,
      per poder comptar posicions de 5 en 5 sense haver de mirar el número.
    """

    _LEFT_COLOR = QColor("#6b7280")
    _LEFT_WIDTH = 3
    _BOTTOM_COLOR = QColor("#9aa0a8")
    _BOTTOM_WIDTH = 2

    def __init__(self, position_columns: set[int], parent=None):
        super().__init__(parent)
        self._position_columns = position_columns

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        rect = option.rect
        painter.save()
        if index.column() in self._position_columns:
            pen = QPen(self._LEFT_COLOR)
            pen.setWidth(self._LEFT_WIDTH)
            painter.setPen(pen)
            x = rect.left()
            painter.drawLine(x, rect.top(), x, rect.bottom())
        if (index.row() + 1) % 5 == 0:
            pen = QPen(self._BOTTOM_COLOR)
            pen.setWidth(self._BOTTOM_WIDTH)
            painter.setPen(pen)
            y = rect.bottom()
            painter.drawLine(rect.left(), y, rect.right(), y)
        painter.restore()


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
        # Marge mínim a totes bandes: la taula és l'únic widget d'aquesta
        # pestanya (els botons de cerca ara viuen dins del panell de
        # detall), així que s'estén fins a la barra d'estat de sota.
        layout.setContentsMargins(9, 3, 9, 3)

        field_labels = [
            t("board.field.position"),
            t("board.field.code"),
            t("board.field.material"),
            t("board.field.dimensions"),
            t("board.field.notes"),
        ]
        self.table = QTableWidget(TABLE_ROWS, FIELDS_PER_BLOCK * len(BLOCKS))
        self.table.setHorizontalHeaderLabels(field_labels * len(BLOCKS))
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellClicked.connect(self._on_cell_clicked)
        # Files compactes i sense numeració de fila (ja hi ha la columna
        # "Posició") perquè les 61 posicions càpiguen sense fer scroll.
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(20)
        # Capçalera més prima: es redueix el padding vertical de la secció,
        # no la mida de la lletra (que es queda igual, a 12px).
        self.table.setStyleSheet(
            "QTableWidget { font-size: 12px; }"
            "QHeaderView::section { font-size: 12px; padding: 1px 4px; }"
        )
        # El tauler sempre té exactament 61 posicions (mai més, mai menys),
        # però ara que la taula s'expandeix per ocupar l'espai vertical
        # sobrant, les files creixen (Stretch) en lloc d'aparèixer files
        # buides: mai canvia el nombre de files, només la seva alçada.
        exact_height = TABLE_ROWS * 20 + 40
        self.table.setMinimumHeight(exact_height)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._configure_column_widths()
        self.table.setItemDelegate(_BoardGridDelegate(self._POSITION_COLUMNS, self.table))

        # Panell de detall incrustat DINS de la taula, a l'espai en blanc
        # del 3r bloc (sota la posició 61, a la dreta de tot). setSpan fon
        # les cel·les buides en una de sola; setCellWidget hi incrusta el
        # panell. No s'afegeix cap fila nova: la taula segueix tenint
        # exactament TABLE_ROWS files sempre.
        self.position_panel = PositionPanel(self.repo)
        self.position_panel.changed.connect(self._on_position_changed)
        self.table.setSpan(PANEL_ROW0, PANEL_COL0, PANEL_ROW_COUNT, FIELDS_PER_BLOCK)
        self.table.setCellWidget(PANEL_ROW0, PANEL_COL0, self.position_panel)

        layout.addWidget(self.table)
        # Únic widget d'aquesta pestanya: s'estén (Expanding) fins a la
        # barra d'estat de sota, sense cap fila de botons pel mig.

        # Botons de cerca reubicats dins del panell de detall (a sota de
        # tot, separats amb una línia divisòria), no en una fila a part
        # sota la taula — així la taula arriba fins a la barra d'estat.
        # Botons compactes (padding reduït respecte al QPushButton global).
        _compact_button_style = "padding: 2px 12px; font-size: 12px;"
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.addStretch()
        self.clear_search_button = QPushButton(t("board.clear_search"))
        self.clear_search_button.setStyleSheet(_compact_button_style)
        self.clear_search_button.clicked.connect(self._clear_search)
        self.clear_search_button.setEnabled(False)
        search_row.addWidget(self.clear_search_button)
        self.search_button = QPushButton(t("board.search_button"))
        self.search_button.setStyleSheet(_compact_button_style)
        self.search_button.clicked.connect(self._open_search_dialog)
        search_row.addWidget(self.search_button)
        self.position_panel.add_footer(search_row)

        # Públic (no "_search_dialog"): MainWindow hi connecta el ressaltat
        # creuat de Desmagatzem (mateixos colors de cerca que el tauler).
        self.search_dialog = SearchDialog(self)
        self.search_dialog.search_changed.connect(self._on_search_changed)
        self.search_dialog.cleared.connect(self._on_search_cleared)
        self._search_state: dict[str, str] = {}

    def _configure_column_widths(self):
        header = self.table.horizontalHeader()
        # Totes les columnes són "Interactive": l'usuari pot eixamplar o
        # estrènyer qualsevol arrossegant la vora, i l'ample que triï es
        # queda fixat (Qt no el reinicia sol; refresh_board() no torna a
        # cridar aquest mètode). Material tenia abans un ample "Stretch"
        # que la feia excessivament ampla i no es podia redimensionar
        # manualment; ara té un ample per defecte contingut, i és Notes
        # (l'últim camp de cada bloc) qui absorbeix l'espai sobrant.
        initial_widths = [46, 62, 180, 80, None]
        for block_idx in range(len(BLOCKS)):
            for field_idx, width in enumerate(initial_widths):
                col = block_idx * FIELDS_PER_BLOCK + field_idx
                if width is None:
                    header.setSectionResizeMode(col, QHeaderView.Stretch)
                else:
                    header.setSectionResizeMode(col, QHeaderView.Interactive)
                    self.table.setColumnWidth(col, width)

    def build_legend_widget(self) -> QWidget:
        """Llegenda de l'escala de color per ocupació, per posar-la a la
        barra d'estat de la finestra (no ocupa espai damunt la taula)."""
        legend = QWidget()
        row = QHBoxLayout(legend)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel(f"{t('legend.title')}:"))
        steps = [
            ("#FFFFFF", t("legend.piece_1")),
            ("#FFF2CC", "2"),
            ("#C6E0B4", "3"),
            ("#B4C6E7", "4"),
            ("#FF0000", t("legend.piece_5")),
        ]
        for color, text in steps:
            swatch = QLabel(f" {text} ")
            swatch.setStyleSheet(
                f"background-color: {color}; border: 1px solid #999; border-radius: 3px;"
                + ("color: white;" if color == "#FF0000" else "color: black;")
            )
            row.addWidget(swatch)
        row.addSpacing(12)
        warn = QLabel(t("legend.warning"))
        warn.setStyleSheet("color: #c62828;")
        row.addWidget(warn)
        return legend

    # ------------------------------------------------------------------ #
    def refresh_board(self):
        # Primer deixa totes les cel·les en blanc i no seleccionables (el
        # bloc de posicions 55-61 només arriba fins a la fila 7), EXCEPTE
        # la regió del panell incrustat (setSpan/setCellWidget): no s'hi
        # torna a tocar mai, per no trencar el span ni el widget incrustat.
        for r in range(TABLE_ROWS):
            for c in range(self.table.columnCount()):
                if r >= PANEL_ROW0 and PANEL_COL0 <= c < PANEL_COL0 + FIELDS_PER_BLOCK:
                    continue
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
                    item.setToolTip(t("board.tooltip.inconsistent"))
                elif field_idx == 2 and entry["material_desc"]:
                    item.setToolTip(entry["material_desc"])
                self.table.setItem(row, col0 + field_idx, item)

        self._reapply_all_highlights()

        # Si hi ha una posició carregada al panell, la refresquem (p. ex.
        # després de moure-hi una peça des d'una altra posició).
        if self.position_panel.position is not None:
            self.position_panel.refresh()

    def _on_cell_clicked(self, row: int, column: int):
        item = self.table.item(row, column)
        if item is None:
            return
        position = item.data(Qt.UserRole)
        if position is None:
            return
        self.position_panel.load_position(position)

    def _on_position_changed(self):
        self.refresh_board()
        self.data_changed.emit()

    # ------------------------------------------------------------------ #
    # Cerca (diàleg)
    # ------------------------------------------------------------------ #
    def _open_search_dialog(self):
        self.search_dialog.show_and_focus()

    def _on_search_changed(self, mode: str, text: str):
        self._search_state[mode] = text
        self.clear_search_button.setEnabled(any(v.strip() for v in self._search_state.values()))
        self._run_search(mode, text)

    def _on_search_cleared(self):
        self._search_state = {}
        self.clear_search_button.setEnabled(False)
        self._reapply_all_highlights()

    def _clear_search(self):
        self.search_dialog.clear_all()

    def _reapply_all_highlights(self):
        self._clear_highlight()
        for mode, text in self._search_state.items():
            self._run_search(mode, text, update_label=False)

    def _run_search(self, mode: str, text: str, update_label: bool = True):
        self._clear_field_highlight(mode)
        if not text.strip():
            if update_label:
                self.search_dialog.set_result(mode, "—", "—", 0)
            return
        result = self.repo.search(text, mode=mode)
        oldest = result["oldest_position"]
        if update_label:
            self.search_dialog.set_result(
                mode, result["count"], oldest if oldest else "—", result["desmagatzem_qty"]
            )
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
