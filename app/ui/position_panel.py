"""Panell de detall d'una posició: fins a 5 peces, alta, baixa i trasllat.

Abans (`PositionDialog`) era una finestra emergent que s'obria en fer doble
clic. Ara és un `QWidget` incrustat de manera permanent DINS de la pròpia
taula del Tauler: el 3r bloc de columnes (posicions 55-61) només fa servir
7 de les 27 files, així que la resta de l'espai d'aquell bloc (a la dreta
de tot) es fusiona amb `QTableWidget.setSpan` i s'hi incrusta aquest
panell amb `setCellWidget` (veure `BoardTab._build_ui`). Com que no s'afegeix
cap fila nova enlloc, la taula de 61 posicions mai canvia de mida.

L'alta d'una peça ja no es fa amb un formulari a part: s'escriu el núm.
de material directament a la primera fila buida de la taula de detall
(la resta de camps s'omplen sols/s'editen després en línia); la baixa
és la tecla Delete (sempre l'última peça, com abans); el trasllat
continua tenint el seu propi botó.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t
from app.logic import rules
from app.logic.repository import DuplicateMaterialError, PositionFullError, Repository, RuleViolation

_PANEL_STYLE = """
QFrame#positionPanel {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 8px;
}
"""


class _MaxLengthDelegate(QStyledItemDelegate):
    """Limita el text que s'hi pot escriure (Notes: màxim 8 caràcters)."""

    def __init__(self, max_length: int, parent=None):
        super().__init__(parent)
        self._max_length = max_length

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setMaxLength(self._max_length)
        return editor


class PositionPanel(QFrame):
    """Emet `changed()` cada vegada que es modifiquen dades, perquè el Tauler
    refresqui la taula principal."""

    changed = Signal()

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.position: int | None = None
        self.setObjectName("positionPanel")
        self.setStyleSheet(_PANEL_STYLE)
        self.setFrameShape(QFrame.NoFrame)
        self._build_ui()

    def _build_ui(self):
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(8, 6, 8, 6)
        self._outer.setSpacing(4)

        self._stack = QStackedWidget()
        self._outer.addWidget(self._stack)

        placeholder = QLabel(t("position.panel.placeholder"))
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setWordWrap(True)
        placeholder.setStyleSheet("color: #8a8f98; font-size: 11px;")
        self._stack.addWidget(placeholder)  # índex 0

        self._stack.addWidget(self._build_detail_page())  # índex 1

    def add_footer(self, widget: QWidget):
        """Afegeix un widget a sota de tot, separat amb una línia divisòria.
        Fora de l'`_stack`, així es veu sempre (hi hagi o no una posició
        seleccionada) — s'hi incrusta el panell de cerca del Tauler."""
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        self._outer.addWidget(separator)
        self._outer.addWidget(widget)
        # Que l'espai sobrant (si el bloc del tauler és més alt del que cal)
        # quedi tot avall de tot, sota el panell de cerca — no com un buit
        # entre el detall de la posició i el panell de cerca.
        self._outer.addStretch()

    def _build_detail_page(self) -> QWidget:
        # Disposició vertical i compacta: aquest panell viu incrustat dins
        # l'ample d'un sol bloc de columnes del tauler (el 3r, posicions
        # 55-61), no dins tot l'ample de la finestra.
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-weight: 700; font-size: 15px; color: #1a1a1a;")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        # L'ordre (slot) segueix important internament — get_position_detail
        # continua retornant les peces ordenades per slot, i encara és qui
        # decideix quina és "l'última peça" a esborrar — però ja no es
        # mostra com a columna a la taula (com tampoc "Entrada").
        detail_columns = [
            t("board.field.code"),
            t("board.field.material"),
            t("board.field.dimensions"),
            t("board.field.notes"),
        ]
        self._DETAIL_CODE_COL, self._DETAIL_MATERIAL_COL, self._DETAIL_DIMS_COL, self._DETAIL_NOTES_COL = range(4)
        self.detail_table = QTableWidget(5, len(detail_columns))
        self.detail_table.setHorizontalHeaderLabels(detail_columns)
        # Només Mides i Notes són editables (i només quan l'slot té un
        # material). Un sol clic ja obre l'editor (via `cellClicked`, més
        # avall) — `EditKeyPressed` es manté per poder-hi entrar també amb
        # el teclat (F2/Retorn) sense haver de clicar.
        self.detail_table.setEditTriggers(QAbstractItemView.EditKeyPressed)
        self.detail_table.cellClicked.connect(self._on_detail_cell_clicked)
        self.detail_table.itemChanged.connect(self._on_detail_item_changed)
        self.detail_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.detail_table.verticalHeader().setVisible(False)
        self.detail_table.verticalHeader().setDefaultSectionSize(18)
        self.detail_table.setStyleSheet("font-size: 10px;")
        # Núm.: màxim 6 xifres (rules.MATERIAL_CODE_MAX = 999999). Notes:
        # màxim 8 caràcters.
        self.detail_table.setItemDelegateForColumn(
            self._DETAIL_CODE_COL, _MaxLengthDelegate(6, self.detail_table)
        )
        self.detail_table.setItemDelegateForColumn(
            self._DETAIL_NOTES_COL, _MaxLengthDelegate(8, self.detail_table)
        )
        # Núm./Mides/Notes: ample inicial ajustat, però "Interactive"
        # (l'usuari els pot canviar i es queden fixats). Material: s'estira
        # perquè les columnes aprofitin tot l'ample que té el panell (que
        # ja és el just i necessari).
        detail_header = self.detail_table.horizontalHeader()
        detail_widths = [55, None, 62, 90]
        for col, width in enumerate(detail_widths):
            if width is None:
                detail_header.setSectionResizeMode(col, QHeaderView.Stretch)
            else:
                detail_header.setSectionResizeMode(col, QHeaderView.Interactive)
                self.detail_table.setColumnWidth(col, width)
        layout.addWidget(self.detail_table)
        # 5 files sempre visibles (el màxim possible per posició), mai
        # scroll intern: mesurat en viu (no amb una xifra fixa en pixels),
        # perquè l'alçada real de la lletra varia segons la plataforma.
        self._fit_detail_table_height()

        # Tecla Delete = esborrar l'última peça (igual que abans el botó
        # "Esborrar última peça"). Només quan la taula NO està editant una
        # cel·la (si no, Delete s'hauria d'aplicar al text que s'edita).
        self._delete_shortcut = QShortcut(QKeySequence(Qt.Key_Delete), self.detail_table)
        self._delete_shortcut.setContext(Qt.WidgetShortcut)
        self._delete_shortcut.activated.connect(self._on_delete_shortcut)

        # Botons compactes: menys padding que el QPushButton global.
        compact_button_style = "padding: 2px 8px; font-size: 10px;"

        move_row = QHBoxLayout()
        move_row.setSpacing(3)
        self.move_target = QSpinBox()
        self.move_target.setRange(1, 61)
        self.move_button = QPushButton(t("position.move_button"))
        self.move_button.setStyleSheet(compact_button_style)
        self.move_button.clicked.connect(self._on_move_piece)
        move_row.addWidget(self.move_button, 1)
        move_row.addWidget(self.move_target)
        layout.addLayout(move_row)
        # Sense stretch aquí: l'espai sobrant s'ha de quedar tot avall de
        # tot el panell (sota el de cerca), no just després del trasllat.
        return page

    def _fit_detail_table_height(self):
        """Alçada exacta per a capçalera + 5 files, sense marge de seguretat
        arbitrari: es mesura l'alçada real (depèn de la lletra de cada
        plataforma), no s'assumeix un valor fix en pixels."""
        header_h = self.detail_table.horizontalHeader().height()
        row_h = self.detail_table.rowHeight(0)
        self.detail_table.setFixedHeight(header_h + row_h * 5 + 2)

    # ------------------------------------------------------------------ #
    def load_position(self, position: int):
        self.position = position
        self.title_label.setText(t("position.subtitle", position=position))
        self.refresh()
        self._stack.setCurrentIndex(1)
        # En canviar de posició, s'arma directament per escriure-hi el
        # següent núm. de material (si n'hi ha, cap fila buida si és plena):
        # amb 2 peces ja fetes, s'arma la 3a; amb 4, la 5a.
        next_free_row = len(self.repo.get_position_detail(position))
        if next_free_row < 5:
            self._start_editing(next_free_row, self._DETAIL_CODE_COL)

    def _start_editing(self, row: int, col: int):
        item = self.detail_table.item(row, col)
        if item is not None and (item.flags() & Qt.ItemIsEditable):
            self.detail_table.setCurrentCell(row, col)
            self.detail_table.editItem(item)

    def _on_detail_cell_clicked(self, row: int, col: int):
        # Un sol clic ja obre l'editor (Mides/Notes d'una peça existent, o
        # el núm. de material de la primera fila buida).
        self._start_editing(row, col)

    def clear_selection(self):
        self.position = None
        self._stack.setCurrentIndex(0)

    def refresh(self):
        if self.position is None:
            return
        detail = self.repo.get_position_detail(self.position)
        # Sempre 5 files (el màxim de peces per posició), tingui dades o
        # no: així la graella es veu sencera igual buida que plena, no
        # només quan hi ha 5 peces.
        # Bloquejem senyals mentre l'omplim: si no, cada setItem dispara
        # itemChanged i intentaria desar-ho com si l'usuari ho hagués
        # editat (a més de ser innecessari, petaria a les files buides).
        self.detail_table.blockSignals(True)
        self.detail_table.setRowCount(5)
        next_free_row = len(detail)  # primera fila buida: hi accepta un núm. nou
        for r in range(5):
            occupied = r < len(detail)
            if occupied:
                p = detail[r]
                values = [p["material_code"], p["material_desc"] or "", p["dimensions"] or "", p["notes"] or ""]
            else:
                values = [""] * self.detail_table.columnCount()
            for c, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
                if occupied and c in (self._DETAIL_DIMS_COL, self._DETAIL_NOTES_COL):
                    # Mides i Notes són editables sempre que l'slot tingui
                    # material; Núm./Material no s'editen mai un cop assignats.
                    flags |= Qt.ItemIsEditable
                elif not occupied and c == self._DETAIL_CODE_COL and r == next_free_row:
                    # Alta d'una peça nova: només la primera fila buida
                    # accepta escriure-hi un núm. de material directament.
                    flags |= Qt.ItemIsEditable
                item.setFlags(flags)
                self.detail_table.setItem(r, c, item)
        self.detail_table.blockSignals(False)
        self._fit_detail_table_height()

    def _on_detail_item_changed(self, item):
        if self.position is None:
            return
        col = item.column()
        row = item.row()
        if col == self._DETAIL_CODE_COL:
            self._on_code_cell_edited(row, item.text().strip())
            return
        if col not in (self._DETAIL_DIMS_COL, self._DETAIL_NOTES_COL):
            return
        code_item = self.detail_table.item(row, self._DETAIL_CODE_COL)
        if code_item is None or not code_item.text():
            return  # slot buit: mai s'hauria de poder arribar aquí
        field = "dimensions" if col == self._DETAIL_DIMS_COL else "notes"
        self.repo.update_piece_field(self.position, slot=row + 1, field=field, value=item.text().strip())
        self.changed.emit()

    def _on_code_cell_edited(self, row: int, code: str):
        """Alta d'una peça nova: s'escriu el núm. de material directament a
        la primera fila buida de la taula (Mides/Notes es poden omplir
        després, editant-les en línia un cop la peça ja existeix)."""
        if not code:
            return  # s'ha buidat la cel·la sense escriure-hi res
        detail = self.repo.get_position_detail(self.position)
        if row != len(detail):
            self.refresh()  # per seguretat: només la primera fila buida hi val
            return

        # Avís (no bloquejant) si el número no existeix al catàleg: es pot
        # continuar igualment, la peça s'afegeix amb el material en blanc.
        if self.repo.lookup_material(code) == rules.EMPTY_MATERIAL_MARK:
            QMessageBox.warning(
                self, t("position.material_not_found.title"), t("position.material_not_found.text", code=code)
            )

        try:
            self.repo.add_piece(self.position, code, dimensions="", notes="")
        except DuplicateMaterialError as exc:
            resp = QMessageBox.question(
                self,
                t("position.duplicate.title"),
                t("position.duplicate.text", positions=", ".join(str(p) for p in exc.positions)),
                QMessageBox.Yes | QMessageBox.No,
            )
            if resp == QMessageBox.Yes:
                try:
                    self.repo.add_piece(self.position, code, dimensions="", notes="", confirm_duplicate=True)
                except RuleViolation as exc2:
                    QMessageBox.critical(self, t("common.error"), str(exc2))
                    self.refresh()
                    return
            else:
                self.refresh()
                return
        except (PositionFullError, RuleViolation) as exc:
            QMessageBox.critical(self, t("position.cannot_add"), str(exc))
            self.refresh()
            return

        self.refresh()
        self.changed.emit()
        # Un cop escrit el núm. i fet Retorn, salta directament a Mides de
        # la mateixa fila per poder-les editar tot seguit.
        self._start_editing(row, self._DETAIL_DIMS_COL)

    def _on_delete_shortcut(self):
        # La tecla Delete no ha d'esborrar la peça mentre s'està editant el
        # text d'una cel·la (Mides/Notes, o el núm. d'una peça nova): en
        # aquest cas Delete s'ha d'aplicar al text, no a la peça sencera.
        if self.detail_table.state() == QAbstractItemView.EditingState:
            return
        self._on_delete_last_piece()

    def _on_delete_last_piece(self):
        # Sempre l'última peça (el slot ocupat més alt): és l'única que es
        # pot esborrar, igual que a l'Excel original.
        detail = self.repo.get_position_detail(self.position)
        if not detail:
            QMessageBox.information(self, t("position.no_pieces.title"), t("position.no_pieces.text"))
            return
        last = max(detail, key=lambda p: p["slot"])
        resp = QMessageBox.question(
            self,
            t("position.confirm_delete.title"),
            t(
                "position.confirm_delete.text",
                position=self.position,
                code=last["material_code"],
                desc=last["material_desc"],
            ),
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        try:
            self.repo.delete_piece(self.position, last["slot"])
        except RuleViolation as exc:
            QMessageBox.critical(self, t("position.cannot_delete"), str(exc))
            return
        self.refresh()
        self.changed.emit()

    def _on_move_piece(self):
        target = self.move_target.value()
        try:
            result = self.repo.move_piece(self.position, target)
        except RuleViolation as exc:
            QMessageBox.critical(self, t("position.cannot_move"), str(exc))
            return
        QMessageBox.information(
            self,
            t("position.moved.title"),
            t(
                "position.moved.text",
                code=result["piece"]["material_code"],
                desc=result["piece"]["material_desc"],
                from_pos=self.position,
                to_pos=target,
            ),
        )
        self.refresh()
        self.changed.emit()
