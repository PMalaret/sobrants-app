"""Impressió/exportació (ImprimirHoja1, ImprimirDesmagatzem, Materials tapats).

A l'original s'imprimia directament a la impressora de Windows i l'informe
de materials tapats s'obria al Bloc de notes. A l'app nova s'exporta a PDF
(multiplataforma, sense dependre d'una impressora concreta) i l'informe es
mostra en un diàleg dins de la mateixa aplicació.

Els PDF del Tauler i de Desmagatzem no es construeixen com una taula a
part: es captura la pestanya tal com es veu en pantalla (colors inclosos:
l'escala d'ocupació i el text vermell d'inconsistència al Tauler, els
ressaltats de cerca a Desmagatzem...) i es col·loca en una pàgina A4
apaïsada. Així s'exporta exactament "tot el que hi ha" a la pestanya
(taula, panell de detall, panell de cerca), sense les pestanyes ni els
botons d'acció (Exportar, Materials tapats, Còpia de seguretat), que viuen
fora del widget de la pestanya i per tant no s'hi capturen mai.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QMarginsF, Qt
from PySide6.QtGui import QPageLayout, QPageSize, QPainter
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QWidget

from app.i18n import t
from app.logic.repository import Repository


def export_board_pdf(widget: QWidget, dest_path: str) -> None:
    _print_widget_to_pdf(widget, dest_path)


def export_desmagatzem_pdf(widget: QWidget, dest_path: str) -> None:
    _print_widget_to_pdf(widget, dest_path)


def _print_widget_to_pdf(widget: QWidget, dest_path: str) -> None:
    """Captura el widget tal com es veu (colors inclosos) i l'encabeix,
    centrat i mantenint la relació d'aspecte, en una pàgina A4 apaïsada."""
    pixmap = widget.grab()

    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(dest_path)
    printer.setPageLayout(
        QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape, QMarginsF(10, 10, 10, 10))
    )

    painter = QPainter(printer)
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
