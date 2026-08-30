"""Panell de cerca del Tauler, incrustat al panell de detall de posició.

Abans (`SearchDialog`) era un diàleg flotant amb targetes de resultat,
obert amb un botó "Cercar...". Ara viu sempre visible, a l'espai que ha
quedat lliure en treure el formulari d'alta de peça (l'alta es fa ara
directament a la taula de detall), amb els dos números més rellevants
(coincidències i unitats a Desmagatzem) més destacats — sense targetes ni
botons; per netejar un camp n'hi ha prou a buidar-ne el text.

Cada cercador té UN color propi i fix (`SEARCH_COLORS`), el mateix amb
què pinta les coincidències al Tauler i a Desmagatzem: la vora esquerra
del camp sempre, i el fons del camp quan hi ha alguna coincidència. El
color identifica el cercador, mai el material o la posició trobats — dos
materials diferents cercats pel mateix camp surten sempre igual.

Distribució de cada cercador: el títol a sobre i, en UNA sola fila, el
camp de text (curt: no li cal més) i els tres resultats (coincidències,
posició més antiga, unitats a Desmagatzem). Cada resultat és un bloc
vertical —el nom a dalt, en negreta com el títol del cercador, i el valor
a sota, molt més gran— perquè els números es llegeixin d'un cop d'ull.
L'espai que abans s'enduia un camp de text de tot l'ample queda per a
aquests tres blocs.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from app.i18n import t

# Vora esquerra de cada camp (identifica quin cercador és, sempre visible);
# mateixos colors que BoardTab._SEARCH_COLOR i DesmagatzemTab per pintar
# les coincidències a les taules.
SEARCH_COLORS = {
    "code": "#ffe08a",
    "description": "#a8e6a1",
    # Rosa de l'Excel ("Light Red Fill"), una mica més pujat que el seu
    # #ffc7ce perquè es distingeixi millor sense arribar a cridar: és el
    # color del cercador per notes a tot arreu (camp, tauler i Desmagatzem).
    "notes": "#ffa8b4",
}

_NO_MATCH_BG = "#ffffff"  # per defecte, sense cap coincidència: sense color

# Ample del camp de text. Curt a propòsit: el que s'hi escriu són números
# de material o trossos de text curts, i l'espai que sobra és més útil per
# als resultats, que van a la mateixa fila.
_EDIT_WIDTH = 105


# Nom de cada resultat a dalt, amb el mateix estil que el títol del
# cercador ("Per núm.:"), i el valor a sota molt més gran.
_STAT_TITLE_STYLE = "font-size: 12px; font-weight: 600; color: #1a1a1a;"
_STAT_VALUE_STYLE = "font-size: 20px; font-weight: 700; color: {color};"
# Coincidències i unitats a Desmagatzem, en vermell (són els dos números
# que interessen més); la posició més antiga, en el color del text normal.
_STATS = (
    ("matches", "search.stat.matches", "#c62828"),
    ("oldest", "search.stat.oldest", "#1a1a1a"),
    ("desmagatzem", "search.stat.desmagatzem", "#c62828"),
)
_NO_VALUE = "—"


class SearchPanel(QWidget):
    """Emet `search_changed(mode, text)` cada vegada que canvia un camp."""

    search_changed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # {mode: {clau del resultat: QLabel del valor}}, per poder-los
        # actualitzar des de set_result sense tornar a construir res.
        self._stat_values: dict[str, dict[str, QLabel]] = {}

        self.code_edit = self._build_field(
            layout, t("search.code_label"), t("search.code_placeholder"), "code"
        )
        self.desc_edit = self._build_field(
            layout, t("search.desc_label"), t("search.desc_placeholder"), "description"
        )
        self.notes_edit = self._build_field(
            layout, t("search.notes_label"), t("search.notes_placeholder"), "notes"
        )

    def _build_field(self, layout: QVBoxLayout, label_text: str, placeholder: str, mode: str):
        """Un cercador = una sola fila de blocs, tots amb la mateixa
        estructura (títol a dalt, contingut a sota): el camp de text i,
        després, els tres resultats."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        # El text complet de l'ajuda va al tooltip: dins d'un camp tan
        # curt no hi cabria sencer.
        edit.setToolTip(placeholder)
        edit.setFixedWidth(_EDIT_WIDTH)
        self._style_edit(edit, mode, _NO_MATCH_BG)
        edit.textChanged.connect(lambda text, m=mode: self.search_changed.emit(m, text))
        # El títol del cercador ("Per núm.:") és el títol d'aquest bloc,
        # just a sobre del seu camp.
        row.addWidget(self._build_block(label_text, edit)[0], 0)

        # Els tres resultats, cadascun amb el seu nom a dalt i el número
        # gran a sota; s'enduen tot l'ample que deixa lliure el camp.
        self._stat_values[mode] = {}
        for key, title_key, color in _STATS:
            value = QLabel(_NO_VALUE)
            value.setStyleSheet(_STAT_VALUE_STYLE.format(color=color))
            self._stat_values[mode][key] = value
            block, title_width = self._build_block(t(title_key), value)
            # Cada bloc creix en proporció al que ocupa el seu nom: així,
            # mentre hi càpiguen tots tres, cap títol no ha de partir-se en
            # dues línies (i la fila es queda baixa). Si l'idioma els fa
            # massa llargs, tornen a partir-se sols; no es retalla text.
            row.addWidget(block, title_width)

        layout.addLayout(row)
        return edit

    @staticmethod
    def _build_block(title_text: str, content: QWidget) -> tuple[QWidget, int]:
        """Bloc d'una columna: el títol a dalt i el contingut a sota, mai
        a la mateixa línia. L'espai que sobra queda entremig, així els
        números i el camp de text queden alineats entre ells encara que un
        títol ocupi dues línies i un altre només una.

        Retorna també l'ample que ocupa el títol en una sola línia, que és
        el que fa servir `_build_field` per repartir l'espai de la fila.
        """
        block = QWidget()
        column = QVBoxLayout(block)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        title = QLabel(title_text)
        title.setStyleSheet(_STAT_TITLE_STYLE)
        title_width = title.sizeHint().width()  # abans d'activar el wrap
        title.setWordWrap(True)
        column.addWidget(title)
        column.addStretch()
        column.addWidget(content)
        return block, title_width

    @staticmethod
    def _style_edit(edit: QLineEdit, mode: str, bg_color: str):
        accent = SEARCH_COLORS[mode]
        edit.setStyleSheet(
            f"background-color: {bg_color}; color: #1a1a1a; border: 1px solid #999; "
            f"border-left: 4px solid {accent}; border-radius: 3px; padding: 1px 6px; font-size: 12px;"
        )

    def set_result(self, mode: str, count, oldest, qty, has_match: bool = False):
        """`has_match` només decideix SI el camp es pinta; el color amb què
        es pinta és sempre el del cercador (`SEARCH_COLORS[mode]`), no un
        color derivat del material o de la posició trobats."""
        edit = {"code": self.code_edit, "description": self.desc_edit, "notes": self.notes_edit}[mode]
        self._style_edit(edit, mode, SEARCH_COLORS[mode] if has_match else _NO_MATCH_BG)
        values = self._stat_values[mode]
        for key, value in (("matches", count), ("oldest", oldest), ("desmagatzem", qty)):
            values[key].setText(str(value))
