"""Operacions sobre la base de dades: la traducció del motor VBA a Python.

Cada mètode documenta de quina(es) macro(s) de SobrantsV4.74.xlsm prové.
Els errors de validació es senyalitzen amb excepcions dedicades perquè la
capa d'interfície (GUI) decideixi com mostrar-les (equivalent als MsgBox
de l'original).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime

from . import rules
from app.i18n import t

BOARD_POSITIONS = range(1, 62)  # 61 posicions, igual que Hoja1 (A2:A28, F2:F28, K2:K8)

# Què s'escriu a la columna "posició" de l'històric per als moviments que no
# són de cap posició del tauler, sinó de Desmagatzem.
DESMAGATZEM_POSITION = "Desmagatzem"


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

    @contextmanager
    def _transaction(self):
        """Cada operació que toca dades va dins d'UNA transacció: o s'hi
        desa tot, o no s'hi desa res.

        En sortir bé fa `commit()`, i amb `synchronous = FULL` (veure
        `app.data.db.connect`) això vol dir que la dada ja és al disc: si
        al segon següent marxa la llum, el canvi hi continua sent. Si
        salta qualsevol excepció pel camí es fa `rollback()`, de manera
        que una operació a mitges (p. ex. la peça desada però l'històric
        no) no hi pot quedar ni pot acabar entrant "de rebot" amb el
        commit de l'operació següent.
        """
        try:
            yield self.conn
        except Exception:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()

    # ------------------------------------------------------------------ #
    # Materials (fulla "Materials")
    # ------------------------------------------------------------------ #
    def lookup_material(self, code: int) -> str:
        """Equivalent a =SI.ERROR(BUSCARV(...);"---------") de Hoja1!M12:M16."""
        row = self.conn.execute(
            "SELECT description FROM materials WHERE code = ?", (code,)
        ).fetchone()
        return row["description"] if row else rules.EMPTY_MATERIAL_MARK

    def search_materials(self, query: str, limit: int | None = None) -> list[sqlite3.Row]:
        """limit=None (per defecte) retorna TOT el catàleg que coincideixi;
        el catàleg és petit (uns 4.000 materials) i cal que es puguin veure
        tots a la pestanya Materials, no només els primers N."""
        q = f"%{query.strip()}%"
        sql = (
            "SELECT code, description FROM materials WHERE description LIKE ? "
            "OR CAST(code AS TEXT) LIKE ? ORDER BY code"
        )
        params: tuple = (q, q)
        if limit is not None:
            sql += " LIMIT ?"
            params = (q, q, limit)
        return self.conn.execute(sql, params).fetchall()

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
        with self._transaction():
            self.conn.execute(
                "INSERT INTO materials(code, description) VALUES (?, ?) "
                "ON CONFLICT(code) DO UPDATE SET description = excluded.description",
                (code, description),
            )

    def delete_material(self, code: int) -> str:
        """Baixa d'un material del catàleg (mateixa protecció per contrasenya
        que `add_material`, des de la UI). No hi ha cap referència de clau
        forana des de pieces/desmagatzem/historic (guarden la descripció en
        caché), així que esborrar-lo no trenca cap registre existent.
        Retorna la descripció esborrada, perquè la UI la pugui mostrar."""
        existing = self.conn.execute(
            "SELECT description FROM materials WHERE code = ?", (code,)
        ).fetchone()
        if existing is None:
            raise RuleViolation(t("err.material_not_found", code=code))
        with self._transaction():
            self.conn.execute("DELETE FROM materials WHERE code = ?", (code,))
        return existing["description"]

    # ------------------------------------------------------------------ #
    # Panell principal (fulla "Hoja1" + "llista")
    # ------------------------------------------------------------------ #
    def count_pieces(self) -> int:
        """Quantes peces hi ha al Tauler en total, sumant les de totes les
        posicions (cada fila de `pieces` és una peça).

        Es compta a la base de dades, no a la pantalla: no depèn de què hi
        hagi pintat, ni de l'scroll, ni de cap filtre.
        """
        return self.conn.execute("SELECT COUNT(*) FROM pieces").fetchone()[0]

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
                    "occupancy": rules.occupancy_level(len(pieces)),
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

        with self._transaction():
            self.conn.execute(
                """INSERT INTO pieces(position, slot, material_code, material_desc, dimensions, notes, entered_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (position, slot, material_code, desc, dimensions or None, notes or None, entered_at),
            )
            self._log_historic(
                str(position), str(material_code), desc, 1, "in",
                dimensions=dimensions, notes=notes,
            )
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
        with self._transaction():
            self.conn.execute("DELETE FROM pieces WHERE position = ? AND slot = ?", (position, slot))
            self._log_historic(
                str(position), str(piece["material_code"]), piece["material_desc"], -1, "out",
                dimensions=piece["dimensions"], notes=piece["notes"],
            )

    def update_piece_field(self, position: int, slot: int, field: str, value: str) -> None:
        """Edició en línia de Mides/Notes des del panell de detall de
        posició. Núm./Material no es poden editar mai des d'aquí (només
        des del formulari d'alta): per això només s'accepten aquests dos
        camps, mai el codi o la descripció del material."""
        if field not in ("dimensions", "notes"):
            raise ValueError(f"Camp no editable: {field}")
        with self._transaction():
            self.conn.execute(
                f"UPDATE pieces SET {field} = ? WHERE position = ? AND slot = ?",  # noqa: S608
                (value or None, position, slot),
            )

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

        # Tot el trasllat (treure d'origen, renumerar, posar a destí i
        # les dues línies d'històric) és una sola transacció: no hi pot
        # quedar mai una peça treta d'un lloc i no posada a l'altre.
        with self._transaction():
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

            # La data/hora de l'històric d'un trasllat és la de l'entrada
            # original de la peça (piece["entered_at"]), no la del moment del
            # trasllat: moure-la no n'ha de canviar la data d'entrada. Els
            # materials no registrats (codi <= 1) no en guarden ("---------"),
            # així que per a aquests es fa servir l'hora actual com a únic
            # valor disponible.
            ts = piece["entered_at"] or _now()
            for position_text, kind in ((str(from_position), "move_out"), (str(to_position), "move_in")):
                self._log_historic(
                    position_text, str(piece["material_code"]), piece["material_desc"], None, kind,
                    dimensions=piece["dimensions"], notes=piece["notes"], ts=ts,
                )
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
    def _log_historic(
        self,
        position: str,
        material_code,
        material_desc,
        direction: int,
        kind: str,
        dimensions: str | None = None,
        notes: str | None = None,
        ts: str | None = None,
    ):
        """Una línia d'històric. Hi van també les mides i les notes que
        tenia la peça en aquell moment: així una línia sola ja descriu la
        peça sencera, que és el que necessita `clear_historic` per deixar
        l'històric amb l'estat actual sense inventar-se res.

        `ts` és per a les línies que han de conservar una data que no és la
        d'ara (el trasllat manté la data d'entrada de la peça); si no es
        diu res, s'hi posa el moment actual.
        """
        self.conn.execute(
            "INSERT INTO historic(position, material_code, material_desc, ts, direction, kind, dimensions, notes) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                position,
                str(material_code) if material_code is not None else None,
                material_desc,
                ts or _now(),
                direction,
                kind,
                dimensions or None,
                notes or None,
            ),
        )

    # order_by="date" = més recents primer (per defecte). order_by="position"
    # = ordre per posició ascendent, equivalent al toggle AlternarOrdre de
    # l'original (que alternava entre ordenar la fulla històric per columna A o D).
    def get_historic(
        self, limit: int | None = None, position: str | None = None, order_by: str = "date"
    ) -> list[dict]:
        """limit=None (per defecte) retorna TOT l'històric, sense tallar-lo a
        les primeres N files: cal poder veure'l sencer, per gran que sigui."""
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
            sql = f"SELECT * FROM historic WHERE position = ? ORDER BY {order_sql}"  # noqa: S608
            params: tuple = (position,)
        else:
            sql = f"SELECT * FROM historic ORDER BY {order_sql}"  # noqa: S608
            params = ()
        if limit is not None:
            sql += " LIMIT ?"
            params += (limit,)
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def movement_stats(self, start_date: str, end_date: str) -> dict:
        """Què ha passat cada dia, entre `start_date` i `end_date` (dates
        ISO "AAAA-MM-DD", tots dos dies inclosos).

        Per a cada dia amb moviment es dona, del TAULER: entrades, sortides,
        trasllats i quantes peces hi havia al final del dia; i de
        DESMAGATZEM: entrades, sortides i quantes unitats hi havia al final
        del dia. A més, la mitjana de sortides del Tauler per dia de
        l'interval.

        Com se sap quantes peces hi havia un dia que ja ha passat: no es
        guarda enlloc, es dedueix. Se sap quantes n'hi ha ARA
        (`count_pieces`), i l'històric diu què ha entrat i sortit cada dia;
        anant enrere des d'avui i desfent els moviments de cada dia
        s'arriba a quantes n'hi havia al final de qualsevol dia anterior.
        Els trasllats no compten: mouen una peça de lloc, no en treuen ni
        n'afegeixen (per això la línia d'origen i la de destí es
        contraresten i aquí només es compta la de destí, com a "trasllat").

        Només llegeix: l'històric no es toca.
        """
        daily = self._daily_movements(start_date)
        board, desmagatzem = self.count_pieces(), self.count_desmagatzem_pieces()
        # De més nou a més vell: el dia més nou acaba amb el que hi ha ara,
        # i cada pas enrere desfà els moviments d'aquell dia.
        for day in sorted(daily, reverse=True):
            entry = daily[day]
            entry["board_pieces"] = board
            entry["desmagatzem_pieces"] = desmagatzem
            board -= entry["board_in"] - entry["board_out"]
            desmagatzem -= entry["desmagatzem_in"] - entry["desmagatzem_out"]

        days = [daily[day] for day in sorted(daily) if start_date <= day <= end_date]
        return {"days": days, "board_out_per_day": self._per_day(days, "board_out", start_date, end_date)}

    def _daily_movements(self, since: str) -> dict:
        """Els moviments de cada dia, de `since` en endavant, comptats per
        tipus. Es demanen des de `since` i no només de l'interval perquè
        per saber quantes peces hi havia un dia s'han de desfer TOTS els
        moviments posteriors, també els de després de l'interval."""
        rows = self.conn.execute(
            "SELECT substr(ts, 1, 10) AS day, "
            " SUM(CASE WHEN kind = 'in'  AND position <> ? THEN 1 ELSE 0 END) AS board_in, "
            " SUM(CASE WHEN kind = 'out' AND position <> ? THEN 1 ELSE 0 END) AS board_out, "
            " SUM(CASE WHEN kind = 'move_in' THEN 1 ELSE 0 END) AS moves, "
            " SUM(CASE WHEN kind = 'in'  AND position = ? THEN 1 ELSE 0 END) AS desmagatzem_in, "
            " SUM(CASE WHEN kind = 'out' AND position = ? THEN 1 ELSE 0 END) AS desmagatzem_out "
            "FROM historic WHERE substr(ts, 1, 10) >= ? GROUP BY day",
            (DESMAGATZEM_POSITION, DESMAGATZEM_POSITION, DESMAGATZEM_POSITION,
             DESMAGATZEM_POSITION, since),
        ).fetchall()
        return {
            row["day"]: {
                "day": row["day"],
                "board_in": row["board_in"],
                "board_out": row["board_out"],
                "moves": row["moves"],
                "desmagatzem_in": row["desmagatzem_in"],
                "desmagatzem_out": row["desmagatzem_out"],
            }
            for row in rows
        }

    @staticmethod
    def _per_day(days: list, field: str, start_date: str, end_date: str) -> float:
        """Mitjana diària d'un dels comptadors dins de l'interval TRIAT.

        Es divideix pels dies de l'interval, no pels dies que han tingut
        moviment: si en 10 dies hi ha hagut 20 sortides, la mitjana és 2 al
        dia encara que 6 d'aquells dies fossin festius i no se'n mogués cap.
        """
        total = sum(day[field] for day in days)
        try:
            span = (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1
        except ValueError:
            span = 0
        return total / span if span > 0 else 0.0

    def current_state_entries(self) -> list[dict]:
        """L'estat d'ARA mateix, escrit com a línies d'històric: una per
        cada peça que hi ha al Tauler i una per cada unitat que hi ha a
        Desmagatzem.

        De cada peça del Tauler se'n guarda tot el que la descriu —material,
        posició, mides, notes i la seva data d'entrada—, que és exactament
        el que caldria per tornar-la a col·locar. De Desmagatzem, una línia
        per unitat (una línia de 5 unitats són 5 peces, igual que compta
        l'històric quan s'hi registren), amb les seves mides, el carro/lot i
        la data de la línia.

        Les dates són les de debò de cada peça, no la d'ara: netejar
        l'històric no ha de canviar quan va entrar res. Si alguna peça no en
        té (els materials no registrats no en guarden), s'hi posa el moment
        actual, que és l'únic valor disponible.
        """
        now = _now()
        entries = []
        board = self.conn.execute(
            "SELECT position, material_code, material_desc, dimensions, notes, entered_at "
            "FROM pieces ORDER BY position, slot"
        ).fetchall()
        for piece in board:
            entries.append(
                {
                    "position": str(piece["position"]),
                    "material_code": str(piece["material_code"]),
                    "material_desc": piece["material_desc"],
                    "dimensions": piece["dimensions"],
                    "notes": piece["notes"],
                    "ts": piece["entered_at"] or now,
                }
            )
        for row in self.list_desmagatzem():
            for _ in range(row["quantity"] or 0):
                entries.append(
                    {
                        "position": DESMAGATZEM_POSITION,
                        "material_code": row["material_code"],
                        "material_desc": row["material_desc"],
                        "dimensions": row["dimensions"],
                        "notes": row["cart_ref"],
                        "ts": row["ts"] or now,
                    }
                )
        return entries

    def clear_historic(self) -> dict:
        """Neteja l'històric i el deixa amb una foto de l'estat actual.

        Abans es conservava una sola línia per material del Tauler (l'última
        que hi hagués), i amb això l'històric deixava de descriure el que hi
        ha: d'una posició amb tres peces del mateix material en quedava una,
        i de Desmagatzem no en quedava res.

        Ara s'esborra tot i s'hi escriu de nou l'estat d'ara mateix
        (`current_state_entries`): una línia d'entrada per cada peça del
        Tauler —amb la seva posició, mides, notes i data— i una per cada
        unitat de Desmagatzem. Així, després de netejar, l'històric segueix
        explicant senceres totes les peces que hi ha.

        Tot dins d'una sola transacció: si peta pel camí no queda l'històric
        mig esborrat, es desfà sencer.
        """
        entries = self.current_state_entries()
        with self._transaction():
            deleted = self.conn.execute("DELETE FROM historic").rowcount
            for entry in entries:
                self._log_historic(
                    entry["position"],
                    entry["material_code"],
                    entry["material_desc"],
                    1,
                    "in",
                    dimensions=entry["dimensions"],
                    notes=entry["notes"],
                    ts=entry["ts"],
                )
        return {"deleted": deleted, "kept": len(entries)}

    def covered_materials_report(self) -> list[dict]:
        """Informe 'Materials tapats' (ComprovarIMostrarTapats_Correcte).

        Fidel a l'original: la macro llegia "Entrades", una còpia literal
        de "Llista" (l'estat ACTUAL de les peces, com la nostra taula
        `pieces`) — no l'històric. Per això es recorren les peces
        VIGENTS de cada posició, no els esdeveniments passats: un
        material que ja s'ha tret o mogut deixa de comptar, i un que hi
        ha arribat movent-lo (no només afegint-lo de nou) sí que hi
        compta.
        """
        covered = []
        for position in BOARD_POSITIONS:
            pieces = self.get_position_detail(position)
            covered.extend(rules.find_covered_in_position(position, pieces))
        return covered

    # ------------------------------------------------------------------ #
    # Desmagatzem
    # ------------------------------------------------------------------ #
    def list_desmagatzem(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM desmagatzem ORDER BY row_order").fetchall()
        return [dict(r) for r in rows]

    def count_desmagatzem_pieces(self) -> int:
        """Quantes peces hi ha ara mateix a Desmagatzem: la SUMA de les
        quantitats de totes les línies, no el nombre de línies (una línia
        de 5 unitats són 5 peces, igual que compta l'històric, que hi
        deixa una entrada per unitat).

        Mateix criteri que `count_pieces` per al Tauler: es compta a la
        base de dades, no al que hi hagi pintat a la pantalla, així que no
        depèn de l'ordre, de l'scroll ni de cap cerca activa.
        """
        return self.conn.execute("SELECT COALESCE(SUM(quantity), 0) FROM desmagatzem").fetchone()[0]

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
        with self._transaction():
            self.conn.execute(
                """INSERT INTO desmagatzem(row_order, quantity, material_code, material_desc, custom_text, dimensions, cart_ref, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                    next_order, quantity, code_str, desc, custom_text,
                    dimensions or None, rules.truncate_desmagatzem_notes(cart_ref), _now(),
                ),
            )
            for _ in range(quantity):
                self._log_historic(
                    DESMAGATZEM_POSITION, code_str, desc, 1, "in",
                    dimensions=dimensions, notes=cart_ref,
                )
        return {"row_order": next_order, "material_desc": desc}

    def update_desmagatzem_field(self, row_id: int, field: str, value: str) -> None:
        """Edició en línia de Mides/Notes d'una línia de desmagatzem, des de
        la mateixa taula.

        Mateix criteri que `update_piece_field` per al Tauler: només
        s'accepten aquests dos camps, mai la quantitat, el núm. de material
        ni la data, que tenen les seves pròpies regles.
        """
        if field not in ("dimensions", "cart_ref"):
            raise ValueError(f"Camp no editable: {field}")
        row = self.conn.execute("SELECT id FROM desmagatzem WHERE id = ?", (row_id,)).fetchone()
        if row is None:
            raise RuleViolation(t("err.desmagatzem_row_not_found"))
        if field == "cart_ref":
            value = rules.truncate_desmagatzem_notes(value)   # mateix límit que el formulari
        with self._transaction():
            self.conn.execute(
                f"UPDATE desmagatzem SET {field} = ? WHERE id = ?",  # noqa: S608
                (value or None, row_id),
            )

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

        # El canvi de quantitat i les línies d'històric que genera van
        # junts: o s'hi desa tot, o no s'hi desa res.
        with self._transaction():
            if change == "delete":
                for _ in range(row["quantity"]):
                    self._log_historic(
                        DESMAGATZEM_POSITION, row["material_code"], row["material_desc"], -1, "out",
                        dimensions=row["dimensions"], notes=row["cart_ref"],
                    )
                self.conn.execute("DELETE FROM desmagatzem WHERE id = ?", (row_id,))
                self._compact_desmagatzem()
            else:
                diff = abs(new_qty - row["quantity"])
                direction = 1 if change == "increase" else -1
                kind = "in" if change == "increase" else "out"
                for _ in range(diff):
                    self._log_historic(
                        DESMAGATZEM_POSITION, row["material_code"], row["material_desc"], direction, kind,
                        dimensions=row["dimensions"], notes=row["cart_ref"],
                    )
                self.conn.execute("UPDATE desmagatzem SET quantity = ? WHERE id = ?", (new_qty, row_id))

        return change

    def _compact_desmagatzem(self):
        """Apilar: renumera row_order per no deixar forats després d'un esborrat."""
        rows = self.conn.execute("SELECT id FROM desmagatzem ORDER BY row_order").fetchall()
        for order, r in enumerate(rows, start=1):
            self.conn.execute("UPDATE desmagatzem SET row_order = ? WHERE id = ?", (order, r["id"]))
