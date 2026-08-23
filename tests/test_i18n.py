import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import i18n


def teardown_function(_):
    # evita que un test deixi l'idioma canviat per als següents
    i18n._state["lang"] = i18n.DEFAULT_LANG
    i18n._settings_path = None


def test_default_language_is_catalan():
    assert i18n.get_language() == "ca"


def test_set_language_changes_translations():
    i18n.set_language("es")
    assert i18n.t("tab.board") == "Tablero"
    i18n.set_language("en")
    assert i18n.t("tab.board") == "Board"
    i18n.set_language("fr")
    assert i18n.t("tab.board") == "Tableau"
    i18n.set_language("ca")
    assert i18n.t("tab.board") == "Tauler"


def test_set_language_rejects_unknown_code():
    import pytest

    with pytest.raises(ValueError):
        i18n.set_language("de")


def test_all_translation_entries_cover_the_four_languages():
    expected = set(i18n.LANGS.keys())
    assert expected == {"ca", "es", "en", "fr"}
    incomplete = {k: v for k, v in i18n.TRANSLATIONS.items() if set(v.keys()) != expected}
    assert incomplete == {}


def test_t_with_placeholders():
    i18n.set_language("es")
    text = i18n.t("position.title", position=5)
    assert text == "Posición 5"


def test_t_unknown_key_returns_key_itself():
    assert i18n.t("clau.que.no.existeix") == "clau.que.no.existeix"


def test_persists_language_choice(tmp_path):
    i18n.init_settings_path(tmp_path)
    i18n.set_language("es")
    assert (tmp_path / "settings.json").exists()

    # simula un nou arrencada: reinicia l'estat i torna a carregar
    i18n._state["lang"] = i18n.DEFAULT_LANG
    i18n.init_settings_path(tmp_path)
    assert i18n.get_language() == "es"
