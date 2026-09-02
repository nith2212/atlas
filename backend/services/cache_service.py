"""
Cache-aside service for indicator data.
Checks indicator_cache first; on miss, fetches from WHO API and stores result.
Maintains coverage metadata (min_year, max_year, countries) in indicators_metadata.
"""

import json
import httpx
from datetime import datetime, timezone
from database.postgres import pool
from config import WHO_BASE_URL
from services.llm_service import infer_and_store_direction

AGGREGATE_DIM1 = {None, "BTSX", "SEX_BTSX", "TOTL", "RESIDENCEAREATYPE_TOTL", "BOTH"}

# Sentinel value stored when WHO returns 0 rows — prevents infinite re-fetch
_SENTINEL_COUNTRY = "__NOCOVERAGE__"
_SENTINEL_YEAR    = 0


async def _get_with_retry(client: httpx.AsyncClient, url: str, params: dict, timeout: int = 60, attempts: int = 3):
    """GET with retries on transient timeouts — WHO API can be slow on first fetch."""
    last_err = None
    for attempt in range(attempts):
        try:
            resp = await client.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except httpx.TimeoutException as e:
            last_err = e
            print(f"[cache_service] WHO API timeout (attempt {attempt + 1}/{attempts}), retrying...")
    raise last_err


async def _fetch_from_who(indicator_code: str, min_year: int | None = 2015) -> list[tuple]:
    """Fetches all country/year rows for an indicator from WHO API using pagination.
    Async so a slow WHO response doesn't block the MCP server's event loop."""
    url = f"{WHO_BASE_URL}/{indicator_code}"
    base_filter = "SpatialDimType eq 'COUNTRY'"
    if min_year is not None:
        base_filter += f" and TimeDim ge {min_year}"
    page_size = 1000
    skip = 0
    rows = []

    async with httpx.AsyncClient() as client:
        while True:
            resp = await _get_with_retry(client, url, {
                "$filter": base_filter,
                "$top": page_size,
                "$skip": skip,
            })
            page = resp.json().get("value", [])
            if not page:
                break
            for row in page:
                numeric_value = row.get("NumericValue")
                text_value = row.get("Value")
                if numeric_value is None and text_value is None:
                    continue
                if row.get("Dim1") not in AGGREGATE_DIM1:
                    continue
                try:
                    numeric_value = float(numeric_value) if numeric_value is not None else None
                    text_value = (
                        str(text_value).strip()
                        if numeric_value is None and text_value is not None
                        else None
                    )
                    rows.append((
                        indicator_code,
                        row["SpatialDim"],
                        int(row["TimeDim"]),
                        numeric_value,
                        text_value,
                    ))
                except (ValueError, TypeError):
                    continue
            skip += page_size

    return rows


def _store_in_cache(rows: list[tuple]):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO indicator_cache (indicator_code, country_code, year, value, value_text, cached_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (indicator_code, country_code, year) DO NOTHING
            """, [(r[0], r[1], r[2], r[3], r[4], datetime.now(timezone.utc)) for r in rows])
        conn.commit()


def _store_coverage(indicator_code: str, rows: list[tuple]):
    """Compute and store coverage metadata. Stores sentinel if no rows."""
    if not rows:
        # Sentinel: marks indicator as fetched but empty — prevents re-fetch loops
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO indicator_cache (indicator_code, country_code, year, value, cached_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (indicator_code, _SENTINEL_COUNTRY, _SENTINEL_YEAR, 0.0, datetime.now(timezone.utc)))
            conn.commit()
        coverage = {"min_year": None, "max_year": None, "country_count": 0, "countries": []}
    else:
        years     = [r[2] for r in rows]
        countries = sorted(set(r[1] for r in rows))
        coverage  = {
            "min_year":     min(years),
            "max_year":     max(years),
            "country_count": len(countries),
            "countries":    countries,
        }

    with pool.connection() as conn:
        conn.execute(
            "UPDATE indicators_metadata SET coverage = %s WHERE code = %s",
            (json.dumps(coverage), indicator_code),
        )
        conn.commit()


def get_coverage(indicator_code: str) -> dict | None:
    """Returns coverage metadata for an indicator, or None if not yet fetched."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT coverage FROM indicators_metadata WHERE code = %s",
            (indicator_code,)
        ).fetchone()
    if not row or row[0] is None:
        return None
    return row[0] if isinstance(row[0], dict) else json.loads(row[0])


def is_cached(indicator_code: str) -> bool:
    """Returns True if indicator has been fetched (including sentinel for empty indicators)."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM indicator_cache WHERE indicator_code = %s LIMIT 1",
            (indicator_code,)
        ).fetchone()
    return row is not None


async def get_or_fetch(indicator_code: str) -> list[dict]:
    """
    Ensures indicator data is in cache. Fetches from WHO on miss.
    After fetch: stores coverage metadata and infers higher_is_better if NULL.
    """
    if not is_cached(indicator_code):
        print(f"[cache miss] Fetching {indicator_code} from WHO API...")
        rows = await _fetch_from_who(indicator_code)
        if not rows:
            print(f"[cache fallback] No data from {indicator_code} since 2015; fetching historical data...")
            rows = await _fetch_from_who(indicator_code, min_year=None)
        _store_in_cache(rows)
        _store_coverage(indicator_code, rows)
        print(f"[cache] Stored {len(rows)} rows for {indicator_code}")

        with pool.connection() as conn:
            meta = conn.execute(
                "SELECT name, higher_is_better FROM indicators_metadata WHERE code = %s",
                (indicator_code,)
            ).fetchone()
        if meta and meta[1] is None:
            infer_and_store_direction(indicator_code, meta[0])

    with pool.connection() as conn:
        rows = conn.execute("""
            SELECT country_code, year, value, value_text
            FROM indicator_cache
            WHERE indicator_code = %s AND country_code != %s
            ORDER BY country_code, year
        """, (indicator_code, _SENTINEL_COUNTRY)).fetchall()

    return [
        {"country_code": r[0], "year": r[1], "value": r[2], "value_text": r[3]}
        for r in rows
    ]


def get_value(indicator_code: str, country_code: str, year: int) -> float | None:
    """Single value lookup."""
    with pool.connection() as conn:
        row = conn.execute("""
            SELECT value FROM indicator_cache
            WHERE indicator_code = %s AND country_code = %s AND year = %s
        """, (indicator_code, country_code.upper(), year)).fetchone()
    return row[0] if row else None


def get_indicator_value(indicator_code: str, country_code: str, year: int) -> dict | None:
    """Return the cached numeric or categorical value for one country/year."""
    with pool.connection() as conn:
        row = conn.execute("""
            SELECT country_code, year, value, value_text
            FROM indicator_cache
            WHERE indicator_code = %s AND country_code = %s AND year = %s
        """, (indicator_code, country_code.upper(), year)).fetchone()
    if not row:
        return None
    return {
        "country_code": row[0],
        "year": row[1],
        "value": row[2],
        "value_text": row[3],
    }


def get_indicator_data_type(indicator_code: str) -> dict:
    """Describe whether cached rows are numeric or categorical."""
    with pool.connection() as conn:
        numeric_count = conn.execute("""
            SELECT COUNT(*)
            FROM indicator_cache
            WHERE indicator_code = %s
              AND country_code != %s
              AND value IS NOT NULL
        """, (indicator_code, _SENTINEL_COUNTRY)).fetchone()[0]
        rows = conn.execute("""
            SELECT DISTINCT value_text
            FROM indicator_cache
            WHERE indicator_code = %s
              AND country_code != %s
              AND value_text IS NOT NULL
            ORDER BY value_text
        """, (indicator_code, _SENTINEL_COUNTRY)).fetchall()
    values = [row[0] for row in rows]
    return {"data_type": "numeric", "values": []} if numeric_count else {
        "data_type": "categorical" if values else "numeric",
        "values": values,
    }
