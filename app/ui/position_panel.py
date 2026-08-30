"""Panell de detall d'una posició: fins a 5 peces, alta, baixa i trasllat.

Abans (`PositionDialog`) era una finestra emergent que s'obria en fer doble
clic. Ara és un `QWidget` incrustat de manera permanent DINS de la pròpia
taula del Tauler: el 3r bloc de columnes (posicions 55-61) només fa servir
7 de les 27 files, així que la resta de l'espai d'aquell bloc (a la dreta
de tot) es fusiona amb `QTableWidget.setSpan` i s'hi incrusta aquest
panell amb `setCellWidget` (veure `BoardTab._build_ui`). Com que no s'afegeix
cap fila nova enlloc, la taula de 61 posicions mai canvia de mida.

L'alta d'una peça ja no es fa amb un formulari a part: s'escriu el núm.
de material directament a la primera fila buida de la taula de detall i
Enter va encadenant els camps de la mateixa fila (Núm. → Mides → Notes;
des de Notes, a la línia següent); el trasllat continua tenint el seu
propi botó.

La baixa només es pot fer sobre l'ÚLTIMA peça de la posició (mateixa
regla que `rules.can_delete_slot`, el 'ORDRE INCORRECTE' de l'original).
Hi ha dues maneres de demanar-la i totes dues comparteixen la mateixa
comprovació (`_last_piece_row`, rellegida sempre de la base de dades):

  - Botó "Esborrar", al costat del de trasllat: desactivat mentre la fila
    seleccionada no sigui l'última peça.
  - Menú contextual (botó dret) sobre una fila: l'opció d'esborrar només
    surt activada a l'última peça; a les primeres surt deshabilitada.
  - Tecles Delete i Retrocés (la tecla "delete" dels teclats Mac), quan
    la taula no està editant cap cel·la.

Els tres criden `_on_delete_last_piece`: la confirmació, el refresc i
l'avís al Tauler es fan en un sol lloc.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
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
from app.ui import dialogs

_PANEL_STYLE = """
QFrame#positionPanel {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 8px;
}
"""


class _CellEditDelegate(QStyledItemDelegate):
    """Editor en línia d'una columna de la taula de detall.

    - Limita el text que s'hi pot escriure (Núm.: 6 xifres; Notes: 8
      caràcters). `max_length=None` vol dir sense límit (Mides).
    - Avisa amb `enter_pressed(fila, columna)` quan s'hi ha premut Enter,
      perquè el panell decideixi on va el focus tot seguit (Mides → Notes
      de la mateixa fila, Notes → la línia següent), en comptes del salt
      per defecte de Qt. El senyal s'emet DESPRÉS de deixar que Qt desi i
      tanqui l'editor com sempre, així el valor escrit no es perd.
    """

    enter_pressed = Signal(int, int)

    def __init__(self, max_length: int | None = None, parent=None):
        super().__init__(parent)
        self._max_length = max_length

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit) and self._max_length is not None:
            editor.setMaxLength(self._max_length)
        # De quina cel·la és aquest editor: dins d'eventFilter ja no hi ha
        # l'índex, i cal saber-ho per dir on ha d'anar el focus després.
        editor.setProperty("_cell_row", index.row())
        editor.setProperty("_cell_col", index.column())
        return editor

    def eventFilter(self, editor, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            row = editor.property("_cell_row")
            col = editor.property("_cell_col")
            handled = super().eventFilter(editor, event)
            if row is not None and col is not None:
                self.enter_pressed.emit(row, col)
            return handled
        return super().eventFilter(editor, event)


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
        # Títol de la posició, el text més gran del panell: és el que diu
        # de quina posició s'està parlant.
        self.title_label.setStyleSheet("font-weight: 700; font-size: 19px; color: #1a1a1a;")
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
        # Sempre les 5 files senceres i sense scroll: l'alçada ja es fixa
        # exactament a `_fit_detail_table_height`, però sense això Qt hi
        # podia mostrar una barra vertical/horitzontal per un arrodoniment
        # d'un parell de píxels.
        self.detail_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.detail_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
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
        # Un delegat per columna editable: Núm. màxim 6 xifres
        # (rules.MATERIAL_CODE_MAX = 999999), Notes màxim 8 caràcters,
        # Mides sense límit. Tots tres avisen quan s'hi prem Enter, perquè
        # el focus vagi al camp següent (`_on_editor_enter`).
        for col, max_length in (
            (self._DETAIL_CODE_COL, 6),
            (self._DETAIL_DIMS_COL, None),
            (self._DETAIL_NOTES_COL, 8),
        ):
            delegate = _CellEditDelegate(max_length, self.detail_table)
            delegate.enter_pressed.connect(self._on_editor_enter)
            self.detail_table.setItemDelegateForColumn(col, delegate)
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

        # Botó dret sobre una fila: opció d'esborrar la peça, activada
        # només a l'última (a les primeres hi surt deshabilitada).
        self.detail_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.detail_table.customContextMenuRequested.connect(self._show_detail_context_menu)

        # Delete i Retrocés = esborrar l'última peça. Són dues tecles
        # diferents (a Windows, Supr i Retrocés; als teclats Mac, la tecla
        # gran de sobre Retorn envia Retrocés i "fn+delete" envia Delete),
        # i totes dues han de fer el mateix. Amb context WidgetShortcut
        # només salten quan té el focus la taula, no un editor de cel·la
        # obert; la comprovació d'EditingState de `_on_delete_shortcut` ho
        # torna a assegurar, perquè Retrocés no s'endugui mai la peça
        # sencera mentre s'edita el text de Mides/Notes.
        self._delete_shortcuts = []
        for key in (Qt.Key_Delete, Qt.Key_Backspace):
            shortcut = QShortcut(QKeySequence(key), self.detail_table)
            shortcut.setContext(Qt.WidgetShortcut)
            shortcut.activated.connect(self._on_delete_shortcut)
            self._delete_shortcuts.append(shortcut)

        # Botons compactes: menys padding que el QPushButton global.
        # Botons compactes, però amb la lletra una mica més gran que abans
        # (10 -> 12 px) per llegir-los millor sense inflar-los.
        compact_button_style = "padding: 3px 10px; font-size: 12px;"

        move_row = QHBoxLayout()
        move_row.setSpacing(3)
        # (la separació concreta entre Esborrar i Moure es posa més avall)
        # Esborrar, a l'esquerra de Moure: fa exactament el mateix que la
        # tecla Delete i que el menú del botó dret (`_on_delete_last_piece`,
        # que ja demana confirmació, refresca i emet `changed`) — aquí no
        # es repeteix res d'aquella lògica. Surt desactivat i només s'activa
        # quan la fila seleccionada és l'última peça (`_can_delete_row`).
        # Paperera a l'esquerra del text, amb el mateix sistema d'icones que
        # la resta de l'aplicació (emoji dins del text del botó).
        self.delete_button = QPushButton(f"🗑️  {t('position.delete_button')}")
        self.delete_button.setStyleSheet(compact_button_style)
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._on_delete_last_piece)
        # S'activa/desactiva segons quina fila queda seleccionada.
        self.detail_table.currentCellChanged.connect(self._on_current_cell_changed)
        self.move_target = QSpinBox()
        self.move_target.setRange(1, 61)
        self.move_button = QPushButton(t("position.move_button"))
        self.move_button.setStyleSheet(compact_button_style)
        self.move_button.clicked.connect(self._on_move_piece)
        move_row.addWidget(self.delete_button, 0)
        # Una mica d'aire entre Esborrar i Moure: són dues accions molt
        # diferents i enganxades es podien confondre en clicar.
        move_row.addSpacing(12)
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

    def _on_editor_enter(self, row: int, col: int):
        """Enter dins d'un editor de cel·la: cap on va el focus tot seguit.

        Núm. → Mides ja ho fa `_on_code_cell_edited` en donar d'alta la
        peça, així que aquí només cal tractar les altres dues columnes:

          - Mides → Notes de la MATEIXA fila: acaba l'edició de Mides i
            continua a Notes (Qt, per defecte, baixaria de fila).
          - Notes → la línia següent (les Notes de la fila de sota).

        Es passa per un QTimer a 0 perquè Qt desa i tanca l'editor amb una
        crida en cua: obrint el següent editor ara mateix, aquell
        tancament se l'enduria pel davant.
        """
        if col == self._DETAIL_DIMS_COL:
            QTimer.singleShot(0, lambda: self._start_editing(row, self._DETAIL_NOTES_COL))
        elif col == self._DETAIL_NOTES_COL:
            QTimer.singleShot(0, lambda: self._go_to_next_notes_row(row))

    def _go_to_next_notes_row(self, row: int):
        """Notes + Enter: salta a les Notes de la línia següent. Si aquella
        línia encara no té peça (les seves Notes no són editables), només
        s'hi deixa el cursor i no s'obre cap editor."""
        next_row = row + 1
        if next_row >= self.detail_table.rowCount():
            return
        self.detail_table.setCurrentCell(next_row, self._DETAIL_NOTES_COL)
        self._start_editing(next_row, self._DETAIL_NOTES_COL)

    def _on_current_cell_changed(self, row, column, previous_row, previous_column):
        self._update_delete_button()

    def _update_delete_button(self):
        """El botó Esborrar només s'activa quan la fila seleccionada és
        l'última peça de la posició — exactament la mateixa condició que fa
        servir el menú del botó dret (`_can_delete_row`)."""
        self.delete_button.setEnabled(self._can_delete_row(self.detail_table.currentRow()))

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
        self._update_delete_button()

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
        self._update_delete_button()

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
        code = (code or "").strip()
        if not code:
            return  # s'ha buidat la cel·la sense escriure-hi res
        detail = self.repo.get_position_detail(self.position)
        if row != len(detail):
            self.refresh()  # per seguretat: només la primera fila buida hi val
            return

        # PRIMER de tot: això que s'hi ha escrit, és un número? Només s'hi
        # admeten números positius (1, 25, 99999...); ni 0, ni negatius, ni
        # lletres. Es comprova ABANS de buscar res a la base de dades, així
        # un text que per casualitat hi coincidís no se saltaria la
        # validació.
        if not rules.is_valid_material_code(code):
            dialogs.warn(
                self, t("position.invalid_code.title"), t("position.invalid_code.text", code=code)
            )
            self.refresh()
            self._start_editing(row, self._DETAIL_CODE_COL)  # per corregir-lo
            return
        code_number = int(float(code))

        # I DESPRÉS, ja sabent que és un número: avís (no bloquejant) si no
        # existeix al catàleg; es pot continuar igualment i la peça s'hi
        # afegeix amb el material en blanc.
        if self.repo.lookup_material(code_number) == rules.EMPTY_MATERIAL_MARK:
            dialogs.warn(
                self,
                t("position.material_not_found.title"),
                t("position.material_not_found.text", code=code_number),
            )

        try:
            self.repo.add_piece(self.position, code_number, dimensions="", notes="")
        except DuplicateMaterialError as exc:
            if dialogs.confirm(
                self,
                t("position.duplicate.title"),
                t("position.duplicate.text", positions=", ".join(str(p) for p in exc.positions)),
            ):
                try:
                    self.repo.add_piece(
                        self.position, code_number, dimensions="", notes="", confirm_duplicate=True
                    )
                except RuleViolation as exc2:
                    dialogs.error(self, t("common.error"), str(exc2))
                    self.refresh()
                    return
            else:
                self.refresh()
                return
        except (PositionFullError, RuleViolation) as exc:
            dialogs.error(self, t("position.cannot_add"), str(exc))
            self.refresh()
            return

        self.refresh()
        self.changed.emit()
        # Un cop escrit el núm. i fet Retorn, salta directament a Mides de
        # la mateixa fila per poder-les editar tot seguit.
        self._start_editing(row, self._DETAIL_DIMS_COL)

    def _last_piece_row(self) -> int | None:
        """Fila de l'ÚLTIMA peça de la posició (None si la posició és buida).

        És l'única fila des d'on es pot esborrar, i es rellegeix sempre de
        la base de dades (mai d'una còpia en memòria): així la restricció
        segueix sent correcta encara que la posició hagi canviat entremig
        —alta, baixa, o un trasllat des d'una altra posició, que renumera
        els slots— sense dependre de quan es va pintar la taula.

        `get_position_detail` retorna les peces ordenades per slot i
        `refresh()` col·loca detail[r] a la fila r, així que l'última peça
        (la de slot més alt, l'única que `rules.can_delete_slot` deixa
        esborrar) és sempre la de la fila len(detail) - 1.
        """
        if self.position is None:
            return None
        detail = self.repo.get_position_detail(self.position)
        if not detail:
            return None
        return len(detail) - 1

    def _can_delete_row(self, row: int) -> bool:
        """Només l'última peça de la posició es pot esborrar (la resta de
        files —les primeres peces i les buides— no)."""
        last_row = self._last_piece_row()
        return last_row is not None and row == last_row

    def _build_delete_menu(self, row: int) -> QMenu:
        """Menú del botó dret d'una fila: una sola opció, esborrar la peça,
        activada només si aquella fila és l'última peça. A les altres hi
        surt igualment, però deshabilitada i amb el motiu al tooltip —
        així es veu que l'opció existeix i per què no s'hi pot fer."""
        menu = QMenu(self.detail_table)
        menu.setToolTipsVisible(True)
        delete_action = menu.addAction(t("position.delete_action"))
        delete_action.setEnabled(self._can_delete_row(row))
        if not delete_action.isEnabled():
            delete_action.setToolTip(t("position.only_last.text"))
        return menu

    def _show_detail_context_menu(self, pos):
        index = self.detail_table.indexAt(pos)
        if not index.isValid():
            return
        menu = self._build_delete_menu(index.row())
        # Una sola opció al menú: si exec() en retorna alguna, és aquella
        # (una de deshabilitada no es pot triar mai).
        if menu.exec(self.detail_table.viewport().mapToGlobal(pos)) is not None:
            self._on_delete_last_piece()

    def _on_delete_shortcut(self):
        # Ni Delete ni Retrocés han d'esborrar la peça mentre s'està
        # editant el text d'una cel·la (Mides/Notes, o el núm. d'una peça
        # nova): allà s'han d'aplicar al text, no a la peça sencera.
        if self.detail_table.state() == QAbstractItemView.EditingState:
            return
        last_row = self._last_piece_row()
        current_row = self.detail_table.currentRow()
        # Només l'última peça es pot esborrar: sobre una de les primeres
        # s'avisa, en lloc d'esborrar-ne una altra per sorpresa. Sobre una
        # fila buida (que no és cap peça, hi ha el cursor tot just carregar
        # la posició) la tecla segueix actuant sobre l'última, com fins ara.
        if last_row is not None and 0 <= current_row < last_row:
            dialogs.info(
                self, t("position.only_last.title"), t("position.only_last.text")
            )
            return
        self._on_delete_last_piece()

    def _on_delete_last_piece(self):
        # Sempre l'última peça (el slot ocupat més alt): és l'única que es
        # pot esborrar, igual que a l'Excel original.
        detail = self.repo.get_position_detail(self.position)
        if not detail:
            dialogs.info(self, t("position.no_pieces.title"), t("position.no_pieces.text"))
            return
        last = max(detail, key=lambda p: p["slot"])
        if not dialogs.confirm(
            self,
            t("position.confirm_delete.title"),
            t(
                "position.confirm_delete.text",
                position=self.position,
                code=last["material_code"],
                desc=last["material_desc"],
            ),
        ):
            return
        try:
            self.repo.delete_piece(self.position, last["slot"])
        except RuleViolation as exc:
            dialogs.error(self, t("position.cannot_delete"), str(exc))
            return
        self.refresh()
        self.changed.emit()

    def _on_move_piece(self):
        target = self.move_target.value()
        try:
            result = self.repo.move_piece(self.position, target)
        except RuleViolation as exc:
            dialogs.error(self, t("position.cannot_move"), str(exc))
            return
        dialogs.info(
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
