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

from PySide6.QtCore import QMarginsF, Qt
from PySide6.QtGui import QPageLayout, QPageSize, QPainter
from PySide6.QtPrintSupport import QPrinter
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


def _print_widget_to_pdf(widget: QWidget, dest_path: str) -> None:
    """Captura el widget tal com es veu (colors inclosos) i l'encabeix,
    centrat i mantenint la relació d'aspecte, en una pàgina A4. L'orientació
    (vertical o apaïsada) es tria segons la forma del propi widget capturat,
    perquè ocupi el màxim possible de la pàgina en comptes de deixar
    marges buits grans a dalt/baix o als costats."""
    pixmap = widget.grab()

    orientation = (
        QPageLayout.Landscape if pixmap.width() >= pixmap.height() else QPageLayout.Portrait
    )

    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(dest_path)
    printer.setPageLayout(
        QPageLayout(QPageSize(QPageSize.A4), orientation, QMarginsF(10, 10, 10, 10))
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
