import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.db import connect
from app.logic import rules
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


def test_delete_piece_allows_any_slot_and_renumbers_the_rest(repo):
    repo.add_piece(position=3, material_code=41011, dimensions="a")  # slot 1
    repo.add_piece(position=3, material_code=41952, dimensions="b", confirm_duplicate=True)  # slot 2
    repo.add_piece(position=3, material_code=999, dimensions="c", confirm_duplicate=True)  # slot 3
    repo.add_piece(position=3, material_code=999, dimensions="d", confirm_duplicate=True)  # slot 4

    repo.delete_piece(position=3, slot=2)  # esborra el del mig, no l'últim

    detail = repo.get_position_detail(3)
    assert [p["slot"] for p in detail] == [1, 2, 3]
    # slot 3 -> 2 i slot 4 -> 3 (pugen), slot 1 no es toca
    assert [p["dimensions"] for p in detail] == ["a", "c", "d"]


def test_delete_piece_rejects_unoccupied_slot(repo):
    repo.add_piece(position=3, material_code=41011)
    with pytest.raises(RuleViolation):
        repo.delete_piece(position=3, slot=5)


def test_delete_piece_logs_historic_out(repo):
    repo.add_piece(position=4, material_code=41011)
    repo.delete_piece(position=4, slot=1)
    hist = repo.get_historic(position="4")
    assert hist[0]["kind"] == "out"
    assert hist[0]["direction"] == -1


def test_update_piece_field_edits_dimensions_and_notes(repo):
    repo.add_piece(position=5, material_code=41011, dimensions="1x1", notes="abans")
    repo.update_piece_field(position=5, slot=1, field="dimensions", value="2600x3210")
    repo.update_piece_field(position=5, slot=1, field="notes", value="després")

    piece = repo.get_position_detail(5)[0]
    assert piece["dimensions"] == "2600x3210"
    assert piece["notes"] == "després"
    assert piece["material_code"] == 41011  # no s'ha tocat


def test_update_piece_field_rejects_non_editable_field(repo):
    repo.add_piece(position=5, material_code=41011)
    with pytest.raises(ValueError):
        repo.update_piece_field(position=5, slot=1, field="material_code", value="999")


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


def test_move_piece_historic_keeps_original_entry_date(repo):
    repo.add_piece(position=10, material_code=41011, dimensions="2600x3210")
    entered_at = repo.get_position_detail(10)[0]["entered_at"]

    repo.move_piece(from_position=10, to_position=20)

    hist = repo.get_historic(limit=10)
    move_rows = [h for h in hist if h["kind"] in ("move_out", "move_in")]
    assert len(move_rows) == 2
    # La data/hora de l'històric del trasllat és la de l'entrada original,
    # no la del moment en què es mou.
    assert all(h["ts"] == entered_at for h in move_rows)


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


def test_board_fill_color_reflects_piece_count(repo):
    repo.add_piece(position=6, material_code=999)
    board = repo.get_board()
    row6 = next(b for b in board if b["position"] == 6)
    assert row6["fill_color"] == "#FFFFFF"  # 1 pieza

    repo.add_piece(position=6, material_code=999)
    row6 = next(b for b in repo.get_board() if b["position"] == 6)
    assert row6["fill_color"] == "#FFF2CC"  # 2 piezas


def test_board_marks_inconsistent_when_mixed_materials(repo):
    repo.add_piece(position=7, material_code=41011)
    repo.add_piece(position=7, material_code=41952, confirm_duplicate=True)
    board = repo.get_board()
    row7 = next(b for b in board if b["position"] == 7)
    assert row7["inconsistent"] is True


def test_board_not_inconsistent_when_same_material_repeated(repo):
    repo.add_piece(position=7, material_code=41011)
    repo.add_piece(position=7, material_code=41011, confirm_duplicate=True)
    board = repo.get_board()
    row7 = next(b for b in board if b["position"] == 7)
    assert row7["inconsistent"] is False


def test_covered_materials_report_detects_mixed_position(repo):
    repo.add_piece(position=7, material_code=41011)
    repo.add_piece(position=7, material_code=41952, confirm_duplicate=True)
    covered = repo.covered_materials_report()
    assert len(covered) == 1
    assert covered[0]["position"] == 7
    assert covered[0]["material_code"] == 41011  # el de l'slot 1, tapat pel de l'slot 2


def test_covered_materials_report_detects_mixing_caused_by_a_move(repo):
    # Abans, l'informe només mirava l'històric d'altes ("in"): una posició
    # que quedava mesclada per un TRASLLAT (no una alta nova) no hi sortia.
    repo.add_piece(position=1, material_code=41011)
    repo.add_piece(position=2, material_code=41952)
    repo.move_piece(from_position=2, to_position=1)  # ara la 1 té dos materials

    covered = repo.covered_materials_report()
    assert len(covered) == 1
    assert covered[0]["position"] == 1
    assert covered[0]["material_code"] == 41011


def test_covered_materials_report_ignores_resolved_position(repo):
    # Una posició que va estar mesclada però ja no ho està (s'ha esborrat
    # l'última peça, tornant a tenir un sol material) no ha de sortir.
    repo.add_piece(position=7, material_code=41011)
    repo.add_piece(position=7, material_code=41952, confirm_duplicate=True)
    repo.delete_piece(position=7, slot=2)
    assert repo.covered_materials_report() == []


def test_search_reports_desmagatzem_quantity(repo):
    repo.add_piece(position=1, material_code=41011)
    repo.add_desmagatzem_row(material_code="41011", quantity=3, dimensions="", cart_ref="carro1")
    repo.add_desmagatzem_row(material_code="41011", quantity=2, dimensions="", cart_ref="carro2")

    res = repo.search("41011", mode="code")
    assert res["desmagatzem_qty"] == 5


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


def test_get_historic_order_by_position_is_numeric_not_lexicographic(repo):
    repo.add_piece(position=2, material_code=41011)
    repo.add_piece(position=10, material_code=999)
    repo.add_piece(position=3, material_code=41952)

    rows = repo.get_historic(order_by="position")
    positions = [r["position"] for r in rows]
    assert positions == ["2", "3", "10"]  # no ["10", "2", "3"] (orden de texto)


def test_desmagatzem_rejects_invalid_quantity(repo):
    with pytest.raises(RuleViolation):
        repo.add_desmagatzem_row(material_code="41011", quantity=21, dimensions="", cart_ref="")


def test_add_material_new_code(repo):
    repo.add_material(50000, "Vidre nou de prova")
    assert repo.lookup_material(50000) == "Vidre nou de prova"


def test_add_material_rejects_existing_code_without_overwrite(repo):
    with pytest.raises(RuleViolation):
        repo.add_material(41011, "Descripció diferent")
    # no s'ha tocat l'original
    assert repo.lookup_material(41011) == "L1010.2 HS"


def test_add_material_overwrite_updates_description(repo):
    repo.add_material(41011, "Descripció actualitzada", overwrite=True)
    assert repo.lookup_material(41011) == "Descripció actualitzada"


def test_list_desmagatzem_orders_by_row_order(repo):
    repo.add_desmagatzem_row(material_code="999", quantity=1, dimensions="", cart_ref="A")
    repo.add_desmagatzem_row(material_code="999", quantity=1, dimensions="", cart_ref="B")

    rows = repo.list_desmagatzem()
    assert [r["cart_ref"] for r in rows] == ["A", "B"]


def test_delete_material_removes_it(repo):
    repo.delete_material(41011)
    assert repo.lookup_material(41011) == rules.EMPTY_MATERIAL_MARK


def test_delete_material_rejects_unknown_code(repo):
    with pytest.raises(RuleViolation):
        repo.delete_material(77777)


def test_get_historic_returns_all_rows_without_limit(repo):
    for i in range(1200):
        repo.add_piece(position=1, material_code=999)
        repo.delete_piece(position=1, slot=1)
    rows = repo.get_historic()
    assert len(rows) == 2400  # 1200 "in" + 1200 "out", cap tallat als 500/1000 d'abans
