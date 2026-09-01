"""Estadístiques de moviments i comptador de peces de Desmagatzem.

Tot surt de l'històric, que no es toca mai: aquí es comprova que es compta
el que toca (un trasllat = un moviment, comptat al destí), que l'interval
de dates es respecta pels dos extrems i que els comptadors no depenen de
com es vegi res a la pantalla.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.db import connect
from app.logic.repository import Repository


@pytest.fixture()
def repo(tmp_path):
    conn = connect(tmp_path / "test.db")
    conn.executemany(
        "INSERT INTO materials(code, description) VALUES (?, ?)",
        [(41011, "L1010.2 HS"), (41952, "L66.6 P5A")],
    )
    conn.commit()
    return Repository(conn)


def log(repo, kind: str, day: str, position: str = "5", material_code: str = "41011"):
    """Una línia d'històric amb la data que convingui a la prova (les que
    escriu l'aplicació sempre són d'ara mateix)."""
    direction = {"in": 1, "out": -1}.get(kind)
    repo.conn.execute(
        "INSERT INTO historic(position, material_code, material_desc, ts, direction, kind) "
        "VALUES (?,?,?,?,?,?)",
        (position, material_code, "L1010.2 HS", f"{day} 10:30:00", direction, kind),
    )
    repo.conn.commit()


def today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------- peces


def test_desmagatzem_count_is_the_sum_of_quantities_not_the_number_of_rows(repo):
    repo.add_desmagatzem_row(material_code="41011", quantity=3, dimensions="", cart_ref="c1")
    repo.add_desmagatzem_row(material_code="41952", quantity=4, dimensions="", cart_ref="c2")
    assert repo.count_desmagatzem_pieces() == 7


def test_desmagatzem_count_follows_quantity_changes_and_deletions(repo):
    repo.add_desmagatzem_row(material_code="41011", quantity=3, dimensions="", cart_ref="c1")
    row_id = repo.list_desmagatzem()[0]["id"]
    repo.update_desmagatzem_quantity(row_id, 8)
    assert repo.count_desmagatzem_pieces() == 8
    repo.update_desmagatzem_quantity(row_id, 0)   # quantitat 0 = esborrar la línia
    assert repo.count_desmagatzem_pieces() == 0


def test_desmagatzem_count_is_zero_when_empty(repo):
    assert repo.count_desmagatzem_pieces() == 0


# ---------------------------------------------------------- estadístiques


def test_movements_are_grouped_by_day(repo):
    log(repo, "in", "2026-08-30")
    log(repo, "in", "2026-08-30")
    log(repo, "out", "2026-08-31")
    stats = repo.movement_stats("2026-08-01", "2026-08-31")
    assert stats == [
        {"day": "2026-08-30", "in": 2, "out": 0, "move": 0, "total": 2},
        {"day": "2026-08-31", "in": 0, "out": 1, "move": 0, "total": 1},
    ]


def test_a_move_counts_once_at_its_destination(repo):
    """Un trasllat deixa dues línies (origen i destí) i ha de comptar com
    un sol moviment, el del destí."""
    repo.add_piece(3, 41011)
    repo.move_piece(3, 20)
    stats = repo.movement_stats(today(), today())
    assert stats[0]["move"] == 1
    assert stats[0]["in"] == 1        # l'alta de la peça; el trasllat no hi compta
    assert stats[0]["out"] == 0       # ni com a sortida


def test_moves_are_counted_by_destination_position(repo):
    repo.add_piece(3, 41011)
    repo.add_piece(4, 41952)
    repo.move_piece(3, 20)
    repo.move_piece(4, 20)
    assert repo.movement_stats_by_destination(today(), today()) == [{"position": "20", "count": 2}]


def test_the_range_includes_both_ends_and_nothing_outside(repo):
    for day in ("2026-08-29", "2026-08-30", "2026-08-31", "2026-09-01"):
        log(repo, "in", day)
    stats = repo.movement_stats("2026-08-30", "2026-08-31")
    assert [row["day"] for row in stats] == ["2026-08-30", "2026-08-31"]


def test_days_without_movements_are_not_listed(repo):
    log(repo, "in", "2026-08-30")
    stats = repo.movement_stats("2026-08-01", "2026-08-31")
    assert len(stats) == 1


def test_an_empty_range_gives_an_empty_result(repo):
    log(repo, "in", "2026-08-30")
    assert repo.movement_stats("2020-01-01", "2020-12-31") == []
    assert repo.movement_stats_by_destination("2020-01-01", "2020-12-31") == []


def test_desmagatzem_movements_count_one_per_unit(repo):
    """Desmagatzem escriu una línia d'històric per unitat: 5 unitats són 5
    entrades, igual que compta l'històric."""
    repo.add_desmagatzem_row(material_code="41011", quantity=5, dimensions="", cart_ref="c1")
    assert repo.movement_stats(today(), today())[0]["in"] == 5


def test_statistics_do_not_change_the_historic(repo):
    repo.add_piece(3, 41011)
    repo.move_piece(3, 20)
    before = repo.get_historic()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    repo.movement_stats(yesterday, today())
    repo.movement_stats_by_destination(yesterday, today())
    assert repo.get_historic() == before
