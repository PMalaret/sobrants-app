"""Diàleg de cerca del Tauler (abans eren 3 caixes fixes a la pantalla).

Cada camp té el mateix color que fa servir per ressaltar les coincidències
al tauler (igual que a l'Excel original, on el color de la pròpia cel·la
de cerca M20/M22/M24 era el que s'usava per pintar les coincidències).
"""
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

from app.i18n import t

# Mateixos colors que BoardTab._SEARCH_COLOR, perquè es vegi d'un cop d'ull
# quin cercador pinta quin color al tauler.
SEARCH_COLORS = {
    "code": "#ffe08a",
    "description": "#a8e6a1",
    "notes": "#9fd3ff",
}


class SearchDialog(QDialog):
    """Emet `search_changed(mode, text)` cada vegada que canvia un camp, i
    `cleared()` quan es netegen tots. El Tauler escolta aquests senyals per
    calcular coincidències i aplicar el ressaltat sobre la taula."""

    search_changed = Signal(str, str)
    cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("search.title"))
        self.setMinimumWidth(520)
        self.setModal(False)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setVerticalSpacing(12)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText(t("search.code_placeholder"))
        self.code_result = QLabel("")
        form.addRow(
            t("search.code_label"),
            self._with_result(self.code_edit, self.code_result, SEARCH_COLORS["code"]),
        )

        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText(t("search.desc_placeholder"))
        self.desc_result = QLabel("")
        form.addRow(
            t("search.desc_label"),
            self._with_result(self.desc_edit, self.desc_result, SEARCH_COLORS["description"]),
        )

        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText(t("search.notes_placeholder"))
        self.notes_result = QLabel("")
        form.addRow(
            t("search.notes_label"),
            self._with_result(self.notes_edit, self.notes_result, SEARCH_COLORS["notes"]),
        )

        layout.addLayout(form)

        self.code_edit.textChanged.connect(lambda t_: self.search_changed.emit("code", t_))
        self.desc_edit.textChanged.connect(lambda t_: self.search_changed.emit("description", t_))
        self.notes_edit.textChanged.connect(lambda t_: self.search_changed.emit("notes", t_))

        buttons = QHBoxLayout()
        clear_button = QPushButton(t("common.clear"))
        clear_button.clicked.connect(self.clear_all)
        buttons.addWidget(clear_button)
        buttons.addStretch()
        close_button = QPushButton(t("common.close"))
        close_button.clicked.connect(self.close)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    @staticmethod
    def _with_result(edit: QLineEdit, result: QLabel, color: str) -> QHBoxLayout:
        edit.setStyleSheet(
            f"background-color: {color}; color: #1a1a1a; border: 1px solid #999; "
            "border-radius: 4px; padding: 5px 7px;"
        )
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
