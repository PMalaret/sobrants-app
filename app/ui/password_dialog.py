"""Demanar les contrasenyes de l'aplicació, sempre igual a tot arreu.

N'hi ha dues i independents (`app.security`): la de les còpies de seguretat
i la dels materials (que també protegeix netejar l'històric). Totes les
accions protegides passen per `ask_password`, que ensenya el camp ocult,
compara amb `security.check_password` i avisa si no és bona: així no hi pot
haver dues maneres diferents de comprovar-les.

`ChangePasswordDialog` és l'ÚNIC lloc on es canvien, i les gestiona totes
dues: es tria quina es vol canviar, s'escriu l'actual i la nova dues
vegades. Canviar-ne una no toca l'altra.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app import security
from app.i18n import t
from app.ui import dialogs


def ask_password(parent: QWidget, scope: str, label: str, wrong_text: str) -> bool:
    """True només si s'ha escrit la contrasenya correcta de `scope`.

    `label` diu per a què es demana i `wrong_text` què passa si no és bona
    (p. ex. "no s'ha fet cap còpia"), perquè cada acció ho pugui explicar
    amb les seves paraules. El text s'escriu sempre ocult: no es veu mai.
    """
    password, ok = dialogs.ask_text(parent, t("password.title"), label, password=True)
    if not ok:
        return False
    if not security.check_password(password, scope):
        dialogs.error(parent, t("password.wrong.title"), wrong_text)
        return False
    return True


class ChangePasswordDialog(QDialog):
    """Un sol diàleg per a les dues contrasenyes.

    Es tria quina es canvia, s'escriu l'actual (la d'aquella, no l'altra) i
    la nova dues vegades. Sense cap requisit de forma: qualsevol text val,
    l'única condició és que les dues escriptures coincideixin.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("password.change.title"))
        layout = QVBoxLayout(self)

        explanation = QLabel(t("password.change.which"))
        explanation.setWordWrap(True)
        explanation.setStyleSheet("font-weight: 600;")
        layout.addWidget(explanation)

        self.admin_radio = QRadioButton(t("password.scope.admin"))
        self.worker_radio = QRadioButton(t("password.scope.worker"))
        self.admin_radio.setChecked(True)
        layout.addWidget(self.admin_radio)
        layout.addWidget(self.worker_radio)

        form = QFormLayout()
        self.current_input = self._password_field()
        self.new_input = self._password_field()
        self.repeat_input = self._password_field()
        form.addRow(t("password.change.current"), self.current_input)
        form.addRow(t("password.change.new"), self.new_input)
        form.addRow(t("password.change.repeat"), self.repeat_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(t("common.ok"))
        buttons.button(QDialogButtonBox.Cancel).setText(t("common.cancel"))
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _password_field() -> QLineEdit:
        field = QLineEdit()
        field.setEchoMode(QLineEdit.Password)  # mai en clar a la pantalla
        return field

    def scope(self) -> str:
        return security.ADMIN if self.admin_radio.isChecked() else security.WORKER

    def _on_accept(self):
        scope = self.scope()
        if not security.check_password(self.current_input.text(), scope):
            dialogs.error(self, t("password.wrong.title"), t("password.wrong.text_generic"))
            return
        if self.new_input.text() != self.repeat_input.text():
            dialogs.error(
                self, t("password.change.mismatch.title"), t("password.change.mismatch.text")
            )
            return
        security.set_password(self.new_input.text(), scope)
        dialogs.info(self, t("password.change.done.title"), t("password.change.done.text"))
        self.accept()
