"""Operaciones sobre la base de datos: la traducción del motor VBA a Python.

Cada método documenta de qué macro(s) de SobrantsV4.74.xlsm proviene.
Los errores de validación se señalizan con excepciones dedicadas para que la
capa de interfaz (GUI) decida cómo mostrarlas (equivalente a los MsgBox del
original).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from . import rules

BOARD_POSITIONS = range(1, 62)  # 61 posiciones, igual que Hoja1 (A2:A28, F2:F28, K2:K8)


class RuleViolation(Exception):
    """Error de validación de negocio (equivalente a un MsgBox de error/bloqueo)."""


class DuplicateMaterialError(Exception):
    """Material ya presente en otras posiciones; requiere confirmación del usuario."""

    def __init__(self, positions: list[int]):
        self.positions = positions
        super().__init__(f"Material duplicado en posiciones: {positions}")


class PositionFullError(RuleViolation):
    pass


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ------------------------------------------------------------------ #
    # Materiales (hoja "Materials")
    # ------------------------------------------------------------------ #
    def lookup_material(self, code: int) -> str:
        """Equivalente a =SI.ERROR(BUSCARV(...);"---------") de Hoja1!M12:M16."""
        row = self.conn.execute(
            "SELECT description FROM materials WHERE code = ?", (code,)
        ).fetchone()
        return row["description"] if row else rules.EMPTY_MATERIAL_MARK

    def search_materials(self, query: str, limit: int = 50) -> list[sqlite3.Row]:
        q = f"%{query.strip()}%"
        return self.conn.execute(
            "SELECT code, description FROM materials WHERE description LIKE ? "
            "OR CAST(code AS TEXT) LIKE ? ORDER BY code LIMIT ?",
            (q, q, limit),
        ).fetchall()

    # ------------------------------------------------------------------ #
    # Panel principal (hoja "Hoja1" + "llista")
    # ------------------------------------------------------------------ #
    def get_board(self) -> list[dict]:
        """Resumen por posición mostrado en el panel (ActualitzarUltimesCoincidencies)."""
        all_pieces = self._all_pieces_by_position()
        board = []
        for pos in BOARD_POSITIONS:
            pieces = all_pieces.get(pos, [])
            piece = rules.board_summary_piece(pieces)
            board.append(
                {
                    "position": pos,
                    "material_code": piece["material_code"] if piece else None,
                    "material_desc": piece["material_desc"] if piece else None,
                    "dimensions": piece["dimensions"] if piece else None,
                    "notes": piece["notes"] if piece else None,
                    "piece_count": len(pieces),
                    "fill_color": rules.fill_color_for_count(len(pieces)),
                    "inconsistent": rules.has_material_inconsistency([p["material_code"] for p in pieces]),
                }
            )
        return board

    def get_position_detail(self, position: int) -> list[dict]:
        """Contenido completo (hasta 5 piezas) de una posición (L12:O16 al seleccionarla)."""
        rows = self.conn.execute(
            "SELECT slot, material_code, material_desc, dimensions, notes, entered_at "
            "FROM pieces WHERE position = ? ORDER BY slot",
            (position,),
        ).fetchall()
        return [dict(r) for r in rows]

    def _all_pieces_by_position(self) -> dict[int, list[dict]]:
        rows = self.conn.execute(
            "SELECT position, slot, material_code, material_desc, dimensions, notes, entered_at FROM pieces"
        ).fetchall()
        out: dict[int, list[dict]] = {}
        for r in rows:
            out.setdefault(r["position"], []).append(dict(r))
        return out

    def _all_pieces_flat(self) -> list[tuple[int, int, int]]:
        rows = self.conn.execute("SELECT position, slot, material_code FROM pieces").fetchall()
        return [(r["position"], r["slot"], r["material_code"]) for r in rows]

    def check_duplicate(self, position: int, material_code: int) -> list[int]:
        """Devuelve las otras posiciones donde ya existe ese material (o lista vacía)."""
        return rules.find_duplicate_positions(self._all_pieces_flat(), material_code, position)

    def add_piece(
        self,
        position: int,
        material_code: int,
        dimensions: str = "",
        notes: str = "",
        confirm_duplicate: bool = False,
    ) -> dict:
        """Alta de una pieza en una posición (ComprovarCoincidenciesL12L16 + Worksheet_Change).

        Lanza:
          - RuleViolation si el código no es válido o la posición está llena / desordenada.
          - DuplicateMaterialError si el material ya existe en otra posición y
            confirm_duplicate=False (la GUI debe volver a llamar con True tras
            confirmarlo con el usuario, igual que el MsgBox OK/Cancel original).
        """
        if not rules.is_valid_material_code(material_code):
            raise RuleViolation("Entrada incorrecta. Sólo se admiten números entre 0 y 99999.")
        material_code = int(material_code)

        existing = self.get_position_detail(position)
        filled_slots = [p["slot"] for p in existing]
        try:
            slot = rules.next_free_slot(filled_slots)
        except ValueError as exc:
            raise RuleViolation(str(exc)) from exc
        if slot is None:
            raise PositionFullError("MOVIMENT IMPOSIBLE: POSICIÓ PLENA")

        if not confirm_duplicate:
            dups = self.check_duplicate(position, material_code)
            if dups:
                raise DuplicateMaterialError(dups)

        desc = self.lookup_material(material_code)
        entered_at = _now() if material_code > rules.CUSTOM_MATERIAL_SENTINEL else None

        self.conn.execute(
            """INSERT INTO pieces(position, slot, material_code, material_desc, dimensions, notes, entered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (position, slot, material_code, desc, dimensions or None, notes or None, entered_at),
        )
        self._log_historic(str(position), str(material_code), desc, 1, "in")
        self.conn.commit()
        return {"position": position, "slot": slot, "material_code": material_code, "material_desc": desc}

    def delete_piece(self, position: int, slot: int) -> None:
        """Baja de una pieza (confirmación 'Estàs segur que vols esborrar la posició?').

        Sólo permite borrar el último slot ocupado (de abajo a arriba), igual
        que el control 'ORDRE INCORRECTE' del original.
        """
        existing = self.get_position_detail(position)
        filled_slots = [p["slot"] for p in existing]
        if not rules.can_delete_slot(filled_slots, slot):
            raise RuleViolation("ORDRE INCORRECTE: sólo se puede borrar la última pieza de la posición.")

        piece = next(p for p in existing if p["slot"] == slot)
        self.conn.execute("DELETE FROM pieces WHERE position = ? AND slot = ?", (position, slot))
        self._log_historic(
            str(position), str(piece["material_code"]), piece["material_desc"], -1, "out"
        )
        self.conn.commit()

    def move_piece(self, from_position: int, to_position: int) -> dict:
        """Traslado de la pieza 'visible' de una posición a otra.

        Traduce MostrarPreview + CopiarPreviewAFilaDinamica: mueve la pieza que
        el panel muestra para from_position (el slot más alto con código > 1)
        al primer slot libre de to_position, y registra dos líneas de
        histórico (⇒⇒ origen / ⇐⇐ destino).
        """
        if from_position == to_position:
            raise RuleViolation("NO ES POT MOURE ELL MATEIX")

        pieces = self.get_position_detail(from_position)
        piece = rules.board_summary_piece(pieces)
        if piece is None:
            raise RuleViolation("No hay ninguna pieza que mover en esa posición.")

        dest_existing = self.get_position_detail(to_position)
        dest_filled = [p["slot"] for p in dest_existing]
        try:
            dest_slot = rules.next_free_slot(dest_filled)
        except ValueError as exc:
            raise RuleViolation(str(exc)) from exc
        if dest_slot is None:
            raise PositionFullError("MOVIMENT IMPOSIBLE: POSICIÓ PLENA")

        # Quita la pieza del origen y renumera los slots restantes para no dejar huecos
        self.conn.execute(
            "DELETE FROM pieces WHERE position = ? AND slot = ?", (from_position, piece["slot"])
        )
        remaining = [p for p in pieces if p["slot"] != piece["slot"]]
        for new_slot, p in enumerate(sorted(remaining, key=lambda x: x["slot"]), start=1):
            if new_slot != p["slot"]:
                self.conn.execute(
                    "UPDATE pieces SET slot = ? WHERE position = ? AND slot = ?",
                    (new_slot, from_position, p["slot"]),
                )

        self.conn.execute(
            """INSERT INTO pieces(position, slot, material_code, material_desc, dimensions, notes, entered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                to_position,
                dest_slot,
                piece["material_code"],
                piece["material_desc"],
                piece["dimensions"],
                piece["notes"],
                piece["entered_at"],
            ),
        )

        ts = _now()
        self.conn.execute(
            "INSERT INTO historic(position, material_code, material_desc, ts, direction, kind) VALUES (?,?,?,?,?,?)",
            (str(from_position), str(piece["material_code"]), piece["material_desc"], ts, None, "move_out"),
        )
        self.conn.execute(
            "INSERT INTO historic(position, material_code, material_desc, ts, direction, kind) VALUES (?,?,?,?,?,?)",
            (str(to_position), str(piece["material_code"]), piece["material_desc"], ts, None, "move_in"),
        )
        self.conn.commit()
        return {"from_position": from_position, "to_position": to_position, "piece": piece}

    # ------------------------------------------------------------------ #
    # Buscadores (M20 / M22 / M24 en Hoja1)
    # ------------------------------------------------------------------ #
    def search(self, query: str, mode: str) -> dict:
        """mode: 'code' (M20, exacto por nº material), 'description' (M22, parcial),
        'notes' (M24, parcial)."""
        if mode not in ("code", "description", "notes"):
            raise ValueError("mode debe ser 'code', 'description' o 'notes'")
        if not str(query).strip():
            return {"matches": [], "count": 0, "oldest_position": None, "desmagatzem_qty": 0}

        field_by_mode = {
            "code": "material_code",
            "description": "material_desc",
            "notes": "notes",
        }[mode]
        rows = self.conn.execute(f"SELECT * FROM pieces").fetchall()  # noqa: S608 (columna fija, no input)
        matches = []
        for r in rows:
            value = r[field_by_mode]
            if value is None:
                continue
            hit = (
                rules.matches_exact(str(value), query)
                if mode == "code"
                else rules.matches_partial(str(value), query)
            )
            if hit:
                matches.append(dict(r))

        oldest = rules.oldest_matching_position(matches)
        desmagatzem_qty = self._search_desmagatzem_quantity(query, mode)
        return {
            "matches": matches,
            "count": len(matches),
            "oldest_position": oldest,
            "desmagatzem_qty": desmagatzem_qty,
        }

    # Columna de "desmagatzem" que corresponde a cada modo de búsqueda del
    # Tablero (BuscaCoincidenciesDesmagatzem_Q20/M22/M24): código exacto,
    # descripción parcial, o el campo de carro/lote (equivalente a "notas").
    _DESMAGATZEM_FIELD = {"code": "material_code", "description": "material_desc", "notes": "cart_ref"}

    def _search_desmagatzem_quantity(self, query: str, mode: str) -> int:
        """Suma de unidades que hay en Desmagatzem para la misma búsqueda del
        Tablero (los buscadores M20/M22/M24 del original también recorrían la
        hoja desmagatzem y mostraban el total en Q20/Q22/Q24)."""
        field = self._DESMAGATZEM_FIELD[mode]
        rows = self.conn.execute(f"SELECT quantity, {field} AS value FROM desmagatzem").fetchall()  # noqa: S608
        total = 0
        for r in rows:
            value = r["value"]
            if value is None:
                continue
            hit = rules.matches_exact(str(value), query) if mode == "code" else rules.matches_partial(str(value), query)
            if hit:
                total += r["quantity"] or 0
        return total

    # ------------------------------------------------------------------ #
    # Histórico (hoja "històric")
    # ------------------------------------------------------------------ #
    def _log_historic(self, position: str, material_code, material_desc, direction: int, kind: str):
        self.conn.execute(
            "INSERT INTO historic(position, material_code, material_desc, ts, direction, kind) VALUES (?,?,?,?,?,?)",
            (position, str(material_code) if material_code is not None else None, material_desc, _now(), direction, kind),
        )

    # order_by="date" = más recientes primero (por defecto). order_by="position"
    # = orden por posición ascendente, equivalente al toggle AlternarOrdre del
    # original (que alternaba entre ordenar la hoja històric por columna A o D).
    def get_historic(self, limit: int = 500, position: str | None = None, order_by: str = "date") -> list[dict]:
        if order_by == "date":
            order_sql = "ts DESC, id DESC"
        else:
            # "position" puede ser un nº (texto) o "Desmagatzem"; se ordena
            # numéricamente cuando es posible y el resto al final, como hacía
            # el ordenado ascendente por columna A en el Excel original.
            order_sql = (
                "CASE WHEN position GLOB '[0-9]*' THEN CAST(position AS INTEGER) ELSE 999999 END, "
                "position, ts DESC, id DESC"
            )
        if position:
            rows = self.conn.execute(
                f"SELECT * FROM historic WHERE position = ? ORDER BY {order_sql} LIMIT ?",  # noqa: S608
                (position, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                f"SELECT * FROM historic ORDER BY {order_sql} LIMIT ?", (limit,)  # noqa: S608
            ).fetchall()
        return [dict(r) for r in rows]

    def covered_materials_report(self) -> list[dict]:
        """Informe 'Materials tapats' (ComprovarIMostrarTapats_Correcte), a partir
        del histórico de entradas ('in') ordenado cronológicamente por posición."""
        rows = self.conn.execute(
            "SELECT position, material_code, material_desc, ts FROM historic "
            "WHERE kind = 'in' ORDER BY position, ts"
        ).fetchall()
        by_position: dict[str, list[dict]] = {}
        for r in rows:
            by_position.setdefault(r["position"], []).append(
                {"material_code": r["material_code"], "material_desc": r["material_desc"], "dimensions": None}
            )
        return rules.find_covered_materials(by_position)

    # ------------------------------------------------------------------ #
    # Desmagatzem
    # ------------------------------------------------------------------ #
    def list_desmagatzem(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM desmagatzem ORDER BY row_order").fetchall()
        return [dict(r) for r in rows]

    def add_desmagatzem_row(
        self, material_code: str, quantity: int, dimensions: str, cart_ref: str, custom_text: str | None = None
    ) -> dict:
        """Nueva línea de retirada (CercaMaterialIMarcaHist + Worksheet_Change desmagatzem)."""
        if not rules.is_valid_desmagatzem_qty(quantity):
            raise RuleViolation("Sólo se admiten cantidades entre 0 y 20.")

        code_str = str(material_code)
        if code_str == str(rules.CUSTOM_MATERIAL_SENTINEL):
            if not custom_text:
                raise RuleViolation("Escribe un material no registrado.")
            desc = custom_text
        else:
            desc = self.lookup_material(int(material_code))

        next_order = (
            self.conn.execute("SELECT COALESCE(MAX(row_order), 0) + 1 FROM desmagatzem").fetchone()[0]
        )
        self.conn.execute(
            """INSERT INTO desmagatzem(row_order, quantity, material_code, material_desc, custom_text, dimensions, cart_ref, ts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (next_order, quantity, code_str, desc, custom_text, dimensions or None, cart_ref or None, _now()),
        )
        for _ in range(quantity):
            self._log_historic("Desmagatzem", code_str, desc, 1, "in")
        self.conn.commit()
        return {"row_order": next_order, "material_desc": desc}

    def update_desmagatzem_quantity(self, row_id: int, new_qty: int) -> str:
        """Cambia la cantidad de una línea (ActualitzaHistorialQuantitat).

        Devuelve 'increase', 'decrease', 'delete' o 'noop' para que la GUI
        pida confirmación con el texto adecuado antes de llamar de nuevo
        (equivalente al MsgBox Sí/No del original).
        """
        if not rules.is_valid_desmagatzem_qty(new_qty):
            raise RuleViolation("Sólo se admiten cantidades entre 0 y 20.")
        row = self.conn.execute("SELECT * FROM desmagatzem WHERE id = ?", (row_id,)).fetchone()
        if row is None:
            raise RuleViolation("Línea de desmagatzem no encontrada.")

        change = rules.quantity_change_kind(row["quantity"], new_qty)
        if change is None:
            return "noop"

        if change == "delete":
            for _ in range(row["quantity"]):
                self._log_historic("Desmagatzem", row["material_code"], row["material_desc"], -1, "out")
            self.conn.execute("DELETE FROM desmagatzem WHERE id = ?", (row_id,))
            self._compact_desmagatzem()
        else:
            diff = abs(new_qty - row["quantity"])
            direction = 1 if change == "increase" else -1
            kind = "in" if change == "increase" else "out"
            for _ in range(diff):
                self._log_historic("Desmagatzem", row["material_code"], row["material_desc"], direction, kind)
            self.conn.execute("UPDATE desmagatzem SET quantity = ? WHERE id = ?", (new_qty, row_id))

        self.conn.commit()
        return change

    def _compact_desmagatzem(self):
        """Apilar: renumera row_order para no dejar huecos tras un borrado."""
        rows = self.conn.execute("SELECT id FROM desmagatzem ORDER BY row_order").fetchall()
        for order, r in enumerate(rows, start=1):
            self.conn.execute("UPDATE desmagatzem SET row_order = ? WHERE id = ?", (order, r["id"]))
