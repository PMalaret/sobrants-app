"""Pestanya 'Estadístiques': quants moviments hi ha hagut, quan, i quantes
peces hi havia cada dia.

Es calcula TOT a partir de l'històric (`Repository.movement_stats`), que és
l'única font de veritat dels moviments de l'aplicació: aquesta pestanya
només llegeix — no escriu, no esborra i no toca cap dada.

L'usuari tria un interval de dates (dos camps de data, amb uns quants
intervals fets per als casos de sempre: avui, els últims 7/30 dies, l'últim
any) i s'hi veu, dia a dia i en una sola taula, el que ha passat al TAULER i
el que ha passat a DESMAGATZEM:

  - Entrades  -> peces col·locades (al Tauler) o unitats registrades (a
                 Desmagatzem: una línia de 5 unitats són 5 entrades).
  - Sortides  -> peces esborrades o unitats retirades.
  - Trasllats -> peces mogudes de posició, comptades una sola vegada: es
                 compta la banda del DESTÍ, perquè un trasllat deixa dues
                 línies a l'històric (origen i destí) i és un sol moviment.
  - Peces     -> quantes n'hi havia al final d'aquell dia. Això no es guarda
                 enlloc: se sap quantes n'hi ha ara i es va desfent el que
                 diu l'històric cap enrere (veure `movement_stats`).

Al costat del títol, la mitjana de sortides del Tauler per dia de
l'interval, que és el número que diu a quin ritme es buida el tauler.
"""
from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import format_number, t
from app.logic.repository import Repository
from app.ui import icons, theme

# Format en què es veuen i s'escriuen les dates dels dos camps (el de la
# base de dades és sempre ISO, veure `_iso`).
DATE_DISPLAY_FORMAT = "dd/MM/yyyy"
# Interval que surt en obrir la pestanya: l'últim mes fins avui.
DEFAULT_RANGE_DAYS = 30
# Intervals fets: (clau de traducció, dies cap enrere comptant avui).
QUICK_RANGES = (
    ("stats.range.today", 1),
    ("stats.range.week", 7),
    ("stats.range.month", 30),
    ("stats.range.year", 365),
)

# Columnes de la taula: (clau de traducció, clau de la dada). Primer el dia,
# després el que ha passat al Tauler i, al final, el de Desmagatzem.
COLUMNS = (
    ("stats.col.day", "day"),
    ("stats.col.in", "board_in"),
    ("stats.col.out", "board_out"),
    ("stats.col.move", "moves"),
    ("stats.col.board_pieces", "board_pieces"),
    ("stats.col.desmagatzem_in", "desmagatzem_in"),
    ("stats.col.desmagatzem_out", "desmagatzem_out"),
    ("stats.col.desmagatzem_pieces", "desmagatzem_pieces"),
)
# Les columnes de moviments se sumen a la fila de totals; les de "quantes
# peces hi havia" no (sumar l'estat de cada dia no voldria dir res).
TOTAL_COLUMNS = ("board_in", "board_out", "moves", "desmagatzem_in", "desmagatzem_out")


class StatisticsTab(QWidget):
    """Només lectura: no emet cap senyal de canvi de dades perquè no en
    canvia cap."""

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ #
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 3, 9, 9)  # el mateix marge que la resta de pestanyes

        layout.addWidget(self._build_filters())

        note = QLabel(t("stats.note"))
        note.setStyleSheet(theme.css("color: $text_muted; font-size: 11px;"))
        layout.addWidget(note)

        layout.addWidget(self._build_days_table())

    def _build_filters(self) -> QWidget:
        box = QGroupBox(t("stats.title"))
        row = QHBoxLayout(box)
        row.setSpacing(6)

        today = QDate.currentDate()
        row.addWidget(QLabel(t("stats.from")))
        self.from_date = self._date_edit(today.addDays(-(DEFAULT_RANGE_DAYS - 1)))
        row.addWidget(self.from_date)
        row.addWidget(QLabel(t("stats.to")))
        self.to_date = self._date_edit(today)
        row.addWidget(self.to_date)

        # Intervals fets: posen les dues dates i consulten de seguida, que
        # és el que es vol el 90% de les vegades.
        for label_key, days in QUICK_RANGES:
            button = QPushButton(t(label_key))
            # Secundaris: acompanyen "Consultar", que és l'acció principal
            # de la fila i l'únic botó que va ple de color.
            button.setProperty("variant", "ghost")
            button.clicked.connect(lambda _checked=False, d=days: self._apply_quick_range(d))
            row.addWidget(button)

        self.apply_button = QPushButton(t("stats.apply"))
        icons.apply_to(self.apply_button, "search")
        self.apply_button.clicked.connect(self.refresh)
        row.addWidget(self.apply_button)

        row.addStretch()
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet(
            theme.css("font-size: 13px; font-weight: 600; color: $text;")
        )
        row.addWidget(self.summary_label)
        return box

    @staticmethod
    def _date_edit(value: QDate) -> QDateEdit:
        edit = QDateEdit(value)
        edit.setCalendarPopup(True)          # amb calendari, per no haver d'escriure la data
        edit.setDisplayFormat(DATE_DISPLAY_FORMAT)
        return edit

    def _build_days_table(self) -> QTableWidget:
        self.days_table = QTableWidget(0, len(COLUMNS))
        self.days_table.setHorizontalHeaderLabels([t(key) for key, _field in COLUMNS])
        self.days_table.setAlternatingRowColors(True)
        self.days_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.days_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.days_table.verticalHeader().setVisible(False)
        header = self.days_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        self.days_table.setColumnWidth(0, 120)
        for col in range(1, len(COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.Stretch)
        return self.days_table

    # ------------------------------------------------------------------ #
    def _apply_quick_range(self, days: int):
        """Interval fet: `days` dies comptant avui (1 = només avui)."""
        today = QDate.currentDate()
        self.from_date.setDate(today.addDays(-(days - 1)))
        self.to_date.setDate(today)
        self.refresh()

    @staticmethod
    def _iso(edit: QDateEdit) -> str:
        """La data del camp en ISO ("AAAA-MM-DD"), que és com es guarda a
        l'històric i com la vol el repositori."""
        return edit.date().toString("yyyy-MM-dd")

    def refresh(self):
        """Torna a calcular-ho tot amb l'interval que hi hagi als camps. Es
        crida sola en entrar a la pestanya i quan el Tauler o Desmagatzem
        escriuen a l'històric.

        Un interval al revés (la data final abans que la inicial) no obre
        cap finestra d'avís —això es crida sol, i un avís enmig d'una alta
        de peça seria una interrupció— sinó que es diu allà mateix, on van
        els resultats, i la taula es queda buida fins que es corregeix.
        """
        if self.from_date.date() > self.to_date.date():
            self.days_table.setRowCount(0)
            self.summary_label.setText(t("stats.invalid_range.text"))
            return
        stats = self.repo.movement_stats(self._iso(self.from_date), self._iso(self.to_date))
        self._fill_days_table(stats["days"])
        self._update_summary(stats)

    def _fill_days_table(self, days: list):
        # Una fila per dia amb moviment i, al final, la fila de totals (en
        # negreta): els dies sense cap moviment no hi surten, per no omplir
        # la taula de zeros — i tampoc s'hi perd res, perquè un dia sense
        # moviment acaba amb les mateixes peces que el dia anterior.
        self.days_table.setRowCount(len(days) + (1 if days else 0))
        for r, day in enumerate(days):
            for c, (_key, field) in enumerate(COLUMNS):
                value = day[field] if field == "day" else format_number(day[field])
                self.days_table.setItem(r, c, self._cell(value, numeric=(field != "day")))
        if days:
            self._fill_totals_row(len(days), days)

    def _fill_totals_row(self, row: int, days: list):
        for c, (_key, field) in enumerate(COLUMNS):
            if field == "day":
                text = t("stats.total_row")
            elif field in TOTAL_COLUMNS:
                text = format_number(sum(day[field] for day in days))
            else:
                text = ""     # sumar les peces de cada dia no voldria dir res
            item = self._cell(text, numeric=(field != "day"))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.days_table.setItem(row, c, item)

    @staticmethod
    def _cell(text: str, numeric: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem(str(text))
        if numeric:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return item

    def _update_summary(self, stats: dict):
        """El número que resumeix l'interval: a quin ritme surten peces del
        Tauler. Es reparteix entre TOTS els dies de l'interval triat, no
        només entre els que han tingut moviment."""
        self.summary_label.setText(
            t("stats.board_out_per_day", value=f"{stats['board_out_per_day']:.2f}")
        )
