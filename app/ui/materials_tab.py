"""Pestanya 'Materials': catàleg (equivalent a la fulla Materials).

L'Excel original no tenia cap protecció per editar aquesta fulla (es
podia escriure directament a les cel·les). Afegir i esborrar un material
són funcionalitats pròpies de l'app, protegides amb la mateixa
contrasenya senzilla (`app/security.py`) perquè no ho faci qualsevol
per error.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import t
from app.logic.repository import Repository, RuleViolation
from app.security import check_password


class _NumericItem(QTableWidgetItem):
    """Perquè "Núm. material" s'ordeni numèricament en clicar la
    capçalera, no com a text (10 abans que 2)."""

    def __init__(self, text: str, sort_value: float):
        super().__init__(text)
        self._sort_value = sort_value

    def __lt__(self, other):
        if isinstance(other, _NumericItem):
            return self._sort_value < other._sort_value
        return super().__lt__(other)


class _AddMaterialDialog(QDialog):
    """Formulari mínim (número + descripció) per donar d'alta un material."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("materials.add_dialog.title"))
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.code_input = QSpinBox()
        self.code_input.setRange(0, 999999)
        form.addRow(t("materials.add_dialog.code"), self.code_input)

        self.description_input = QLineEdit()
        form.addRow(t("materials.add_dialog.description"), self.description_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(t("common.add"))
        buttons.button(QDialogButtonBox.Cancel).setText(t("common.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[int, str]:
        return self.code_input.value(), self.description_input.text().strip()


class MaterialsTab(QWidget):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 3, 9, 9)  # marge superior mínim, taula enganxada a les pestanyes

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel(t("materials.search_label")))
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("materials.search_placeholder"))
        self.search.textChanged.connect(self.refresh)
        search_row.addWidget(self.search)
        search_row.addStretch()
        self.add_button = QPushButton(t("materials.add_button"))
        self.add_button.clicked.connect(self._on_add_material)
        search_row.addWidget(self.add_button)
        self.delete_button = QPushButton(t("materials.delete_button"))
        self.delete_button.clicked.connect(self._on_delete_material)
        search_row.addWidget(self.delete_button)
        layout.addLayout(search_row)

        columns = [t("materials.col.code"), t("materials.col.description")]
        self.table = QTableWidget(0, len(columns))
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # Núm. material i Descripció: totes dues "Interactive" amb un ample
        # per defecte contingut (no ajustat al contingut més llarg de tot
        # el catàleg, que la feia excessivament ampla); l'usuari les pot
        # redimensionar arrossegant la vora de la capçalera.
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 130)  # que hi càpiga el títol "Núm. material" sencer
        self.table.setColumnWidth(1, 320)
        # Ordenació clicant la capçalera (nativa de QTableWidget, alterna
        # ascendent/descendent). "Núm. material" s'ordena numèricament.
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #666;")
        layout.addWidget(self.count_label)

    def refresh(self):
        query = self.search.text().strip()
        # Sense límit: el catàleg és petit (uns 4.000 materials) i han de
        # poder-se veure tots, no només els primers N.
        rows = self.repo.search_materials(query)
        # Desactivem l'ordenació mentre omplim la taula (si no, Qt reordena
        # fila a fila a cada setItem: amb ~4.000 files és O(files²) i penja
        # la interfície).
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, _NumericItem(str(row["code"]), float(row["code"])))
            self.table.setItem(r, 1, QTableWidgetItem(row["description"]))
        self.table.setSortingEnabled(True)
        self.count_label.setText(t("materials.count", count=len(rows)))

    # ------------------------------------------------------------------ #
    def _on_add_material(self):
        password, ok = QInputDialog.getText(
            self,
            t("materials.password.title"),
            t("materials.password.label"),
            QLineEdit.Password,
        )
        if not ok:
            return
        if not check_password(password):
            QMessageBox.critical(self, t("materials.password.wrong.title"), t("materials.password.wrong.text"))
            return

        dialog = _AddMaterialDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        code, description = dialog.values()
        if not description:
            QMessageBox.warning(self, t("common.error"), t("materials.add.missing_fields"))
            return

        try:
            self.repo.add_material(code, description)
        except RuleViolation:
            existing = self.repo.lookup_material(code)
            resp = QMessageBox.question(
                self,
                t("materials.password.title"),
                t("materials.add.confirm_overwrite", code=code, description=existing),
                QMessageBox.Yes | QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return
            self.repo.add_material(code, description, overwrite=True)

        self.refresh()
        QMessageBox.information(self, t("common.done"), t("materials.add.success"))

    def _on_delete_material(self):
        items = self.table.selectedItems()
        if not items:
            QMessageBox.warning(
                self, t("materials.delete.no_selection.title"), t("materials.delete.no_selection.text")
            )
            return
        row = items[0].row()
        code = int(self.table.item(row, 0).text())
        description = self.table.item(row, 1).text()

        # Mateix mecanisme de contrasenya que per afegir un material.
        password, ok = QInputDialog.getText(
            self,
            t("materials.password.title"),
            t("materials.password.label_delete"),
            QLineEdit.Password,
        )
        if not ok:
            return
        if not check_password(password):
            QMessageBox.critical(
                self, t("materials.password.wrong.title"), t("materials.password.wrong.text_delete")
            )
            return

        resp = QMessageBox.question(
            self,
            t("materials.delete.confirm.title"),
            t("materials.delete.confirm.text", code=code, description=description),
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        try:
            self.repo.delete_material(code)
        except RuleViolation as exc:
            QMessageBox.critical(self, t("common.error"), str(exc))
            return

        self.refresh()
        QMessageBox.information(self, t("common.done"), t("materials.delete.success"))
