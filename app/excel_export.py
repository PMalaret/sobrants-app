"""Exportació a Excel (.xlsx).

En un mòdul a part i SENSE Qt a posta: així es pot fer servir —i provar—
sense necessitar cap entorn gràfic (la compilació de GitHub Actions passa
els tests en un Linux sense pantalla). La impressió i el PDF, que sí que
necessiten Qt, viuen a `app.export`.
"""
from __future__ import annotations

from openpyxl import Workbook


def export_historic_xlsx(rows: list[dict], headers: list[str], fields: list[str], dest_path: str) -> int:
    """Tot l'històric a un .xlsx: la capçalera amb els noms de les columnes i
    després TOTES les files que se li passin (no només les que es veuen a la
    pantalla). Retorna quantes n'ha escrit.

    Fa servir openpyxl, que ja és una dependència del projecte (és el que
    llegeix el .xlsm original a la migració), en mode "write_only": no
    manté el full sencer a memòria, així un històric de desenes de milers
    de línies s'escriu sense problema.
    """
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(title="Historic")
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(field) for field in fields])
    workbook.save(dest_path)
    return len(rows)
