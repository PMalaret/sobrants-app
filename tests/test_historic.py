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


def test_clear_keeps_every_piece_on_the_board_not_one_per_material(repo):
    """Tres peces del mateix material a la mateixa posició són TRES peces:
    després de netejar hi han de continuar sent les tres, no una."""
    for _ in range(3):
        repo.add_piece(3, 41011, confirm_duplicate=True)
    repo.add_piece(4, 41012)

    result = repo.clear_historic()
    after = historic_rows(repo)

    assert len(after) == 4 == result["kept"]
    assert sorted(r["material_code"] for r in after) == ["41011", "41011", "41011", "41012"]
    assert sorted(r["position"] for r in after) == ["3", "3", "3", "4"]


def test_clear_keeps_all_the_data_of_each_piece(repo):
    """De cada peça s'hi ha de quedar tot el que la descriu: material,
    posició, mides, notes i la seva data d'entrada."""
    repo.add_piece(7, 41011, dimensions="2600x3210", notes="lot-1")
    entered_at = repo.get_position_detail(7)[0]["entered_at"]

    repo.clear_historic()

    kept = historic_rows(repo)[0]
    assert kept["position"] == "7"
    assert kept["material_code"] == "41011"
    assert kept["material_desc"] == "Vidre A"
    assert kept["dimensions"] == "2600x3210"
    assert kept["notes"] == "lot-1"
    assert kept["ts"] == entered_at          # la data de la peça, no la de netejar
    assert kept["kind"] == "in"


def test_clear_keeps_the_pieces_in_desmagatzem_one_per_unit(repo):
    repo.add_desmagatzem_row(material_code="41011", quantity=3, dimensions="10x20", cart_ref="carro 1")
    repo.add_desmagatzem_row(material_code="41012", quantity=1, dimensions="", cart_ref="carro 2")

    repo.clear_historic()
    after = historic_rows(repo)

    assert len(after) == 4                    # 3 unitats + 1 unitat
    assert {r["position"] for r in after} == {"Desmagatzem"}
    first = next(r for r in after if r["material_code"] == "41011")
    assert first["dimensions"] == "10x20"
    assert first["notes"] == "carro 1"        # a Desmagatzem, les notes són el carro


def test_clear_keeps_the_board_and_desmagatzem_together(repo):
    repo.add_piece(3, 41011, dimensions="100x200", notes="lot-1")
    repo.add_piece(4, 41012)
    repo.add_desmagatzem_row(material_code="41013", quantity=2, dimensions="", cart_ref="carro")
    # moviments que sí que s'han d'esborrar
    repo.add_piece(5, 41013, confirm_duplicate=True)
    repo.delete_piece(5, 1)

    before = len(historic_rows(repo))
    result = repo.clear_historic()
    after = historic_rows(repo)

    assert len(after) == 4 == result["kept"]  # 2 peces del Tauler + 2 unitats
    assert result["deleted"] == before
    assert sorted(r["position"] for r in after) == ["3", "4", "Desmagatzem", "Desmagatzem"]


def test_clear_removes_everything_when_there_are_no_pieces_left(repo):
    repo.add_piece(3, 41011)
    repo.delete_piece(3, 1)           # el Tauler i Desmagatzem es queden buits
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


def test_an_old_database_gets_the_new_columns(tmp_path):
    """Una base de dades feta amb una versió anterior (sense les columnes
    de mides i notes a l'històric) s'ha de poder obrir igual, i les seves
    dades s'han de quedar on eren."""
    import sqlite3

    old_db = tmp_path / "antiga.db"
    legacy = sqlite3.connect(old_db)
    legacy.executescript(
        """
        CREATE TABLE materials (code INTEGER PRIMARY KEY, description TEXT NOT NULL);
        CREATE TABLE pieces (id INTEGER PRIMARY KEY AUTOINCREMENT, position INTEGER NOT NULL,
            slot INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 5), material_code INTEGER,
            material_desc TEXT, dimensions TEXT, notes TEXT, entered_at TEXT,
            UNIQUE (position, slot));
        CREATE TABLE historic (id INTEGER PRIMARY KEY AUTOINCREMENT, position TEXT NOT NULL,
            material_code TEXT, material_desc TEXT, ts TEXT NOT NULL, direction INTEGER,
            kind TEXT NOT NULL CHECK (kind IN ('in','out','move_out','move_in')));
        CREATE TABLE desmagatzem (id INTEGER PRIMARY KEY AUTOINCREMENT, row_order INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0, material_code TEXT, material_desc TEXT,
            custom_text TEXT, dimensions TEXT, cart_ref TEXT, ts TEXT);
        INSERT INTO historic(position, material_code, material_desc, ts, direction, kind)
            VALUES ('7', '41011', 'Vidre A', '2026-01-02 10:00:00', 1, 'in');
        """
    )
    legacy.commit()
    legacy.close()

    repo = Repository(connect(old_db))          # com obrir-la amb la versió nova

    columns = {row[1] for row in repo.conn.execute("PRAGMA table_info(historic)")}
    assert {"dimensions", "notes"} <= columns
    old_row = repo.get_historic()[0]
    assert old_row["position"] == "7"           # la línia que ja hi havia, intacta
    assert old_row["dimensions"] is None        # d'aquella no en sabem les mides
    # i els moviments nous ja hi guarden les mides
    repo.conn.execute("INSERT INTO materials(code, description) VALUES (41011, 'Vidre A')")
    repo.add_piece(3, 41011, dimensions="100x200", notes="lot")
    assert repo.get_historic()[0]["dimensions"] == "100x200"
