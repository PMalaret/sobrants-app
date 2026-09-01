import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.logic import rules


def test_normalize_text_strips_accents_and_case():
    assert rules.normalize_text("  Sunguard HD Silver  ") == "sunguard hd silver"
    assert rules.normalize_text("Acústic") == "acustic"
    assert rules.normalize_text("ENPLUS_10T") == "enplus_10t"
    assert rules.normalize_text(None) == ""


def test_is_valid_material_code_range():
    # Només números positius: 0 i negatius no són codis vàlids
    assert rules.is_valid_material_code(1) is True
    assert rules.is_valid_material_code(25) is True
    assert rules.is_valid_material_code(99999) is True
    assert rules.is_valid_material_code(999999) is True
    assert rules.is_valid_material_code(1000000) is False
    assert rules.is_valid_material_code(0) is False
    assert rules.is_valid_material_code(-1) is False
    assert rules.is_valid_material_code(-25) is False
    assert rules.is_valid_material_code("abc") is False
    assert rules.is_valid_material_code("") is False
    assert rules.is_valid_material_code(None) is False
    assert rules.is_valid_material_code("12x") is False
    # Un text que sigui un número sí que val (és el que s'escriu a la cel·la)
    assert rules.is_valid_material_code("25") is True


def test_is_valid_desmagatzem_qty_range():
    assert rules.is_valid_desmagatzem_qty(0) is True
    assert rules.is_valid_desmagatzem_qty(20) is True
    assert rules.is_valid_desmagatzem_qty(999) is True
    assert rules.is_valid_desmagatzem_qty(1000) is False
    assert rules.is_valid_desmagatzem_qty(-1) is False


def test_next_free_slot_sequential_fill():
    assert rules.next_free_slot([]) == 1
    assert rules.next_free_slot([1]) == 2
    assert rules.next_free_slot([1, 2, 3]) == 4
    assert rules.next_free_slot([1, 2, 3, 4, 5]) is None


def test_next_free_slot_rejects_gaps():
    import pytest

    with pytest.raises(ValueError):
        rules.next_free_slot([1, 3])


def test_can_delete_slot_only_last_occupied():
    assert rules.can_delete_slot([1, 2, 3], 3) is True
    assert rules.can_delete_slot([1, 2, 3], 2) is False
    assert rules.can_delete_slot([1, 2, 3], 1) is False
    assert rules.can_delete_slot([], 1) is False


def test_find_duplicate_positions_excludes_current_position():
    all_pieces = [
        (2, 1, 41011),
        (5, 1, 41011),
        (5, 2, 32000),
        (9, 1, 41011),
    ]
    dups = rules.find_duplicate_positions(all_pieces, 41011, exclude_position=5)
    assert dups == [2, 9]


def test_find_duplicate_positions_none_when_unique():
    all_pieces = [(2, 1, 41011)]
    assert rules.find_duplicate_positions(all_pieces, 41011, exclude_position=2) == []


def test_board_summary_piece_picks_highest_slot_above_sentinel():
    pieces = [
        {"slot": 1, "material_code": 41964},
        {"slot": 2, "material_code": 41964},
        {"slot": 3, "material_code": 41964},
        {"slot": 4, "material_code": 41952},
    ]
    result = rules.board_summary_piece(pieces)
    assert result["slot"] == 4
    assert result["material_code"] == 41952


def test_board_summary_piece_skips_custom_sentinel_code_1():
    pieces = [
        {"slot": 1, "material_code": 500},
        {"slot": 2, "material_code": 1},  # texto libre, no debe mostrarse en el panel
    ]
    result = rules.board_summary_piece(pieces)
    assert result["slot"] == 1


def test_board_summary_piece_empty_position():
    assert rules.board_summary_piece([]) is None


def test_matches_exact_and_partial():
    assert rules.matches_exact("32946", "32946") is True
    assert rules.matches_exact("32946", "3294") is False
    assert rules.matches_partial("Sunguard HD Silver 20 10mm HS", "silver") is True
    assert rules.matches_partial("Sunguard HD Silver 20 10mm HS", "xyz") is False
    assert rules.matches_partial("cualquiera", "") is False


def test_oldest_matching_position_picks_earliest_dated():
    matches = [
        {"position": 5, "entered_at": "2026-04-10 10:00:00"},
        {"position": 2, "entered_at": "2026-01-01 08:00:00"},
        {"position": 9, "entered_at": None},
    ]
    assert rules.oldest_matching_position(matches) == 2


def test_oldest_matching_position_none_when_no_dates():
    assert rules.oldest_matching_position([{"position": 1, "entered_at": None}]) is None


def test_occupancy_level_matches_original_scale():
    """Els mateixos trams que els cinc colors de referència K12:K16 de
    l'Excel; quin color li toca a cada nivell ja no és cosa de les regles."""
    assert rules.occupancy_level(0) == 1
    assert rules.occupancy_level(1) == 1
    assert rules.occupancy_level(2) == 2
    assert rules.occupancy_level(3) == 3
    assert rules.occupancy_level(4) == 4
    assert rules.occupancy_level(5) == 5
    assert rules.occupancy_level(9) == 5


def test_has_material_inconsistency_multiple_distinct_codes():
    assert rules.has_material_inconsistency([41011, 41011, 41952]) is True
    assert rules.has_material_inconsistency([41011, 41011, 41011]) is False
    assert rules.has_material_inconsistency([41011]) is False
    assert rules.has_material_inconsistency([]) is False
    assert rules.has_material_inconsistency([None, 41011]) is False


def test_quantity_change_kind():
    assert rules.quantity_change_kind(0, 3) == "increase"
    assert rules.quantity_change_kind(3, 1) == "decrease"
    assert rules.quantity_change_kind(3, 0) == "delete"
    assert rules.quantity_change_kind(3, 3) is None


def test_find_covered_in_position_detects_conflict_and_keeps_last_slot():
    pieces = [
        {"slot": 1, "material_code": 100, "material_desc": "A", "dimensions": "1x1"},
        {"slot": 2, "material_code": 200, "material_desc": "B", "dimensions": "2x2"},
    ]
    covered = rules.find_covered_in_position(7, pieces)
    assert len(covered) == 1
    assert covered[0]["position"] == 7
    assert covered[0]["material_code"] == 100  # slot 1: tapat pel de l'slot 2 (el més alt)


def test_find_covered_in_position_no_conflict_when_single_material():
    pieces = [
        {"slot": 1, "material_code": 300, "material_desc": "C", "dimensions": "3x3"},
        {"slot": 2, "material_code": 300, "material_desc": "C", "dimensions": "3x3"},
    ]
    assert rules.find_covered_in_position(8, pieces) == []


def test_find_covered_in_position_ignores_empty_slots():
    pieces = [
        {"slot": 1, "material_code": None, "material_desc": "---------", "dimensions": None},
        {"slot": 2, "material_code": 300, "material_desc": "C", "dimensions": "3x3"},
    ]
    assert rules.find_covered_in_position(9, pieces) == []
