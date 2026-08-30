"""Pestanya 'Històric': equivalent a la fulla històric (auditoria, només lectura).

Aquesta taula pot arribar a tenir desenes de milers de línies, així que no
es fa com les altres (un `QTableWidget` amb un objecte per cel·la, que amb
50.000 files voldria dir 250.000 objectes i triga segons a omplir-se): és un
`QTableView` amb un model propi (`_HistoricModel`) que només guarda les
files tal com surten de la base de dades. Qt només demana al model les
cel·les que es veuen, de manera que 10.000, 50.000 o 100.000 línies s'obren
igual de ràpid i no hi ha cap límit artificial de files.

L'ordre es tria clicant les capçaleres (`setSortingEnabled`, amb la fletxa
d'ordre que ja pinta Qt), no amb botons a part; i tampoc hi ha botó
d'actualitzar: la pestanya es refresca sola quan hi ha canvis (el Tauler i
Desmagatzem avisen) i cada cop que s'hi entra.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.excel_export import export_historic_xlsx
from app.i18n import t
from app.logic.repository import Repository
from app.security import ADMIN
from app.ui import dialogs
from app.ui.password_dialog import ask_password

# Ordre de les columnes de la taula i camp de la base de dades de cadascuna.
COLUMNS = [
    ("historic.col.position", "position"),
    ("historic.col.code", "material_code"),
    ("historic.col.material", "material_desc"),
    ("historic.col.datetime", "ts"),
    ("historic.col.movement", "kind"),
]


def _sort_key(value, field: str):
    """Clau d'ordre d'una cel·la. Posició i núm. de material s'ordenen com a
    números quan ho són ("10" darrere de "9", no davant), i la resta com a
    text; els buits van sempre al final."""
    if value in (None, ""):
        return (2, "")
    if field in ("position", "material_code"):
        try:
            return (0, float(value))
        except (TypeError, ValueError):
            return (1, str(value).lower())
    return (0, str(value).lower())


class _HistoricModel(QAbstractTableModel):
    """Les files de l'històric, tal com venen de la base de dades.

    No en fa cap còpia per cel·la: Qt li demana només el que es veu, i per
    això la taula aguanta desenes de milers de línies sense notar-ho.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []
        self._headers = [t(key) for key, _field in COLUMNS]
        self._kind_labels = {
            "in": (t("historic.kind.in"), QColor("#1a7f37")),
            "out": (t("historic.kind.out"), QColor("#c62828")),
            "move_out": (t("historic.kind.move_out"), QColor("#b48c64")),
            "move_in": (t("historic.kind.move_in"), QColor("#78460f")),
        }

    # -- dades ------------------------------------------------------- #
    def set_rows(self, rows: list[dict]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rows(self) -> list[dict]:
        return self._rows

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def value_at(self, row: int, column: int):
        field = COLUMNS[column][1]
        value = self._rows[row].get(field)
        if field == "kind":
            return self._kind_labels.get(value, (value, None))[0]
        return "" if value is None else value

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return str(self.value_at(index.row(), index.column()))
        if role == Qt.ForegroundRole:
            label_color = self._kind_labels.get(self._rows[index.row()].get("kind"))
            return label_color[1] if label_color else None
        return None

    def headerData(self, section: int, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._headers[section]
        return section + 1

    def sort(self, column: int, order=Qt.AscendingOrder):
        """Ordena clicant la capçalera. Es fa sobre la llista que ja hi ha a
        memòria (no es torna a consultar la base de dades), que per a
        desenes de milers de files és immediat."""
        field = COLUMNS[column][1]
        self.layoutAboutToBeChanged.emit()
        self._rows.sort(
            key=lambda row: _sort_key(row.get(field), field),
            reverse=(order == Qt.DescendingOrder),
        )
        self.layoutChanged.emit()


class HistoricTab(QWidget):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 3, 9, 9)  # marge superior mínim, taula enganxada a les pestanyes

        filters = QHBoxLayout()
        filters.addWidget(QLabel(t("historic.filter_label")))
        self.position_filter = QLineEdit()
        self.position_filter.setPlaceholderText(t("historic.filter_placeholder"))
        self.position_filter.textChanged.connect(self.refresh)
        filters.addWidget(self.position_filter)
        filters.addStretch()

        # Ja no hi ha botó d'actualitzar (es refresca sola) ni botons
        # d'ordenar (es fa clicant les capçaleres).
        self.export_button = QPushButton(t("historic.export_excel"))
        self.export_button.clicked.connect(self._on_export_excel)
        filters.addWidget(self.export_button)

        self.clear_button = QPushButton(t("historic.clear"))
        self.clear_button.setStyleSheet("background-color: #c62828;")
        self.clear_button.clicked.connect(self._on_clear)
        filters.addWidget(self.clear_button)

        self.count_label = QLabel()
        filters.addWidget(self.count_label)
        layout.addLayout(filters)

        self.model = _HistoricModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        # Ordre clicant la capçalera, amb la fletxa d'ascendent/descendent.
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.sortByColumn(3, Qt.DescendingOrder)  # data, de la més nova a la més vella
        self._configure_column_widths()
        layout.addWidget(self.table)

    def _configure_column_widths(self):
        # Per defecte, "Material" i "Data/hora" queden massa estrets amb
        # l'ample automàtic de Qt i el text es talla. Interactive perquè
        # l'usuari encara les pugui reajustar arrossegant la vora.
        header = self.table.horizontalHeader()
        widths = [70, 90, 320, 150, 110]  # Posició, Núm., Material, Data/hora, Moviment
        for col, width in enumerate(widths):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
            self.table.setColumnWidth(col, width)

    # ------------------------------------------------------------------ #
    def refresh(self):
        """Rellegeix l'històric de la base de dades. Es crida sola en entrar
        a la pestanya i quan el Tauler o Desmagatzem hi han escrit res."""
        position = self.position_filter.text().strip() or None
        rows = self.repo.get_historic(position=position)
        self.model.set_rows(rows)
        # Es manté l'ordre que l'usuari hagi triat a la capçalera.
        header = self.table.horizontalHeader()
        self.model.sort(header.sortIndicatorSection(), header.sortIndicatorOrder())
        self.count_label.setText(t("historic.count", count=len(rows)))

    # ------------------------------------------------------------------ #
    def _on_export_excel(self):
        """Exporta TOT l'històric (totes les files i columnes), no només el
        que es veu a la pantalla."""
        default_name = f"historic_{date.today().isoformat()}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, t("historic.export.title"), default_name, "Excel (*.xlsx)"
        )
        if not path:
            return
        rows = self.repo.get_historic()  # sense filtre ni límit: l'històric sencer
        try:
            export_historic_xlsx(rows, [t(key) for key, _field in COLUMNS], [f for _k, f in COLUMNS], path)
        except OSError as exc:
            dialogs.error(self, t("historic.export.error.title"), t("historic.export.error.text", error=exc))
            return
        dialogs.info(self, t("common.done"), t("historic.export.done", count=len(rows), path=path))

    def _on_clear(self):
        """Netejar l'històric: contrasenya de materials, després confirmar
        que ja s'ha exportat a Excel, i llavors s'esborra tot MENYS l'última
        entrada de cada material que encara hi ha al Tauler."""
        if not ask_password(
            self, ADMIN, t("historic.clear.password"), t("password.wrong.text_generic")
        ):
            return
        if not dialogs.confirm(self, t("historic.clear.confirm.title"), t("historic.clear.confirm.text")):
            return
        try:
            result = self.repo.clear_historic()
        except Exception as exc:  # noqa: BLE001 - qualsevol fallada: es desfà i s'avisa
            dialogs.error(self, t("common.error"), t("historic.clear.error", error=exc))
            return
        self.refresh()
        dialogs.info(
            self,
            t("common.done"),
            t("historic.clear.done", deleted=result["deleted"], kept=result["kept"]),
        )
