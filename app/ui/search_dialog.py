"""Diàleg de cerca del Tauler (abans eren 3 caixes fixes a la pantalla)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class SearchDialog(QDialog):
    """Emet `search_changed(mode, text)` cada vegada que canvia un camp, i
    `cleared()` quan es netegen tots. El Tauler escolta aquests senyals per
    calcular coincidències i aplicar el ressaltat sobre la taula."""

    search_changed = Signal(str, str)
    cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cercar al tauler")
        self.setMinimumWidth(480)
        self.setModal(False)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("Núm. de material exacte")
        self.code_result = QLabel("")
        form.addRow("Per núm. (exacte):", self._with_result(self.code_edit, self.code_result))

        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Text parcial a la descripció")
        self.desc_result = QLabel("")
        form.addRow("Per material (parcial):", self._with_result(self.desc_edit, self.desc_result))

        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Text parcial a les notes")
        self.notes_result = QLabel("")
        form.addRow("Per notes (parcial):", self._with_result(self.notes_edit, self.notes_result))

        layout.addLayout(form)

        self.code_edit.textChanged.connect(lambda t: self.search_changed.emit("code", t))
        self.desc_edit.textChanged.connect(lambda t: self.search_changed.emit("description", t))
        self.notes_edit.textChanged.connect(lambda t: self.search_changed.emit("notes", t))

        buttons = QHBoxLayout()
        clear_button = QPushButton("Netejar")
        clear_button.clicked.connect(self.clear_all)
        buttons.addWidget(clear_button)
        buttons.addStretch()
        close_button = QPushButton("Tancar")
        close_button.clicked.connect(self.close)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    @staticmethod
    def _with_result(edit: QLineEdit, result: QLabel) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(edit)
        row.addWidget(result)
        return row

    def clear_all(self):
        for edit in (self.code_edit, self.desc_edit, self.notes_edit):
            edit.blockSignals(True)
            edit.clear()
            edit.blockSignals(False)
        for label in (self.code_result, self.desc_result, self.notes_result):
            label.setText("")
        self.cleared.emit()

    def set_result_text(self, mode: str, text: str):
        label = {"code": self.code_result, "description": self.desc_result, "notes": self.notes_result}[mode]
        label.setText(text)

    def show_and_focus(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.code_edit.setFocus(Qt.PopupFocusReason)
