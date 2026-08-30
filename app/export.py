"""Impressió/exportació (ImprimirHoja1, ImprimirDesmagatzem, Materials tapats).

A l'original s'imprimia directament a la impressora de Windows i l'informe
de materials tapats s'obria al Bloc de notes. A l'app nova s'exporta a PDF
(multiplataforma, sense dependre d'una impressora concreta) i l'informe es
mostra en un diàleg dins de la mateixa aplicació.

Els PDF del Tauler i de Desmagatzem no es construeixen com una taula a
part: es captura el widget corresponent tal com es veu en pantalla (colors
inclosos: l'escala d'ocupació i el text vermell d'inconsistència al
Tauler, els ressaltats de cerca a Desmagatzem...) i es col·loca en una
pàgina A4, en vertical o apaïsat segons quina forma s'ajusti més a la del
widget capturat, perquè ocupi el màxim possible de la pàgina sense
deformar-se. El Tauler exporta la pestanya sencera (taula, panell de
detall, panell de cerca); Desmagatzem exporta només la seva taula (sense
el formulari "Nova entrada" de sobre, perquè hi càpiga més ampla i es
llegeixi bé). Cap dels dos inclou mai les pestanyes ni els botons d'acció
(Exportar, Materials tapats, Còpia de seguretat), que viuen fora d'aquests
widgets.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import NamedTuple

from PySide6.QtCore import QMarginsF, Qt
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QWidget

from app.i18n import t
from app.logic.repository import Repository


def export_board_pdf(board_tab_widget: QWidget, dest_path: str) -> None:
    """`widget` és tota la pestanya Tauler (taula + panell de detall +
    panell de cerca)."""
    _print_widget_to_pdf(board_tab_widget, dest_path)


def export_desmagatzem_pdf(table_widget: QWidget, dest_path: str) -> None:
    """`widget` és només la taula de Desmagatzem (sense el formulari "Nova
    entrada" de sobre), perquè hi càpiga més ampla i es llegeixi bé."""
    _print_widget_to_pdf(table_widget, dest_path)


def _paint_widget_on_printer(widget: QWidget, printer: QPrinter) -> None:
    """Captura el widget tal com es veu (colors inclosos) i l'encabeix,
    centrat i mantenint la relació d'aspecte, en una pàgina A4. L'orientació
    (vertical o apaïsada) es tria segons la forma del propi widget capturat,
    perquè ocupi el màxim possible de la pàgina en comptes de deixar
    marges buits grans a dalt/baix o als costats.

    És el mateix dibuix tant si la pàgina va a un PDF com si va a una
    impressora de debò: el contingut i el format no canvien.
    """
    pixmap = widget.grab()

    orientation = (
        QPageLayout.Landscape if pixmap.width() >= pixmap.height() else QPageLayout.Portrait
    )
    printer.setPageLayout(
        QPageLayout(QPageSize(QPageSize.A4), orientation, QMarginsF(10, 10, 10, 10))
    )

    painter = QPainter()
    if not painter.begin(printer):
        # Impressora no disponible, sense permisos, fitxer bloquejat...
        raise RuntimeError(t("print.error.text"))
    try:
        page_rect = printer.pageRect(QPrinter.DevicePixel)
        scaled = pixmap.scaled(
            page_rect.size().toSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        x = (page_rect.width() - scaled.width()) / 2
        y = (page_rect.height() - scaled.height()) / 2
        painter.drawPixmap(int(x), int(y), scaled)
    finally:
        painter.end()


def _print_widget_to_pdf(widget: QWidget, dest_path: str) -> None:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(dest_path)
    _paint_widget_on_printer(widget, printer)


def print_widget(widget: QWidget, parent: QWidget | None = None) -> bool:
    """Obre el diàleg d'impressió NATIU del sistema i, si s'accepta, hi
    imprimeix el widget amb el mateix format de sempre.

    `QPrintDialog` és el diàleg propi de cada sistema (Windows, macOS,
    Linux): l'usuari hi tria la impressora —o "imprimir a PDF", si en té—,
    còpies, pàgines... No es genera cap fitxer temporal pel camí: es pinta
    directament a la impressora que s'hagi triat, així no queda res per
    netejar. Retorna False si s'ha cancel·lat (llavors no s'imprimeix res).
    """
    printer = QPrinter(QPrinter.HighResolution)
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle(t("print.dialog.title"))
    if dialog.exec() != QPrintDialog.Accepted:
        return False  # cancel·lat: no es fa res, i no és cap error
    _paint_widget_on_printer(widget, printer)
    return True


class ReportCell(NamedTuple):
    """Una cel·la de l'informe: el text i, si en té, el color de fons que
    tingui a la taula (per exemple el d'un ressaltat de cerca)."""

    text: str
    background: str = ""


def print_table_report(
    title: str,
    headers: list[str],
    rows: list[list[ReportCell]],
    parent: QWidget | None = None,
) -> bool:
    """Imprimeix una taula SENCERA com un informe, no com una captura.

    Es fa amb un `QTextDocument`: se li dona la taula en HTML i el motor de
    text de Qt ja s'encarrega de repartir-la en pàgines, de repetir la
    capçalera (`<thead>`) a cada pàgina i de no partir les files pel mig.
    Per això no depèn gens del que es vegi a la pantalla: hi surten totes
    les files que se li passin, per moltes que siguin, i cap botó ni cap
    altre control de l'aplicació.

    Surt apaïsat (les taules són més amples que altes) i no crea cap fitxer
    temporal: es pinta directament a la impressora que triï l'usuari al
    diàleg del sistema. Retorna False si s'ha cancel·lat.
    """
    printer = QPrinter(QPrinter.HighResolution)
    printer.setPageLayout(
        QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape, QMarginsF(12, 12, 12, 12))
    )
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle(t("print.dialog.title"))
    if dialog.exec() != QPrintDialog.Accepted:
        return False

    document = QTextDocument()
    document.setDefaultStyleSheet(_REPORT_STYLE)
    document.setHtml(_report_html(title, headers, rows))
    document.setPageSize(printer.pageRect(QPrinter.Point).size())
    document.print_(printer)
    return True


_REPORT_STYLE = """
h1 { font-size: 13pt; font-family: sans-serif; }
p.subtitle { font-size: 8pt; color: #444; font-family: sans-serif; }
table { border-collapse: collapse; font-family: sans-serif; font-size: 8pt; }
th { background-color: #eef0f3; border: 1px solid #9aa0a8; padding: 3px 5px; text-align: left; }
td { border: 1px solid #c7cad1; padding: 2px 5px; }
"""


def _cell_html(cell) -> str:
    """Una cel·la. Si porta color, es posa al propi <td>: així el fons surt
    imprès igual que es veu a la taula, a totes les pàgines (el motor de
    text de Qt pinta els fons de les cel·les tal com els hi digui l'HTML,
    no cal activar-hi res)."""
    if isinstance(cell, ReportCell):
        text, background = cell.text, cell.background
    else:
        text, background = cell, ""
    style = f' bgcolor="{escape(background)}"' if background else ""
    return f"<td{style}>{escape('' if text is None else str(text))}</td>"


def _report_html(title: str, headers: list[str], rows: list[list[ReportCell]]) -> str:
    """La taula en HTML. `<thead>` és el que fa que Qt repeteixi la
    capçalera a cada pàgina."""
    head = "".join(f"<th>{escape(str(h))}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(_cell_html(cell) for cell in row) + "</tr>" for row in rows
    )
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    return (
        f"<h1>{escape(title)}</h1>"
        f"<p class='subtitle'>{escape(t('print.report.subtitle', count=len(rows), datetime=now))}</p>"
        f"<table width='100%'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )


def covered_materials_report_text(repo: Repository) -> str:
    """Informe 'Materials tapats': text per mostrar en un diàleg de l'app."""
    covered = repo.covered_materials_report()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    lines = [
        f"{t('report.covered.title')} — {now}",
        "",
        f"{t('export.col.position'):<10}{t('export.col.code'):<10}{t('export.col.material'):<50}"
        f"{t('export.col.dimensions')}",
    ]
    lines.append("-" * 90)
    if not covered:
        lines.append(t("report.covered.empty"))
    for c in covered:
        lines.append(
            f"{c['position']:<10}{c['material_code'] or '':<10}{c['material_desc'] or '':<50}"
            f"{c['dimensions'] or ''}"
        )
    return "\n".join(lines)
