-- Esquema de la base de datos de SobrantsApp
-- Sustituye al libro SobrantsV4.74.xlsm conservando el mismo modelo de datos:
--   materials   <- hoja "Materials" (catálogo código -> descripción)
--   pieces      <- hoja "llista" (fuente de verdad; "Entrades" era una copia redundante, se omite)
--   historic    <- hoja "històric" (auditoría append-only)
--   desmagatzem <- hoja "desmagatzem" (registro de retirada por carro/lote)

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS materials (
    code        INTEGER PRIMARY KEY,
    description TEXT NOT NULL
);

-- Una pieza física almacenada en una posición (1..61).
-- Cada posición admite hasta 5 piezas (slot 1..5), igual que L12:O16 en el Excel original.
CREATE TABLE IF NOT EXISTS pieces (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    position      INTEGER NOT NULL,
    slot          INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 5),
    material_code INTEGER,            -- NULL = slot vacío. 1 = material no registrado (texto libre)
    material_desc TEXT,               -- descripción cacheada (catálogo, o texto libre si material_code = 1)
    dimensions    TEXT,
    notes         TEXT,
    entered_at    TEXT,               -- ISO datetime; sólo se rellena si material_code > 1 (igual que el original)
    UNIQUE (position, slot)
);
CREATE INDEX IF NOT EXISTS idx_pieces_position ON pieces(position);
CREATE INDEX IF NOT EXISTS idx_pieces_material ON pieces(material_code);

-- Registro de auditoría append-only (nunca se edita ni se borra desde la UI).
CREATE TABLE IF NOT EXISTS historic (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    position      TEXT NOT NULL,      -- número de posición, o "Desmagatzem" para movimientos de ese módulo
    material_code TEXT,
    material_desc TEXT,
    ts            TEXT NOT NULL,      -- ISO datetime
    direction     INTEGER,            -- 1 = entrada, -1 = salida, NULL si kind es move_*
    kind          TEXT NOT NULL CHECK (kind IN ('in','out','move_out','move_in'))
);
CREATE INDEX IF NOT EXISTS idx_historic_ts ON historic(ts);
CREATE INDEX IF NOT EXISTS idx_historic_position ON historic(position);

-- Registro de "desalmacenaje" por carro/lote (hoja "desmagatzem").
CREATE TABLE IF NOT EXISTS desmagatzem (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    row_order     INTEGER NOT NULL,   -- orden visual (equivalente a la compactación "Apilar")
    quantity      INTEGER NOT NULL DEFAULT 0,
    material_code TEXT,               -- puede ser "1" (no registrado) o vacío
    material_desc TEXT,
    custom_text   TEXT,               -- texto libre cuando material_code = 1 (columna Z original)
    dimensions    TEXT,
    cart_ref      TEXT,               -- referencia de carro/lote (columna "notes" original)
    ts            TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
