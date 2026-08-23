"""Operacions sobre la base de dades: la traducció del motor VBA a Python.

Cada mètode documenta de quina(es) macro(s) de SobrantsV4.74.xlsm prové.
Els errors de validació es senyalitzen amb excepcions dedicades perquè la
capa d'interfície (GUI) decideixi com mostrar-les (equivalent als MsgBox
de l'original).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from . import rules
from app.i18n import t

BOARD_POSITIONS = range(1, 62)  # 61 posicions, igual que Hoja1 (A2:A28, F2:F28, K2:K8)


class RuleViolation(Exception):
    """Error de validació de negoci (equivalent a un MsgBox d'error/bloqueig)."""


class DuplicateMaterialError(Exception):
    """Material ja present en altres posicions; requereix confirmació de l'usuari."""

    def __init__(self, positions: list[int]):
        self.positions = positions
        super().__init__(t("err.duplicate_material", positions=positions))


class PositionFullError(RuleViolation):
    pass


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ------------------------------------------------------------------ #
    # Materials (fulla "Materials")
    # ------------------------------------------------------------------ #
    def lookup_material(self, code: int) -> str:
        """Equivalent a =SI.ERROR(BUSCARV(...);"---------") de Hoja1!M12:M16."""
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

    def add_material(self, code: int, description: str, overwrite: bool = False) -> None:
        """Alta (o actualització) d'un material al catàleg.

        No existia al VBA original (el catàleg Materials s'editava
        directament a la fulla, sense cap validació); és una funcionalitat
        nova, protegida per contrasenya des de la UI (veure app/security.py).
        Si el codi ja existeix i overwrite=False, llança RuleViolation amb
        la descripció actual perquè la UI pugui oferir sobreescriure-la.
        """
        existing = self.conn.execute(
            "SELECT description FROM materials WHERE code = ?", (code,)
        ).fetchone()
        if existing is not None and not overwrite:
            raise RuleViolation(t("err.material_exists", code=code, description=existing["description"]))
        self.conn.execute(
            "INSERT INTO materials(code, description) VALUES (?, ?) "
            "ON CONFLICT(code) DO UPDATE SET description = excluded.description",
            (code, description),
        )
        self.conn.commit()

    # ------------------------------------------------------------------ #
    # Panell principal (fulla "Hoja1" + "llista")
    # ------------------------------------------------------------------ #
    def get_board(self) -> list[dict]:
        """Resum per posició mostrat al panell (ActualitzarUltimesCoincidencies)."""
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
        """Contingut complet (fins a 5 peces) d'una posició (L12:O16 en seleccionar-la)."""
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
        """Retorna les altres posicions on ja existeix aquest material (o llista buida)."""
        return rules.find_duplicate_positions(self._all_pieces_flat(), material_code, position)

    def add_piece(
        self,
        position: int,
        material_code: int,
        dimensions: str = "",
        notes: str = "",
        confirm_duplicate: bool = False,
    ) -> dict:
        """Alta d'una peça en una posició (ComprovarCoincidenciesL12L16 + Worksheet_Change).

        Llança:
          - RuleViolation si el codi no és vàlid o la posició està plena / desordenada.
          - DuplicateMaterialError si el material ja existeix en una altra posició i
            confirm_duplicate=False (la GUI ha de tornar a cridar amb True després
            de confirmar-ho amb l'usuari, igual que el MsgBox OK/Cancel original).
        """
        if not rules.is_valid_material_code(material_code):
            raise RuleViolation(t("err.invalid_material_code"))
        material_code = int(material_code)

        existing = self.get_position_detail(position)
        filled_slots = [p["slot"] for p in existing]
        try:
            slot = rules.next_free_slot(filled_slots)
        except ValueError as exc:
            raise RuleViolation(str(exc)) from exc
        if slot is None:
            raise PositionFullError(t("err.position_full"))

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
        """Baixa d'una peça (confirmació 'Estàs segur que vols esborrar la posició?').

        Només permet esborrar l'últim slot ocupat (de baix a dalt), igual
        que el control 'ORDRE INCORRECTE' de l'original.
        """
        existing = self.get_position_detail(position)
        filled_slots = [p["slot"] for p in existing]
        if not rules.can_delete_slot(filled_slots, slot):
            raise RuleViolation(t("err.wrong_delete_order"))

        piece = next(p for p in existing if p["slot"] == slot)
        self.conn.execute("DELETE FROM pieces WHERE position = ? AND slot = ?", (position, slot))
        self._log_historic(
            str(position), str(piece["material_code"]), piece["material_desc"], -1, "out"
        )
        self.conn.commit()

    def move_piece(self, from_position: int, to_position: int) -> dict:
        """Trasllat de la peça 'visible' d'una posició a una altra.

        Tradueix MostrarPreview + CopiarPreviewAFilaDinamica: mou la peça que
        el panell mostra per a from_position (el slot més alt amb codi > 1)
        al primer slot lliure de to_position, i registra dues línies
        d'històric (⇒⇒ origen / ⇐⇐ destí).
        """
        if from_position == to_position:
            raise RuleViolation(t("err.cannot_move_to_self"))

        pieces = self.get_position_detail(from_position)
        piece = rules.board_summary_piece(pieces)
        if piece is None:
            raise RuleViolation(t("err.no_piece_to_move"))

        dest_existing = self.get_position_detail(to_position)
        dest_filled = [p["slot"] for p in dest_existing]
        try:
            dest_slot = rules.next_free_slot(dest_filled)
        except ValueError as exc:
            raise RuleViolation(str(exc)) from exc
        if dest_slot is None:
            raise PositionFullError(t("err.position_full"))

        # Treu la peça de l'origen i renumera els slots restants per no deixar forats
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
    # Cercadors (M20 / M22 / M24 a Hoja1)
    # ------------------------------------------------------------------ #
    def search(self, query: str, mode: str) -> dict:
        """mode: 'code' (M20, exacte per núm. material), 'description' (M22, parcial),
        'notes' (M24, parcial)."""
        if mode not in ("code", "description", "notes"):
            raise ValueError("mode ha de ser 'code', 'description' o 'notes'")
        if not str(query).strip():
            return {"matches": [], "count": 0, "oldest_position": None, "desmagatzem_qty": 0}

        field_by_mode = {
            "code": "material_code",
            "description": "material_desc",
            "notes": "notes",
        }[mode]
        rows = self.conn.execute(f"SELECT * FROM pieces").fetchall()  # noqa: S608 (columna fixa, no input)
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

    # Columna de "desmagatzem" que correspon a cada mode de cerca del
    # Tauler (BuscaCoincidenciesDesmagatzem_Q20/M22/M24): codi exacte,
    # descripció parcial, o el camp de carro/lot (equivalent a "notes").
    _DESMAGATZEM_FIELD = {"code": "material_code", "description": "material_desc", "notes": "cart_ref"}

    def _search_desmagatzem_quantity(self, query: str, mode: str) -> int:
        """Suma d'unitats que hi ha a Desmagatzem per a la mateixa cerca del
        Tauler (els cercadors M20/M22/M24 de l'original també recorrien la
        fulla desmagatzem i mostraven el total a Q20/Q22/Q24)."""
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
    # Històric (fulla "històric")
    # ------------------------------------------------------------------ #
    def _log_historic(self, position: str, material_code, material_desc, direction: int, kind: str):
        self.conn.execute(
            "INSERT INTO historic(position, material_code, material_desc, ts, direction, kind) VALUES (?,?,?,?,?,?)",
            (position, str(material_code) if material_code is not None else None, material_desc, _now(), direction, kind),
        )

    # order_by="date" = més recents primer (per defecte). order_by="position"
    # = ordre per posició ascendent, equivalent al toggle AlternarOrdre de
    # l'original (que alternava entre ordenar la fulla històric per columna A o D).
    def get_historic(self, limit: int = 500, position: str | None = None, order_by: str = "date") -> list[dict]:
        if order_by == "date":
            order_sql = "ts DESC, id DESC"
        else:
            # "position" pot ser un núm. (text) o "Desmagatzem"; s'ordena
            # numèricament quan és possible i la resta al final, com feia
            # l'ordenat ascendent per columna A a l'Excel original.
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
        de l'històric d'entrades ('in') ordenat cronològicament per posició."""
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
        """Nova línia de retirada (CercaMaterialIMarcaHist + Worksheet_Change desmagatzem)."""
        if not rules.is_valid_desmagatzem_qty(quantity):
            raise RuleViolation(t("err.invalid_quantity"))

        code_str = str(material_code)
        if code_str == str(rules.CUSTOM_MATERIAL_SENTINEL):
            if not custom_text:
                raise RuleViolation(t("err.unregistered_material_text"))
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
        """Canvia la quantitat d'una línia (ActualitzaHistorialQuantitat).

        Retorna 'increase', 'decrease', 'delete' o 'noop' perquè la GUI
        demani confirmació amb el text adequat abans de tornar a cridar
        (equivalent al MsgBox Sí/No de l'original).
        """
        if not rules.is_valid_desmagatzem_qty(new_qty):
            raise RuleViolation(t("err.invalid_quantity"))
        row = self.conn.execute("SELECT * FROM desmagatzem WHERE id = ?", (row_id,)).fetchone()
        if row is None:
            raise RuleViolation(t("err.desmagatzem_row_not_found"))

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
        """Apilar: renumera row_order per no deixar forats després d'un esborrat."""
        rows = self.conn.execute("SELECT id FROM desmagatzem ORDER BY row_order").fetchall()
        for order, r in enumerate(rows, start=1):
            self.conn.execute("UPDATE desmagatzem SET row_order = ? WHERE id = ?", (order, r["id"]))
