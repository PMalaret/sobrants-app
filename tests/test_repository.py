import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.db import connect
from app.logic.repository import (
    DuplicateMaterialError,
    PositionFullError,
    Repository,
    RuleViolation,
)


@pytest.fixture()
def repo(tmp_path):
    conn = connect(tmp_path / "test.db")
    conn.executemany(
        "INSERT INTO materials(code, description) VALUES (?, ?)",
        [(41011, "L1010.2 HS"), (41952, "L66.6 P5A"), (999, "OTRO MATERIAL")],
    )
    conn.commit()
    return Repository(conn)


def test_add_piece_happy_path(repo):
    result = repo.add_piece(position=5, material_code=41011, dimensions="2600x3210", notes="opt")
    assert result["slot"] == 1
    assert result["material_desc"] == "L1010.2 HS"

    board = repo.get_board()
    row = next(b for b in board if b["position"] == 5)
    assert row["material_code"] == 41011
    assert row["piece_count"] == 1


def test_add_piece_unknown_code_falls_back_to_dashes(repo):
    result = repo.add_piece(position=1, material_code=77777, dimensions="1x1")
    assert result["material_desc"] == "---------"


def test_add_piece_rejects_invalid_code(repo):
    with pytest.raises(RuleViolation):
        repo.add_piece(position=1, material_code=100000)
    with pytest.raises(RuleViolation):
        repo.add_piece(position=1, material_code=-5)


def test_add_piece_fills_slots_in_order(repo):
    for i in range(5):
        r = repo.add_piece(position=8, material_code=999, dimensions="x")
        assert r["slot"] == i + 1
    with pytest.raises(PositionFullError):
        repo.add_piece(position=8, material_code=999)


def test_add_piece_duplicate_requires_confirmation(repo):
    repo.add_piece(position=2, material_code=41011, dimensions="a")
    with pytest.raises(DuplicateMaterialError) as exc:
        repo.add_piece(position=9, material_code=41011, dimensions="b")
    assert exc.value.positions == [2]

    # Con confirmación explícita, se permite
    result = repo.add_piece(position=9, material_code=41011, dimensions="b", confirm_duplicate=True)
    assert result["position"] == 9


def test_delete_piece_only_allows_last_slot(repo):
    repo.add_piece(position=3, material_code=41011)
    repo.add_piece(position=3, material_code=41952)

    with pytest.raises(RuleViolation):
        repo.delete_piece(position=3, slot=1)  # no es el último

    repo.delete_piece(position=3, slot=2)  # sí es el último, permitido
    detail = repo.get_position_detail(3)
    assert len(detail) == 1
    assert detail[0]["slot"] == 1


def test_delete_piece_logs_historic_out(repo):
    repo.add_piece(position=4, material_code=41011)
    repo.delete_piece(position=4, slot=1)
    hist = repo.get_historic(position="4")
    assert hist[0]["kind"] == "out"
    assert hist[0]["direction"] == -1


def test_move_piece_between_positions(repo):
    repo.add_piece(position=10, material_code=41011, dimensions="2600x3210")
    result = repo.move_piece(from_position=10, to_position=20)
    assert result["to_position"] == 20

    assert repo.get_position_detail(10) == []
    dest = repo.get_position_detail(20)
    assert len(dest) == 1
    assert dest[0]["material_code"] == 41011

    hist = repo.get_historic(limit=10)
    kinds = {h["kind"] for h in hist}
    assert "move_out" in kinds and "move_in" in kinds


def test_move_piece_rejects_same_position(repo):
    repo.add_piece(position=11, material_code=41011)
    with pytest.raises(RuleViolation):
        repo.move_piece(from_position=11, to_position=11)


def test_move_piece_rejects_full_destination(repo):
    repo.add_piece(position=12, material_code=41011)
    for _ in range(5):
        repo.add_piece(position=13, material_code=999)
    with pytest.raises(PositionFullError):
        repo.move_piece(from_position=12, to_position=13)


def test_search_by_code_exact(repo):
    repo.add_piece(position=1, material_code=41011)
    repo.add_piece(position=2, material_code=41952)
    res = repo.search("41011", mode="code")
    assert res["count"] == 1
    assert res["matches"][0]["position"] == 1


def test_search_by_description_partial_and_oldest(repo):
    repo.add_piece(position=1, material_code=41011)  # "L1010.2 HS"
    repo.add_piece(position=2, material_code=41952)  # "L66.6 P5A"
    res = repo.search("l", mode="description")
    assert res["count"] == 2
    assert res["oldest_position"] in (1, 2)  # ambas tienen entered_at casi simultáneo


def test_search_empty_query_returns_nothing(repo):
    res = repo.search("", mode="description")
    assert res["count"] == 0
    assert res["matches"] == []


def test_desmagatzem_add_and_quantity_changes(repo):
    row = repo.add_desmagatzem_row(material_code="41011", quantity=2, dimensions="1x1", cart_ref="carro1")
    assert row["material_desc"] == "L1010.2 HS"

    rows = repo.list_desmagatzem()
    assert len(rows) == 1
    row_id = rows[0]["id"]

    change = repo.update_desmagatzem_quantity(row_id, 5)
    assert change == "increase"

    change = repo.update_desmagatzem_quantity(row_id, 1)
    assert change == "decrease"

    change = repo.update_desmagatzem_quantity(row_id, 0)
    assert change == "delete"
    assert repo.list_desmagatzem() == []


def test_desmagatzem_custom_material_sentinel(repo):
    with pytest.raises(RuleViolation):
        repo.add_desmagatzem_row(material_code="1", quantity=1, dimensions="", cart_ref="")

    row = repo.add_desmagatzem_row(
        material_code="1", quantity=1, dimensions="", cart_ref="", custom_text="Vidrio sin catalogar"
    )
    assert row["material_desc"] == "Vidrio sin catalogar"


def test_desmagatzem_rejects_invalid_quantity(repo):
    with pytest.raises(RuleViolation):
        repo.add_desmagatzem_row(material_code="41011", quantity=21, dimensions="", cart_ref="")
