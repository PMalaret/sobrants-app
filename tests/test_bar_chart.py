"""L'escala vertical del gràfic de barres.

El que es comprova aquí és `axis_top`, que decideix fins on arriba l'eix i
cada quant hi va una línia. És l'única part del gràfic que es pot provar
sense pantalla, i és on hi ha la decisió: les línies han de caure a números
de comptar (0, 5, 10, 15...) i no al que surti de dividir el màxim, perquè
si no el gràfic no es pot llegir de reüll.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ui.bar_chart import axis_top


@pytest.mark.parametrize(
    "max_value, expected",
    [
        (17, (20, 5)),      # el cas de sempre: 17 sortides -> 0, 5, 10, 15, 20
        (3, (3, 1)),        # pocs moviments: d'un en un, sense mitges peces
        (1, (1, 1)),
        (250, (300, 100)),
        (1000, (1000, 250)),
    ],
)
def test_the_axis_lands_on_round_numbers(max_value, expected):
    assert axis_top(max_value) == expected


def test_an_empty_or_zero_series_still_has_an_axis():
    """Un interval sense cap moviment no ha de deixar l'eix a zero: sense
    sostre no hi hauria on dibuixar i la divisió peta."""
    assert axis_top(0) == (1, 1)
    assert axis_top(-5) == (1, 1)


def test_the_top_always_covers_the_tallest_bar():
    """La barra més alta hi ha de cabre sencera, i el sostre ha de ser un
    múltiple del salt perquè l'última línia caigui just a dalt de tot. Es
    prova amb tots els valors fins a 2.000, que és molt més del que veurà
    mai un dia de feina."""
    for max_value in range(1, 2001):
        top, step = axis_top(max_value)
        assert top >= max_value, max_value
        assert step >= 1, max_value
        assert top % step == 0, max_value


@pytest.mark.parametrize("max_value", (7, 45, 120, 999, 5000))
def test_the_axis_does_not_end_up_with_too_many_lines(max_value):
    """Entre tres i sis línies: menys no diu res i més embruten el gràfic."""
    top, step = axis_top(max_value)
    assert 1 <= top // step <= 6
