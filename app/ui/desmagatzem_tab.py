"""Pestanya 'Desmagatzem': retirada de peces per carro/lot.

Els cercadors del Tauler (M20/M22/M24 a l'Excel original) també pintaven
les cel·les coincidents de la fulla desmagatzem amb el mateix color del
cercador (`BuscaCoincidenciesDesmagatzem_Q20/M22/M24`); aquí es reprodueix
exactament igual, reutilitzant els mateixos colors que el cercador
(`theme.search_qcolor`) — mai es crea una paleta nova.

L'ordenació es fa clicant la capçalera de cada columna (mode natiu de
QTableWidget, alterna ascendent/descendent), no amb botons a part. Per
defecte surt ordenat per Data ascendent (la més antiga primer).
"""
from __future__ import annotations

from contextlib import contextmanager

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import format_number, t
from app.logic import rules
from app.logic.repository import Repository, RuleViolation
from app.logic.rules import quantity_change_kind
from app.export import ReportCell
from app.ui import dialogs, icons, theme


# Amples del formulari de nova entrada, calculats sobre el que pot valer
# cada camp: núm. de material fins a 6 xifres (rules.MATERIAL_CODE_MAX),
# quantitat de 0 a 20 i notes de 8 caràcters com a màxim.
_CODE_MAX_CHARS = 6
_CODE_WIDTH = 70
_QTY_WIDTH = 60
_DIMS_WIDTH = 95
_NOTES_WIDTH = 110
# Alçada de les files de la taula: prou per llegir-les bé amb la lletra de
# 13 px, i prou justa per veure'n unes quantes més d'un cop d'ull.
DESMAGATZEM_ROW_HEIGHT = 26


class _MaxLengthDelegate(QStyledItemDelegate):
    """Limita el text que s'hi pot escriure en editar la cel·la (Notes: el
    mateix màxim que el camp del formulari)."""

    def __init__(self, max_length: int, parent=None):
        super().__init__(parent)
        self._max_length = max_length

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        # La mateixa lletra que la cel·la (veure `theme.font_size_css`).
        editor.setStyleSheet(theme.font_size_css(option.font))
        if isinstance(editor, QLineEdit):
            editor.setMaxLength(self._max_length)
        return editor


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
    # Perquè l'Històric es refresqui sol quan aquí s'hi escriu (les altes i
    # els canvis de quantitat hi deixen línies): ja no hi ha cap botó
    # d'actualitzar a l'Històric.
    data_changed = Signal()
    # Imprimir la taula: el botó és aquí, però el flux d'impressió comú
    # segueix a `MainWindow._print_desmagatzem`.
    print_requested = Signal()

    # Columna de la taula (Quantitat, Núm., Material, Mides, Carro/lot, Data)
    # que ressalta cada cercador — igual que B/C/E a la fulla desmagatzem
    # original per a M20/M22/M24 respectivament.
    _SEARCH_COLUMN = {"code": 1, "description": 2, "notes": 4}
    # Les úniques dues columnes que es poden editar des de la taula, i el
    # camp de la base de dades de cadascuna. La resta (quantitat, núm. de
    # material, descripció i data) tenen les seves pròpies regles i es
    # queden de només lectura.
    _EDITABLE_COLUMNS = {3: "dimensions", 4: "cart_ref"}
    _SEARCH_FIELD = {"code": "material_code", "description": "material_desc", "notes": "cart_ref"}
    _DATE_COL = 5

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._search_state: dict[str, str] = {}
        # Cert mentre és l'aplicació qui toca la taula (omplir-la, pintar-hi
        # els ressaltats de cerca...). Sense això, cada `setBackground` es
        # prendria per una edició de l'usuari i tornaria a desar i refrescar.
        self._updating = False
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

    def _confirm_text(self, current_qty: int, new_qty: int):
        """Text de la confirmació, amb les dues quantitats de debò (la que
        hi ha ara i la que s'hi posarà), en negreta perquè es vegin d'un
        cop d'ull. Els valors surten sempre de la línia i del que ha
        escrit l'usuari, mai d'un exemple."""
        quantities = t("desmagatzem.confirm.quantities", current=current_qty, new=new_qty)
        return {
            "increase": quantities + t("desmagatzem.confirm.increase"),
            "decrease": quantities + t("desmagatzem.confirm.decrease"),
            "delete": quantities + t("desmagatzem.confirm.delete"),
        }

    def _configure_column_widths(self):
        # Totes les columnes "Interactive" (redimensionables arrossegant la
        # vora), sense cap "Stretch": una columna en mode "Stretch" no es
        # pot redimensionar manualment (Qt en controla l'ample per omplir
        # l'espai sobrant), i totes s'han de poder canviar de mida.
        header = self.table.horizontalHeader()
        # Quantitat, Núm. material, Material, Mides, Notes, Data. El núm. de
        # material té 6 xifres i el títol de la columna és llarg: amb 80 px
        # es retallava la capçalera.
        widths = [70, 105, 200, 90, 200, 150]
        for col, width in enumerate(widths):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
            self.table.setColumnWidth(col, width)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 3, 9, 9)  # marge superior mínim, taula enganxada a les pestanyes

        # Tot el formulari en UNA sola fila: etiqueta + camp, un darrere
        # l'altre, i el botó al final. Els amples surten del que pot valer
        # cada camp de debò (núm. de material fins a 6 xifres, quantitat
        # 0-20, notes 8 caràcters), no d'un valor per omissió: així no
        # sobra espai enlloc i tot hi cap sense passar a una segona línia.
        # L'únic que s'estira és la descripció del material, que és
        # l'únic camp de llargada lliure.
        form_box = QGroupBox(t("desmagatzem.form_title"))
        # Aquest apartat, ben arrapat: és una sola fila de camps i no li
        # calen els 14+10 px de marge intern que el full d'estil dóna a
        # qualsevol QGroupBox (pensats per a caixes de diverses línies).
        # Només aquesta caixa —el full general no es toca, que l'altra
        # QGroupBox de l'aplicació (Estadístiques) sí que en té, de línies.
        form_box.setStyleSheet("QGroupBox { padding: 6px 12px 6px 12px; }")
        form = QHBoxLayout(form_box)
        form.setSpacing(6)
        # I sense el marge que Qt posa per omissió a tot layout (9 px per
        # banda): amunt i avall se suma al de la caixa i el fa el doble de
        # gruixut del que sembla. Als costats, el de la caixa ja hi és.
        form.setContentsMargins(0, 0, 0, 0)

        self.code_input = QLineEdit()
        self.code_input.setMaxLength(_CODE_MAX_CHARS)
        self.code_input.setFixedWidth(_CODE_WIDTH)
        # L'ajuda sencera al tooltip: dins d'un camp d'aquest ample no hi
        # cabria, i l'etiqueta del costat ja diu què hi va.
        self.code_input.setToolTip(t("desmagatzem.code_placeholder"))

        self.custom_text_input = QLineEdit()
        self.custom_text_input.setPlaceholderText(t("desmagatzem.custom_placeholder"))
        self.custom_text_input.setToolTip(t("desmagatzem.custom_placeholder"))

        self.qty_input = QSpinBox()
        # 0-20: el límit de sempre de la fulla desmagatzem
        # (`rules.is_valid_desmagatzem_qty`), que no es toca.
        self.qty_input.setRange(rules.DESMAGATZEM_QTY_MIN, rules.DESMAGATZEM_QTY_MAX)
        self.qty_input.setFixedWidth(_QTY_WIDTH)

        self.dims_input = QLineEdit()
        self.dims_input.setFixedWidth(_DIMS_WIDTH)

        self.cart_input = QLineEdit()
        # 15 caràcters com a màxim: el propi camp ja no en deixa escriure ni
        # enganxar més, i el repositori hi torna a aplicar el mateix límit
        # (`rules.truncate_desmagatzem_notes`) abans de desar.
        self.cart_input.setMaxLength(rules.DESMAGATZEM_NOTES_MAX_CHARS)
        self.cart_input.setFixedWidth(_NOTES_WIDTH)
        self.cart_input.setToolTip(t("desmagatzem.cart_placeholder"))

        for label_key, widget, stretch in (
            ("desmagatzem.field.code", self.code_input, 0),
            ("desmagatzem.field.custom", self.custom_text_input, 1),
            ("desmagatzem.field.quantity", self.qty_input, 0),
            ("desmagatzem.field.dimensions", self.dims_input, 0),
            ("desmagatzem.field.cart", self.cart_input, 0),
        ):
            form.addWidget(QLabel(t(label_key)))
            form.addWidget(widget, stretch)

        self.add_button = QPushButton(t("desmagatzem.add_button"))
        # Botó normal, el mateix que "Imprimir desmagatzem" del peu de la
        # pestanya: són les dues accions de la pantalla i s'han de veure
        # igual d'importants. L'alçada que costa surt del marge de la
        # caixa, que s'ha aprimat aquí sobre.
        self.add_button.clicked.connect(self._on_add_row)
        form.addWidget(self.add_button)
        layout.addWidget(form_box)

        # Enter passa al camp següent, d'esquerra a dreta, i al final de la
        # fila desa la línia (el mateix que el botó) i torna al principi:
        # es pot anar entrant material rere material sense tocar el ratolí.
        self._enter_chain = [
            self.code_input,
            self.custom_text_input,
            self.qty_input,
            self.dims_input,
            self.cart_input,
        ]
        for position, widget in enumerate(self._enter_chain):
            line_edit = widget.lineEdit() if isinstance(widget, QSpinBox) else widget
            if widget is self.code_input:
                # El núm. de material no salta sense més: primer es mira
                # al catàleg (veure `_on_code_entered`).
                line_edit.returnPressed.connect(self._on_code_entered)
            elif position + 1 < len(self._enter_chain):
                next_widget = self._enter_chain[position + 1]
                line_edit.returnPressed.connect(lambda w=next_widget: self._focus_field(w))
            else:
                line_edit.returnPressed.connect(self._on_add_row)

        # Si es torna a tocar el núm., la descripció que s'hi hagués
        # recuperat ja no hi val: es buida i es torna a deixar escriure.
        self.code_input.textEdited.connect(self._on_code_edited)

        columns = self._columns()
        self.table = QTableWidget(0, len(columns))
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels(columns)
        # Pista discreta que aquestes dues es poden editar (només a la
        # pantalla: el que s'imprimeix fa servir `_columns()`, sense marca).
        for col in self._EDITABLE_COLUMNS:
            header_item = self.table.horizontalHeaderItem(col)
            header_item.setText(f"{columns[col]} \u270e")
            header_item.setToolTip(t("desmagatzem.editable_hint"))
        self._configure_column_widths()
        self.table.horizontalHeader().setSortIndicatorShown(True)
        # Només Mides i Notes són editables (els seus ítems porten el
        # flag; la resta, no). Un sol clic ja obre l'editor, com a la taula
        # de detall del Tauler, i Retorn/Escapada fan el de sempre.
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )
        # Editant Notes dins de la taula, el mateix límit que al formulari.
        self.table.setItemDelegateForColumn(
            4, _MaxLengthDelegate(rules.DESMAGATZEM_NOTES_MAX_CHARS, self.table)
        )
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # Files una mica més justes (30 -> 26 px): amb la lletra de 13 px hi
        # van bé i s'hi veuen dues o tres línies més de cop, que en aquesta
        # pestanya és el que es demana.
        self.table.verticalHeader().setDefaultSectionSize(DESMAGATZEM_ROW_HEIGHT)
        # Sense la línia de sota que la regla `QHeaderView` del full d'estil
        # posa per tancar la capçalera horitzontal: aquesta taula és
        # l'única que ensenya els números de fila, i allà aquella línia
        # cauria al capdavall de la columna dels números, on no separa res.
        self.table.verticalHeader().setStyleSheet("QHeaderView { border: none; }")
        layout.addWidget(self.table)

        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel(t("desmagatzem.new_qty_label")))
        self.new_qty_input = QSpinBox()
        self.new_qty_input.setRange(rules.DESMAGATZEM_QTY_MIN, rules.DESMAGATZEM_QTY_MAX)
        qty_row.addWidget(self.new_qty_input)
        self.print_button = QPushButton(t("action.print_desmagatzem"))
        icons.apply_to(self.print_button, "print")
        self.print_button.clicked.connect(self.print_requested.emit)

        self.update_qty_button = QPushButton(t("desmagatzem.apply_qty"))
        self.update_qty_button.clicked.connect(self._on_update_qty)
        # Només té sentit amb una línia triada: desactivat mentre no n'hi
        # hagi cap (i es veu desactivat, per la regla QPushButton:disabled
        # del full d'estil). Fa servir la mateixa selecció de sempre,
        # `_selected_row_id`.
        self.update_qty_button.setEnabled(False)
        self.table.itemSelectionChanged.connect(self._update_qty_button_state)

        # Delete/Supr (i Retrocés, la tecla "delete" dels Mac) sobre una
        # línia triada = esborrar-la, igual que posar-hi quantitat 0. Amb
        # context WidgetShortcut només salta quan té el focus la taula: als
        # camps de text del formulari, Delete segueix esborrant caràcters.
        self._delete_shortcuts = []
        for key in (Qt.Key_Delete, Qt.Key_Backspace):
            shortcut = QShortcut(QKeySequence(key), self.table)
            shortcut.setContext(Qt.WidgetShortcut)
            shortcut.activated.connect(self._on_delete_selected)
            self._delete_shortcuts.append(shortcut)
        qty_row.addWidget(self.update_qty_button)
        qty_row.addStretch()
        # Zona d'accions de la pestanya: el total de peces i, a la seva
        # dreta, imprimir la taula sencera. El total es pinta igual que el
        # del Tauler (mateixa mida, mateix pes i mateix separador de
        # milers), perquè els dos comptadors es llegeixin igual.
        self.piece_count_label = QLabel()
        self.piece_count_label.setStyleSheet(
            theme.css("font-size: 13px; font-weight: 600; color: $text;")
        )
        qty_row.addWidget(self.piece_count_label)
        qty_row.addWidget(self.print_button)
        layout.addLayout(qty_row)
        self._update_piece_count()

    def printable_rows(self) -> tuple[list[str], list[list[ReportCell]]]:
        """Capçaleres i TOTES les files de la taula, en l'ordre en què es
        veuen (l'ordenació que hagi triat l'usuari clicant una capçalera).

        Es llegeix de la taula, no de la pantalla: el `QTableWidget` té
        totes les files carregades —no hi ha paginació ni virtualització—,
        així que aquí hi surten totes, hi hagi scroll o no, i amb el mateix
        text que es veu. Si algun dia s'hi afegís un filtre, aquest mètode
        seguiria donant el conjunt que la taula mostra.
        """
        headers = self._columns()   # sense la marca d'editable de la pantalla
        rows = []
        for r in range(self.table.rowCount()):
            if self.table.isRowHidden(r):
                continue
            rows.append([self._printable_cell(r, c) for c in range(self.table.columnCount())])
        return headers, rows

    def _printable_cell(self, row: int, column: int) -> ReportCell:
        """El text de la cel·la i, si en té, el seu color de fons (per
        exemple el d'un ressaltat de cerca), perquè l'informe surti igual
        de colorit que la taula."""
        item = self.table.item(row, column)
        if item is None:
            return ReportCell("")
        brush = item.background()
        color = brush.color()
        background = color.name() if brush.style() != Qt.NoBrush and color.alpha() > 0 else ""
        return ReportCell(item.text(), background)

    @contextmanager
    def _programmatic_update(self):
        """Mentre l'aplicació omple o repinta la taula, els canvis d'ítem no
        són edicions de l'usuari i no s'han de desar."""
        previous = self._updating
        self._updating = True
        self.table.blockSignals(True)
        try:
            yield
        finally:
            self.table.blockSignals(False)
            self._updating = previous

    def refresh(self):
        # Desactivem l'ordenació mentre omplim la taula (si no, Qt reordena
        # fila a fila a cada setItem, molt lent i pot descol·locar dades).
        with self._programmatic_update():
            self._fill_table()

    def _fill_table(self):
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
            # Els ítems de Qt són editables per defecte: aquí es deixa
            # explícit que només ho són Mides i Notes, i que la resta
            # (quantitat, núm., material i data) són de només lectura.
            for col in range(self.table.columnCount()):
                item = self.table.item(r, col)
                flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
                if col in self._EDITABLE_COLUMNS:
                    flags |= Qt.ItemIsEditable
                    item.setToolTip(t("desmagatzem.editable_hint"))
                item.setFlags(flags)
        self.table.setSortingEnabled(True)
        # Per defecte, ordenat per data ascendent (la més antiga primer).
        # L'usuari sempre pot canviar-ho clicant qualsevol altra capçalera.
        self.table.sortByColumn(self._DATE_COL, Qt.AscendingOrder)
        self._reapply_highlights()
        self._update_qty_button_state()
        self._update_piece_count()

    # ------------------------------------------------------------------ #
    # Ressaltat creuat amb els cercadors del Tauler (mateixos colors)
    # ------------------------------------------------------------------ #
    def apply_search_highlight(self, mode: str, text: str):
        self._search_state[mode] = text
        with self._programmatic_update():
            self._highlight_mode(mode, text)

    def clear_search_highlight(self):
        self._search_state = {}
        with self._programmatic_update():
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
        color = theme.search_qcolor(mode)
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

    def _on_cell_clicked(self, row: int, column: int):
        """Un sol clic ja obre l'editor de Mides i Notes (a la resta de
        columnes no fa res, perquè els seus ítems no són editables)."""
        item = self.table.item(row, column)
        if item is not None and item.flags() & Qt.ItemIsEditable:
            self.table.editItem(item)

    def _on_item_changed(self, item):
        """Desa el que s'hagi editat a Mides o Notes.

        El valor va a la base de dades a l'instant (`update_desmagatzem_field`,
        que ja fa la seva transacció) i la taula es refresca; si el desament
        falla, es torna a llegir de la base de dades, així el que es veu és
        sempre el que hi ha desat de debò.
        """
        if self._updating:
            return  # ho està canviant l'aplicació, no l'usuari
        field = self._EDITABLE_COLUMNS.get(item.column())
        if field is None:
            return
        id_item = self.table.item(item.row(), 0)
        row_id = id_item.data(Qt.UserRole) if id_item is not None else None
        if row_id is None:
            return
        try:
            self.repo.update_desmagatzem_field(row_id, field, item.text().strip())
        except (RuleViolation, ValueError) as exc:
            dialogs.error(self, t("common.error"), str(exc))
            self.refresh()          # es recupera el valor que hi havia
            return
        self.refresh()
        self.data_changed.emit()

    def _update_piece_count(self):
        """Quantes peces hi ha ara a Desmagatzem (la suma de les quantitats
        de totes les línies). Ve de la base de dades (`count_desmagatzem_pieces`),
        no del que hi hagi pintat a la taula: es manté correcte amb
        qualsevol ordenació o ressaltat de cerca."""
        count = self.repo.count_desmagatzem_pieces()
        self.piece_count_label.setText(
            t("desmagatzem.piece_count", count=format_number(count))
        )

    def _update_qty_button_state(self):
        self.update_qty_button.setEnabled(self._selected_row_id() is not None)

    def _on_code_edited(self, _text: str):
        """En canviar el núm., la descripció recuperada abans deixa de
        valer: es buida i es torna a poder escriure."""
        if self.custom_text_input.isReadOnly():
            self.custom_text_input.clear()
            self.custom_text_input.setReadOnly(False)

    def _material_description(self, code: str) -> str | None:
        """Descripció del material `code` al catàleg, o None si no hi és
        (i llavors ja avisa). Fa servir la mateixa cerca de sempre
        (`Repository.lookup_material`), no en duplica cap.

        El codi 1 no s'hi busca mai: és el "material no registrat" de
        l'original, i és l'usuari qui n'escriu la descripció."""
        if not rules.is_valid_material_code(code):
            dialogs.warn(
                self, t("desmagatzem.material_not_found.title"),
                t("desmagatzem.material_not_found.text", code=code),
            )
            return None
        description = self.repo.lookup_material(int(code))
        if description == rules.EMPTY_MATERIAL_MARK:
            # No existeix: no es registra res i no es crea cap material
            # nou; l'usuari es queda al camp per corregir el número.
            dialogs.warn(
                self, t("desmagatzem.material_not_found.title"),
                t("desmagatzem.material_not_found.text", code=code),
            )
            return None
        return description

    def _on_code_entered(self):
        """Enter al núm. de material, el que decideix com continua l'alta:

          - núm. 1 (material no registrat): es descriu a mà, així que el
            focus va al camp de material, en blanc i editable.
          - qualsevol altre núm.: es busca al catàleg. Si hi és, la seva
            descripció s'omple sola (i no es pot tocar: la de veritat és
            la del catàleg) i el focus salta directament a Quantitat. Si
            no hi és, s'avisa i no es continua.
        """
        code = self.code_input.text().strip()
        if not code:
            return
        if code == str(rules.CUSTOM_MATERIAL_SENTINEL):
            self.custom_text_input.setReadOnly(False)
            self.custom_text_input.clear()
            self._focus_field(self.custom_text_input)
            return
        description = self._material_description(code)
        if description is None:
            self._focus_field(self.code_input)
            return
        self.custom_text_input.setText(description)
        self.custom_text_input.setReadOnly(True)
        self._focus_field(self.qty_input)

    @staticmethod
    def _focus_field(widget: QWidget):
        """Porta el focus al camp i en selecciona el text, perquè es vegi
        clarament on s'escriu i escrivint s'hi substitueixi el que hi havia."""
        widget.setFocus()
        if isinstance(widget, QSpinBox):
            widget.selectAll()
        elif isinstance(widget, QLineEdit):
            widget.selectAll()

    def _on_add_row(self):
        code = self.code_input.text().strip()
        if not code:
            dialogs.warn(self, t("desmagatzem.missing_code.title"), t("desmagatzem.missing_code.text"))
            return
        # Mateixa comprovació que amb Enter, també si s'ha clicat el botó:
        # un núm. que no sigui l'1 ha d'existir al catàleg.
        if code != str(rules.CUSTOM_MATERIAL_SENTINEL) and self._material_description(code) is None:
            self._focus_field(self.code_input)
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
            dialogs.error(self, t("desmagatzem.cannot_register"), str(exc))
            return
        self.code_input.clear()
        self.custom_text_input.clear()
        self.custom_text_input.setReadOnly(False)
        self.qty_input.setValue(0)
        self.dims_input.clear()
        self.cart_input.clear()
        self.refresh()
        self.data_changed.emit()
        # Llest per a la següent entrada, sense tocar el ratolí.
        self._focus_field(self.code_input)

    def _on_update_qty(self):
        """Botó "Aplicar canvi de quantitat"."""
        self._apply_quantity(self.new_qty_input.value())

    def _on_delete_selected(self):
        """Tecla Delete/Supr sobre la línia triada.

        No hi ha cap lògica d'esborrat pròpia: posar la quantitat a 0 JA és
        esborrar la línia (`rules.quantity_change_kind` en diu "delete"), o
        sigui que es crida exactament el mateix camí que el botó, amb 0 —
        mateixa confirmació, mateix registre a l'històric i mateix refresc.
        """
        self._apply_quantity(0)

    def _apply_quantity(self, new_qty: int):
        row_id = self._selected_row_id()
        if row_id is None:
            dialogs.warn(self, t("desmagatzem.no_selection.title"), t("desmagatzem.no_selection.text"))
            return

        # Esbrina quin tipus de canvi serà, per demanar la confirmació
        # adequada (igual que el MsgBox Sí/No d'ActualitzaHistorialQuantitat).
        current = next(r for r in self.repo.list_desmagatzem() if r["id"] == row_id)
        change = quantity_change_kind(current["quantity"], new_qty)
        if change is None:
            return
        if not dialogs.confirm(
            self, t("common.confirm"), self._confirm_text(current["quantity"], new_qty)[change]
        ):
            return
        try:
            self.repo.update_desmagatzem_quantity(row_id, new_qty)
        except RuleViolation as exc:
            dialogs.error(self, t("common.error"), str(exc))
            return
        self.refresh()
        self.data_changed.emit()
