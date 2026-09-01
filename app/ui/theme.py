"""Els colors de l'aplicació, tots en un sol lloc.

Abans cada widget portava el seu color escrit a dins (una vintena llarga de
`setStyleSheet` amb codis `#rrggbb` repartits per dotze fitxers, més els de
`style.qss` i els de l'escala d'ocupació, que fins i tot vivien dins de les
regles de negoci). Amb això no es podia canviar l'aspecte de res sense
anar-lo a buscar per tot arreu, i molt menys tenir-ne dues versions.

Ara el color té un sol origen: la paleta d'aquest mòdul. Funciona igual que
`app.i18n` amb els idiomes —hi ha una paleta activa i tothom hi passa per
una funció— i la regla és la mateixa: **cap `#rrggbb` fora d'aquí**.

Com s'hi accedeix, segons què es necessiti:

  - `color("accent")` / `qcolor("accent")` — un color solt, en text o com a
    QColor (per pintar cel·les de taula).
  - `css("color: $text_muted;")` — un fragment de full d'estil amb els
    colors substituïts. És el que fan servir els widgets que porten estil
    propi: es continua veient l'estil al costat del widget, però el color
    surt de la paleta.
  - `stylesheet()` — `style.qss` sencer, que és aquest mateix mecanisme
    aplicat al full global (el fitxer porta `$token` en comptes de codis).
  - `apply(app)` — el que crida l'arrencada: estil Fusion, paleta de Qt i
    full d'estil, tot alhora.

Per què Fusion i no l'estil natiu de Windows: Fusion pinta tots els widgets
estàndard a partir de la `QPalette`, i l'estil natiu se salta bona part dels
seus colors. Mentre tot és clar gairebé no es nota; amb una paleta fosca, en
canvi, l'estil natiu deixaria menús, calendaris, barres de desplaçament i
diàlegs en clar. Fusion és, doncs, el que fa que una paleta nova s'apliqui
de debò a tot arreu.

Els noms dels colors diuen QUÈ són, no de quin color són (`danger`, no
`red`): així una paleta pot fer servir un altre to per a la mateixa cosa
sense que el nom passi a mentir.
"""
from __future__ import annotations

from pathlib import Path
from string import Template

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QStyleFactory

STYLESHEET_PATH = Path(__file__).with_name("style.qss")

# Paleta clara: exactament els colors que ha tingut sempre l'aplicació,
# ara amb nom. Els comentaris diuen d'on ve cadascun quan no és evident.
LIGHT = {
    # -- Fons i text ------------------------------------------------- #
    "window": "#f5f6f8",          # fons de la finestra
    "surface": "#ffffff",         # taules, quadres i panells
    "surface_alt": "#eef0f3",     # capçaleres de taula, barra d'estat, zona d'accions
    "surface_tab": "#e8eaee",     # pestanya no seleccionada
    "row_alt": "#fafbfc",         # files alternes de les taules
    "text": "#1a1a1a",
    "text_secondary": "#555555",  # text d'ajuda dels diàlegs
    "text_muted": "#8a8f98",      # text de suport, encara més discret
    "text_disabled": "#9aa0a8",   # opcions de menú desactivades
    # -- Vores ------------------------------------------------------- #
    "border": "#d0d3d9",
    "border_input": "#c7cad1",    # vora dels camps de text
    "border_mid": "#999999",      # vora dels elements de color (cercadors, llegenda),
                                  # on la vora neutra es perdria
    "grid": "#e2e4e8",            # graella de les taules
    # -- Color d'acció ----------------------------------------------- #
    "accent": "#2f6fed",
    "accent_hover": "#2559c9",
    "accent_pressed": "#1e47a3",
    "accent_soft": "#d8e2fb",     # fons d'una opció de menú assenyalada
    "on_accent": "#ffffff",       # text a sobre del color d'acció
    "disabled_bg": "#c9cdd4",
    "disabled_text": "#7e838b",
    # -- Estats ------------------------------------------------------ #
    "danger": "#c62828",          # avisos, esborrar, "Materials tapats"
    "danger_hover": "#a52020",
    "danger_pressed": "#8b1a1a",
    "success": "#1a9c6d",         # USB connectat
    "warning": "#b26a00",         # avisos que no són errors
    # -- Tauler: escala d'ocupació d'una posició --------------------- #
    # Els cinc colors de referència del propi Excel original (K12:K16):
    # 0-1 peça blanc, 2 groc clar, 3 verd clar, 4 blau clar, 5 (plena) vermell.
    "occupancy_1": "#ffffff",
    "occupancy_2": "#fff2cc",
    "occupancy_3": "#c6e0b4",
    "occupancy_4": "#b4c6e7",
    "occupancy_5": "#ff0000",
    "occupancy_text": "#000000",       # text a sobre dels quatre primers
    "occupancy_text_full": "#ffffff",  # a sobre del vermell de posició plena
    # -- Tauler: vores que ajuden a llegir la graella ---------------- #
    "grid_block": "#6b7280",      # on comença cada bloc de 5 camps
    "grid_row": "#9aa0a8",        # cada 5 files, per comptar de 5 en 5
    # -- Cercadors --------------------------------------------------- #
    # Un color per cercador, el mateix al camp, al Tauler i a Desmagatzem.
    # El de notes és el "Light Red Fill" de l'Excel, una mica més pujat.
    "search_code": "#ffe08a",
    "search_description": "#a8e6a1",
    "search_notes": "#ffa8b4",
    "search_empty": "#ffffff",    # camp sense cap coincidència
    # -- Històric: color de cada tipus de moviment ------------------- #
    "movement_in": "#1a7f37",
    "movement_out": "#c62828",
    "movement_move_out": "#b48c64",
    "movement_move_in": "#78460f",
}

# De moment només n'hi ha una. La paleta fosca serà una entrada més d'aquí:
# tot el que dibuixa passa per `color()`/`css()`, o sigui que afegir-la no
# demana tocar cap widget.
PALETTES = {"light": LIGHT}
DEFAULT_THEME = "light"

_state = {"theme": DEFAULT_THEME}


def get_theme() -> str:
    return _state["theme"]


def set_theme(name: str) -> None:
    if name not in PALETTES:
        raise ValueError(f"Tema desconegut: {name}")
    _state["theme"] = name


def palette() -> dict:
    """La paleta activa sencera."""
    return PALETTES[_state["theme"]]


def color(name: str) -> str:
    """El color `name` de la paleta activa, en text ("#rrggbb")."""
    try:
        return palette()[name]
    except KeyError:
        raise KeyError(f"Color desconegut: {name}") from None


def qcolor(name: str) -> QColor:
    """El mateix, com a QColor (per pintar cel·les, vores i textos)."""
    return QColor(color(name))


def css(fragment: str) -> str:
    """Un fragment de full d'estil amb els `$token` substituïts pels colors
    de la paleta activa.

    S'escriu com un full d'estil normal, però amb noms en comptes de codis:

        button.setStyleSheet(theme.css("background-color: $danger; color: $on_accent;"))

    Es fa servir `string.Template` (i no `str.format`) perquè un full
    d'estil va ple de claus `{ }` que `format` es prendria com a seves.
    """
    return Template(fragment).substitute(palette())


def stylesheet() -> str:
    """`style.qss` amb els colors de la paleta activa.

    Si el fitxer no hi fos (una còpia incompleta), es torna un full buit:
    l'aplicació s'ha de poder obrir igual, encara que es vegi amb l'aspecte
    pelat de Qt.
    """
    if not STYLESHEET_PATH.exists():
        return ""
    return css(STYLESHEET_PATH.read_text(encoding="utf-8"))


def qt_palette() -> QPalette:
    """La paleta activa traduïda a una `QPalette` de Qt.

    El full d'estil no arriba a tot: els diàlegs del sistema, el calendari
    d'un camp de data o un tooltip els pinta Qt amb la QPalette. Posant-hi
    els mateixos colors, tot va a joc vingui d'on vingui.
    """
    qp = QPalette()
    roles = {
        QPalette.Window: "window",
        QPalette.WindowText: "text",
        QPalette.Base: "surface",
        QPalette.AlternateBase: "row_alt",
        QPalette.Text: "text",
        QPalette.ToolTipBase: "surface",
        QPalette.ToolTipText: "text",
        QPalette.Button: "surface_alt",
        QPalette.ButtonText: "text",
        QPalette.Highlight: "accent",
        QPalette.HighlightedText: "on_accent",
        QPalette.PlaceholderText: "text_muted",
    }
    for role, token in roles.items():
        qp.setColor(role, qcolor(token))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        qp.setColor(QPalette.Disabled, role, qcolor("disabled_text"))
    qp.setColor(QPalette.Disabled, QPalette.Button, qcolor("disabled_bg"))
    return qp


def occupancy_colors(level: int) -> tuple:
    """(fons, text) amb què es pinta una posició segons com d'ocupada
    estigui (`rules.occupancy_level`, d'1 a 5).

    El text el decideix el fons: a sobre del vermell de "posició plena" ha
    de ser clar per continuar sent llegible, i a sobre dels altres quatre,
    fosc. Es decideix aquí, amb el color, i no a cada taula que el pinta.
    """
    background = color(f"occupancy_{level}")
    foreground = color("occupancy_text_full" if level == 5 else "occupancy_text")
    return background, foreground


def search_color(mode: str) -> str:
    """El color d'un dels tres cercadors ("code", "description", "notes").

    És el mateix a tot arreu —la vora del camp, les coincidències del
    Tauler i les de Desmagatzem—, i identifica el CERCADOR, mai el
    material trobat.
    """
    return color(f"search_{mode}")


def search_qcolor(mode: str) -> QColor:
    return QColor(search_color(mode))


def apply(app) -> None:
    """Deixa l'aplicació amb el tema actiu: estil Fusion, paleta i full
    d'estil. Es crida a l'arrencada i, quan hi hagi més d'una paleta,
    cada vegada que se'n canviï."""
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(qt_palette())
    app.setStyleSheet(stylesheet())
