"""Estadístiques de moviments i comptador de peces de Desmagatzem.

Tot surt de l'històric, que no es toca mai: aquí es comprova que es compta
el que toca (un trasllat = un moviment, comptat al destí), que se separa el
que passa al Tauler del que passa a Desmagatzem, que les peces de cada dia
es dedueixen bé cap enrere, que l'interval de dates es respecta pels dos
extrems i que els comptadors no depenen de com es vegi res a la pantalla.
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


def days_of(stats) -> list:
    return stats["days"]


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
    days = days_of(repo.movement_stats("2026-08-01", "2026-08-31"))

    assert [d["day"] for d in days] == ["2026-08-30", "2026-08-31"]
    assert (days[0]["board_in"], days[0]["board_out"]) == (2, 0)
    assert (days[1]["board_in"], days[1]["board_out"]) == (0, 1)


def test_the_board_and_desmagatzem_are_counted_apart(repo):
    """Una unitat que entra a Desmagatzem no és una entrada al Tauler."""
    repo.add_piece(3, 41011)
    repo.add_desmagatzem_row(material_code="41952", quantity=2, dimensions="", cart_ref="c")
    day = days_of(repo.movement_stats(today(), today()))[0]

    assert day["board_in"] == 1
    assert day["desmagatzem_in"] == 2
    assert day["board_out"] == day["desmagatzem_out"] == 0


def test_a_move_counts_once_at_its_destination(repo):
    """Un trasllat deixa dues línies (origen i destí) i ha de comptar com
    un sol moviment, sense tocar les entrades ni les sortides."""
    repo.add_piece(3, 41011)
    repo.move_piece(3, 20)
    day = days_of(repo.movement_stats(today(), today()))[0]

    assert day["moves"] == 1
    assert day["board_in"] == 1        # l'alta de la peça; el trasllat no hi compta
    assert day["board_out"] == 0       # ni com a sortida


def test_the_pieces_of_each_day_are_worked_out_backwards(repo):
    """Les peces d'un dia passat no es guarden enlloc: se saben les d'ara i
    es desfà el que diu l'històric cap enrere."""
    log(repo, "in", "2026-08-01")      # +1 -> 1 peça
    log(repo, "in", "2026-08-02")      # +1 -> 2 peces
    log(repo, "out", "2026-08-03")     # -1 -> 1 peça
    # ara mateix el Tauler està buit, o sigui que el dia 3 va acabar amb 0
    days = {d["day"]: d for d in days_of(repo.movement_stats("2026-08-01", "2026-08-31"))}

    assert days["2026-08-03"]["board_pieces"] == 0
    assert days["2026-08-02"]["board_pieces"] == 1
    assert days["2026-08-01"]["board_pieces"] == 0


def test_the_pieces_of_desmagatzem_are_worked_out_the_same_way(repo):
    repo.add_desmagatzem_row(material_code="41011", quantity=4, dimensions="", cart_ref="c")
    day = days_of(repo.movement_stats(today(), today()))[0]

    assert day["desmagatzem_in"] == 4
    assert day["desmagatzem_pieces"] == 4 == repo.count_desmagatzem_pieces()


def test_movements_after_the_range_still_count_for_the_pieces(repo, monkeypatch):
    """Encara que l'interval acabi abans, per saber les peces d'aquell dia
    s'han de desfer TAMBÉ els moviments posteriors."""
    import app.logic.repository as repository_module

    monkeypatch.setattr(repository_module, "_now", lambda: "2026-08-01 10:00:00")
    repo.add_piece(3, 41011)
    monkeypatch.setattr(repository_module, "_now", lambda: "2026-09-01 10:00:00")
    repo.add_piece(4, 41952)           # fora de l'interval que es demana

    days = days_of(repo.movement_stats("2026-08-01", "2026-08-31"))

    assert [d["day"] for d in days] == ["2026-08-01"]
    # Ara al Tauler hi ha 2 peces; desfent la que va entrar al setembre,
    # l'1 d'agost va acabar amb una.
    assert repo.count_pieces() == 2
    assert days[0]["board_pieces"] == 1


def test_the_range_includes_both_ends_and_nothing_outside(repo):
    for day in ("2026-08-29", "2026-08-30", "2026-08-31", "2026-09-01"):
        log(repo, "in", day)
    days = days_of(repo.movement_stats("2026-08-30", "2026-08-31"))
    assert [d["day"] for d in days] == ["2026-08-30", "2026-08-31"]


def test_days_without_movements_are_not_listed(repo):
    log(repo, "in", "2026-08-30")
    assert len(days_of(repo.movement_stats("2026-08-01", "2026-08-31"))) == 1


def test_an_empty_range_gives_an_empty_result(repo):
    log(repo, "in", "2026-08-30")
    stats = repo.movement_stats("2020-01-01", "2020-12-31")
    assert stats["days"] == []
    assert stats["board_out_per_day"] == 0


def test_desmagatzem_movements_count_one_per_unit(repo):
    """Desmagatzem escriu una línia d'històric per unitat: 5 unitats són 5
    entrades."""
    repo.add_desmagatzem_row(material_code="41011", quantity=5, dimensions="", cart_ref="c1")
    assert days_of(repo.movement_stats(today(), today()))[0]["desmagatzem_in"] == 5


def test_the_average_of_exits_is_spread_over_every_day_of_the_range(repo):
    """20 sortides en un interval de 10 dies són 2 al dia, encara que s'hagin
    fet totes en dos dies."""
    for _ in range(12):
        log(repo, "out", "2026-08-02")
    for _ in range(8):
        log(repo, "out", "2026-08-05")

    stats = repo.movement_stats("2026-08-01", "2026-08-10")   # 10 dies
    assert stats["board_out_per_day"] == 2.0


def test_the_average_ignores_what_is_outside_the_range(repo):
    for _ in range(10):
        log(repo, "out", "2026-08-02")
    log(repo, "out", "2026-09-15")                            # fora
    stats = repo.movement_stats("2026-08-01", "2026-08-10")
    assert stats["board_out_per_day"] == 1.0


def test_statistics_do_not_change_the_historic(repo):
    repo.add_piece(3, 41011)
    repo.move_piece(3, 20)
    before = repo.get_historic()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    repo.movement_stats(yesterday, today())

    assert repo.get_historic() == before
