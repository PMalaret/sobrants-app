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
    QLabel,
    QMainWindow,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from app import i18n, settings
from app.backup import create_backup, run_backup
from app.data.db import connect
from app.export import covered_materials_report_text, print_table_report, print_widget
from app.i18n import t
from app.logic.repository import Repository
from app.security import ADMIN
from app.ui import dialogs, theme
from app.ui.about_dialog import AboutDialog
from app.ui.backup_dialog import BackupSettingsDialog, backup_folder, backup_keep, backup_prefix
from app.ui.import_actions import import_from_database, import_from_excel
from app.ui.usb_indicator import removable_drives
from app.ui.board_tab import BoardTab
from app.ui.desmagatzem_tab import DesmagatzemTab
from app.ui.historic_tab import HistoricTab
from app.ui.materials_tab import MaterialsTab
from app.ui.password_dialog import ChangePasswordDialog, ask_password
from app.ui.statistics_tab import StatisticsTab
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

# Quina pestanya és el Tauler. La llegenda de colors de la barra d'estat
# només té sentit quan es veu el Tauler (és el que explica), així que només
# hi surt quan aquesta és la pestanya activa.
BOARD_TAB_INDEX = 0


class MainWindow(QMainWindow):
    def __init__(self, repo: Repository, db_path: str):
        super().__init__()
        self.repo = repo
        self.db_path = db_path
        # L'alçada la marca el Tauler, que és l'única pestanya que no fa
        # scroll: hi han de cabre les 61 posicions I el panell de detall
        # incrustat sencer (les 5 línies de la posició, els botons
        # d'Esborrar/Moure, el cercador i la zona d'accions de sota). Amb
        # 700 quedava just i, segons la lletra del sistema, l'última part
        # del panell es podia quedar fora; 780 hi deixa marge i encara cap
        # en una pantalla de 1366x768 en dues passes (la finestra és
        # redimensionable i el contingut s'hi adapta).
        self.resize(1500, 780)

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
        self.statistics_tab = StatisticsTab(self.repo)
        self.board_tab.data_changed.connect(self.historic_tab.refresh)
        # El comptador de peces es refresca amb qualsevol canvi de dades.
        for tab in (self.board_tab, self.desmagatzem_tab, self.materials_tab):
            tab.data_changed.connect(self.refresh_piece_count)
        self.desmagatzem_tab.data_changed.connect(self.historic_tab.refresh)
        # Les estadístiques surten de l'històric: es refresquen amb ell.
        for tab in (self.board_tab, self.desmagatzem_tab):
            tab.data_changed.connect(self.statistics_tab.refresh)
        # Els resultats dels cercadors del Tauler també compten unitats de
        # Desmagatzem ("Unitats a Desmagatzem"), així que una alta, una
        # baixa o un canvi de quantitat allà els fa canviar. Es tornen a
        # executar pel mateix camí que quan es toca el Tauler
        # (`BoardTab.refresh_searches`), amb cerca activa o sense.
        self.desmagatzem_tab.data_changed.connect(self.board_tab.refresh_searches)
        # Els botons d'imprimir viuen dins de les pestanyes, però el flux
        # d'impressió segueix sent el mateix d'aquí.
        self.board_tab.print_requested.connect(self._print_board)
        self.board_tab.covered_requested.connect(self._show_covered_report)
        self.desmagatzem_tab.print_requested.connect(self._print_desmagatzem)
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
        tab_bar.addTab(t("tab.statistics"))
        tab_bar.setExpanding(False)
        tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar = tab_bar

        stack = QStackedWidget()
        stack.setObjectName("tabStack")
        stack.addWidget(self.board_tab)
        stack.addWidget(self.desmagatzem_tab)
        stack.addWidget(self.historic_tab)
        stack.addWidget(self.materials_tab)
        stack.addWidget(self.statistics_tab)
        self._stack = stack

        top_row = QWidget()
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 4, 0)
        top_row_layout.setSpacing(8)
        top_row_layout.addWidget(tab_bar)
        top_row_layout.addStretch()
        # A la dreta de la fila de pestanyes només hi ha l'indicador d'USB:
        # el total de peces ha baixat a la barra d'estat.
        self.usb_indicator = UsbIndicator()
        top_row_layout.addWidget(self.usb_indicator)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(top_row)
        central_layout.addWidget(stack)
        self.setCentralWidget(central)

        self.menuBar().clear()
        self._build_menu()

        self._build_status_bar()

    def _build_status_bar(self):
        """La barra d'estat, d'esquerra a dreta: quantes peces hi ha al
        Tauler, on és la base de dades i, a la dreta de tot, la llegenda de
        colors d'ocupació (només mentre es veu el Tauler).

        Es reconstrueix sencera quan canvia l'idioma, així que primer es
        treu el que hi hagués posat abans."""
        status = self.statusBar()
        for child in status.findChildren(QWidget):
            if getattr(child, "_sobrants_status_widget", False):
                status.removeWidget(child)
                child.deleteLater()

        # Total de peces, a l'esquerra de tot. Ve de la base de dades
        # (`Repository.count_pieces`), no del que hi hagi pintat.
        self.pieces_label = QLabel()
        self.pieces_label.setStyleSheet(
            theme.css("font-size: 13px; font-weight: 600; color: $text;")
        )
        self.refresh_piece_count()

        self.db_label = QLabel(t("status.db", path=self.db_path))
        # La llegenda explica els colors del Tauler: només hi surt quan la
        # pestanya que es veu és aquella.
        self.legend_widget = self.board_tab.build_legend_widget()
        for widget in (self.pieces_label, self.db_label, self.legend_widget):
            widget._sobrants_status_widget = True
        status.addWidget(self.pieces_label)
        status.addWidget(self.db_label)
        status.addPermanentWidget(self.legend_widget)
        self._update_legend_visibility(BOARD_TAB_INDEX)

    def _update_legend_visibility(self, index: int):
        self.legend_widget.setVisible(index == BOARD_TAB_INDEX)

    def refresh_piece_count(self):
        """Torna a comptar les peces i ho ensenya. Es crida cada cop que
        alguna cosa pot haver-les canviat (altes, baixes, trasllats, canvis
        de quantitat, importacions...) i en canviar de pestanya."""
        count = self.repo.count_pieces()
        self.pieces_label.setText(t("board.piece_count", count=i18n.format_number(count)))

    def _on_tab_changed(self, index: int):
        self._stack.setCurrentIndex(index)
        self._update_legend_visibility(index)
        widget = self._stack.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()
        self.refresh_piece_count()

    def _menu(self, title: str):
        """Un menú de la barra, ja preparat perquè se li vegin les
        cantonades arrodonides (veure `theme.prepare_menu`)."""
        menu = self.menuBar().addMenu(title)
        theme.prepare_menu(menu)
        return menu

    def _build_menu(self):
        menu = self._menu(t("menu.file"))

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
        import_menu = self._menu(t("menu.import"))
        import_excel_action = import_menu.addAction(t("menu.import_excel"))
        import_excel_action.triggered.connect(self._import_from_excel)
        import_db_action = import_menu.addAction(t("menu.import_database"))
        import_db_action.triggered.connect(self._import_from_database)

        # Menú propi de còpies de seguretat, entre Fitxer i Idioma: tot el
        # que hi té a veure (fer-ne una ara i cada quantes hores es fan
        # soles) en un sol lloc, i les dues protegides amb la contrasenya.
        backup_menu = self._menu(t("menu.backups"))
        backup_now_action = backup_menu.addAction(t("menu.backup_now"))
        backup_now_action.triggered.connect(self._manual_backup)
        interval_action = backup_menu.addAction(t("menu.backup_interval"))
        interval_action.triggered.connect(self._change_backup_interval)

        lang_menu = self._menu(f"🌐 {t('app.language')}")
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

    def _backup_folder(self):
        from app.backup import default_backups_dir

        return backup_folder(self.db_path, default_backups_dir(self.db_path))

    def _usb_root(self, ask: bool = False):
        """Quin USB fer servir per a la segona còpia, o None si no n'hi ha.

        Amb un de sol, aquell. Amb més d'un: si es pot preguntar (còpia
        manual) es deixa triar, i si no (còpia automàtica) s'agafa el
        primer per ordre, que és un criteri estable i previsible.
        """
        drives = removable_drives()
        if not drives:
            return None
        if len(drives) == 1 or not ask:
            return drives[0]
        choice, ok = dialogs.ask_choice(
            self, t("backup.usb.pick.title"), t("backup.usb.pick.text"), drives
        )
        return choice if ok else None

    def _do_backup(self, ask_usb: bool) -> "BackupResult":
        """La còpia tal com la fa l'aplicació, amb la carpeta i el nom
        configurats i la segona còpia al USB si n'hi ha."""
        return run_backup(
            self.db_path,
            backups_dir=self._backup_folder(),
            prefix=backup_prefix(),
            usb_root=self._usb_root(ask=ask_usb),
            keep=backup_keep(),
        )

    def _manual_backup(self):
        # Protegida amb la contrasenya d'administrador: si no és correcta no
        # se'n comença cap part (es surt abans de tocar cap fitxer).
        if not ask_password(self, ADMIN, t("password.label_backup"), t("password.wrong.text_backup")):
            return
        result = self._do_backup(ask_usb=True)
        if not result.ok:
            dialogs.error(
                self, t("dialog.backup.error.title"),
                t("dialog.backup.error.text", error="; ".join(result.errors)),
            )
            return
        # Es diu exactament què ha passat: mai "duplicada" si no ho és.
        if result.duplicated:
            text = t("dialog.backup.text_usb", path=result.main_path, usb=result.usb_path)
        elif result.usb_error:
            text = t("dialog.backup.text_usb_failed", path=result.main_path, error=result.usb_error)
        else:
            text = t("dialog.backup.text", path=result.main_path)
        dialogs.info(self, t("dialog.backup.title"), text)

    def _change_backup_interval(self):
        """Configuració de les còpies: on van, com es diuen i cada quantes
        hores es fan. La contrasenya protegeix la CONFIGURACIÓ; un cop
        desada, les còpies programades es fan soles quan toca, sense
        demanar-la (i sense haver-la de desar enlloc)."""
        if not ask_password(self, ADMIN, t("password.label_interval"), t("password.wrong.text_generic")):
            return
        from app.backup import default_backups_dir

        dialog = BackupSettingsDialog(
            default_backups_dir(self.db_path),
            self.backup_interval_hours(),
            MIN_BACKUP_INTERVAL_HOURS,
            MAX_BACKUP_INTERVAL_HOURS,
            self,
        )
        if dialog.exec() != BackupSettingsDialog.Accepted:
            return
        self._apply_backup_interval()
        dialogs.info(self, t("common.done"), t("backup.settings.done", folder=self._backup_folder()))

    def _change_password(self):
        """Un sol diàleg per a les DUES contrasenyes (còpies de seguretat i
        materials): s'hi tria quina es canvia, i canviar-ne una no toca
        l'altra. Cada canvi demana la contrasenya actual d'aquella mateixa i
        la nova dues vegades (veure `ChangePasswordDialog`)."""
        ChangePasswordDialog(self).exec()

    def _auto_backup(self):
        """Còpia programada: mai demana res (ni contrasenya ni quin USB) i
        mai interromp la feina si falla."""
        try:
            result = self._do_backup(ask_usb=False)
        except OSError:
            return
        if result.ok:
            self.statusBar().showMessage(t("status.db_backed_up", path=result.main_path), 5000)

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
        """Desmagatzem s'imprimeix com un INFORME, no com una captura: es
        demanen a la pestanya totes les files de la taula (hi hagi scroll
        o no) i es componen en pàgines amb la capçalera repetida."""
        headers, rows = self.desmagatzem_tab.printable_rows()
        try:
            printed = print_table_report(t("tab.desmagatzem"), headers, rows, self)
        except Exception as exc:  # noqa: BLE001 - qualsevol problema de la impressora
            dialogs.error(self, t("print.error.title"), t("print.error.detail", error=exc))
            return
        if printed:
            self.statusBar().showMessage(t("print.sent"), 5000)

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
    def _ask_import_password(self) -> bool:
        """Les dues importacions substitueixen dades que ja hi ha, així que
        totes dues demanen primer la contrasenya d'administrador (la
        mateixa de les còpies de seguretat i de netejar l'històric, via
        `ask_password`: aquí no hi ha cap comprovació pròpia). Si no és
        correcta o es cancel·la el diàleg, no es toca res: se surt abans
        d'obrir cap fitxer."""
        return ask_password(
            self, ADMIN, t("password.label_import"), t("password.wrong.text_import")
        )

    def _import_from_excel(self):
        if not self._ask_import_password():
            return
        if import_from_excel(self, Path(self.db_path)):
            self._reload_database()

    def _import_from_database(self):
        """Substitueix la base de dades per la d'un fitxer .db. La connexió
        oberta es tanca abans de tocar el fitxer i es torna a obrir després,
        perquè cap pestanya no es quedi amb dades velles."""
        if not self._ask_import_password():
            return
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
            self._do_backup(ask_usb=False)
        except OSError:
            pass
        super().closeEvent(event)
