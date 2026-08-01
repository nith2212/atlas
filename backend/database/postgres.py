import os
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=5, open=True)


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
                last_updated     TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS indicator_cache (
                indicator_code TEXT,
                country_code   TEXT,
                year           INTEGER,
                value          REAL,
                cached_at      TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (indicator_code, country_code, year)
            )
        """)
        conn.commit()
