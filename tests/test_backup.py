import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backup import (
    DEFAULT_KEEP_BACKUPS,
    DEFAULT_PREFIX,
    backup_name,
    create_backup,
    list_backups,
    rotate_backups,
    run_backup,
    sanitize_prefix,
)


def test_create_backup_copies_file(tmp_path):
    db = tmp_path / "sobrants.db"
    db.write_text("dummy content")

    dest = create_backup(db, tmp_path / "Backups")
    assert dest.exists()
    assert dest.read_text() == "dummy content"


def test_backup_name_starts_with_the_timestamp(tmp_path):
    when = datetime(2026, 8, 30, 19, 35)
    assert backup_name("Backup", when) == "202608301935_Backup.db"
    assert backup_name("CopiaAlmacen", when) == "202608301935_CopiaAlmacen.db"
    # dos dígits sempre, i ordenar pel nom = ordenar per data
    names = [
        backup_name("Backup", datetime(2026, 8, 30, 12, 0)),
        backup_name("Backup", datetime(2026, 8, 30, 15, 30)),
        backup_name("Backup", datetime(2026, 8, 31, 10, 15)),
        backup_name("Backup", datetime(2026, 9, 1, 9, 5)),
    ]
    assert names == sorted(names)
    assert names[-1] == "202609010905_Backup.db"


def test_sanitize_prefix_removes_problematic_characters():
    assert sanitize_prefix("Copia/Seguretat") == "CopiaSeguretat"
    assert sanitize_prefix(r"a:b\c*d?") == "abcd"
    assert sanitize_prefix("   ") == DEFAULT_PREFIX
    assert sanitize_prefix("") == DEFAULT_PREFIX


def test_backup_never_overwrites_a_previous_one(tmp_path):
    db = tmp_path / "sobrants.db"
    db.write_text("dades")
    backups = tmp_path / "Backups"

    first = create_backup(db, backups)
    second = create_backup(db, backups)   # dins del mateix minut

    assert first != second
    assert first.exists() and second.exists()
    assert second.name.endswith("-2.db")


def test_run_backup_makes_a_second_copy_on_the_usb(tmp_path):
    db = tmp_path / "sobrants.db"
    db.write_text("dades")
    usb = tmp_path / "USB"
    usb.mkdir()

    result = run_backup(db, tmp_path / "Backups", "Backup", usb_root=usb)

    assert result.ok and result.duplicated
    assert result.main_path.exists() and result.usb_path.exists()
    assert result.main_path.name == result.usb_path.name
    assert result.main_path.read_bytes() == result.usb_path.read_bytes() == b"dades"
    assert not result.usb_error


def test_run_backup_without_usb_still_works(tmp_path):
    db = tmp_path / "sobrants.db"
    db.write_text("dades")

    result = run_backup(db, tmp_path / "Backups", "Backup", usb_root=None)

    assert result.ok
    assert not result.duplicated
    assert not result.usb_error and not result.errors


def test_run_backup_reports_a_failing_usb_but_keeps_the_main_copy(tmp_path):
    db = tmp_path / "sobrants.db"
    db.write_text("dades")
    # un fitxer on hauria d'anar la carpeta del USB: no s'hi pot escriure
    fake_usb = tmp_path / "usb-desconnectat"
    fake_usb.write_text("no soc una carpeta")

    result = run_backup(db, tmp_path / "Backups", "Backup", usb_root=fake_usb)

    assert result.ok               # la principal s'ha fet igualment
    assert not result.duplicated   # i NO es diu que estigui duplicada
    assert result.usb_error


def test_run_backup_reports_a_failing_destination(tmp_path):
    db = tmp_path / "sobrants.db"
    db.write_text("dades")
    blocked = tmp_path / "no-es-una-carpeta"
    blocked.write_text("x")

    result = run_backup(db, blocked, "Backup")

    assert not result.ok
    assert result.errors


def test_rotate_backups_keeps_only_last_n(tmp_path):
    backups_dir = tmp_path / "Backups"
    backups_dir.mkdir()
    for i in range(15):
        f = backups_dir / f"20260830{i:02d}00_Backup.db"
        f.write_text("x")
        time.sleep(0.001)

    rotate_backups(backups_dir, keep=10)
    remaining = sorted(p.name for p in backups_dir.glob("*.db"))
    assert len(remaining) == 10
    assert remaining[0] == "202608300500_Backup.db"
    assert remaining[-1] == "202608301400_Backup.db"


def test_rotation_only_touches_our_own_backups(tmp_path):
    backups_dir = tmp_path / "Backups"
    backups_dir.mkdir()
    other = backups_dir / "una-altra-base-de-dades.db"
    other.write_text("no es meva")
    for i in range(15):
        (backups_dir / f"20260830{i:02d}00_Backup.db").write_text("x")
        time.sleep(0.001)

    rotate_backups(backups_dir, keep=10)

    assert other.exists()   # no se l'emporta la rotació
    assert len(list(backups_dir.glob("2026*.db"))) == 10


def test_old_style_backups_are_still_rotated(tmp_path):
    backups_dir = tmp_path / "Backups"
    backups_dir.mkdir()
    for i in range(30):
        (backups_dir / f"Backup_20260830_1200{i:02d}.db").write_text("x")
        time.sleep(0.001)

    rotate_backups(backups_dir, keep=DEFAULT_KEEP_BACKUPS)
    assert len(list(backups_dir.glob("Backup_*.db"))) == DEFAULT_KEEP_BACKUPS


def test_default_limit_is_25(tmp_path):
    db = tmp_path / "sobrants.db"
    db.write_text("dades")
    backups = tmp_path / "Backups"
    for i in range(25):
        backups.mkdir(exist_ok=True)
        (backups / f"2026083012{i:02d}_Backup.db").write_text("vella")

    # amb 25 ja fetes, la 26a n'esborra la més antiga i en deixa 25
    create_backup(db, backups)

    remaining = list_backups(backups)
    assert len(remaining) == DEFAULT_KEEP_BACKUPS == 25
    assert "202608301200_Backup.db" not in [p.name for p in remaining]   # la més vella ha caigut


def test_the_oldest_is_decided_by_the_name_not_by_the_file_date(tmp_path):
    """El nom porta AAAAMMDDHHMM: és el que mana, encara que el fitxer més
    antic del disc sigui un altre."""
    backups = tmp_path / "Backups"
    backups.mkdir()
    # es creen a l'inrevés: el de data més antiga al nom s'escriu l'últim
    for name in ("202609010900_Backup.db", "202608300800_Backup.db"):
        (backups / name).write_text("x")
        time.sleep(0.01)

    assert [p.name for p in list_backups(backups)] == [
        "202608300800_Backup.db",
        "202609010900_Backup.db",
    ]
    rotate_backups(backups, keep=1)
    assert [p.name for p in backups.glob("*.db")] == ["202609010900_Backup.db"]


def test_backups_below_the_limit_are_all_kept(tmp_path):
    db = tmp_path / "sobrants.db"
    db.write_text("dades")
    backups = tmp_path / "Backups"

    for _ in range(3):
        create_backup(db, backups, keep=25)

    assert len(list_backups(backups)) == 3


def test_a_lower_limit_is_applied_on_the_next_backup(tmp_path):
    db = tmp_path / "sobrants.db"
    db.write_text("dades")
    backups = tmp_path / "Backups"
    backups.mkdir()
    for i in range(20):
        (backups / f"2026083012{i:02d}_Backup.db").write_text("vella")

    create_backup(db, backups, keep=10)

    remaining = list_backups(backups)
    assert len(remaining) == 10
    assert remaining[-1].name.endswith("_Backup.db")   # la nova hi és


def test_a_failed_backup_does_not_delete_any_previous_one(tmp_path):
    """Primer es copia i només després es roten: si la còpia peta, no s'ha
    perdut cap de les que ja hi havia."""
    db = tmp_path / "sobrants.db"
    db.write_text("dades")
    backups = tmp_path / "Backups"
    backups.mkdir()
    for i in range(25):
        (backups / f"2026083012{i:02d}_Backup.db").write_text("vella")
    before = {p.name for p in list_backups(backups)}

    db.unlink()   # l'original desapareix: la còpia no es podrà fer
    result = run_backup(db, backups, "Backup", keep=25)

    assert not result.ok
    assert {p.name for p in list_backups(backups)} == before


def test_rotation_does_not_touch_a_usb_that_is_not_connected(tmp_path):
    """Si el destí del USB no existeix, no es toca res (ni s'hi peta)."""
    rotate_backups(tmp_path / "USB-que-no-hi-es" / "SobrantsBackups", keep=1)   # no ha de fallar


def test_the_limit_applies_to_each_destination(tmp_path):
    db = tmp_path / "sobrants.db"
    db.write_text("dades")
    usb = tmp_path / "USB"
    usb.mkdir()
    backups = tmp_path / "Backups"

    for _ in range(4):
        run_backup(db, backups, "Backup", usb_root=usb, keep=2)

    from app.backup import USB_FOLDER

    assert len(list_backups(backups)) == 2
    assert len(list_backups(usb / USB_FOLDER)) == 2
