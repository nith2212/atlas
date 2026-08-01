"""
Cache-aside service for indicator data.
Checks indicator_cache first; on miss, fetches from WHO API and stores result.
"""

import requests
from datetime import datetime, timezone
from database.postgres import pool
from config import WHO_BASE_URL

AGGREGATE_DIM1 = {None, "BTSX", "SEX_BTSX", "TOTL", "RESIDENCEAREATYPE_TOTL", "BOTH"}


def _fetch_from_who(indicator_code: str) -> list[tuple]:
    """Fetches all country/year rows for an indicator from WHO API using pagination."""
    url = f"{WHO_BASE_URL}/{indicator_code}"
    base_filter = "SpatialDimType eq 'COUNTRY' and TimeDim ge 2015"
    page_size = 1000
    skip = 0
    rows = []

    while True:
        resp = requests.get(url, params={
            "$filter": base_filter,
            "$top": page_size,
            "$skip": skip,
        }, timeout=30)
        resp.raise_for_status()
        page = resp.json().get("value", [])
        if not page:
            break
        for row in page:
            val = row.get("NumericValue")
            if val is None:
                continue
            if row.get("Dim1") not in AGGREGATE_DIM1:
                continue
            try:
                rows.append((
                    indicator_code,
                    row["SpatialDim"],
                    int(row["TimeDim"]),
                    float(val),
                ))
            except (ValueError, TypeError):
                continue
        skip += page_size

    return rows


def _store_in_cache(rows: list[tuple]):
    with pool.connection() as conn:
        conn.executemany("""
            INSERT INTO indicator_cache (indicator_code, country_code, year, value, cached_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (indicator_code, country_code, year) DO NOTHING
        """, [(r[0], r[1], r[2], r[3], datetime.now(timezone.utc)) for r in rows])
        conn.commit()


def is_cached(indicator_code: str) -> bool:
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM indicator_cache WHERE indicator_code = %s LIMIT 1",
            (indicator_code,)
        ).fetchone()
    return row is not None


def get_or_fetch(indicator_code: str) -> list[dict]:
    """
    Returns all rows for an indicator from cache.
    If not cached, fetches from WHO API, stores, then returns.
    """
    if not is_cached(indicator_code):
        print(f"[cache miss] Fetching {indicator_code} from WHO API...")
        rows = _fetch_from_who(indicator_code)
        _store_in_cache(rows)
        print(f"[cache] Stored {len(rows)} rows for {indicator_code}")

    with pool.connection() as conn:
        rows = conn.execute("""
            SELECT country_code, year, value
            FROM indicator_cache
            WHERE indicator_code = %s
            ORDER BY country_code, year
        """, (indicator_code,)).fetchall()

    return [{"country_code": r[0], "year": r[1], "value": r[2]} for r in rows]


def get_value(indicator_code: str, country_code: str, year: int) -> float | None:
    """Single value lookup — used by tools that need one specific data point."""
    with pool.connection() as conn:
        row = conn.execute("""
            SELECT value FROM indicator_cache
            WHERE indicator_code = %s AND country_code = %s AND year = %s
        """, (indicator_code, country_code.upper(), year)).fetchone()
    return row[0] if row else None
