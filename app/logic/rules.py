"""Regles de negoci pures (sense base de dades), fàcils de testejar.

Cada funció aquí és la traducció directa d'una regla concreta del VBA
original de SobrantsV4.74.xlsm. Es documenta al docstring de quina macro
prové, per poder auditar la fidelitat de la conversió.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime

from app.i18n import t

MAX_SLOTS = 5
# Només números positius: el 0 no és cap material (i els negatius, menys).
MATERIAL_CODE_MIN, MATERIAL_CODE_MAX = 1, 999999
DESMAGATZEM_QTY_MIN, DESMAGATZEM_QTY_MAX = 0, 999
# Màxim de caràcters de les notes d'una línia de desmagatzem. Es defineix
# aquí perquè el camp del formulari, l'edició dins de la taula i el que
# desa el repositori facin servir tots el mateix límit.
DESMAGATZEM_NOTES_MAX_CHARS = 15
CUSTOM_MATERIAL_SENTINEL = 1  # codi "1" = material no registrat (text lliure)
EMPTY_MATERIAL_MARK = "---------"


def normalize_text(text) -> str:
    """Equivalent a NormalitzaText: minúscules, sense espais als extrems, sense accents."""
    if text is None:
        return ""
    text = str(text).strip().lower()
    # Descompon i elimina marques diacrítiques (á->a, ñ->n es cobreix a part)
    text = text.replace("ñ", "n").replace("ç", "c")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def is_valid_material_code(value) -> bool:
    """Worksheet_Change Hoja1: només números positius a L12:L16 (l'original
    admetia fins a 99999, però l'alta de materials nous ja permet codis de
    6 xifres — cal que aquí també s'hi puguin col·locar peces).

    Fals per a qualsevol cosa que no sigui un número (lletres, buit, símbols)
    i també per al 0 i els negatius."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return False
    if n != int(n):
        return False  # un codi de material és un enter, no 12,5
    return MATERIAL_CODE_MIN <= n <= MATERIAL_CODE_MAX


def truncate_desmagatzem_notes(value: str) -> str | None:
    """Les notes d'una línia de desmagatzem, retallades al màxim permès.
    Retorna None si no en queda res (la base de dades hi vol NULL)."""
    text = (value or "").strip()[:DESMAGATZEM_NOTES_MAX_CHARS]
    return text or None


def is_valid_desmagatzem_qty(value) -> bool:
    """Worksheet_Change desmagatzem: només números 0..100 a la columna A."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return False
    return DESMAGATZEM_QTY_MIN <= n <= DESMAGATZEM_QTY_MAX


def next_free_slot(filled_slots: list[int]) -> int | None:
    """Següent slot disponible per a una posició (ompliment ordenat, sense forats).

    Correspon al control 'ORDRE NO CORRECTE' de Worksheet_Change/SelectionChange:
    només es pot escriure a la fila següent a l'última ocupada.
    """
    filled = sorted(filled_slots)
    expected = list(range(1, len(filled) + 1))
    if filled != expected:
        raise ValueError(t("err.corrupt_slots"))
    if len(filled) >= MAX_SLOTS:
        return None
    return len(filled) + 1


def can_delete_slot(filled_slots: list[int], slot: int) -> bool:
    """Només es pot esborrar l'últim slot ocupat (de baix cap amunt).

    Correspon al bloqueig 'ORDRE INCORRECTE' en esborrar a Worksheet_Change Hoja1
    (comprova que la fila inferior no tingui valor > 1) i a la lògica anàloga
    de desmagatzem (esborrat de fila = buidar quantitat a 0).
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
    """MATERIAL DUPLICAT: posicions (≠ l'actual) que ja contenen aquest codi.

    all_pieces: llista de (position, slot, material_code).
    Retorna la llista de posicions diferents on apareix el material,
    tal com es llistava al MsgBox de ComprovarCoincidenciesL12L16.
    """
    positions = set()
    for position, _slot, code in all_pieces:
        if code == material_code and position != exclude_position:
            positions.add(position)
    return sorted(positions)


def board_summary_piece(pieces_in_position: list[dict]) -> dict | None:
    """Peça que es mostra al panell principal per a una posició.

    Tradueix ActualitzarUltimesCoincidencies / MostrarUltimValorMesGranQue1:
    recorre les peces de la posició de l'última a la primera i agafa la
    primera amb codi numèric > 1 (és a dir, el slot ocupat més alt que no
    sigui el codi "material no registrat" = 1).
    """
    for piece in sorted(pieces_in_position, key=lambda p: p["slot"], reverse=True):
        code = piece.get("material_code")
        if code is not None and code > CUSTOM_MATERIAL_SENTINEL:
            return piece
    return None


def matches_exact(value: str, query: str) -> bool:
    """Cercador M20: coincidència exacta normalitzada (per codi de material)."""
    return normalize_text(value) == normalize_text(query)


def matches_partial(value: str, query: str) -> bool:
    """Cercadors M22/M24: coincidència parcial normalitzada (subcadena)."""
    q = normalize_text(query)
    if q == "":
        return False
    return q in normalize_text(value)


def oldest_matching_position(matches: list[dict]) -> int | str | None:
    """Posició de prioritat (O20/O22/O24): la coincidència amb entered_at més antic.

    matches: llista de dicts amb 'position' i 'entered_at' (ISO str o None).
    Només es consideren peces amb data d'entrada (codi > 1, igual que l'original).
    """
    dated = [m for m in matches if m.get("entered_at")]
    if not dated:
        return None
    best = min(dated, key=lambda m: m["entered_at"])
    return best["position"]


# Escala de color per ocupació d'una posició (AplicarColorsPerCoincidencies /
# AplicarColorSegonsFilaIValorK12): el color de referència es prenia de les
# cel·les K12:K16 del mateix Excel. Valors extrets del fitxer original:
# 0-1 peça=blanc, 2=groc clar, 3=verd clar, 4=blau clar, 5+=vermell.
FILL_COLOR_SCALE = ["#FFFFFF", "#FFF2CC", "#C6E0B4", "#B4C6E7", "#FF0000"]


def fill_color_for_count(piece_count: int) -> str:
    """Color de "com d'ocupada" està una posició, igual que la referència K12:K16."""
    if piece_count <= 1:
        return FILL_COLOR_SCALE[0]
    if piece_count >= 5:
        return FILL_COLOR_SCALE[4]
    return FILL_COLOR_SCALE[piece_count - 1]


def has_material_inconsistency(material_codes: list) -> bool:
    """MarcarInconsistencies: una posició es marca en vermell si conté més
    d'un material diferent entre les seves peces (avís de possible error d'ubicació).
    """
    distinct = {c for c in material_codes if c not in (None, "")}
    return len(distinct) > 1


def quantity_change_kind(old_qty: int, new_qty: int) -> str | None:
    """ActualitzaHistorialQuantitat: determina si és un augment, disminució o esborrat."""
    if new_qty == 0 and old_qty > 0:
        return "delete"
    if new_qty > old_qty:
        return "increase"
    if new_qty < old_qty:
        return "decrease"
    return None


def find_covered_in_position(position, pieces: list[dict]) -> list[dict]:
    """Peces "tapades" d'UNA posició (ComprovarIMostrarTapats_Correcte).

    Fidel a l'original: la macro llegia la fulla "Entrades" (una còpia
    literal de "Llista", és a dir, l'estat ACTUAL de les peces — no
    l'històric) i, per a cada posició, agrupava les seves files (slots).
    Si hi havia més d'un material diferent entre les peces ocupades de la
    posició, es mostraven totes MENYS la de l'slot ocupat més alt (la
    "vigent"): les altres es consideren "tapades" per aquesta.

    `pieces`: les peces d'UNA posició tal com les retorna
    `Repository.get_position_detail` (amb "slot", "material_code", etc.).
    Retorna una llista de dicts {position, material_code, material_desc, dimensions}.
    """
    valid = [p for p in pieces if p.get("material_code") is not None]
    if not valid:
        return []
    distinct_codes = {p["material_code"] for p in valid}
    if len(distinct_codes) <= 1:
        return []
    last_valid = max(valid, key=lambda p: p["slot"])
    return [
        {
            "position": position,
            "material_code": p["material_code"],
            "material_desc": p["material_desc"],
            "dimensions": p["dimensions"],
        }
        for p in valid
        if p["slot"] != last_valid["slot"]
    ]
