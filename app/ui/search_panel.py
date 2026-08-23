"""Panell de cerca del Tauler, incrustat al panell de detall de posició.

Abans (`SearchDialog`) era un diàleg flotant amb targetes de resultat,
obert amb un botó "Cercar...". Ara viu sempre visible, a l'espai que ha
quedat lliure en treure el formulari d'alta de peça (l'alta es fa ara
directament a la taula de detall): només els 3 camps de text, sense
targetes de resultat ni botons — per netejar-ne un n'hi ha prou a
buidar-ne el text.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QWidget

from app.i18n import t

# Mateixos colors que BoardTab._SEARCH_COLOR i DesmagatzemTab, perquè es
# vegi d'un cop d'ull quin cercador pinta quin color a cada banda.
SEARCH_COLORS = {
    "code": "#ffe08a",
    "description": "#a8e6a1",
    "notes": "#9fd3ff",
}


class SearchPanel(QWidget):
    """Emet `search_changed(mode, text)` cada vegada que canvia un camp."""

    search_changed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.code_edit = self._build_field(layout, t("search.code_label"), t("search.code_placeholder"), "code")
        self.desc_edit = self._build_field(
            layout, t("search.desc_label"), t("search.desc_placeholder"), "description"
        )
        self.notes_edit = self._build_field(layout, t("search.notes_label"), t("search.notes_placeholder"), "notes")

    def _build_field(self, layout: QFormLayout, label_text: str, placeholder: str, mode: str) -> QLineEdit:
        color = SEARCH_COLORS[mode]

        label = QLabel(label_text)
        label.setStyleSheet("font-size: 10px; font-weight: 600; color: #1a1a1a;")
        label.setWordWrap(True)

        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setStyleSheet(
            f"background-color: {color}; color: #1a1a1a; border: 1px solid #999; "
            "border-radius: 3px; padding: 2px 6px; font-size: 10px;"
        )
        edit.textChanged.connect(lambda text, m=mode: self.search_changed.emit(m, text))

        layout.addRow(label, edit)
        return edit
