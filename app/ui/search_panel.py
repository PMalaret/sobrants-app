"""Panell de cerca del Tauler, incrustat al panell de detall de posició.

Abans (`SearchDialog`) era un diàleg flotant amb targetes de resultat,
obert amb un botó "Cercar...". Ara viu sempre visible, a l'espai que ha
quedat lliure en treure el formulari d'alta de peça (l'alta es fa ara
directament a la taula de detall): el títol a sobre de cada camp de
text (no al costat, per no eixamplar l'espai) i, a sota, els resultats
(coincidències, posició més antiga, unitats a Desmagatzem) en una línia
compacta — sense targetes ni botons; per netejar un camp n'hi ha prou a
buidar-ne el text.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from app.i18n import t

# Mateixos colors que BoardTab._SEARCH_COLOR i DesmagatzemTab, perquè es
# vegi d'un cop d'ull quin cercador pinta quin color a cada banda.
SEARCH_COLORS = {
    "code": "#ffe08a",
    "description": "#a8e6a1",
    "notes": "#9fd3ff",
}


def _stats_text(count, oldest, qty) -> str:
    return (
        f"{t('search.stat.matches')}: {count}   "
        f"{t('search.stat.oldest')}: {oldest}   "
        f"{t('search.stat.desmagatzem')}: {qty}"
    )


class SearchPanel(QWidget):
    """Emet `search_changed(mode, text)` cada vegada que canvia un camp."""

    search_changed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.code_edit, self.code_stats = self._build_field(
            layout, t("search.code_label"), t("search.code_placeholder"), "code"
        )
        self.desc_edit, self.desc_stats = self._build_field(
            layout, t("search.desc_label"), t("search.desc_placeholder"), "description"
        )
        self.notes_edit, self.notes_stats = self._build_field(
            layout, t("search.notes_label"), t("search.notes_placeholder"), "notes"
        )

    def _build_field(self, layout: QVBoxLayout, label_text: str, placeholder: str, mode: str):
        color = SEARCH_COLORS[mode]

        # Títol a sobre del camp (no al costat): mateix ample de sempre,
        # només canvia com es reparteix l'espai que ja hi havia.
        label = QLabel(label_text)
        label.setStyleSheet("font-size: 11px; font-weight: 600; color: #1a1a1a;")
        label.setWordWrap(True)
        layout.addWidget(label)

        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setStyleSheet(
            f"background-color: {color}; color: #1a1a1a; border: 1px solid #999; "
            "border-radius: 3px; padding: 3px 6px; font-size: 11px;"
        )
        edit.textChanged.connect(lambda text, m=mode: self.search_changed.emit(m, text))
        layout.addWidget(edit)

        stats = QLabel(_stats_text("—", "—", "—"))
        stats.setStyleSheet("font-size: 10px; color: #555;")
        stats.setWordWrap(True)
        layout.addWidget(stats)

        return edit, stats

    def set_result(self, mode: str, count, oldest, qty):
        stats = {"code": self.code_stats, "description": self.desc_stats, "notes": self.notes_stats}[mode]
        stats.setText(_stats_text(count, oldest, qty))
