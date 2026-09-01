"""Pestanya 'Estadístiques': quants moviments hi ha hagut i quan.

Es calcula TOT a partir de l'històric (`Repository.movement_stats` i
`movement_stats_by_destination`), que és l'única font de veritat dels
moviments de l'aplicació: aquesta pestanya només llegeix — no escriu, no
esborra i no toca cap dada.

L'usuari tria un interval de dates (dos camps de data, amb uns quants
intervals fets per als casos de sempre: avui, els últims 7/30 dies, l'últim
any) i s'hi veu, dia a dia:

  - Entrades  -> línies "in" de l'històric (peces col·locades al Tauler i
                 unitats registrades a Desmagatzem).
  - Sortides  -> línies "out" (peces esborrades i unitats retirades).
  - Trasllats -> línies "move_in", és a dir la banda del DESTÍ. Un trasllat
                 deixa dues línies a l'històric (origen i destí) i comptant
                 només la del destí surt un moviment per trasllat, no dos,
                 i alhora es pot dir a quina posició ha anat a parar (la
                 taula de la dreta).

És la primera versió, a posta senzilla: la taula de dies i el repartiment
per posició de destí. Qualsevol estadística nova hauria de sortir d'aquí
mateix, del mateix interval de dates i de les mateixes consultes.
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
from app.ui import theme

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

# Columnes de la taula de dies: (clau de traducció, clau de la dada).
DAY_COLUMNS = (
    ("stats.col.day", "day"),
    ("stats.col.in", "in"),
    ("stats.col.out", "out"),
    ("stats.col.move", "move"),
    ("stats.col.total", "total"),
)


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

        tables = QHBoxLayout()
        tables.setSpacing(9)
        tables.addWidget(self._build_days_table(), 3)
        tables.addWidget(self._build_destinations_box(), 1)
        layout.addLayout(tables)

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
            button.clicked.connect(lambda _checked=False, d=days: self._apply_quick_range(d))
            row.addWidget(button)

        self.apply_button = QPushButton(t("stats.apply"))
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
        self.days_table = QTableWidget(0, len(DAY_COLUMNS))
        self.days_table.setHorizontalHeaderLabels([t(key) for key, _field in DAY_COLUMNS])
        self.days_table.setAlternatingRowColors(True)
        self.days_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.days_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.days_table.verticalHeader().setVisible(False)
        header = self.days_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        self.days_table.setColumnWidth(0, 140)
        for col in range(1, len(DAY_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.Stretch)
        return self.days_table

    def _build_destinations_box(self) -> QWidget:
        box = QGroupBox(t("stats.destinations_title"))
        column = QVBoxLayout(box)
        self.destinations_table = QTableWidget(0, 2)
        self.destinations_table.setHorizontalHeaderLabels(
            [t("stats.col.position"), t("stats.col.move")]
        )
        self.destinations_table.setAlternatingRowColors(True)
        self.destinations_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.destinations_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.destinations_table.verticalHeader().setVisible(False)
        destinations_header = self.destinations_table.horizontalHeader()
        for col in range(2):
            destinations_header.setSectionResizeMode(col, QHeaderView.Stretch)
        column.addWidget(self.destinations_table)
        return box

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
        els resultats, i les taules es queden buides fins que es corregeix.
        """
        if self.from_date.date() > self.to_date.date():
            self.days_table.setRowCount(0)
            self.destinations_table.setRowCount(0)
            self.summary_label.setText(t("stats.invalid_range.text"))
            return
        start, end = self._iso(self.from_date), self._iso(self.to_date)
        days = self.repo.movement_stats(start, end)
        self._fill_days_table(days)
        self._fill_destinations_table(self.repo.movement_stats_by_destination(start, end))
        self._update_summary(days)

    def _fill_days_table(self, days: list[dict]):
        # Una fila per dia amb moviment i, al final, la fila de totals (en
        # negreta): els dies sense cap moviment no hi surten, per no omplir
        # la taula de zeros.
        self.days_table.setRowCount(len(days) + (1 if days else 0))
        for r, day in enumerate(days):
            for c, (_key, field) in enumerate(DAY_COLUMNS):
                value = day[field] if field == "day" else format_number(day[field])
                self.days_table.setItem(r, c, self._cell(value, numeric=(field != "day")))
        if days:
            self._fill_totals_row(len(days), days)

    def _fill_totals_row(self, row: int, days: list[dict]):
        totals = {field: sum(day[field] for day in days) for _key, field in DAY_COLUMNS[1:]}
        values = [t("stats.total_row")] + [format_number(totals[field]) for _k, field in DAY_COLUMNS[1:]]
        for c, value in enumerate(values):
            item = self._cell(value, numeric=(c > 0))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.days_table.setItem(row, c, item)

    def _fill_destinations_table(self, destinations: list[dict]):
        self.destinations_table.setRowCount(len(destinations))
        for r, entry in enumerate(destinations):
            self.destinations_table.setItem(r, 0, self._cell(str(entry["position"])))
            self.destinations_table.setItem(
                r, 1, self._cell(format_number(entry["count"]), numeric=True)
            )

    @staticmethod
    def _cell(text: str, numeric: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem(str(text))
        if numeric:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return item

    def _update_summary(self, days: list[dict]):
        if not days:
            self.summary_label.setText(t("stats.empty"))
            return
        self.summary_label.setText(
            t(
                "stats.summary",
                days=format_number(len(days)),
                in_count=format_number(sum(day["in"] for day in days)),
                out_count=format_number(sum(day["out"] for day in days)),
                move_count=format_number(sum(day["move"] for day in days)),
            )
        )
