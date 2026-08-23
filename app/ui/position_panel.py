"""Panell de detall d'una posició: fins a 5 peces, alta, baixa i trasllat.

Abans (`PositionDialog`) era una finestra emergent que s'obria en fer doble
clic. Ara és un `QWidget` incrustat de manera permanent DINS de la pròpia
taula del Tauler: el 3r bloc de columnes (posicions 55-61) només fa servir
7 de les 27 files, així que la resta de l'espai d'aquell bloc (a la dreta
de tot) es fusiona amb `QTableWidget.setSpan` i s'hi incrusta aquest
panell amb `setCellWidget` (veure `BoardTab._build_ui`). Com que no s'afegeix
cap fila nova enlloc, la taula de 61 posicions mai canvia de mida.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t
from app.logic.repository import DuplicateMaterialError, PositionFullError, Repository, RuleViolation

_PANEL_STYLE = """
QFrame#positionPanel {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 8px;
}
"""


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

    def add_footer(self, layout):
        """Afegeix una fila de botons a sota de tot, separada amb una línia
        divisòria. Fora de l'`_stack`, així es veu sempre (hi hagi o no una
        posició seleccionada) — s'hi reubica el buscador del Tauler."""
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        self._outer.addWidget(separator)
        self._outer.addLayout(layout)

    def _build_detail_page(self) -> QWidget:
        # Disposició vertical i compacta: aquest panell viu incrustat dins
        # l'ample d'un sol bloc de columnes del tauler (el 3r, posicions
        # 55-61), no dins tot l'ample de la finestra.
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-weight: 700; font-size: 11px; color: #1a1a1a;")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        detail_columns = [
            t("position.detail.order"),
            t("board.field.code"),
            t("board.field.material"),
            t("board.field.dimensions"),
            t("board.field.notes"),
            t("position.detail.entered"),
        ]
        self.detail_table = QTableWidget(5, len(detail_columns))
        self.detail_table.setHorizontalHeaderLabels(detail_columns)
        self.detail_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.detail_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.detail_table.verticalHeader().setVisible(False)
        self.detail_table.verticalHeader().setDefaultSectionSize(18)
        self.detail_table.setStyleSheet("font-size: 10px;")
        # Ordre/Núm./Mides/Notes/Entrada: ample inicial ajustat, però
        # "Interactive" (l'usuari els pot canviar i es queden fixats).
        # Material: s'estira perquè les columnes aprofitin tot l'ample
        # que té el panell (que ja és el just i necessari).
        detail_header = self.detail_table.horizontalHeader()
        detail_widths = [32, 55, None, 62, 55, 90]
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

        # Botons compactes: menys padding que el QPushButton global.
        compact_button_style = "padding: 2px 8px; font-size: 10px;"

        add_box = QGroupBox(t("position.add_box"))
        add_box.setStyleSheet("QGroupBox { font-size: 10px; }")
        add_layout = QFormLayout(add_box)
        add_layout.setSpacing(3)
        add_layout.setContentsMargins(6, 10, 6, 6)
        self.add_code = QSpinBox()
        self.add_code.setRange(0, 99999)
        self.add_dims = QLineEdit()
        self.add_notes = QLineEdit()
        add_layout.addRow(t("desmagatzem.field.code"), self.add_code)
        add_layout.addRow(t("desmagatzem.field.dimensions"), self.add_dims)
        add_layout.addRow(t("board.field.notes") + ":", self.add_notes)
        layout.addWidget(add_box)

        # Afegir peça i Esborrar última peça a la mateixa fila.
        add_delete_row = QHBoxLayout()
        add_delete_row.setSpacing(4)
        self.add_button = QPushButton(t("position.add_button"))
        self.add_button.setStyleSheet(compact_button_style)
        self.add_button.clicked.connect(self._on_add_piece)
        add_delete_row.addWidget(self.add_button)
        self.delete_button = QPushButton(t("position.delete_button"))
        self.delete_button.setStyleSheet(compact_button_style)
        self.delete_button.clicked.connect(self._on_delete_last_piece)
        add_delete_row.addWidget(self.delete_button)
        layout.addLayout(add_delete_row)

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

        layout.addStretch()
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
        self.detail_table.setRowCount(5)
        for r in range(5):
            if r < len(detail):
                p = detail[r]
                values = [
                    p["slot"],
                    p["material_code"],
                    p["material_desc"] or "",
                    p["dimensions"] or "",
                    p["notes"] or "",
                    p["entered_at"] or "",
                ]
            else:
                values = [""] * self.detail_table.columnCount()
            for c, v in enumerate(values):
                self.detail_table.setItem(r, c, QTableWidgetItem(str(v)))
        self._fit_detail_table_height()

    def _on_add_piece(self):
        code = self.add_code.value()
        dims = self.add_dims.text().strip()
        notes = self.add_notes.text().strip()

        try:
            self.repo.add_piece(self.position, code, dims, notes)
        except DuplicateMaterialError as exc:
            resp = QMessageBox.question(
                self,
                t("position.duplicate.title"),
                t("position.duplicate.text", positions=", ".join(str(p) for p in exc.positions)),
                QMessageBox.Yes | QMessageBox.No,
            )
            if resp == QMessageBox.Yes:
                try:
                    self.repo.add_piece(self.position, code, dims, notes, confirm_duplicate=True)
                except RuleViolation as exc2:
                    QMessageBox.critical(self, t("common.error"), str(exc2))
                    return
            else:
                return
        except (PositionFullError, RuleViolation) as exc:
            QMessageBox.critical(self, t("position.cannot_add"), str(exc))
            return

        self.add_code.setValue(0)
        self.add_dims.clear()
        self.add_notes.clear()
        self.refresh()
        self.changed.emit()

    def _on_delete_last_piece(self):
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
