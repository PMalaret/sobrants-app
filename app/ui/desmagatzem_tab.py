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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t
from app.logic import rules
from app.logic.repository import Repository, RuleViolation
from app.logic.rules import quantity_change_kind
from app.ui import dialogs
from app.ui.search_panel import SEARCH_COLORS


# Amples del formulari de nova entrada, calculats sobre el que pot valer
# cada camp: núm. de material fins a 6 xifres (rules.MATERIAL_CODE_MAX),
# quantitat de 0 a 20 i notes de 8 caràcters com a màxim.
_CODE_MAX_CHARS = 6
_CODE_WIDTH = 70
_QTY_WIDTH = 60
_DIMS_WIDTH = 95
_NOTES_MAX_CHARS = 8
_NOTES_WIDTH = 70


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

        # Tot el formulari en UNA sola fila: etiqueta + camp, un darrere
        # l'altre, i el botó al final. Els amples surten del que pot valer
        # cada camp de debò (núm. de material fins a 6 xifres, quantitat
        # 0-20, notes 8 caràcters), no d'un valor per omissió: així no
        # sobra espai enlloc i tot hi cap sense passar a una segona línia.
        # L'únic que s'estira és la descripció del material, que és
        # l'únic camp de llargada lliure.
        form_box = QGroupBox(t("desmagatzem.form_title"))
        form = QHBoxLayout(form_box)
        form.setSpacing(6)

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
        self.cart_input.setMaxLength(_NOTES_MAX_CHARS)
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
        self._configure_column_widths()
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table)

        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel(t("desmagatzem.new_qty_label")))
        self.new_qty_input = QSpinBox()
        self.new_qty_input.setRange(rules.DESMAGATZEM_QTY_MIN, rules.DESMAGATZEM_QTY_MAX)
        qty_row.addWidget(self.new_qty_input)
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
        self._update_qty_button_state()

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
        if not dialogs.confirm(self, t("common.confirm"), self._confirm_text()[change]):
            return
        try:
            self.repo.update_desmagatzem_quantity(row_id, new_qty)
        except RuleViolation as exc:
            dialogs.error(self, t("common.error"), str(exc))
            return
        self.refresh()
        self.data_changed.emit()
