import os
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

pool = ConnectionPool(
    DATABASE_URL,
    min_size=1,
    max_size=5,
    check=ConnectionPool.check_connection,
    open=True,
)


def init_db():
    with pool.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS indicators_metadata (
                code             TEXT PRIMARY KEY,
                name             TEXT,
                description      TEXT,
                category         TEXT,
                unit             TEXT,
                higher_is_better BOOLEAN,
                last_updated     TIMESTAMP,
                coverage         JSONB
            )
        """)
        conn.execute("""
            ALTER TABLE indicators_metadata
            ADD COLUMN IF NOT EXISTS coverage JSONB
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS indicator_cache (
                indicator_code TEXT,
                country_code   TEXT,
                year           INTEGER,
                value          REAL,
                value_text     TEXT,
                cached_at      TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (indicator_code, country_code, year)
            )
        """)
        conn.execute("""
            ALTER TABLE indicator_cache
            ADD COLUMN IF NOT EXISTS value_text TEXT
        """)
        conn.commit()
