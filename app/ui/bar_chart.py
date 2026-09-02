"""Gràfic de barres: una barra per dia, d'una sola dada a la vegada.

És un widget que es pinta sencer aquí dins, no un QtCharts. Els motius són
els de sempre en aquesta aplicació: els colors han de sortir de la paleta
(`theme`) com la resta de la pantalla, el gràfic és d'una sola sèrie i sense
interacció més enllà d'ensenyar el valor en passar-hi el ratolí, i portar
QtCharts obligaria a ficar `Qt6Charts.dll` dins de l'executable per dibuixar
rectangles.

Qui l'omple decideix QUÈ s'hi veu: aquí només arriben les barres ja fetes
(`Bar`), amb l'etiqueta curta de l'eix, el text llarg per al ratolí i el
valor. El gràfic no sap res de dates ni de moviments.
"""
from __future__ import annotations

import math
from typing import NamedTuple

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from app.i18n import format_number
from app.ui import theme


class Bar(NamedTuple):
    """Una barra: `label` és el que va sota l'eix (curt, que n'hi caben
    poques), `caption` el que es veu en passar-hi el ratolí (la data
    sencera) i `value` l'alçada."""

    label: str
    caption: str
    value: int


def axis_top(max_value: int, divisions: int = 4) -> tuple[int, int]:
    """El sostre de l'eix vertical i el salt entre línies, tots dos rodons.

    Amb el màxim just (posem 17) les línies caurien a 4,25 / 8,5 / 12,75 i
    no es podria llegir res de reüll. Es busca el salt "de comptar" més
    petit que faci prou —1, 2, 2,5 o 5 per la potència de 10 que toqui— i el
    sostre és el primer múltiple d'aquell salt que arribi al màxim: per a 17,
    salt de 5 i sostre 20.

    El 2,5 (o sigui 25, 250, 2.500...) hi és perquè sense ell, entre 500 i
    1.000, l'únic salt que fa prou és el de 500 i l'eix es quedava amb dues
    línies comptades. Només s'hi val a partir de la potència 10, que és quan
    dona un número enter.

    Els valors són comptadors de peces, sempre enters, així que el salt mai
    no baixa d'1: amb pocs moviments val més tenir 0-1-2-3 que mitges peces.
    """
    if max_value <= 0:
        return 1, 1
    raw = max_value / divisions
    power = 10 ** math.floor(math.log10(raw)) if raw >= 1 else 1
    multipliers = (1, 2, 5, 10) if power < 10 else (1, 2, 2.5, 5, 10)
    step = int(next(m * power for m in multipliers if m * power >= raw))
    return step * math.ceil(max_value / step), step


class BarChart(QWidget):
    """Les barres d'una sola dada. `set_series` ho canvia tot de cop."""

    # Marges de dins del requadre. L'esquerre no és fix: es calcula al
    # moment de pintar, perquè depèn de quant ocupen els números de l'eix
    # (no és el mateix "8" que "1.240").
    PADDING = 12
    # Separació entre els números de l'eix i el gràfic, i entre el gràfic i
    # les dates de sota.
    LABEL_GAP = 6
    # Amplada de barra: mai tan fina que no es vegi ni tan ampla que sembli
    # un bloc. Entremig, ocupa el 70% del que li toca perquè quedi aire
    # entre barra i barra.
    MIN_BAR_WIDTH = 3
    MAX_BAR_WIDTH = 44
    BAR_WIDTH_RATIO = 0.7

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bars: list[Bar] = []
        self._color = theme.qcolor("accent")
        self._empty_text = ""
        self._hover = -1
        # Sense clicar: el valor de cada barra ha de sortir només acostant-hi
        # el ratolí, que és com es llegeix un gràfic.
        self.setMouseTracking(True)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # ------------------------------------------------------------------ #
    def set_series(self, bars: list[Bar], color: QColor, empty_text: str = ""):
        """Les barres que s'han de veure. `empty_text` és el que es diu quan
        no n'hi ha cap: un gràfic buit sense explicació sembla espatllat."""
        self._bars = list(bars)
        self._color = color
        self._empty_text = empty_text
        self._hover = -1
        self.update()

    # ------------------------------------------------------------------ #
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        frame = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(QPen(theme.qcolor("border"), 1))
        painter.setBrush(theme.qcolor("surface"))
        painter.drawRoundedRect(frame, 10, 10)

        if not self._bars:
            painter.setPen(theme.qcolor("text_muted"))
            painter.drawText(frame, Qt.AlignCenter, self._empty_text)
            return

        metrics = painter.fontMetrics()
        top_value, step = axis_top(max(bar.value for bar in self._bars))
        ticks = list(range(0, top_value + 1, step))
        axis_width = max(metrics.horizontalAdvance(format_number(v)) for v in ticks)

        left = frame.left() + self.PADDING + axis_width + self.LABEL_GAP
        bottom = frame.bottom() - self.PADDING - metrics.height() - self.LABEL_GAP
        plot = QRect(
            left,
            frame.top() + self.PADDING,
            frame.right() - self.PADDING - left,
            bottom - frame.top() - self.PADDING,
        )
        # Finestra massa petita per a un gràfic: val més no dibuixar res que
        # dibuixar barres d'un píxel damunt dels números.
        if plot.width() < 40 or plot.height() < 40:
            return

        self._paint_grid(painter, plot, ticks, top_value, metrics)
        self._paint_bars(painter, plot, top_value)
        self._paint_day_labels(painter, plot, metrics)

    def _paint_grid(self, painter, plot: QRect, ticks, top_value: int, metrics):
        """Les línies horitzontals i el seu número a l'esquerra."""
        for value in ticks:
            y = plot.bottom() - round(value / top_value * plot.height())
            # La de baix (el zero) és la línia de terra de les barres i va
            # més marcada; les altres són guies i han de quedar al fons.
            painter.setPen(QPen(theme.qcolor("border" if value == 0 else "grid"), 1))
            painter.drawLine(plot.left(), y, plot.right(), y)
            painter.setPen(theme.qcolor("text_muted"))
            label_box = QRect(
                plot.left() - self.LABEL_GAP - 400, y - metrics.height() // 2,
                400, metrics.height(),
            )
            painter.drawText(label_box, Qt.AlignRight | Qt.AlignVCenter, format_number(value))

    def _paint_bars(self, painter, plot: QRect, top_value: int):
        painter.setPen(Qt.NoPen)
        for index, _bar in enumerate(self._bars):
            rect = self._bar_rect(index, plot, top_value)
            if rect is None:
                continue
            # La barra de sota el ratolí, més fosca: així es veu de quina
            # és el valor que surt al rètol.
            painter.setBrush(self._color.darker(115) if index == self._hover else self._color)
            painter.drawRect(rect)

    def _paint_day_labels(self, painter, plot: QRect, metrics):
        """Les dates de sota. No hi caben totes quan l'interval és llarg, o
        sigui que se'n salten: se'n posa una cada tantes, les que hi
        càpiguen sense tocar-se."""
        widest = max(metrics.horizontalAdvance(bar.label) for bar in self._bars) + 10
        every = max(1, math.ceil(len(self._bars) * widest / plot.width()))
        painter.setPen(theme.qcolor("text_muted"))
        slot = plot.width() / len(self._bars)
        for index in range(0, len(self._bars), every):
            center = plot.left() + slot * (index + 0.5)
            box = QRect(
                round(center - widest / 2), plot.bottom() + self.LABEL_GAP,
                round(widest), metrics.height(),
            )
            painter.drawText(box, Qt.AlignHCenter | Qt.AlignTop, self._bars[index].label)

    def _bar_rect(self, index: int, plot: QRect, top_value: int) -> QRect | None:
        """El rectangle d'una barra, o None si val zero (un dia sense res no
        ha de deixar cap ratlla arran de terra: no s'ha de confondre amb un
        dia d'un sol moviment)."""
        bar = self._bars[index]
        if bar.value <= 0:
            return None
        slot = plot.width() / len(self._bars)
        width = min(max(slot * self.BAR_WIDTH_RATIO, self.MIN_BAR_WIDTH), self.MAX_BAR_WIDTH)
        height = max(1, round(bar.value / top_value * plot.height()))
        center = plot.left() + slot * (index + 0.5)
        return QRect(round(center - width / 2), plot.bottom() - height, round(width), height)

    # ------------------------------------------------------------------ #
    def mouseMoveEvent(self, event):
        """El valor de la barra que es té sota el ratolí. Es mira la
        COLUMNA, no el rectangle pintat: una barra baixa és un blanc molt
        petit i s'hauria d'encertar de ple per veure'n el número."""
        index = self._index_at(event.position().x())
        if index != self._hover:
            self._hover = index
            self.update()
        if index >= 0:
            bar = self._bars[index]
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{bar.caption}: {format_number(bar.value)}",
                self,
            )
        else:
            QToolTip.hideText()

    def leaveEvent(self, event):
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def _index_at(self, x: float) -> int:
        """Quina barra cau a l'alçada horitzontal `x`, o -1 si és fora."""
        if not self._bars:
            return -1
        metrics = self.fontMetrics()
        top_value, step = axis_top(max(bar.value for bar in self._bars))
        axis_width = max(
            metrics.horizontalAdvance(format_number(v))
            for v in range(0, top_value + 1, step)
        )
        left = self.PADDING + axis_width + self.LABEL_GAP
        width = self.rect().width() - self.PADDING - left
        if width <= 0 or not (left <= x < left + width):
            return -1
        index = int((x - left) / (width / len(self._bars)))
        return min(index, len(self._bars) - 1)
