"""SQLite Datenbank-Setup und Schema-Initialisierung."""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "cards.db"


def get_connection() -> sqlite3.Connection:
    """Datenbankverbindung mit Row-Factory zurückgeben."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Schema-Migrationen für bestehende Datenbanken."""
    migrations = [
        ("notion_page_id TEXT", "notion_page_id"),
        ("price_grade9 REAL", "price_grade9"),
        ("price_psa10 REAL", "price_psa10"),
    ]
    for col_def, col_name in migrations:
        try:
            conn.execute(f"ALTER TABLE cards ADD COLUMN {col_def}")
            logger.info(f"Migration: {col_name} Spalte hinzugefügt")
        except sqlite3.OperationalError:
            pass  # Spalte existiert bereits


def init_db() -> None:
    """Alle Tabellen anlegen falls sie noch nicht existieren."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cards (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                character       TEXT,
                card_set        TEXT,
                card_type       TEXT NOT NULL,   -- autograph / vintage / numbered / base
                series_year     INTEGER,
                numbered_to     INTEGER,         -- z.B. 99 für /99
                psa_grade       INTEGER,
                avg_price_usd   REAL,
                median_price_usd REAL,
                last_sold_usd   REAL,
                sales_count     INTEGER DEFAULT 0,
                liquidity       TEXT,            -- Hoch / Mittel / Niedrig
                ebay_link       TEXT,
                pricecharting_link TEXT,
                notion_page_id  TEXT,
                last_checked    TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS deals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id         INTEGER REFERENCES cards(id),
                listing_price   REAL NOT NULL,
                market_price    REAL NOT NULL,
                savings_percent REAL NOT NULL,
                ebay_listing_url TEXT NOT NULL,
                ebay_item_id    TEXT UNIQUE,
                status          TEXT DEFAULT 'Neu',  -- Neu / Geprüft / Gekauft / Abgelaufen
                notion_page_id  TEXT,
                telegram_sent   INTEGER DEFAULT 0,
                found_at        TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id     INTEGER REFERENCES cards(id),
                price_usd   REAL NOT NULL,
                sale_date   TEXT,
                source      TEXT DEFAULT 'ebay',
                recorded_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS meta (
                key     TEXT PRIMARY KEY,
                value   TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_cards_character ON cards(character);
            CREATE INDEX IF NOT EXISTS idx_cards_type ON cards(card_type);
            CREATE INDEX IF NOT EXISTS idx_deals_status ON deals(status);
            CREATE INDEX IF NOT EXISTS idx_price_history_card ON price_history(card_id);
        """)

        _run_migrations(conn)

    logger.info(f"Datenbank initialisiert: {DB_PATH}")


def get_meta(key: str) -> str | None:
    """Metadaten-Wert abrufen."""
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_meta(key: str, value: str) -> None:
    """Metadaten-Wert setzen oder aktualisieren."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
