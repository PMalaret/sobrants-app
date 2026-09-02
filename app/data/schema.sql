-- Esquema de la base de dades de SobrantsApp
-- Substitueix el llibre SobrantsV4.74.xlsm conservant el mateix model de dades:
--   materials   <- fulla "Materials" (catàleg codi -> descripció)
--   pieces      <- fulla "llista" (font de veritat; "Entrades" era una còpia redundant, s'omet)
--   historic    <- fulla "històric" (auditoria append-only)
--   desmagatzem <- fulla "desmagatzem" (registre de retirada per carro/lot)

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS materials (
    code        INTEGER PRIMARY KEY,
    description TEXT NOT NULL
);

-- Una peça física emmagatzemada en una posició (1..61).
-- Cada posició admet fins a 5 peces (slot 1..5), igual que L12:O16 a l'Excel original.
CREATE TABLE IF NOT EXISTS pieces (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    position      INTEGER NOT NULL,
    slot          INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 5),
    material_code INTEGER,            -- NULL = slot buit. 1 = material no registrat (text lliure)
    material_desc TEXT,               -- descripció en caché (catàleg, o text lliure si material_code = 1)
    dimensions    TEXT,
    notes         TEXT,
    entered_at    TEXT,               -- ISO datetime; només s'omple si material_code > 1 (igual que l'original)
    UNIQUE (position, slot)
);
CREATE INDEX IF NOT EXISTS idx_pieces_position ON pieces(position);
CREATE INDEX IF NOT EXISTS idx_pieces_material ON pieces(material_code);

-- Registre d'auditoria append-only (mai s'edita ni s'esborra des de la UI).
CREATE TABLE IF NOT EXISTS historic (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    position      TEXT NOT NULL,      -- número de posició, o "Desmagatzem" per a moviments d'aquest mòdul
    material_code TEXT,
    material_desc TEXT,
    ts            TEXT NOT NULL,      -- ISO datetime
    direction     INTEGER,            -- 1 = entrada, -1 = sortida, NULL si kind és move_*
    kind          TEXT NOT NULL CHECK (kind IN ('in','out','move_out','move_in')),
    dimensions    TEXT,               -- mides de la peça en aquell moment
    notes         TEXT                -- notes de la peça (a Desmagatzem, el carro/lot)
);
CREATE INDEX IF NOT EXISTS idx_historic_ts ON historic(ts);
CREATE INDEX IF NOT EXISTS idx_historic_position ON historic(position);

-- Registre de "desemmagatzematge" per carro/lot (fulla "desmagatzem").
CREATE TABLE IF NOT EXISTS desmagatzem (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    row_order     INTEGER NOT NULL,   -- ordre visual (equivalent a la compactació "Apilar")
    quantity      INTEGER NOT NULL DEFAULT 0,
    material_code TEXT,               -- pot ser "1" (no registrat) o buit
    material_desc TEXT,
    custom_text   TEXT,               -- text lliure quan material_code = 1 (columna Z original)
    dimensions    TEXT,
    cart_ref      TEXT,               -- referència de carro/lot (columna "notes" original)
    ts            TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
