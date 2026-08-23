import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backup import create_backup, rotate_backups


def test_create_backup_copies_file(tmp_path):
    db = tmp_path / "sobrants.db"
    db.write_text("dummy content")

    dest = create_backup(db, tmp_path / "Backups")
    assert dest.exists()
    assert dest.read_text() == "dummy content"


def test_rotate_backups_keeps_only_last_n(tmp_path):
    backups_dir = tmp_path / "Backups"
    backups_dir.mkdir()
    for i in range(15):
        f = backups_dir / f"Backup_{i:02d}.db"
        f.write_text("x")
        time.sleep(0.001)

    rotate_backups(backups_dir, keep=10)
    remaining = list(backups_dir.glob("Backup_*.db"))
    assert len(remaining) == 10
    # Deben quedar los más recientes (índices 5..14)
    names = sorted(p.name for p in remaining)
    assert names[0] == "Backup_05.db"
    assert names[-1] == "Backup_14.db"
