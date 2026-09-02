"""
Migrates existing data from SQLite disease_indicators into Neon indicator_cache.
Much faster than re-fetching from WHO API since the data is already local.
Safe to re-run — uses ON CONFLICT DO NOTHING.
"""

import sqlite3
from datetime import datetime, timezone
from database.postgres import pool, init_db
from config import DB_PATH, PRELOAD_INDICATORS

# Map WHO code → internal SQLite indicator_name key
# SQLite stores keys like LIFE_EXPECTANCY, Neon cache stores WHO codes like WHOSIS_000001
SQLITE_KEY_MAP = {
    "WHOSIS_000001": "LIFE_EXPECTANCY",
    "WHS4_100":      "HOSPITAL_BED_DENSITY",
    "NCDMORT3070":   "NCD_MORTALITY_PROB",
    "SDGPM25":       "AIR_POLLUTION_PM25",
}


def run():
    init_db()

    with sqlite3.connect(DB_PATH) as sqlite_conn:
        sqlite_conn.row_factory = sqlite3.Row
        rows = sqlite_conn.execute(
            "SELECT indicator_name, country_code, year, numeric_value FROM disease_indicators"
        ).fetchall()

    print(f"Read {len(rows)} rows from SQLite")

    # Invert map: SQLite key → WHO code
    key_to_code = {v: k for k, v in SQLITE_KEY_MAP.items()}

    batch = []
    skipped = 0
    now = datetime.now(timezone.utc)

    for row in rows:
        code = key_to_code.get(row["indicator_name"])
        if not code:
            skipped += 1
            continue
        batch.append((code, row["country_code"], row["year"], row["numeric_value"], now))

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO indicator_cache (indicator_code, country_code, year, value, cached_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (indicator_code, country_code, year) DO NOTHING
            """, batch)
        conn.commit()

    print(f"Migrated {len(batch)} rows to Neon indicator_cache ({skipped} skipped)")


if __name__ == "__main__":
    run()
