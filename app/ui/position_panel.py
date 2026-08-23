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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack)

        placeholder = QLabel(t("position.panel.placeholder"))
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setWordWrap(True)
        placeholder.setStyleSheet("color: #8a8f98; font-size: 11px;")
        self._stack.addWidget(placeholder)  # índex 0

        self._stack.addWidget(self._build_detail_page())  # índex 1

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
        self.detail_table = QTableWidget(0, len(detail_columns))
        self.detail_table.setHorizontalHeaderLabels(detail_columns)
        self.detail_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.detail_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.detail_table.verticalHeader().setVisible(False)
        self.detail_table.verticalHeader().setDefaultSectionSize(18)
        self.detail_table.horizontalHeader().setDefaultSectionSize(46)
        self.detail_table.setStyleSheet("font-size: 10px;")
        self.detail_table.setFixedHeight(18 * 5 + 24)  # capçalera + fins a 5 files, mai més
        layout.addWidget(self.detail_table)

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
        self.add_button = QPushButton(t("position.add_button"))
        self.add_button.clicked.connect(self._on_add_piece)
        add_layout.addRow(self.add_button)
        layout.addWidget(add_box)

        self.delete_button = QPushButton(t("position.delete_button"))
        self.delete_button.clicked.connect(self._on_delete_last_piece)
        layout.addWidget(self.delete_button)

        move_row = QHBoxLayout()
        move_row.setSpacing(3)
        self.move_target = QSpinBox()
        self.move_target.setRange(1, 61)
        self.move_button = QPushButton(t("position.move_button"))
        self.move_button.clicked.connect(self._on_move_piece)
        move_row.addWidget(self.move_button, 1)
        move_row.addWidget(self.move_target)
        layout.addLayout(move_row)

        layout.addStretch()
        return page

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
