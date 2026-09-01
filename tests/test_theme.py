"""La paleta: que hi siguin tots els colors i que no n'hi hagi cap fora.

La regla de `app/ui/theme.py` és que el color té un sol origen. Això només
es manté si algú ho comprova: el primer test recorre el codi buscant codis
`#rrggbb` escrits a mà, i els altres asseguren que qualsevol paleta pugui
pintar-ho tot (que és el que farà falta quan n'hi hagi una de fosca).
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ui import theme

# Un codi de color escrit a mà: #abc o #aabbcc.
COLOR_CODE = re.compile(r"#[0-9a-fA-F]{3}\b|#[0-9a-fA-F]{6}\b")
# L'únic fitxer que en pot tenir: la paleta.
PALETTE_FILE = ROOT / "app" / "ui" / "theme.py"


def teardown_function(_):
    # que un test no deixi el tema canviat per als següents
    theme.set_theme(theme.DEFAULT_THEME)


def test_no_color_codes_outside_the_palette():
    """Cap `#rrggbb` fora de theme.py: ni als widgets, ni al full d'estil,
    ni a les regles de negoci. Si aquest test falla, el color que s'hi ha
    escrit ha d'anar a la paleta i sortir-ne per `color()` o `css()` —
    altrament, el dia que hi hagi una paleta fosca aquell tros es quedaria
    clar."""
    offenders = []
    for path in sorted(list((ROOT / "app").rglob("*.py")) + list((ROOT / "app").rglob("*.qss"))):
        if path == PALETTE_FILE:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if COLOR_CODE.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert offenders == []


def test_every_palette_has_exactly_the_same_colors():
    """Cap paleta pot oblidar-se d'un color: si a una li'n falta un, el
    widget que el demani peta (o es queda sense pintar). Mateixa idea que
    la comprovació dels 4 idiomes a `test_i18n`."""
    names = {name: set(colors) for name, colors in theme.PALETTES.items()}
    reference = names[theme.DEFAULT_THEME]
    incomplete = {name: reference ^ keys for name, keys in names.items() if keys != reference}
    assert incomplete == {}


def test_all_colors_are_written_as_hex_codes():
    for name, colors in theme.PALETTES.items():
        for key, value in colors.items():
            assert re.fullmatch(r"#[0-9a-f]{6}", value), f"{name}.{key} = {value}"


def test_the_stylesheet_can_be_built_with_every_palette():
    """`style.qss` fa servir noms de color: si un no és a la paleta, el
    full no es pot construir i l'aplicació s'obriria sense estil."""
    for name in theme.PALETTES:
        theme.set_theme(name)
        rendered = theme.stylesheet()
        assert rendered, name
        assert "$" not in rendered, f"{name}: ha quedat algun nom sense substituir"


def test_occupancy_colors_give_a_readable_pair_for_every_level():
    """Cada nivell d'ocupació té el seu fons, i el text hi va a joc: clar
    sobre el vermell de posició plena, fosc sobre la resta."""
    from app.logic.rules import OCCUPANCY_LEVELS

    backgrounds = []
    for level in OCCUPANCY_LEVELS:
        background, foreground = theme.occupancy_colors(level)
        backgrounds.append(background)
        assert foreground == theme.color(
            "occupancy_text_full" if level == 5 else "occupancy_text"
        )
    assert len(set(backgrounds)) == len(OCCUPANCY_LEVELS)  # un color per nivell, mai repetit


def test_each_search_has_its_own_color():
    colors = {mode: theme.search_color(mode) for mode in ("code", "description", "notes")}
    assert len(set(colors.values())) == 3


def test_an_unknown_color_fails_loudly():
    """Val més petar en construir el widget que pintar-lo de qualsevol
    manera: així una errada d'escriptura surt de seguida."""
    with pytest.raises(KeyError):
        theme.color("no_existeix")
    with pytest.raises(KeyError):
        theme.css("color: $no_existeix;")


def test_an_unknown_theme_is_rejected():
    with pytest.raises(ValueError):
        theme.set_theme("neon")
    assert theme.get_theme() == theme.DEFAULT_THEME
