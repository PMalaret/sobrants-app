"""Icones dels botons, monocromes i del color que els toqui.

Abans les icones eren emojis dins del text del botó ("🗑️ Esborrar"). Es
veien, però són dibuixos de colors fixos: sobre un botó blau o vermell
quedaven com un adhesiu enganxat, no seguien el color del text i, a la mida
d'un botó, es veien borrosos.

Aquí es fan servir les icones que ja porta Windows a la font **Segoe Fluent
Icons** (Windows 11) o **Segoe MDL2 Assets** (Windows 10): línies
monocromes, dibuixades a la mida exacta que calgui i **pintades amb el
color que se'ls digui**, de manera que la icona d'un botó blau surt blanca i
la d'un botó desactivat, grisa. No cal cap fitxer d'imatge ni cap
dependència nova.

Si cap de les dues fonts hi és (per exemple executant l'aplicació a macOS o
Linux, on el codi també arrenca), `icon()` retorna una icona buida i el botó
es queda només amb el text — que sempre hi és i ja diu què fa.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap

from app.ui import theme

# Per ordre de preferència: la de Windows 11 i, si no, la de Windows 10.
ICON_FONT_CANDIDATES = ("Segoe Fluent Icons", "Segoe MDL2 Assets")

# Nom de la icona -> caràcter de la font. Els noms diuen QUÈ fan, no com es
# veuen, igual que els colors de la paleta.
GLYPHS = {
    "delete": "",    # paperera
    "move": "",      # fletxa cap a la dreta
    "print": "",     # impressora
    "eye": "",       # ull (materials tapats)
    "search": "",    # lupa
    "add": "",       # més
    "export": "",    # fletxa cap avall (exportar)
    "clear": "",     # goma d'esborrar (netejar l'històric)
    # Les dels menús.
    "lock": "\uE72E",         # cadenat (contrasenya)
    "exit": "\uE7E8",         # sortir de l'aplicació
    "save": "\uE74E",         # desar (còpia de seguretat ara)
    "clock": "\uE121",        # rellotge (cada quantes hores)
    "settings": "\uE713",     # engranatges (configuració)
    "open_file": "\uE8E5",    # full amb fletxa (importar d'un fitxer)
    "database": "\uEDA2",     # base de dades
    "globe": "\uE774",        # idioma
    # Les quatre dels dialegs (veure `app.ui.dialogs`).
    "info": "",      # "i" dins d'un cercle
    "question": "",  # "?" dins d'un cercle
    "warning": "",   # triangle d'avis
    "error": "",     # aspa dins d'un cercle
}

# Mida en punts de la icona dins del botó. Es dibuixa al doble de resolució
# (veure `icon`), així es veu igual de fina en pantalles d'alta densitat.
ICON_SIZE = 16
_RENDER_SCALE = 2

_state: dict = {"family": None, "checked": False}


def font_family() -> str | None:
    """La primera font d'icones que hi hagi al sistema, o None si no n'hi ha
    cap. Es mira una sola vegada."""
    if not _state["checked"]:
        available = set(QFontDatabase.families())
        _state["family"] = next((f for f in ICON_FONT_CANDIDATES if f in available), None)
        _state["checked"] = True
    return _state["family"]


def _pixmap(glyph: str, color: str, size: int) -> QPixmap:
    pixmap = QPixmap(size * _RENDER_SCALE, size * _RENDER_SCALE)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    font = QFont(font_family())
    font.setPixelSize(int(size * _RENDER_SCALE * 0.9))
    painter.setFont(font)
    painter.setPen(QColor(color))
    painter.drawText(QRectF(0, 0, pixmap.width(), pixmap.height()), Qt.AlignCenter, glyph)
    painter.end()
    pixmap.setDevicePixelRatio(_RENDER_SCALE)
    return pixmap


def icon(name: str, color_token: str = "on_accent", disabled_token: str = "text_disabled") -> QIcon:
    """La icona `name` pintada amb el color `color_token` de la paleta, i
    amb una segona versió amb `disabled_token` per quan el botó està
    desactivat.

    Les dues versions es dibuixen aquí a posta: si només se'n donés una, Qt
    en faria la de desactivat esvaint-la, i una icona blanca esvaïda damunt
    d'un botó desactivat (que és clar) no es veuria.
    """
    if name not in GLYPHS:
        raise KeyError(f"Icona desconeguda: {name}")
    result = QIcon()
    if font_family() is None:
        return result  # sense font d'icones: el botó es queda amb el text
    glyph = GLYPHS[name]
    result.addPixmap(_pixmap(glyph, theme.color(color_token), ICON_SIZE), QIcon.Normal)
    result.addPixmap(_pixmap(glyph, theme.color(disabled_token), ICON_SIZE), QIcon.Disabled)
    return result


def pixmap(name: str, color_token: str, size: int) -> QPixmap:
    """La icona `name` dibuixada a la mida que es demani, per als llocs on
    no va dins d'un botó (la icona gran dels diàlegs). Torna un mapa de
    píxels buit si no hi ha cap font d'icones."""
    if name not in GLYPHS:
        raise KeyError(f"Icona desconeguda: {name}")
    if font_family() is None:
        return QPixmap()
    return _pixmap(GLYPHS[name], theme.color(color_token), size)


def apply_to(button, name: str, color_token: str = "on_accent") -> None:
    """Posa la icona `name` al botó, amb la mida de sempre. El text del botó
    no es toca: la icona l'acompanya, no el substitueix."""
    button.setIcon(icon(name, color_token))
    button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
