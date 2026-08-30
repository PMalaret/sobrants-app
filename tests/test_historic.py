"""Històric: netejar-lo conservant l'última entrada de cada material del
Tauler, exportar-lo sencer a Excel i aguantar desenes de milers de línies."""
import sys
import time
from pathlib import Path

import pytest
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.db import connect
from app.excel_export import export_historic_xlsx
from app.logic.repository import Repository


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "sobrants.db"


@pytest.fixture()
def repo(db_path):
    conn = connect(db_path)
    for code, description in ((41011, "Vidre A"), (41012, "Vidre B"), (41013, "Vidre C")):
        conn.execute("INSERT INTO materials(code, description) VALUES (?, ?)", (code, description))
    conn.commit()
    return Repository(conn)


def historic_rows(repo):
    return repo.get_historic()


def test_last_entry_of_a_material_is_the_newest_one_not_the_first_row(repo):
    """L'última entrada es decideix per data (i per id en cas d'empat), no
    per com es veu ordenada la taula."""
    repo.add_piece(3, 41011)          # entrada 1
    repo.add_piece(4, 41011, confirm_duplicate=True)   # entrada 2 (la més nova)
    keep = repo.historic_ids_to_keep()
    newest = max(r["id"] for r in historic_rows(repo) if r["material_code"] == "41011")
    assert keep == [newest]


def test_clear_keeps_the_last_entry_of_every_material_on_the_board(repo):
    repo.add_piece(3, 41011)
    repo.add_piece(4, 41012)
    repo.add_piece(5, 41013)
    # moviments extra que sí que s'han d'esborrar
    repo.update_piece_field(3, 1, "notes", "x")
    repo.add_piece(3, 41012, confirm_duplicate=True)
    repo.delete_piece(3, 2)           # el 41012 surt de la posició 3
    # i un material que ja no és al Tauler
    repo.add_piece(6, 41013, confirm_duplicate=True)
    repo.delete_piece(6, 1)

    before = len(historic_rows(repo))
    result = repo.clear_historic()
    after = historic_rows(repo)

    on_board = {str(p["material_code"]) for p in repo.conn.execute("SELECT material_code FROM pieces")}
    assert on_board == {"41011", "41012", "41013"}
    # queda exactament una entrada per material del Tauler
    assert len(after) == len(on_board) == result["kept"]
    assert {r["material_code"] for r in after} == on_board
    assert result["deleted"] == before - len(after)
    # i la que queda és, per a cada material, la més nova
    for code in on_board:
        kept_row = next(r for r in after if r["material_code"] == code)
        assert kept_row["id"] == max(
            r["id"] for r in repo.conn.execute(
                "SELECT id FROM historic WHERE material_code = ?", (code,)
            ).fetchall()
        )


def test_clear_removes_everything_when_the_board_is_empty(repo):
    repo.add_piece(3, 41011)
    repo.delete_piece(3, 1)           # el Tauler es queda buit
    assert historic_rows(repo) != []

    result = repo.clear_historic()

    assert historic_rows(repo) == []
    assert result["kept"] == 0


def test_clear_is_persisted_immediately(repo, db_path):
    repo.add_piece(3, 41011)
    repo.add_piece(4, 41012)
    repo.delete_piece(4, 1)
    repo.clear_historic()

    reopened = Repository(connect(db_path))   # com un arrencada nova
    assert len(reopened.get_historic()) == 1
    assert reopened.get_historic()[0]["material_code"] == "41011"


class _FailsAfterDeleting:
    """Connexió que deixa fer l'esborrat i tot seguit peta: simula una
    fallada amb l'històric JA mig esborrat dins de la transacció."""

    def __init__(self, real):
        self._real = real

    def execute(self, sql, *args, **kwargs):
        result = self._real.execute(sql, *args, **kwargs)
        if sql.strip().upper().startswith("DELETE FROM HISTORIC"):
            raise RuntimeError("fallada simulada just despres d'esborrar")
        return result

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_a_failed_clear_rolls_back_and_leaves_the_history_intact(repo, db_path):
    repo.add_piece(3, 41011)
    repo.add_piece(4, 41012)
    repo.delete_piece(4, 1)
    before = historic_rows(repo)
    assert len(before) > 1

    real_conn = repo.conn
    repo.conn = _FailsAfterDeleting(real_conn)
    with pytest.raises(RuntimeError):
        repo.clear_historic()
    repo.conn = real_conn

    # L'esborrat s'ha desfet: no queda l'històric a mitges
    assert historic_rows(repo) == before
    assert Repository(connect(db_path)).get_historic() == before


def test_history_handles_tens_of_thousands_of_rows(repo):
    """50.000 moviments: es llegeixen sencers i sense cap límit de files."""
    rows = [("3", "41011", "Vidre A", f"2026-01-01 10:{i // 60:02d}:{i % 60:02d}", 1, "in")
            for i in range(50_000)]
    repo.conn.executemany(
        "INSERT INTO historic(position, material_code, material_desc, ts, direction, kind) "
        "VALUES (?,?,?,?,?,?)",
        rows,
    )
    repo.conn.commit()

    start = time.perf_counter()
    loaded = repo.get_historic()
    elapsed = time.perf_counter() - start

    assert len(loaded) == 50_000     # cap límit artificial de 100/500/1000
    assert elapsed < 10              # i la consulta és raonablement ràpida


def test_export_writes_every_row_and_the_headers(repo, tmp_path):
    for i in range(1200):
        repo.conn.execute(
            "INSERT INTO historic(position, material_code, material_desc, ts, direction, kind) "
            "VALUES (?,?,?,?,?,?)",
            (str(i % 61 + 1), "41011", "Vidre A", f"2026-01-01 10:00:{i % 60:02d}", 1, "in"),
        )
    repo.conn.commit()
    rows = repo.get_historic()
    dest = tmp_path / "historic.xlsx"

    written = export_historic_xlsx(
        rows,
        ["Posicio", "Num.", "Material", "Data", "Moviment"],
        ["position", "material_code", "material_desc", "ts", "kind"],
        str(dest),
    )

    assert written == len(rows) == 1200
    sheet = load_workbook(dest, read_only=True).active
    values = list(sheet.values)
    assert values[0] == ("Posicio", "Num.", "Material", "Data", "Moviment")
    assert len(values) == 1201        # capçalera + totes les files
    assert values[1][2] == "Vidre A"


def test_export_error_does_not_touch_the_history(repo, tmp_path):
    repo.add_piece(3, 41011)
    before = historic_rows(repo)
    impossible = tmp_path / "carpeta-que-no-existeix" / "historic.xlsx"

    with pytest.raises(OSError):
        export_historic_xlsx(before, ["A"], ["position"], str(impossible))

    assert historic_rows(repo) == before
