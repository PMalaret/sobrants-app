"""Impressió/exportació (ImprimirHoja1, ImprimirDesmagatzem, Materials tapats).

A l'original s'imprimia directament a la impressora de Windows i l'informe
de materials tapats s'obria al Bloc de notes. A l'app nova s'exporta a PDF
(multiplataforma, sense dependre d'una impressora concreta) i l'informe es
mostra en un diàleg dins de la mateixa aplicació.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter

from app.i18n import t
from app.logic.repository import Repository


def _html_table(title: str, headers: list[str], rows: list[list[str]]) -> str:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows
    )
    return f"""
    <html><head><style>
        body {{ font-family: Arial, sans-serif; font-size: 10pt; }}
        h2 {{ text-align: center; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #888; padding: 3px 6px; text-align: left; }}
        th {{ background: #eee; }}
    </style></head><body>
        <h2>{title} — {now}</h2>
        <table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>
    </body></html>
    """


def export_board_pdf(repo: Repository, dest_path: str) -> None:
    board = repo.get_board()
    rows = [
        [b["position"], b["material_code"] or "", b["material_desc"] or "", b["dimensions"] or "", b["notes"] or ""]
        for b in board
    ]
    headers = [
        t("export.col.position"),
        t("export.col.code"),
        t("export.col.material"),
        t("export.col.dimensions"),
        t("export.col.notes"),
    ]
    html = _html_table(t("export.board.title"), headers, rows)
    _print_html_to_pdf(html, dest_path, landscape=True)


def export_desmagatzem_pdf(repo: Repository, dest_path: str) -> None:
    rows_data = repo.list_desmagatzem()
    rows = [
        [r["quantity"], r["material_code"], r["material_desc"] or "", r["dimensions"] or "", r["cart_ref"] or ""]
        for r in rows_data
    ]
    headers = [
        t("export.col.quantity"),
        t("export.col.code"),
        t("export.col.material"),
        t("export.col.dimensions"),
        t("export.col.cart"),
    ]
    html = _html_table(t("export.desmagatzem.title"), headers, rows)
    _print_html_to_pdf(html, dest_path, landscape=False)


def _print_html_to_pdf(html: str, dest_path: str, landscape: bool) -> None:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(dest_path)
    layout = QPageLayout(
        QPageSize(QPageSize.A4),
        QPageLayout.Landscape if landscape else QPageLayout.Portrait,
        QMarginsF(10, 10, 10, 10),
    )
    printer.setPageLayout(layout)

    doc = QTextDocument()
    doc.setHtml(html)
    doc.setPageSize(QSizeF(printer.pageRect(QPrinter.Point).size()))
    doc.print_(printer)


def covered_materials_report_text(repo: Repository) -> str:
    """Informe 'Materials tapats': text per mostrar en un diàleg de l'app."""
    covered = repo.covered_materials_report()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    lines = [
        f"{t('report.covered.title')} — {now}",
        "",
        f"{t('export.col.position'):<10}{t('export.col.code'):<10}{t('export.col.material')}",
    ]
    lines.append("-" * 70)
    if not covered:
        lines.append(t("report.covered.empty"))
    for c in covered:
        lines.append(f"{c['position']:<10}{c['material_code'] or '':<10}{c['material_desc'] or ''}")
    return "\n".join(lines)
