"""Diàlegs de l'aplicació, amb TOTS els botons traduïts.

Els diàlegs estàndard de Qt (`QMessageBox.question`, `QInputDialog.getText`...)
posen els botons en anglès —"Yes", "No", "OK", "Cancel"— perquè fan servir
les traduccions pròpies de Qt, que no s'hi carreguen. Per això l'aplicació
no els crida directament: passa per aquestes funcions, que creen el diàleg i
en reescriuen els botons amb les claus de `app.i18n` (`common.yes`,
`common.no`, `common.ok`, `common.cancel`), com la resta de textos.
"""
from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox, QWidget

from app.i18n import t


def _translate_buttons(box: QMessageBox) -> None:
    for standard, key in (
        (QMessageBox.Yes, "common.yes"),
        (QMessageBox.No, "common.no"),
        (QMessageBox.Ok, "common.ok"),
        (QMessageBox.Cancel, "common.cancel"),
    ):
        button = box.button(standard)
        if button is not None:
            button.setText(t(key))


def _show(parent: QWidget, icon, title: str, text: str) -> None:
    box = QMessageBox(icon, title, text, QMessageBox.Ok, parent)
    _translate_buttons(box)
    box.exec()


def info(parent: QWidget, title: str, text: str) -> None:
    _show(parent, QMessageBox.Information, title, text)


def warn(parent: QWidget, title: str, text: str) -> None:
    _show(parent, QMessageBox.Warning, title, text)


def error(parent: QWidget, title: str, text: str) -> None:
    _show(parent, QMessageBox.Critical, title, text)


def confirm(parent: QWidget, title: str, text: str) -> bool:
    """Sí/No traduïts. True només si s'ha triat que sí."""
    box = QMessageBox(QMessageBox.Question, title, text, QMessageBox.Yes | QMessageBox.No, parent)
    box.setDefaultButton(QMessageBox.No)
    _translate_buttons(box)
    return box.exec() == QMessageBox.Yes


def ask_text(parent: QWidget, title: str, label: str, password: bool = False) -> tuple[str, bool]:
    """Com QInputDialog.getText, però amb Acceptar/Cancel·lar traduïts."""
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setTextEchoMode(QLineEdit.Password if password else QLineEdit.Normal)
    dialog.setOkButtonText(t("common.ok"))
    dialog.setCancelButtonText(t("common.cancel"))
    accepted = dialog.exec() == QInputDialog.Accepted
    return dialog.textValue(), accepted


def ask_int(
    parent: QWidget, title: str, label: str, value: int, minimum: int, maximum: int
) -> tuple[int, bool]:
    """Com QInputDialog.getInt, però amb Acceptar/Cancel·lar traduïts."""
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setInputMode(QInputDialog.IntInput)
    dialog.setIntRange(minimum, maximum)
    dialog.setIntValue(value)
    dialog.setOkButtonText(t("common.ok"))
    dialog.setCancelButtonText(t("common.cancel"))
    accepted = dialog.exec() == QInputDialog.Accepted
    return dialog.intValue(), accepted
