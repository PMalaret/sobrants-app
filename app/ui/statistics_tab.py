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

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import format_number, t
from app.logic.repository import Repository
from app.ui import icons, theme
from app.ui.bar_chart import Bar, BarChart

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

# El gràfic ensenya UNA columna a la vegada, la que es triï al desplegable:
# totes menys el dia, que és el que va a l'eix horitzontal. Posar-les totes
# juntes no serviria de res, perquè "quantes peces hi havia" es compta per
# centenars i els moviments d'un dia per unitats: al costat de les primeres,
# les barres dels moviments quedarien totes arran de terra.
CHART_COLUMNS = tuple((key, field) for key, field in COLUMNS if field != "day")
# De quin color va la barra segons què s'ensenyi: els mateixos colors amb
# què l'històric pinta els moviments, per no haver-ne d'aprendre uns altres.
# Verd el que entra, vermell el que surt, i el color d'acció per als
# trasllats i per als recomptes, que no són ni una cosa ni l'altra.
CHART_COLORS = {
    "board_in": "movement_in",
    "board_out": "movement_out",
    "moves": "accent",
    "board_pieces": "accent",
    "desmagatzem_in": "movement_in",
    "desmagatzem_out": "movement_out",
    "desmagatzem_pieces": "accent",
}
# La data de sota l'eix va curta, que n'hi han de cabre moltes; la del rètol
# que surt en passar-hi el ratolí, sencera (DATE_DISPLAY_FORMAT), perquè un
# interval pot passar d'any.
CHART_LABEL_FORMAT = "dd/MM"
# Marge que es deixa a l'ample de la taula per a la barra de desplaçament
# vertical, que hi surt en quant l'interval passa dels dies que hi caben.
# Sense això, l'última columna quedava sota la barra i es veia retallada.
_SCROLLBAR_ALLOWANCE = 20
# Per estreta que quedi la taula, prou per veure-hi el dia i un parell de
# columnes; la resta, amb la barra de sota.
_TABLE_MIN_WIDTH = 320


class StatisticsTab(QWidget):
    """Només lectura: no emet cap senyal de canvi de dades perquè no en
    canvia cap."""

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        # Els dies de l'última consulta. Es guarden perquè canviar què
        # ensenya el gràfic només ha de tornar a pintar, no a consultar.
        self._days: list = []
        # Cert un cop la taula ja té l'ample de les seves columnes (veure
        # `_fit_table_width`).
        self._table_sized = False
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ #
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 3, 9, 9)  # el mateix marge que la resta de pestanyes

        # Sense separació entre els filtres i el que filtren: la caixa dels
        # filtres ja té vora pròpia i es distingeix sense deixar-hi un buit.
        layout.setSpacing(0)
        layout.addWidget(self._build_filters())

        # La taula i el gràfic es reparteixen l'amplada, amb una nansa al mig
        # per si es vol donar més espai a l'un o a l'altre. La taula és de
        # columnes estretes —números de dues o tres xifres— i no necessita
        # mitja pantalla; el gràfic sí que se n'aprofita.
        self.content = QSplitter(Qt.Horizontal)
        self.content.addWidget(self._build_days_table())
        self.content.addWidget(self._build_chart())
        # Tota l'amplada que sobri, per al gràfic: la taula ja té la seva
        # (veure `_fit_table_width`) i eixamplar-la més només li deixaria un
        # marge buit a la dreta.
        self.content.setStretchFactor(0, 0)
        self.content.setStretchFactor(1, 1)
        # Que la nansa no pugui amagar del tot cap dels dos: mitja pantalla
        # buida sembla que l'aplicació s'hagi trencat.
        self.content.setChildrenCollapsible(False)
        layout.addWidget(self.content)

    def build_note_widget(self) -> QWidget:
        """La nota de com es compten els moviments, per posar-la a la barra
        d'estat de la finestra —com la llegenda del Tauler—, i no damunt de
        la taula: es llegeix un cop i després només fa nosa."""
        note = QLabel(t("stats.note"))
        note.setStyleSheet(theme.css("color: $text_muted; font-size: 11px;"))
        return note

    def _build_chart(self) -> QWidget:
        """El gràfic i el desplegable que diu quina columna s'hi veu."""
        panel = QWidget()
        box = QVBoxLayout(panel)
        box.setContentsMargins(9, 0, 0, 0)   # només la separació amb la taula

        picker = QHBoxLayout()
        picker.addWidget(QLabel(t("stats.chart.metric")))
        self.metric_picker = QComboBox()
        for key, field in CHART_COLUMNS:
            self.metric_picker.addItem(t(key), field)
        # Comença per les sortides del tauler: és el número del qual ja es
        # dona la mitjana aquí dalt, o sigui el que es mira més.
        self.metric_picker.setCurrentIndex(
            [field for _key, field in CHART_COLUMNS].index("board_out")
        )
        picker.addWidget(self.metric_picker)
        # A l'ample que li demani el nom més llarg, no a tot l'ample del
        # gràfic: és un tria-i-para, no un camp per escriure-hi.
        picker.addStretch()
        box.addLayout(picker)

        self.chart = BarChart()
        box.addWidget(self.chart, 1)
        # El senyal, l'últim de tot: `_update_chart` pinta a `self.chart`, o
        # sigui que no es pot deixar connectat abans que el gràfic existeixi.
        self.metric_picker.currentIndexChanged.connect(self._update_chart)
        # Per estret que es deixi el gràfic, prou per veure-hi les barres.
        panel.setMinimumWidth(260)
        return panel

    def _fit_table_width(self):
        """Dona a la taula l'ample de les seves columnes i la resta al
        gràfic.

        Es fa un sol cop, la primera vegada que hi ha files: les columnes són
        "ResizeToContents" i fins que no hi ha res a dins encara no tenen
        l'ample bo. I només un cop, perquè si es repetís a cada consulta
        desfaria la nansa cada vegada que l'usuari l'hagués mogut.
        """
        # Mentre la pestanya no es vegi, `width()` no és l'ample de debò sinó
        # el de per omissió (640 px), i el repartiment sortiria d'aquell. La
        # primera consulta es fa des del constructor, o sigui abans de veure
        # res: aquella s'ha de deixar passar de llarg.
        available = self.content.width()
        if self._table_sized or not self.isVisible() or available <= 0:
            return
        if self.days_table.rowCount() == 0:
            return
        columns = sum(
            self.days_table.columnWidth(col) for col in range(self.days_table.columnCount())
        )
        natural = columns + 2 * self.days_table.frameWidth() + _SCROLLBAR_ALLOWANCE
        # Mai més de la meitat, encara que les capçaleres siguin llargues:
        # l'ample d'una columna depèn de la lletra del sistema i de l'idioma
        # (en francès els títols són més llargs), i el gràfic ha de tenir
        # espai sempre. Si la taula no hi cap, li surt la barra de sota; i la
        # nansa és allà mateix per a qui la vulgui més ampla.
        natural = min(natural, max(_TABLE_MIN_WIDTH, available // 2))
        self.content.setSizes([natural, available - natural])
        self._table_sized = True

    def showEvent(self, event):
        """L'ample de debò no se sap fins que la pestanya es veu: quan es
        construeix encara no té mida.

        I ni tan sols aquí: dins de `showEvent` el splitter encara no ha
        repartit res i `width()` dona el valor de per omissió. Es demana per
        al tomb següent del bucle d'esdeveniments, quan la geometria ja està
        feta."""
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_table_width)

    def _build_filters(self) -> QWidget:
        box = QGroupBox(t("stats.title"))
        # Que no creixi: sense això la caixa s'enduia tota l'alçada que
        # sobrava (219 px per a una sola fila de camps) i la deixava buida
        # amunt i avall dels controls, que és alçada que li fa falta a la
        # taula i al gràfic.
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        # I el mateix marge intern arrapat que a "Nova entrada" de
        # Desmagatzem: una sola fila no necessita els 14+10 px que el full
        # d'estil dona a qualsevol QGroupBox.
        box.setStyleSheet("QGroupBox { padding: 5px 12px 5px 12px; }")
        row = QHBoxLayout(box)
        row.setSpacing(6)
        row.setContentsMargins(0, 0, 0, 0)

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
            button.setProperty("compact", "true")
            button.clicked.connect(lambda _checked=False, d=days: self._apply_quick_range(d))
            row.addWidget(button)

        self.apply_button = QPushButton(t("stats.apply"))
        self.apply_button.setProperty("compact", "true")
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
        # Pla, com els botons del costat: van tots a la mateixa fila.
        edit.setProperty("compact", "true")
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
        self.days_table.setColumnWidth(0, 100)
        # A l'ample just de la capçalera, no estirades: ara la taula comparteix
        # l'amplada amb el gràfic i el que hi va són números de dues o tres
        # xifres. Estirades es menjaven l'espai que ara fa servir el gràfic.
        for col in range(1, len(COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
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
            self._days = []
            self._update_chart()
            self.summary_label.setText(t("stats.invalid_range.text"))
            return
        stats = self.repo.movement_stats(self._iso(self.from_date), self._iso(self.to_date))
        self._days = stats["days"]
        self._fill_days_table(self._days)
        self._fit_table_width()
        self._update_chart()
        self._update_summary(stats)

    def _update_chart(self):
        """Torna a pintar el gràfic amb la columna que hi hagi triada al
        desplegable. No consulta res: fa servir els dies de l'última
        consulta, que per això es guarden."""
        field = self.metric_picker.currentData()
        bars = []
        for day in self._days:
            when = QDate.fromString(day["day"], "yyyy-MM-dd")
            bars.append(
                Bar(
                    label=when.toString(CHART_LABEL_FORMAT),
                    caption=when.toString(DATE_DISPLAY_FORMAT),
                    value=day[field],
                )
            )
        self.chart.set_series(bars, theme.qcolor(CHART_COLORS[field]), t("stats.chart.empty"))

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
