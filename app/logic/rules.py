"""Reglas de negocio puras (sin base de datos), fáciles de testear.

Cada función aquí es la traducción directa de una regla concreta del VBA
original de SobrantsV4.74.xlsm. Se documenta en el docstring de qué macro
proviene, para poder auditar la fidelidad de la conversión.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime

MAX_SLOTS = 5
MATERIAL_CODE_MIN, MATERIAL_CODE_MAX = 0, 99999
DESMAGATZEM_QTY_MIN, DESMAGATZEM_QTY_MAX = 0, 20
CUSTOM_MATERIAL_SENTINEL = 1  # código "1" = material no registrado (texto libre)
EMPTY_MATERIAL_MARK = "---------"


def normalize_text(text) -> str:
    """Equivalente a NormalitzaText: minúsculas, sin espacios extremos, sin acentos."""
    if text is None:
        return ""
    text = str(text).strip().lower()
    # Descompone y elimina marcas diacríticas (á->a, ñ->n queda cubierto aparte)
    text = text.replace("ñ", "n").replace("ç", "c")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def is_valid_material_code(value) -> bool:
    """Worksheet_Change Hoja1: sólo números 0..99999 en L12:L16."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return False
    return MATERIAL_CODE_MIN <= n <= MATERIAL_CODE_MAX


def is_valid_desmagatzem_qty(value) -> bool:
    """Worksheet_Change desmagatzem: sólo números 0..20 en columna A."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return False
    return DESMAGATZEM_QTY_MIN <= n <= DESMAGATZEM_QTY_MAX


def next_free_slot(filled_slots: list[int]) -> int | None:
    """Siguiente slot disponible para una posición (llenado ordenado, sin huecos).

    Corresponde al control 'ORDRE NO CORRECTE' de Worksheet_Change/SelectionChange:
    sólo se puede escribir en la fila siguiente a la última ocupada.
    """
    filled = sorted(filled_slots)
    expected = list(range(1, len(filled) + 1))
    if filled != expected:
        raise ValueError("Los huecos de la posición están corruptos (deben ser consecutivos desde 1)")
    if len(filled) >= MAX_SLOTS:
        return None
    return len(filled) + 1


def can_delete_slot(filled_slots: list[int], slot: int) -> bool:
    """Sólo se puede borrar el último slot ocupado (de abajo hacia arriba).

    Corresponde al bloqueo 'ORDRE INCORRECTE' al borrar en Worksheet_Change Hoja1
    (comprueba que la fila inferior no tenga valor > 1) y a la lógica análoga
    de desmagatzem (borrado de fila = vaciar cantidad a 0).
    """
    if not filled_slots:
        return False
    return slot == max(filled_slots)


@dataclass
class DuplicateMatch:
    position: int
    slot: int


def find_duplicate_positions(
    all_pieces: list[tuple[int, int, int]], material_code: int, exclude_position: int
) -> list[int]:
    """MATERIAL DUPLICAT: posiciones (≠ la actual) que ya contienen ese código.

    all_pieces: lista de (position, slot, material_code).
    Devuelve la lista de posiciones distintas donde aparece el material,
    tal y como se listaba en el MsgBox de ComprovarCoincidenciesL12L16.
    """
    positions = set()
    for position, _slot, code in all_pieces:
        if code == material_code and position != exclude_position:
            positions.add(position)
    return sorted(positions)


def board_summary_piece(pieces_in_position: list[dict]) -> dict | None:
    """Pieza que se muestra en el panel principal para una posición.

    Traduce ActualitzarUltimesCoincidencies / MostrarUltimValorMesGranQue1:
    recorre las piezas de la posición de la última a la primera y toma la
    primera con código numérico > 1 (es decir, el slot ocupado más alto que
    no sea el código "material no registrado" = 1).
    """
    for piece in sorted(pieces_in_position, key=lambda p: p["slot"], reverse=True):
        code = piece.get("material_code")
        if code is not None and code > CUSTOM_MATERIAL_SENTINEL:
            return piece
    return None


def matches_exact(value: str, query: str) -> bool:
    """Buscador M20: coincidencia exacta normalizada (por código de material)."""
    return normalize_text(value) == normalize_text(query)


def matches_partial(value: str, query: str) -> bool:
    """Buscadores M22/M24: coincidencia parcial normalizada (substring)."""
    q = normalize_text(query)
    if q == "":
        return False
    return q in normalize_text(value)


def oldest_matching_position(matches: list[dict]) -> int | str | None:
    """Posición de prioridad (O20/O22/O24): la coincidencia con entered_at más antiguo.

    matches: lista de dicts con 'position' y 'entered_at' (ISO str o None).
    Sólo se consideran piezas con fecha de entrada (código > 1, igual que el original).
    """
    dated = [m for m in matches if m.get("entered_at")]
    if not dated:
        return None
    best = min(dated, key=lambda m: m["entered_at"])
    return best["position"]


# Escala de color por ocupación de una posición (AplicarColorsPerCoincidencies /
# AplicarColorSegonsFilaIValorK12): el color de referencia se tomaba de las
# celdas K12:K16 del propio Excel. Valores extraídos del archivo original:
# 0-1 pieza=blanco, 2=amarillo claro, 3=verde claro, 4=azul claro, 5+=rojo.
FILL_COLOR_SCALE = ["#FFFFFF", "#FFF2CC", "#C6E0B4", "#B4C6E7", "#FF0000"]


def fill_color_for_count(piece_count: int) -> str:
    """Color de "cuánto ocupa" una posición, igual que la referencia K12:K16."""
    if piece_count <= 1:
        return FILL_COLOR_SCALE[0]
    if piece_count >= 5:
        return FILL_COLOR_SCALE[4]
    return FILL_COLOR_SCALE[piece_count - 1]


def has_material_inconsistency(material_codes: list) -> bool:
    """MarcarInconsistencies: una posición se marca en rojo si contiene más de
    un material distinto entre sus piezas (aviso de posible error de ubicación).
    """
    distinct = {c for c in material_codes if c not in (None, "")}
    return len(distinct) > 1


def quantity_change_kind(old_qty: int, new_qty: int) -> str | None:
    """ActualitzaHistorialQuantitat: determina si es un aumento, disminución o borrado."""
    if new_qty == 0 and old_qty > 0:
        return "delete"
    if new_qty > old_qty:
        return "increase"
    if new_qty < old_qty:
        return "decrease"
    return None


def find_covered_materials(entries_by_position: dict[int, list[dict]]) -> list[dict]:
    """Informe 'Materials tapats' (ComprovarIMostrarTapats_Correcte).

    Para cada posición, si ha habido más de un material distinto a lo largo
    del histórico de entradas y el último registrado no es el único, se listan
    todas las entradas "tapadas" (todas menos la última válida).
    entries_by_position: {posicion: [ {material_code, material_desc, dimensions}, ... ]}
    en orden cronológico de entrada.
    Devuelve lista de dicts {position, material_code, material_desc, dimensions}.
    """
    covered = []
    for position, entries in entries_by_position.items():
        valid = [e for e in entries if e.get("material_code") not in (None, "", EMPTY_MATERIAL_MARK)]
        if not valid:
            continue
        distinct_codes = {e["material_code"] for e in valid}
        if len(distinct_codes) <= 1:
            continue
        last_valid = valid[-1]
        for e in valid[:-1]:
            covered.append({"position": position, **e})
        # nota: last_valid se omite a propósito (es la entrada vigente, no "tapada")
        del last_valid
    return covered
