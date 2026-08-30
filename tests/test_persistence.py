"""Cada operació es desa immediatament, i una que falla no deixa res a mitges.

La comprovació no es fa mirant la mateixa connexió que ha escrit (allà el
canvi es veuria encara que estigués només dins d'una transacció oberta):
s'obre una SEGONA connexió al mateix fitxer, que és el que veuria
l'aplicació si es tornés a obrir després d'una apagada. Si el canvi hi és,
és perquè hi ha hagut `commit()` de debò.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.db import connect
from app.logic.repository import Repository, RuleViolation


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "sobrants.db"


@pytest.fixture()
def repo(db_path):
    conn = connect(db_path)
    conn.execute("INSERT INTO materials(code, description) VALUES (41011, 'Vidre de prova')")
    conn.execute("INSERT INTO materials(code, description) VALUES (41012, 'Vidre de prova 2')")
    conn.commit()
    return Repository(conn)


def reopened(db_path) -> Repository:
    """La base de dades tal com la veuria un arrencada nova de l'aplicació."""
    return Repository(connect(db_path))


def test_add_piece_is_on_disk_immediately(repo, db_path):
    repo.add_piece(3, 41011, dimensions="10x10", notes="AA")
    detail = reopened(db_path).get_position_detail(3)
    assert [p["material_code"] for p in detail] == [41011]
    assert detail[0]["dimensions"] == "10x10"


def test_update_piece_field_is_on_disk_immediately(repo, db_path):
    repo.add_piece(3, 41011)
    repo.update_piece_field(3, slot=1, field="notes", value="NOU")
    assert reopened(db_path).get_position_detail(3)[0]["notes"] == "NOU"


def test_delete_piece_is_on_disk_immediately(repo, db_path):
    repo.add_piece(3, 41011)
    repo.delete_piece(3, slot=1)
    assert reopened(db_path).get_position_detail(3) == []


def test_move_piece_is_on_disk_immediately(repo, db_path):
    repo.add_piece(3, 41011)
    repo.move_piece(3, 7)
    after = reopened(db_path)
    assert after.get_position_detail(3) == []
    assert [p["material_code"] for p in after.get_position_detail(7)] == [41011]


def test_material_changes_are_on_disk_immediately(repo, db_path):
    repo.add_material(50000, "Material nou")
    assert reopened(db_path).lookup_material(50000) == "Material nou"
    repo.add_material(50000, "Material canviat", overwrite=True)
    assert reopened(db_path).lookup_material(50000) == "Material canviat"
    repo.delete_material(50000)
    assert reopened(db_path).lookup_material(50000) != "Material canviat"


def test_desmagatzem_changes_are_on_disk_immediately(repo, db_path):
    repo.add_desmagatzem_row(material_code="41011", quantity=2, dimensions="1x1", cart_ref="c1")
    rows = reopened(db_path).list_desmagatzem()
    assert len(rows) == 1 and rows[0]["quantity"] == 2

    repo.update_desmagatzem_quantity(rows[0]["id"], 5)
    assert reopened(db_path).list_desmagatzem()[0]["quantity"] == 5

    repo.update_desmagatzem_quantity(rows[0]["id"], 0)  # 0 = esborrar la línia
    assert reopened(db_path).list_desmagatzem() == []


def test_historic_is_written_with_the_operation(repo, db_path):
    repo.add_piece(3, 41011)
    assert len(reopened(db_path).get_historic()) == 1


def test_failed_operation_leaves_nothing_behind(repo, db_path, monkeypatch):
    """Si una operació peta un cop ja ha escrit alguna cosa, no en queda res:
    ni al disc ni a l'espera del commit de l'operació següent."""

    def explota(*args, **kwargs):
        raise RuntimeError("fallada simulada enmig de l'operació")

    monkeypatch.setattr(Repository, "_log_historic", explota)
    with pytest.raises(RuntimeError):
        repo.add_piece(3, 41011)

    # Ni la connexió que ha fallat ni una de nova en veuen cap rastre
    assert repo.get_position_detail(3) == []
    assert reopened(db_path).get_position_detail(3) == []

    # I la següent operació, que sí que va bé, no s'arrossega la fallida
    monkeypatch.undo()
    repo.add_piece(3, 41012)
    detail = reopened(db_path).get_position_detail(3)
    assert [p["material_code"] for p in detail] == [41012]


def test_rejected_operation_changes_nothing(repo, db_path):
    """Una operació rebutjada per les regles de negoci tampoc no toca res."""
    repo.add_piece(3, 41011)
    with pytest.raises(RuleViolation):
        repo.delete_piece(3, slot=5)  # no és l'última peça: no es pot
    assert len(reopened(db_path).get_position_detail(3)) == 1


def test_every_write_commits_before_returning(repo, db_path):
    """Cap operació no deixa una transacció oberta: quan torna, ja està desada.
    (`in_transaction` és fals just després de cada crida.)"""
    operations = [
        lambda: repo.add_piece(3, 41011),
        lambda: repo.update_piece_field(3, 1, "notes", "X"),
        lambda: repo.add_material(50001, "Un altre"),
        lambda: repo.add_desmagatzem_row(material_code="41011", quantity=1, dimensions="", cart_ref="c"),
        lambda: repo.delete_material(50001),
        lambda: repo.delete_piece(3, 1),
    ]
    for operation in operations:
        operation()
        assert repo.conn.in_transaction is False
