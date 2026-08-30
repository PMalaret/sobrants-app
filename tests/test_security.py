"""Les DUES contrasenyes (administrador i treballador): independents,
desades amb hash i persistents."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import security, settings


@pytest.fixture()
def data_dir(tmp_path):
    settings.init(tmp_path)
    yield tmp_path
    settings._path = None


def test_both_start_at_1234(data_dir):
    assert security.check_password("1234", security.ADMIN) is True
    assert security.check_password("1234", security.WORKER) is True
    assert security.is_default_password(security.ADMIN) is True
    assert security.is_default_password(security.WORKER) is True


def test_wrong_password_is_rejected(data_dir):
    assert security.check_password("9999", security.ADMIN) is False
    assert security.check_password("", security.WORKER) is False
    assert security.check_password(None, security.WORKER) is False


def test_changing_admin_does_not_touch_worker(data_dir):
    security.set_password("admin-nova", security.ADMIN)

    assert security.check_password("admin-nova", security.ADMIN) is True
    assert security.check_password("1234", security.ADMIN) is False
    # la de materials segueix com estava
    assert security.check_password("1234", security.WORKER) is True
    assert security.check_password("admin-nova", security.WORKER) is False


def test_changing_worker_does_not_touch_admin(data_dir):
    security.set_password("treball-nova", security.WORKER)

    assert security.check_password("treball-nova", security.WORKER) is True
    assert security.check_password("1234", security.WORKER) is False
    assert security.check_password("1234", security.ADMIN) is True


def test_each_one_can_have_a_different_value(data_dir):
    security.set_password("abcd", security.ADMIN)
    security.set_password("9876", security.WORKER)

    assert security.check_password("abcd", security.ADMIN) is True
    assert security.check_password("9876", security.WORKER) is True
    assert security.check_password("9876", security.ADMIN) is False
    assert security.check_password("abcd", security.WORKER) is False


def test_no_restrictions_on_the_new_password(data_dir):
    for value in ("a", "", "  ", "1", "una contrasenya llarga amb espais", "!@#$%^&*()", "ÀÉÍÒÚ"):
        security.set_password(value, security.WORKER)
        assert security.check_password(value, security.WORKER) is True


def test_passwords_are_never_stored_in_plain_text(data_dir):
    security.set_password("secret-admin", security.ADMIN)
    security.set_password("secret-treball", security.WORKER)
    raw = (data_dir / "settings.json").read_text(encoding="utf-8")

    assert "secret-admin" not in raw
    assert "secret-treball" not in raw
    stored = json.loads(raw)
    for scope in security.SCOPES:
        assert sorted(stored[scope]) == ["hash", "iterations", "salt"]
        assert len(stored[scope]["hash"]) == 64
    # i són dues credencials diferents de debò
    assert stored[security.ADMIN] != stored[security.WORKER]


def test_passwords_survive_a_restart(data_dir):
    security.set_password("abcd", security.ADMIN)
    settings.init(data_dir)  # com si es tornés a obrir l'aplicació
    assert security.check_password("abcd", security.ADMIN) is True


def test_passwords_from_previous_versions_still_work(data_dir):
    """Qui ja hagués canviat una contrasenya amb les claus d'abans no la
    perd: la de còpies passa a ser la d'administrador i la de materials, la
    de treballador."""
    security.set_password("antiga", security.ADMIN)
    stored = settings.get(security.ADMIN)
    settings.set_value("password_backup", stored)      # com ho desava la versió anterior
    settings.set_value("password_materials", stored)
    settings.set_value(security.ADMIN, None)
    settings.set_value(security.WORKER, None)

    assert security.check_password("antiga", security.ADMIN) is True
    assert security.check_password("antiga", security.WORKER) is True

    # i en canviar-ne una, l'altra es queda com estava
    security.set_password("nomes-treballador", security.WORKER)
    assert security.check_password("nomes-treballador", security.WORKER) is True
    assert security.check_password("antiga", security.ADMIN) is True


def test_the_oldest_single_password_still_works(data_dir):
    """I la d'encara més enrere, quan només n'hi havia una per a tot."""
    security.set_password("unica", security.ADMIN)
    settings.set_value("password", settings.get(security.ADMIN))
    settings.set_value(security.ADMIN, None)

    assert security.check_password("unica", security.ADMIN) is True
    assert security.check_password("unica", security.WORKER) is True


def test_unknown_scope_is_an_error(data_dir):
    with pytest.raises(ValueError):
        security.check_password("1234", "no-existeix")
    with pytest.raises(ValueError):
        security.set_password("x", "no-existeix")
