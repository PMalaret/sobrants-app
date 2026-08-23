"""Diàleg de cerca del Tauler (abans eren 3 caixes fixes a la pantalla).

Cada camp té el mateix color que fa servir per ressaltar les coincidències
al tauler (igual que a l'Excel original, on el color de la pròpia cel·la
de cerca M20/M22/M24 era el que s'usava per pintar les coincidències), i
mostra els resultats (coincidències, posició més antiga, unitats a
Desmagatzem) en targetes clares en lloc d'una línia de text.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t

# Mateixos colors que BoardTab._SEARCH_COLOR i DesmagatzemTab, perquè es
# vegi d'un cop d'ull quin cercador pinta quin color a cada banda.
SEARCH_COLORS = {
    "code": "#ffe08a",
    "description": "#a8e6a1",
    "notes": "#9fd3ff",
}


class SearchStatsCard(QWidget):
    """Targeta amb els 3 resultats d'un cercador (coincidències, posició més
    antiga, unitats a Desmagatzem), amb número gran i etiqueta petita."""

    def __init__(self, accent_color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "background-color: #fafbfc; border: 1px solid #d8dae0; "
            f"border-left: 5px solid {accent_color}; border-radius: 6px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(22)

        self.count_value = self._add_tile(layout, t("search.stat.matches"))
        self.oldest_value = self._add_tile(layout, t("search.stat.oldest"))
        self.qty_value = self._add_tile(layout, t("search.stat.desmagatzem"))

    @staticmethod
    def _add_tile(layout: QHBoxLayout, caption: str) -> QLabel:
        box = QVBoxLayout()
        box.setSpacing(2)
        cap = QLabel(caption)
        cap.setStyleSheet("color: #6b7280; font-size: 10px; font-weight: 600;")
        cap.setWordWrap(True)
        value = QLabel("—")
        value.setStyleSheet("color: #1a1a1a; font-size: 21px; font-weight: 700;")
        box.addWidget(cap)
        box.addWidget(value)
        wrap = QWidget()
        wrap.setLayout(box)
        layout.addWidget(wrap)
        return value

    def set_values(self, count, oldest, qty):
        self.count_value.setText(str(count))
        self.oldest_value.setText(str(oldest) if oldest not in (None, "") else "—")
        self.qty_value.setText(str(qty))


class SearchDialog(QDialog):
    """Emet `search_changed(mode, text)` cada vegada que canvia un camp, i
    `cleared()` quan es netegen tots. El Tauler escolta aquests senyals per
    calcular coincidències i aplicar el ressaltat sobre la taula."""

    search_changed = Signal(str, str)
    cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("search.title"))
        self.setMinimumWidth(620)
        self.setModal(False)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        self.code_edit, self.code_card = self._build_field(
            layout, t("search.code_label"), t("search.code_placeholder"), "code"
        )
        self.desc_edit, self.desc_card = self._build_field(
            layout, t("search.desc_label"), t("search.desc_placeholder"), "description"
        )
        self.notes_edit, self.notes_card = self._build_field(
            layout, t("search.notes_label"), t("search.notes_placeholder"), "notes"
        )

        layout.addStretch()

        buttons = QHBoxLayout()
        clear_button = QPushButton(t("common.clear"))
        clear_button.clicked.connect(self.clear_all)
        buttons.addWidget(clear_button)
        buttons.addStretch()
        close_button = QPushButton(t("common.close"))
        close_button.clicked.connect(self.close)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _build_field(self, layout: QVBoxLayout, label_text: str, placeholder: str, mode: str):
        color = SEARCH_COLORS[mode]

        title = QLabel(label_text)
        title.setStyleSheet("font-weight: 600; color: #1a1a1a;")
        layout.addWidget(title)

        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setStyleSheet(
            f"background-color: {color}; color: #1a1a1a; border: 1px solid #999; "
            "border-radius: 4px; padding: 6px 8px; font-size: 13px;"
        )
        edit.textChanged.connect(lambda text, m=mode: self.search_changed.emit(m, text))
        layout.addWidget(edit)

        card = SearchStatsCard(color)
        layout.addWidget(card)

        return edit, card

    def clear_all(self):
        for edit in (self.code_edit, self.desc_edit, self.notes_edit):
            edit.blockSignals(True)
            edit.clear()
            edit.blockSignals(False)
        for card in (self.code_card, self.desc_card, self.notes_card):
            card.set_values("—", "—", "—")
        self.cleared.emit()

    def set_result(self, mode: str, count, oldest, qty):
        card = {"code": self.code_card, "description": self.desc_card, "notes": self.notes_card}[mode]
        card.set_values(count, oldest, qty)

    def show_and_focus(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.code_edit.setFocus(Qt.PopupFocusReason)
