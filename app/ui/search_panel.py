"""Panell de cerca del Tauler, incrustat al panell de detall de posició.

Abans (`SearchDialog`) era un diàleg flotant amb targetes de resultat,
obert amb un botó "Cercar...". Ara viu sempre visible, a l'espai que ha
quedat lliure en treure el formulari d'alta de peça (l'alta es fa ara
directament a la taula de detall): el títol a sobre de cada camp de
text (no al costat, per no eixamplar l'espai) i, a sota, els resultats
(coincidències, posició més antiga, unitats a Desmagatzem) en una línia,
amb els dos números més rellevants (coincidències i unitats a
Desmagatzem) més destacats — sense targetes ni botons; per netejar un
camp n'hi ha prou a buidar-ne el text.

El fons del camp de cerca ja no és un color fix per mode: per defecte
no en té cap, i quan hi ha una coincidència es pinta amb el mateix color
d'ocupació que té la posició trobada (escala blanc/groc/verd/blau/vermell
de `rules.fill_color_for_count`) — el color hi diu alguna cosa de la
posició trobada, no només de quin cercador és.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from app.i18n import t

# Vora esquerra de cada camp (identifica quin cercador és, sempre visible);
# mateixos colors que BoardTab._SEARCH_COLOR i DesmagatzemTab per pintar
# les coincidències a les taules.
SEARCH_COLORS = {
    "code": "#ffe08a",
    "description": "#a8e6a1",
    "notes": "#9fd3ff",
}

_NO_MATCH_BG = "#ffffff"  # per defecte, sense cap coincidència: sense color


def _stats_text(count, oldest, qty) -> str:
    # Coincidències i unitats a Desmagatzem més destacades (negreta i una
    # mica més grans) que la posició més antiga, per llegir-les d'un cop
    # d'ull; RichText perquè el QLabel interpreti l'HTML.
    return (
        f"{t('search.stat.matches')}: <b style='font-size:12px;color:#c62828;'>{count}</b>"
        "&nbsp;&nbsp;&nbsp;"
        f"{t('search.stat.oldest')}: {oldest}"
        "&nbsp;&nbsp;&nbsp;"
        f"{t('search.stat.desmagatzem')}: <b style='font-size:12px;color:#c62828;'>{qty}</b>"
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
        # Títol a sobre del camp (no al costat): mateix ample de sempre,
        # només canvia com es reparteix l'espai que ja hi havia.
        label = QLabel(label_text)
        label.setStyleSheet("font-size: 12px; font-weight: 600; color: #1a1a1a;")
        label.setWordWrap(True)
        layout.addWidget(label)

        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        self._style_edit(edit, mode, _NO_MATCH_BG)
        edit.textChanged.connect(lambda text, m=mode: self.search_changed.emit(m, text))
        layout.addWidget(edit)

        stats = QLabel(_stats_text("—", "—", "—"))
        stats.setTextFormat(Qt.RichText)
        stats.setStyleSheet("font-size: 11px; color: #444;")
        stats.setWordWrap(True)
        layout.addWidget(stats)

        return edit, stats

    @staticmethod
    def _style_edit(edit: QLineEdit, mode: str, bg_color: str):
        accent = SEARCH_COLORS[mode]
        edit.setStyleSheet(
            f"background-color: {bg_color}; color: #1a1a1a; border: 1px solid #999; "
            f"border-left: 4px solid {accent}; border-radius: 3px; padding: 3px 6px; font-size: 12px;"
        )

    def set_result(self, mode: str, count, oldest, qty, match_color: str | None = None):
        edit = {"code": self.code_edit, "description": self.desc_edit, "notes": self.notes_edit}[mode]
        stats = {"code": self.code_stats, "description": self.desc_stats, "notes": self.notes_stats}[mode]
        self._style_edit(edit, mode, match_color or _NO_MATCH_BG)
        stats.setText(_stats_text(count, oldest, qty))
