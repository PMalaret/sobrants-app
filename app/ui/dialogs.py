"""Diàlegs de l'aplicació, amb TOTS els botons traduïts.

Els diàlegs estàndard de Qt (`QMessageBox.question`, `QInputDialog.getText`...)
posen els botons en anglès —"Yes", "No", "OK", "Cancel"— perquè fan servir
les traduccions pròpies de Qt, que no s'hi carreguen. Per això l'aplicació
no els crida directament: passa per aquestes funcions, que creen el diàleg i
en reescriuen els botons amb les claus de `app.i18n` (`common.yes`,
`common.no`, `common.ok`, `common.cancel`), com la resta de textos.

També és aquí on es decideix com es VEUEN, i per això hi passa tothom:

  - Els botons no criden tots igual: el que continua l'acció (Acceptar, Sí)
    va ple de color i el que la deixa córrer (Cancel·lar, No) va buit
    (`style_buttons`, que ho decideix pel PAPER de cada botó, no pel seu
    text, així val per a qualsevol idioma).
  - Prémer Enter és prémer aquest mateix botó afirmatiu, mai el de
    cancel·lar (`enter_accepts`).
  - La icona no és la del sistema (un cercle ple de color, d'aspecte antic)
    sinó la mateixa família d'icones de línia que els botons
    (`app.ui.icons`), amb el color que li toca a cada tipus d'avís.
  - Els marges són una mica més amples que els que posa Qt per defecte.
"""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QInputDialog, QLineEdit, QMessageBox, QWidget

from app.i18n import t
from app.ui import icons

# Icona i color de cada tipus de diàleg.
_ICONS = {
    QMessageBox.Information: ("info", "accent"),
    QMessageBox.Question: ("question", "accent"),
    QMessageBox.Warning: ("warning", "warning"),
    QMessageBox.Critical: ("error", "danger"),
}
_ICON_SIZE = 34
# Marges de dins del diàleg: una mica més d'aire que el que posa Qt.
_MARGINS = (18, 16, 18, 14)


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


def _mark_secondary(button) -> None:
    """Deixa el botó buit (variant "ghost"). Cal tornar a polir-lo perquè,
    a diferència d'un botó acabat de crear, aquest ja té l'estil aplicat i
    Qt no el refaria sol."""
    button.setProperty("variant", "ghost")
    button.style().unpolish(button)
    button.style().polish(button)


def style_buttons(dialog: QWidget) -> None:
    """Els botons de cancel·lar/no d'un diàleg, com a secundaris.

    Es mira el PAPER de cada botó (`ButtonRole`), no el seu text: així
    funciona igual en els 4 idiomes i en qualsevol diàleg, sigui un
    QMessageBox, un QInputDialog o un dels diàlegs propis de l'aplicació
    (que fan servir un QDialogButtonBox).
    """
    if isinstance(dialog, QMessageBox):
        for button in dialog.buttons():
            if dialog.buttonRole(button) in (QMessageBox.NoRole, QMessageBox.RejectRole):
                _mark_secondary(button)
        return
    for box in dialog.findChildren(QDialogButtonBox):
        for button in box.buttons():
            if box.buttonRole(button) in (QDialogButtonBox.RejectRole, QDialogButtonBox.NoRole):
                _mark_secondary(button)


def _dialog_buttons(dialog: QWidget) -> list:
    """(paper, botó) de tots els botons d'un diàleg, sigui un QMessageBox o
    un diàleg propi amb el seu QDialogButtonBox."""
    if isinstance(dialog, QMessageBox):
        return [(dialog.buttonRole(button), button) for button in dialog.buttons()]
    return [
        (box.buttonRole(button), button)
        for box in dialog.findChildren(QDialogButtonBox)
        for button in box.buttons()
    ]


def _role_value(role):
    """El número que hi ha sota un `ButtonRole`, vingui de la enumeració
    que vingui."""
    return getattr(role, "value", role)


def enter_accepts(dialog: QWidget) -> None:
    """Prémer Enter fa el mateix que clicar el botó afirmatiu.

    Qt marca com a "per defecte" (el que respon a Enter) el primer botó que
    li sembla, i als avisos de Sí/No era el "No". Aquí es diu explícitament:
    el botó que continua l'acció és el de per defecte, i als altres se'ls
    treu la possibilitat de ser-ho, de manera que Enter no pot acabar mai
    cancel·lant.

    Es decideix pel PAPER del botó, com a `style_buttons`, no pel seu text.
    I només es marca UN botó per defecte, així una sola premuda no pot
    disparar l'acció dues vegades.
    """
    # Es comparen els VALORS dels papers: un QMessageBox i un
    # QDialogButtonBox tenen cadascun la seva enumeració, però amb els
    # mateixos números a sota.
    affirmative = {_role_value(QDialogButtonBox.AcceptRole), _role_value(QDialogButtonBox.YesRole)}
    for role, button in _dialog_buttons(dialog):
        is_affirmative = _role_value(role) in affirmative
        button.setAutoDefault(is_affirmative)
        button.setDefault(is_affirmative)


def prepare_dialog(dialog: QWidget, icon=None) -> None:
    """El que s'aplica a TOTS els diàlegs: botons amb jerarquia, Enter que
    accepta, marges amb aire i, si n'hi ha, la icona pròpia en comptes de
    la del sistema."""
    style_buttons(dialog)
    enter_accepts(dialog)
    layout = dialog.layout()
    if layout is not None:
        layout.setContentsMargins(*_MARGINS)
    if isinstance(dialog, QMessageBox) and icon in _ICONS:
        name, color_token = _ICONS[icon]
        pixmap = icons.pixmap(name, color_token, _ICON_SIZE)
        if not pixmap.isNull():
            dialog.setIconPixmap(pixmap)   # si no hi ha font d'icones, es deixa la de Qt


def _show(parent: QWidget, icon, title: str, text: str) -> None:
    box = QMessageBox(icon, title, text, QMessageBox.Ok, parent)
    _translate_buttons(box)
    prepare_dialog(box, icon)
    box.exec()


def info(parent: QWidget, title: str, text: str) -> None:
    _show(parent, QMessageBox.Information, title, text)


def warn(parent: QWidget, title: str, text: str) -> None:
    _show(parent, QMessageBox.Warning, title, text)


def error(parent: QWidget, title: str, text: str) -> None:
    _show(parent, QMessageBox.Critical, title, text)


def confirm(parent: QWidget, title: str, text: str) -> bool:
    """Sí/No traduïts. True només si s'ha triat que sí.

    Enter fa que sí (veure `enter_accepts`): abans el botó preseleccionat
    era el "No" i qui premés Enter es trobava que no havia passat res.
    """
    box = QMessageBox(QMessageBox.Question, title, text, QMessageBox.Yes | QMessageBox.No, parent)
    _translate_buttons(box)
    prepare_dialog(box, QMessageBox.Question)
    return box.exec() == QMessageBox.Yes


def ask_text(parent: QWidget, title: str, label: str, password: bool = False) -> tuple[str, bool]:
    """Com QInputDialog.getText, però amb Acceptar/Cancel·lar traduïts."""
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setTextEchoMode(QLineEdit.Password if password else QLineEdit.Normal)
    dialog.setOkButtonText(t("common.ok"))
    dialog.setCancelButtonText(t("common.cancel"))
    prepare_dialog(dialog)
    accepted = dialog.exec() == QInputDialog.Accepted
    return dialog.textValue(), accepted


def ask_choice(parent: QWidget, title: str, label: str, options: list[str]) -> tuple[str, bool]:
    """Triar un element d'una llista, amb Acceptar/Cancel·lar traduïts."""
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setComboBoxItems(options)
    dialog.setOkButtonText(t("common.ok"))
    dialog.setCancelButtonText(t("common.cancel"))
    prepare_dialog(dialog)
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
    prepare_dialog(dialog)
    accepted = dialog.exec() == QInputDialog.Accepted
    return dialog.intValue(), accepted
