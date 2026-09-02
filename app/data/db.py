"""Capa d'accés a la base de dades SQLite (substitueix el llibre .xlsm)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


# Taules que ha de tenir qualsevol base de dades de l'aplicació.
REQUIRED_TABLES = ("materials", "pieces", "historic", "desmagatzem")

# Columnes que s'han afegit a una taula després que hi hagués bases de dades
# al carrer. `CREATE TABLE IF NOT EXISTS` no toca les taules que ja
# existeixen, així que a una base de dades antiga s'hi han d'afegir a mà
# (veure `_add_missing_columns`); a una de nova ja hi són i no es fa res.
ADDED_COLUMNS = {
    "historic": (("dimensions", "TEXT"), ("notes", "TEXT")),
}


class IncompatibleDatabaseError(Exception):
    """El fitxer triat no és una base de dades d'aquesta aplicació."""


def describe_database(db_path: str | Path) -> dict[str, int]:
    """Comprova que el fitxer sigui una base de dades d'aquesta aplicació i
    en retorna quantes files té cada taula.

    Serveix per validar el .db que es vol importar ABANS de tocar res: si
    no és SQLite, si està fet malbé o si li falta alguna taula, llança
    `IncompatibleDatabaseError` i qui l'ha cridat no arriba a substituir
    res. No modifica el fitxer (s'obre en mode només lectura).
    """
    db_path = Path(db_path)
    if not db_path.is_file():
        raise IncompatibleDatabaseError(f"{db_path}")
    try:
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise IncompatibleDatabaseError(str(exc)) from exc
    try:
        existing = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        missing = [table for table in REQUIRED_TABLES if table not in existing]
        if missing:
            raise IncompatibleDatabaseError(", ".join(missing))
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
            for table in REQUIRED_TABLES
        }
    except sqlite3.DatabaseError as exc:   # fitxer corrupte o que no és SQLite
        raise IncompatibleDatabaseError(str(exc)) from exc
    finally:
        conn.close()


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Obre (creant-la si cal) la base de dades i aplica l'esquema.

    `synchronous = FULL` (que és el valor per defecte de SQLite, però aquí
    es deixa escrit expressament perquè no depengui de cap defecte): en
    acabar cada operació, el `commit()` de `Repository._transaction` no
    torna fins que el canvi és de debò al disc. Per això un canvi fet un
    segon abans d'una apagada hi continua sent en tornar a obrir l'app.

    Es manté el journal per defecte (DELETE, no WAL) a posta: així el
    fitxer .db és sencer i coherent entre operacions, que és el que copia
    `app.backup` amb una còpia de fitxer.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = FULL")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _add_missing_columns(conn)
    conn.commit()
    return conn


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    """Afegeix a les taules que ja existien les columnes noves.

    Obrir una base de dades d'una versió anterior de l'aplicació ha de
    seguir funcionant: l'esquema es torna a aplicar sencer a cada
    arrencada, però `CREATE TABLE IF NOT EXISTS` no toca les taules que ja
    hi són, o sigui que les columnes noves s'hi afegeixen aquí. Les files
    que ja hi havia es queden amb la columna nova buida, que és el que
    toca: d'aquelles no en sabem el valor.
    """
    for table, columns in ADDED_COLUMNS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}  # noqa: S608
        for name, kind in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")  # noqa: S608
