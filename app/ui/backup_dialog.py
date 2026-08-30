"""Configuració de les còpies de seguretat, tot en un sol diàleg.

Abans només es podia canviar cada quantes hores es feien (amb un quadre de
demanar un número). Ara, al mateix lloc, s'hi tria també on van, com es
diuen, quantes se'n guarden, i s'hi veu si hi ha un USB connectat per
fer-ne la segona còpia.

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
from app.backup import (
    DEFAULT_KEEP_BACKUPS,
    DEFAULT_PREFIX,
    MAX_KEEP_BACKUPS,
    MIN_KEEP_BACKUPS,
    backup_name,
    list_backups,
    sanitize_prefix,
)
from app.i18n import t
from app.ui import dialogs
from app.ui.usb_indicator import removable_drives

# Claus de preferències (les mateixes que llegeix `MainWindow`).
FOLDER_SETTING = "backup_folder"
PREFIX_SETTING = "backup_prefix"
INTERVAL_SETTING = "backup_interval_hours"
KEEP_SETTING = "backup_keep"


def backup_folder(db_path: str | Path, default: Path) -> Path:
    """Carpeta configurada, o la de sempre si no se n'ha triat cap."""
    value = settings.get(FOLDER_SETTING)
    return Path(value) if value else Path(default)


def backup_prefix() -> str:
    return sanitize_prefix(settings.get(PREFIX_SETTING) or DEFAULT_PREFIX)


def backup_keep() -> int:
    """Quantes còpies es conserven a cada destí. Si el valor desat no és
    utilitzable (tocat a mà, buit, fora de rang), val el de per defecte."""
    try:
        value = int(settings.get(KEEP_SETTING, DEFAULT_KEEP_BACKUPS))
    except (TypeError, ValueError):
        return DEFAULT_KEEP_BACKUPS
    if not MIN_KEEP_BACKUPS <= value <= MAX_KEEP_BACKUPS:
        return DEFAULT_KEEP_BACKUPS
    return value


def count_backups(folder: Path) -> int:
    """Quantes còpies de l'aplicació hi ha ara mateix en una carpeta."""
    return len(list_backups(folder))


class BackupSettingsDialog(QDialog):
    """Carpeta de destí, nom de les còpies, cada quantes hores es fan i
    quantes se'n conserven."""

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

        # Quantes se'n guarden. Un QSpinBox ja només deixa escriure-hi
        # enters dins del rang, així que no s'hi pot posar cap valor
        # invàlid ni desproporcionat.
        self.keep_input = QSpinBox()
        self.keep_input.setRange(MIN_KEEP_BACKUPS, MAX_KEEP_BACKUPS)
        self.keep_input.setValue(backup_keep())
        form.addRow(t("backup.settings.keep"), self.keep_input)

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
        # Si es baixa el límit i ara hi ha més còpies de les que hi cabran,
        # no se n'esborra cap ara mateix: només s'avisa que les més antigues
        # aniran caient a mesura que se'n facin de noves.
        keep = self.keep_input.value()
        existing = count_backups(folder)
        if existing > keep:
            dialogs.info(
                self,
                t("backup.settings.keep_warning.title"),
                t("backup.settings.keep_warning.text", existing=existing, keep=keep),
            )
        settings.set_value(FOLDER_SETTING, str(folder))
        settings.set_value(PREFIX_SETTING, sanitize_prefix(self.prefix_input.text()))
        settings.set_value(INTERVAL_SETTING, self.interval_input.value())
        settings.set_value(KEEP_SETTING, keep)
        self.accept()
