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
propi botó, que pregunta a quina posició va la peça.

La taula de detall ensenya SEMPRE les seves 5 línies (el màxim de peces
per posició), tingui peces o no: l'alçada es calcula perquè hi càpiguen
totes (`_fit_detail_table_height`) i no canvia amb el contingut, així la
interfície no es mou segons quantes peces hi hagi.

La baixa i el trasllat només es poden fer sobre l'ÚLTIMA peça de la
posició (mateixa regla que `rules.can_delete_slot`, el 'ORDRE INCORRECTE'
de l'original): els dos botons s'activen amb la mateixa comprovació
(`_can_delete_row`, feta en un sol lloc a `_update_action_buttons`).
La baixa es pot demanar de tres maneres i totes tres comparteixen la
mateixa comprovació (`_last_piece_row`, rellegida sempre de la base de
dades):

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
    QSizePolicy,
    QStackedWidget,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t
from app.logic import rules
from app.logic.repository import (
    BOARD_POSITIONS,
    DuplicateMaterialError,
    PositionFullError,
    Repository,
    RuleViolation,
)
from app.ui import dialogs, icons, theme

# Alçada de cada fila de la taula de detall. Ha de deixar respirar el text
# TAMBÉ mentre s'edita (quan Qt hi posa un camp a dins amb la seva vora):
# amb 20 px el que s'escrivia quedava escanyat. Deixar-la fixa és el que fa
# que el panell càpiga sencer (amb els botons de sota) sense haver de fer
# scroll, així que puja el mínim que fa falta, no més.
DETAIL_ROW_HEIGHT = 26
# Files de la taula de detall: sempre 5 (el màxim de peces per posició),
# tinguin dades o no.
DETAIL_ROWS = 5
# Separació entre la taula de detall i la fila d'Esborrar/Moure. Baixa una
# mica els botons (i tot el que ve a sota: el cercador i la zona d'accions)
# perquè les 5 línies mai quedin justes contra ells.
DETAIL_TABLE_BOTTOM_GAP = 6

_PANEL_STYLE = """
QFrame#positionPanel {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 10px;
}

/* Els contenidors de dins no pinten fons propi: el panell és una sola
   superfície blanca. Sense això, la regla general de QWidget els donava el
   gris de la finestra i el panell sortia a trossos —blanc on hi havia una
   taula i gris a la resta—, amb una franja grisa ben visible sota el
   cercador. Les taules i la franja d'accions sí que porten el seu color,
   perquè cadascuna té el seu propi full d'estil. */
QStackedWidget#positionStack,
QWidget#positionPage,
QWidget#boardFooter,
QWidget#boardSearch,
QWidget#boardSearch QWidget {
    background-color: transparent;
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
        # Última posició de destí triada al diàleg de trasllat, per no
        # haver-la de tornar a escriure si se'n mouen unes quantes seguides.
        self._last_move_target: int | None = None
        self.setObjectName("positionPanel")
        self.setStyleSheet(theme.css(_PANEL_STYLE))
        self.setFrameShape(QFrame.NoFrame)
        self._build_ui()

    def _build_ui(self):
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(8, 3, 8, 3)
        self._outer.setSpacing(3)

        self._stack = QStackedWidget()
        self._stack.setObjectName("positionStack")
        self._outer.addWidget(self._stack)

        placeholder = QLabel(t("position.panel.placeholder"))
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setWordWrap(True)
        placeholder.setStyleSheet(theme.css("color: $text_muted; font-size: 11px;"))
        self._stack.addWidget(placeholder)  # índex 0

        self._stack.addWidget(self._build_detail_page())  # índex 1

    def add_footer(self, widget: QWidget):
        """Afegeix un widget a sota de tot, fora de l'`_stack`, així es veu
        sempre (hi hagi o no una posició seleccionada) — s'hi incrusta el
        cercador del Tauler amb la seva zona d'accions, que ja es distingeix
        pel seu fons i no necessita cap línia divisòria."""
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
        page.setObjectName("positionPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.title_label = QLabel()
        # Títol de la posició, el text més gran del panell: és el que diu
        # de quina posició s'està parlant.
        self.title_label.setStyleSheet(
            theme.css("font-weight: 700; font-size: 19px; color: $text;")
        )
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
        self.detail_table = QTableWidget(DETAIL_ROWS, len(detail_columns))
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
        # Files d'alçada fixa: si es deixa que creixin amb el contingut,
        # cada fila es menja uns quants píxels de més i el panell no arriba
        # a encabir els botons de sota. Amb lletra de 10 px, 20 px de fila
        # van sobrats.
        self.detail_table.verticalHeader().setDefaultSectionSize(DETAIL_ROW_HEIGHT)
        # I que 20 px sigui de debò l'alçada de la fila: per defecte Qt no
        # deixa cap secció per sota d'un mínim que surt de la lletra del
        # sistema (uns 22-25 px), així que les files acabaven sent més
        # altes del que es donava per fet i la 5a línia no cabia dins de
        # l'alçada calculada — es veia tallada, o directament no es veia,
        # que és el que passava a les posicions amb poques peces.
        self.detail_table.verticalHeader().setMinimumSectionSize(DETAIL_ROW_HEIGHT)
        self.detail_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        # Lletra petita i capçalera compacta: aquesta taula ha d'encabir
        # sempre les seves 5 línies dins del panell, que té l'alçada
        # comptada (veure `_fit_detail_table_height`).
        self.detail_table.setStyleSheet(
            theme.css("QTableWidget { font-size: 11px; }"
                      "QHeaderView::section { font-size: 11px; padding: 2px 4px;"
                      " border-bottom: 1px solid $border; }")
        )
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
        # Una mica d'aire entre la taula de detall i els botons de sota:
        # separa les 5 línies (que sempre hi són, amb peces o sense) de les
        # accions, i deixa clar que la 5a línia buida encara forma part de
        # la taula i no és un espai perdut.
        layout.addSpacing(DETAIL_TABLE_BOTTOM_GAP)

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

        move_row = QHBoxLayout()
        move_row.setSpacing(2)
        # (la separació concreta entre Esborrar i Moure es posa més avall)
        # Esborrar, a l'esquerra de Moure: fa exactament el mateix que la
        # tecla Delete i que el menú del botó dret (`_on_delete_last_piece`,
        # que ja demana confirmació, refresca i emet `changed`) — aquí no
        # es repeteix res d'aquella lògica. Surt desactivat i només s'activa
        # quan la fila seleccionada és l'última peça (`_can_delete_row`).
        # Paperera a l'esquerra del text, amb el mateix sistema d'icones que
        # la resta de l'aplicació (emoji dins del text del botó).
        self.delete_button = QPushButton(t("position.delete_button"))
        self.delete_button.setProperty("compact", "true")
        icons.apply_to(self.delete_button, "delete")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._on_delete_last_piece)
        # S'activa/desactiva segons quina fila queda seleccionada.
        self.detail_table.currentCellChanged.connect(self._on_current_cell_changed)
        # El trasllat: la posició de destí no s'escriu en un número al
        # costat, es demana amb un diàleg en clicar el botó
        # (`_on_move_piece`), així no hi ha cap número posat per omissió
        # esperant que algú el premi sense mirar-lo.
        self.move_button = QPushButton(t("position.move_button"))
        self.move_button.setProperty("compact", "true")
        icons.apply_to(self.move_button, "move")
        # Igual que Esborrar: surt desactivat i només s'activa quan la fila
        # seleccionada és l'última peça de la posició (`_can_delete_row`).
        self.move_button.setEnabled(False)
        self.move_button.clicked.connect(self._on_move_piece)
        # L'ample del botó s'ajusta al seu text, no s'estira.
        self.move_button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

        # Esborrar a una banda i el trasllat a l'altra, amb tot l'espai
        # sobrant entremig: són dues accions molt diferents i enganxades es
        # podien confondre en clicar.
        move_row.addWidget(self.delete_button, 0)
        move_row.addStretch(1)
        move_row.addWidget(self.move_button, 0)
        layout.addLayout(move_row)
        # Sense stretch aquí: l'espai sobrant s'ha de quedar tot avall de
        # tot el panell (sota el de cerca), no just després del trasllat.
        return page

    def _fit_detail_table_height(self):
        """Alçada exacta per a capçalera + les 5 files, sempre.

        Les files es fixen a `DETAIL_ROW_HEIGHT`: si es deixa que creixin
        amb el contingut, cada fila s'endú uns quants píxels de més i el
        panell ja no arriba a encabir els botons que van a sota. De la
        capçalera i del marc sí que se'n mesura l'alçada real, que depèn de
        la lletra i de l'estil de cada plataforma.

        De la capçalera es pren la MÉS GRAN entre l'alçada que té ara i la
        que demana (`sizeHint`): la primera vegada que es crida —mentre es
        construeix el panell— encara no s'ha disposat res i `height()` pot
        anar curta; quedar-se curt aquí voldria dir tallar l'última línia
        de la taula, que és justament la que ha de continuar veient-se
        encara que no tingui cap peça.

        I de les files se'n suma l'alçada REAL, la que han acabat tenint
        després de demanar-la, no la que se'ls ha demanat: així, si Qt no
        les deixés baixar de cap mínim seu, l'alçada de la taula creix amb
        elles i les 5 línies hi continuen cabent senceres.
        """
        for row in range(self.detail_table.rowCount()):
            self.detail_table.setRowHeight(row, DETAIL_ROW_HEIGHT)
        header = self.detail_table.horizontalHeader()
        header_h = max(header.height(), header.sizeHint().height())
        rows_h = sum(self.detail_table.rowHeight(row) for row in range(DETAIL_ROWS))
        frame = 2 * self.detail_table.frameWidth()
        self.detail_table.setFixedHeight(header_h + rows_h + frame)

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
        if next_free_row < DETAIL_ROWS:
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
        """Enter des de Notes: on va el cursor depèn de si la línia següent
        ja existeix o no.

          - Si ja hi ha una peça a la línia de sota, el cursor va a les
            seves MIDES: la peça ja té núm. i material, el que toca és
            continuar-la d'omplir.
          - Si encara no n'hi ha cap, la línia següent és la que està a
            punt de crear-se: el cursor va al seu NÚM., que és per on
            comença una peça nova (i no es crea res fins que s'hi escriu,
            amb les mateixes validacions de sempre).
        """
        next_row = row + 1
        if next_row >= self.detail_table.rowCount():
            return  # ja s'és a l'última línia de la posició
        pieces = len(self.repo.get_position_detail(self.position)) if self.position else 0
        column = self._DETAIL_DIMS_COL if next_row < pieces else self._DETAIL_CODE_COL
        self.detail_table.setCurrentCell(next_row, column)
        self._start_editing(next_row, column)

    def _on_current_cell_changed(self, row, column, previous_row, previous_column):
        self._update_action_buttons()

    def _update_action_buttons(self):
        """Esborrar i Moure només s'activen quan la fila seleccionada és
        l'última peça de la posició — exactament la mateixa condició que fa
        servir el menú del botó dret (`_can_delete_row`), en un sol lloc
        per als dos botons.

        Les dues accions treballen sobre la mateixa peça (l'última de la
        posició), així que no tindria sentit que una es pogués fer des
        d'una fila des d'on l'altra no. Mentre estan desactivats, el
        tooltip diu per què.
        """
        enabled = self._can_delete_row(self.detail_table.currentRow())
        for button in (self.delete_button, self.move_button):
            button.setEnabled(enabled)
            button.setToolTip("" if enabled else t("position.move.only_last.tooltip"))

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
        self._update_action_buttons()

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
        self.detail_table.setRowCount(DETAIL_ROWS)
        next_free_row = len(detail)  # primera fila buida: hi accepta un núm. nou
        for r in range(DETAIL_ROWS):
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
        self._update_action_buttons()

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

    def _default_move_target(self) -> int:
        """Número que surt escrit al diàleg de destí: l'últim que s'hi va
        fer servir (és habitual moure unes quantes peces al mateix lloc)
        i, la primera vegada, la primera posició del tauler. Mai la
        posició on és ara la peça, que no és un destí vàlid: en aquest cas
        se'n proposa una altra."""
        first, last = min(BOARD_POSITIONS), max(BOARD_POSITIONS)
        target = self._last_move_target if self._last_move_target is not None else first
        if target == self.position:
            target = last if self.position == first else first
        return target

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
        delete_action.setIcon(icons.icon("delete", "text"))
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
        """Trasllat de la peça: primer es demana a quina posició ha d'anar.

        La posició de destí es tria en un diàleg (`dialogs.ask_int`, el
        mateix estil que la resta de diàlegs de l'aplicació, amb els botons
        traduïts) i, un cop triada, es continua exactament pel camí de
        sempre: confirmació, `Repository.move_piece` —que és qui treu la
        peça, la col·loca i escriu les dues línies d'històric— i refresc.
        Aquí no hi ha cap lògica de moviment pròpia. Si es cancel·la el
        diàleg no es toca res.
        """
        if self.position is None:
            return
        target, chosen = dialogs.ask_int(
            self,
            t("position.move.ask.title"),
            t("position.move.ask.label", from_pos=self.position),
            value=self._default_move_target(),
            minimum=min(BOARD_POSITIONS),
            maximum=max(BOARD_POSITIONS),
        )
        if not chosen:
            return
        # Moure una peça de lloc no es desfà: primer es pregunta. El
        # diàleg és el mateix de tota l'aplicació (`dialogs.confirm`, amb
        # Cancel·lar per defecte), i si es cancel·la no es toca res.
        piece = rules.board_summary_piece(self.repo.get_position_detail(self.position))
        if not dialogs.confirm(
            self,
            t("position.confirm_move.title"),
            t(
                "position.confirm_move.text",
                code=piece["material_code"] if piece else "—",
                desc=piece["material_desc"] if piece else "—",
                from_pos=self.position,
                to_pos=target,
            ),
        ):
            return
        try:
            result = self.repo.move_piece(self.position, target)
        except RuleViolation as exc:
            dialogs.error(self, t("position.cannot_move"), str(exc))
            return
        self._last_move_target = target
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
