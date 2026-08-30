"""Finestra principal: substitueix el llibre Excel amb una pestanya per fulla."""
from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from app import i18n, settings
from app.backup import create_backup
from app.data.db import connect
from app.export import covered_materials_report_text, print_widget
from app.i18n import t
from app.logic.repository import Repository
from app.security import ADMIN
from app.ui import dialogs
from app.ui.about_dialog import AboutDialog
from app.ui.import_actions import import_from_database, import_from_excel
from app.ui.board_tab import BoardTab
from app.ui.desmagatzem_tab import DesmagatzemTab
from app.ui.historic_tab import HistoricTab
from app.ui.materials_tab import MaterialsTab
from app.ui.password_dialog import ChangePasswordDialog, ask_password
from app.ui.usb_indicator import UsbIndicator
from app.version import APP_VERSION

# Cada quantes hores es fa la còpia automàtica. 4 per defecte, igual que
# IniciarBackupAutomatic a l'original, però ara es pot canviar des de
# Fitxer → interval de còpies i es recorda entre arrencades
# (`settings.json`). Els límits són només de sentit comú: com a mínim cada
# hora i com a molt un cop per setmana.
DEFAULT_BACKUP_INTERVAL_HOURS = 4
MIN_BACKUP_INTERVAL_HOURS = 1
MAX_BACKUP_INTERVAL_HOURS = 168
BACKUP_INTERVAL_SETTING = "backup_interval_hours"

# Botons grans d'accions (icona + text + color), per a gent a qui li costi
# llegir un menú de text pla. (clau de traducció, emoji, color, mètode a cridar)
# La còpia de seguretat ja no hi és: ara demana contrasenya i viu només al
# menú Fitxer; al seu lloc, a la fila, hi ha l'indicador d'USB.
ACTION_BUTTONS = [
    # Imprimir: obren el diàleg d'impressió del sistema (abans desaven un
    # PDF a un fitxer; el PDF es pot seguir fent triant-lo com a impressora).
    ("action.print_board", "🖨️", "#1a9c6d", "_print_board"),
    ("action.print_desmagatzem", "🖨️", "#c9852b", "_print_desmagatzem"),
    # Ull: "materials tapats" és veure els que queden amagats darrere d'un altre.
    ("action.covered", "👁️", "#c62828", "_show_covered_report"),
]


class MainWindow(QMainWindow):
    def __init__(self, repo: Repository, db_path: str):
        super().__init__()
        self.repo = repo
        self.db_path = db_path
        # 700, no 760: amb el tauler (l'única pestanya d'alçada fixa, sempre
        # 61 posicions) l'alçada extra només es traduïa en un buit en blanc
        # sota els botons "Netejar cerca"/"Cercar". Les altres pestanyes
        # tenen taules amb scroll, així que no en pateixen.
        self.resize(1500, 700)

        self._backup_timer = QTimer(self)
        self._backup_timer.timeout.connect(self._auto_backup)
        self._apply_backup_interval()

        self._build_everything()

    # ------------------------------------------------------------------ #
    # Construcció completa de la UI. Es torna a cridar sencera quan canvia
    # l'idioma, perquè totes les cadenes es recalculen amb t() en construir
    # els widgets (més senzill i robust que retraduir widget per widget).
    # ------------------------------------------------------------------ #
    def _build_everything(self):
        self.setWindowTitle(t("app.title"))

        self.board_tab = BoardTab(self.repo)
        self.historic_tab = HistoricTab(self.repo)
        self.materials_tab = MaterialsTab(self.repo)
        self.desmagatzem_tab = DesmagatzemTab(self.repo)
        self.board_tab.data_changed.connect(self.historic_tab.refresh)
        self.desmagatzem_tab.data_changed.connect(self.historic_tab.refresh)
        # Els cercadors del Tauler també ressalten coincidències a
        # Desmagatzem amb el mateix color (igual que l'original). Netejar
        # un camp de cerca (text buit) ja neteja el ressaltat corresponent
        # via apply_search_highlight, no cal cap senyal "cleared" a part.
        self.board_tab.search_panel.search_changed.connect(self.desmagatzem_tab.apply_search_highlight)

        # Pestanyes (QTabBar sol, no QTabWidget) i botons d'acció en una
        # sola fila: amb `QTabWidget.setCornerWidget` Qt força l'alçada
        # dels botons a la de la barra de pestanyes i el text quedava
        # tallat en fer-la compacta. Amb un QHBoxLayout normal cap dels
        # dos widgets es força a encongir-se: la fila agafa l'alçada que
        # calgui pel més alt dels dos.
        tab_bar = QTabBar()
        tab_bar.addTab(t("tab.board"))
        tab_bar.addTab(t("tab.desmagatzem"))
        tab_bar.addTab(t("tab.historic"))
        tab_bar.addTab(t("tab.materials"))
        tab_bar.setExpanding(False)
        tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar = tab_bar

        stack = QStackedWidget()
        stack.setObjectName("tabStack")
        stack.addWidget(self.board_tab)
        stack.addWidget(self.desmagatzem_tab)
        stack.addWidget(self.historic_tab)
        stack.addWidget(self.materials_tab)
        self._stack = stack

        top_row = QWidget()
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 4, 0)
        top_row_layout.setSpacing(8)
        top_row_layout.addWidget(tab_bar)
        top_row_layout.addStretch()
        self._add_action_buttons(top_row_layout)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(top_row)
        central_layout.addWidget(stack)
        self.setCentralWidget(central)

        self.menuBar().clear()
        self._build_menu()

        status = self.statusBar()
        # netegem widgets permanents anteriors (si es reconstrueix per canvi d'idioma)
        for child in status.findChildren(QWidget):
            if getattr(child, "_sobrants_status_widget", False):
                status.removeWidget(child)
                child.deleteLater()
        legend = self.board_tab.build_legend_widget()
        legend._sobrants_status_widget = True
        status.addPermanentWidget(legend)
        status.showMessage(t("status.db", path=self.db_path))

    def _add_action_buttons(self, layout):
        """Botons grans amb icona i color, arraconats a la dreta de la
        mateixa fila que les pestanyes, amb l'indicador d'USB al davant
        (just on abans hi havia el botó de còpia de seguretat)."""
        self.usb_indicator = UsbIndicator()
        layout.addWidget(self.usb_indicator)
        for label_key, emoji, color, slot_name in ACTION_BUTTONS:
            label = t(label_key).replace("\n", " ")
            button = QPushButton(f"{emoji}  {label}")
            button.setToolTip(label)
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-size: 12px;
                    font-weight: 600;
                    border: none;
                    border-radius: 6px;
                    padding: 4px 10px;
                }}
                """
            )
            button.clicked.connect(getattr(self, slot_name))
            layout.addWidget(button)

    def _on_tab_changed(self, index: int):
        self._stack.setCurrentIndex(index)
        widget = self._stack.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def _build_menu(self):
        menu = self.menuBar().addMenu(t("menu.file"))

        change_password_action = menu.addAction(t("menu.change_password"))
        change_password_action.triggered.connect(self._change_password)

        menu.addSeparator()

        print_board_action = menu.addAction(t("menu.print_board"))
        print_board_action.triggered.connect(self._print_board)

        print_desmagatzem_action = menu.addAction(t("menu.print_desmagatzem"))
        print_desmagatzem_action.triggered.connect(self._print_desmagatzem)

        report_action = menu.addAction(t("menu.report_covered"))
        report_action.triggered.connect(self._show_covered_report)

        menu.addSeparator()
        exit_action = menu.addAction(t("menu.exit"))
        exit_action.triggered.connect(self.close)

        menu.addSeparator()
        about_action = menu.addAction(t("menu.about"))
        about_action.triggered.connect(self._show_about)

        menu.addSeparator()
        version_action = menu.addAction(t("menu.version", version=APP_VERSION))
        version_action.setEnabled(False)  # només informatiu, no cal que faci res en clicar

        # Menú d'importació, entre Fitxer i Còpies de seguretat.
        import_menu = self.menuBar().addMenu(t("menu.import"))
        import_excel_action = import_menu.addAction(t("menu.import_excel"))
        import_excel_action.triggered.connect(self._import_from_excel)
        import_db_action = import_menu.addAction(t("menu.import_database"))
        import_db_action.triggered.connect(self._import_from_database)

        # Menú propi de còpies de seguretat, entre Fitxer i Idioma: tot el
        # que hi té a veure (fer-ne una ara i cada quantes hores es fan
        # soles) en un sol lloc, i les dues protegides amb la contrasenya.
        backup_menu = self.menuBar().addMenu(t("menu.backups"))
        backup_now_action = backup_menu.addAction(t("menu.backup_now"))
        backup_now_action.triggered.connect(self._manual_backup)
        interval_action = backup_menu.addAction(t("menu.backup_interval"))
        interval_action.triggered.connect(self._change_backup_interval)

        lang_menu = self.menuBar().addMenu(f"🌐 {t('app.language')}")
        group = QActionGroup(self)
        group.setExclusive(True)
        for code, name in i18n.LANGS.items():
            action = QAction(name, self, checkable=True)
            action.setChecked(i18n.get_language() == code)
            action.triggered.connect(lambda checked, c=code: self._change_language(c))
            group.addAction(action)
            lang_menu.addAction(action)

    def _change_language(self, lang: str):
        if lang == i18n.get_language():
            return
        i18n.set_language(lang)
        self._build_everything()

    def _show_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    # ------------------------------------------------------------------ #
    # Còpies de seguretat
    # ------------------------------------------------------------------ #
    def backup_interval_hours(self) -> int:
        """Cada quantes hores es fa la còpia automàtica (de settings.json).
        Si el valor desat no és utilitzable, es torna al de sempre."""
        value = settings.get(BACKUP_INTERVAL_SETTING, DEFAULT_BACKUP_INTERVAL_HOURS)
        try:
            hours = int(value)
        except (TypeError, ValueError):
            return DEFAULT_BACKUP_INTERVAL_HOURS
        if not MIN_BACKUP_INTERVAL_HOURS <= hours <= MAX_BACKUP_INTERVAL_HOURS:
            return DEFAULT_BACKUP_INTERVAL_HOURS
        return hours

    def _apply_backup_interval(self):
        self._backup_timer.start(self.backup_interval_hours() * 60 * 60 * 1000)

    def _manual_backup(self):
        # Protegida amb la contrasenya de l'aplicació: si no és correcta no
        # se'n comença cap part (es surt abans de tocar cap fitxer).
        if not ask_password(self, ADMIN, t("password.label_backup"), t("password.wrong.text_backup")):
            return
        dest = create_backup(self.db_path)
        dialogs.info(self, t("dialog.backup.title"), t("dialog.backup.text", path=dest))

    def _change_backup_interval(self):
        """La contrasenya protegeix la CONFIGURACIÓ de les còpies
        automàtiques; un cop desada, les còpies programades es fan soles
        quan toca, sense demanar-la (i sense haver-la de desar enlloc)."""
        if not ask_password(self, ADMIN, t("password.label_interval"), t("password.wrong.text_generic")):
            return
        hours, ok = dialogs.ask_int(
            self,
            t("backup.interval.title"),
            t("backup.interval.label", min=MIN_BACKUP_INTERVAL_HOURS, max=MAX_BACKUP_INTERVAL_HOURS),
            self.backup_interval_hours(),
            MIN_BACKUP_INTERVAL_HOURS,
            MAX_BACKUP_INTERVAL_HOURS,
        )
        if not ok:
            return
        settings.set_value(BACKUP_INTERVAL_SETTING, hours)
        self._apply_backup_interval()
        dialogs.info(self, t("common.done"), t("backup.interval.done", hours=hours))

    def _change_password(self):
        """Un sol diàleg per a les DUES contrasenyes (còpies de seguretat i
        materials): s'hi tria quina es canvia, i canviar-ne una no toca
        l'altra. Cada canvi demana la contrasenya actual d'aquella mateixa i
        la nova dues vegades (veure `ChangePasswordDialog`)."""
        ChangePasswordDialog(self).exec()

    def _auto_backup(self):
        try:
            create_backup(self.db_path)
            self.statusBar().showMessage(t("status.db_backed_up", path=self.db_path), 5000)
        except OSError:
            pass  # backup silenciós; no s'interromp la feina si falla

    def _ensure_tab_laid_out(self, tab_widget: QWidget):
        """Els botons d'exportar es poden clicar des de qualsevol pestanya
        (viuen a la fila d'accions, no dins de cap pestanya): si
        `tab_widget` no és la pestanya activa del `QStackedWidget`, Qt mai
        li ha donat una mida real (es queda amb el pedaç per defecte de
        640x480, molt petit) i l'exportació sortiria retallada. Fent-la
        "current" un instant es disposa correctament; en tornar a la
        pestanya original, la mida ja apresa es manté."""
        index = self._stack.indexOf(tab_widget)
        if index == -1 or self._stack.currentIndex() == index:
            return
        original = self._stack.currentIndex()
        self._stack.setCurrentIndex(index)
        QApplication.processEvents()
        self._stack.setCurrentIndex(original)

    # ------------------------------------------------------------------ #
    # Imprimir
    # ------------------------------------------------------------------ #
    def _print_board(self):
        self._print(self.board_tab, self.board_tab)

    def _print_desmagatzem(self):
        self._print(self.desmagatzem_tab, self.desmagatzem_tab.table)

    def _print(self, tab: QWidget, widget: QWidget):
        """Flux d'impressió comú als dos botons: preparar el que s'ha
        d'imprimir, obrir el diàleg del sistema i imprimir-hi si s'accepta.

        Cancel·lar no és cap error i no diu res; si falla la impressió (cap
        impressora, sense permisos...) s'avisa i no queda res a mitges.
        """
        self._ensure_tab_laid_out(tab)
        try:
            printed = print_widget(widget, self)
        except Exception as exc:  # noqa: BLE001 - qualsevol problema de la impressora
            dialogs.error(self, t("print.error.title"), t("print.error.detail", error=exc))
            return
        if printed:
            self.statusBar().showMessage(t("print.sent"), 5000)

    # ------------------------------------------------------------------ #
    # Importar
    # ------------------------------------------------------------------ #
    def _import_from_excel(self):
        if import_from_excel(self, Path(self.db_path)):
            self._reload_database()

    def _import_from_database(self):
        """Substitueix la base de dades per la d'un fitxer .db. La connexió
        oberta es tanca abans de tocar el fitxer i es torna a obrir després,
        perquè cap pestanya no es quedi amb dades velles."""
        self.repo.conn.close()
        replaced = import_from_database(self, Path(self.db_path))
        self._reload_database()
        if replaced:
            dialogs.info(self, t("common.done"), t("import.db.reloaded"))

    def _reload_database(self):
        """Torna a obrir la base de dades i reconstrueix la finestra amb les
        dades noves (mateix camí que en canviar d'idioma)."""
        try:
            self.repo.conn.close()
        except Exception:  # noqa: BLE001 - ja podia estar tancada
            pass
        self.repo = Repository(connect(self.db_path))
        self._build_everything()

    def _show_covered_report(self):
        # Igual que l'original (ComprovarIMostrarTapats_Correcte): escriu
        # l'informe a un .txt a la carpeta temporal i l'obre directament
        # amb l'aplicació de text per defecte del sistema — sense mostrar
        # cap finestra pròpia de l'app (l'original feia "Shell notepad.exe").
        text = covered_materials_report_text(self.repo)
        path = Path(tempfile.gettempdir()) / t("report.covered.filename")
        path.write_text(text, encoding="utf-8")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def closeEvent(self, event):
        try:
            create_backup(self.db_path)
        except OSError:
            pass
        super().closeEvent(event)
