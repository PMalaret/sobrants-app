"""Diàleg de detall d'una posició: fins a 5 peces, alta, baixa i trasllat.

Abans era un panell fix a la dreta del Tauler; ara s'obre en fer doble clic
sobre una posició, perquè la taula del Tauler pugui ocupar tot l'ample.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.i18n import t
from app.logic.repository import DuplicateMaterialError, PositionFullError, Repository, RuleViolation


class PositionDialog(QDialog):
    """Emet `changed()` cada vegada que es modifiquen dades, perquè el Tauler
    refresqui la taula principal."""

    changed = Signal()

    def __init__(self, repo: Repository, position: int, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.position = position
        self.setWindowTitle(t("position.title", position=position))
        self.setMinimumWidth(560)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.title_label = QLabel(t("position.subtitle", position=self.position))
        self.title_label.setStyleSheet("font-weight: 600; font-size: 14px;")
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
        layout.addWidget(self.detail_table)

        add_box = QGroupBox(t("position.add_box"))
        add_layout = QFormLayout(add_box)
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

        actions = QHBoxLayout()
        self.delete_button = QPushButton(t("position.delete_button"))
        self.delete_button.clicked.connect(self._on_delete_last_piece)
        actions.addWidget(self.delete_button)

        self.move_target = QSpinBox()
        self.move_target.setRange(1, 61)
        self.move_button = QPushButton(t("position.move_button"))
        self.move_button.clicked.connect(self._on_move_piece)
        actions.addWidget(self.move_button)
        actions.addWidget(self.move_target)
        layout.addLayout(actions)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_button = QPushButton(t("common.close"))
        close_button.clicked.connect(self.close)
        close_row.addWidget(close_button)
        layout.addLayout(close_row)

    def refresh(self):
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
                t(
                    "position.duplicate.text",
                    positions=", ".join(str(p) for p in exc.positions),
                ),
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
