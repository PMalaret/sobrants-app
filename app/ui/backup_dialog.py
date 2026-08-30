"""Configuració de les còpies de seguretat, tot en un sol diàleg.

Abans només es podia canviar cada quantes hores es feien (amb un quadre de
demanar un número). Ara, al mateix lloc, s'hi tria també on van, com es
diuen i s'hi veu si hi ha un USB connectat per fer-ne la segona còpia.

Tot el que s'hi tria es recorda a `settings.json` (`app.settings`), que ja
és on viuen la resta de preferències.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app import settings
from app.backup import DEFAULT_PREFIX, backup_name, sanitize_prefix
from app.i18n import t
from app.ui import dialogs
from app.ui.usb_indicator import removable_drives

# Claus de preferències (les mateixes que llegeix `MainWindow`).
FOLDER_SETTING = "backup_folder"
PREFIX_SETTING = "backup_prefix"
INTERVAL_SETTING = "backup_interval_hours"


def backup_folder(db_path: str | Path, default: Path) -> Path:
    """Carpeta configurada, o la de sempre si no se n'ha triat cap."""
    value = settings.get(FOLDER_SETTING)
    return Path(value) if value else Path(default)


def backup_prefix() -> str:
    return sanitize_prefix(settings.get(PREFIX_SETTING) or DEFAULT_PREFIX)


class BackupSettingsDialog(QDialog):
    """Carpeta de destí, nom de les còpies i cada quantes hores es fan."""

    def __init__(self, default_folder: Path, interval_hours: int, min_hours: int, max_hours: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("backup.settings.title"))
        self._default_folder = Path(default_folder)
        layout = QVBoxLayout(self)

        form = QFormLayout()

        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit(str(backup_folder(None, self._default_folder)))
        self.folder_input.setMinimumWidth(320)
        pick_button = QPushButton(t("backup.settings.pick_folder"))
        pick_button.clicked.connect(self._pick_folder)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(pick_button)
        form.addRow(t("backup.settings.folder"), folder_row)

        self.prefix_input = QLineEdit(backup_prefix())
        self.prefix_input.textChanged.connect(self._update_example)
        form.addRow(t("backup.settings.name"), self.prefix_input)

        self.example_label = QLabel()
        self.example_label.setStyleSheet("color: #555;")
        form.addRow("", self.example_label)

        self.interval_input = QSpinBox()
        self.interval_input.setRange(min_hours, max_hours)
        self.interval_input.setValue(interval_hours)
        self.interval_input.setSuffix(" h")
        form.addRow(t("backup.settings.interval"), self.interval_input)

        # Estat del USB: informatiu, per saber si la còpia sortirà duplicada.
        drives = removable_drives()
        usb_label = QLabel(
            t("backup.settings.usb_found", drives=", ".join(drives)) if drives
            else t("backup.settings.usb_missing")
        )
        usb_label.setStyleSheet("color: %s;" % ("#1a9c6d" if drives else "#c62828"))
        form.addRow(t("backup.settings.usb"), usb_label)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(t("common.ok"))
        buttons.button(QDialogButtonBox.Cancel).setText(t("common.cancel"))
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_example()

    def _update_example(self):
        self.example_label.setText(
            t("backup.settings.example", name=backup_name(self.prefix_input.text()))
        )

    def _pick_folder(self):
        chosen = QFileDialog.getExistingDirectory(
            self, t("backup.settings.pick_folder"), self.folder_input.text()
        )
        if chosen:
            self.folder_input.setText(chosen)

    def _on_accept(self):
        folder = Path(self.folder_input.text().strip() or self._default_folder)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            # La carpeta triada ja no hi és, o no s'hi pot escriure: es diu
            # clarament i es deixa triar una altra en comptes de desar-la.
            dialogs.error(self, t("backup.settings.folder_error.title"),
                          t("backup.settings.folder_error.text", folder=folder, error=exc))
            return
        settings.set_value(FOLDER_SETTING, str(folder))
        settings.set_value(PREFIX_SETTING, sanitize_prefix(self.prefix_input.text()))
        settings.set_value(INTERVAL_SETTING, self.interval_input.value())
        self.accept()
