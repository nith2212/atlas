"""
Query helpers for indicators_metadata.
"""

import difflib
from collections import Counter
from database.postgres import pool
from config import INDICATOR_ALIASES

FUZZY_CUTOFF = 0.72


def summarize_categories(rows: list[tuple] | list[dict] | None) -> list[dict]:
    """Convert raw category rows into sorted category summaries."""
    if not rows:
        return []

    counts: Counter[str] = Counter()
    for row in rows:
        if isinstance(row, dict):
            category = row.get("category") or row.get("Category")
        else:
            category = row[0] if len(row) > 0 else None

        if category is None:
            continue
        category = str(category).strip()
        if not category:
            continue
        counts[category] += 1

    return [
        {"category": category, "count": count}
        for category, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def list_categories(limit: int = 20) -> list[dict]:
    """Browse indicator categories by volume."""
    with pool.connection() as conn:
        rows = conn.execute("""
            SELECT category, COUNT(*)
            FROM indicators_metadata
            WHERE category IS NOT NULL AND TRIM(category) != ''
            GROUP BY category
            ORDER BY COUNT(*) DESC, category
            LIMIT %s
        """, (limit,)).fetchall()
    return [{"category": r[0], "count": r[1]} for r in rows]


def search_indicators(query: str, limit: int = 5, category: str | None = None) -> list[dict]:
    """Full-text search on indicator name using ILIKE, optionally scoped to a category."""
    sql = """
        SELECT code, name, category, unit
        FROM indicators_metadata
        WHERE name ILIKE %s
    """
    params: list[object] = [f"%{query}%"]

    if category:
        sql += " AND category = %s"
        params.append(category)

    sql += " ORDER BY name LIMIT %s"
    params.append(limit)

    with pool.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [{"code": r[0], "name": r[1], "category": r[2], "unit": r[3]} for r in rows]


def get_indicator_details(code: str) -> dict | None:
    """Return the catalog metadata needed by the indicator detail view."""
    with pool.connection() as conn:
        row = conn.execute("""
            SELECT code, name, description, category, unit
            FROM indicators_metadata
            WHERE code = %s
        """, (code,)).fetchone()
    if not row:
        return None
    return {
        "code": row[0],
        "name": row[1],
        "description": row[2] or "No description is available for this indicator.",
        "category": row[3],
        "unit": row[4] or "Not specified",
    }


def _row_to_meta(row) -> dict:
    return {
        "code":             row[0],
        "name":             row[1],
        "unit":             row[2] or "",
        "higher_is_better": row[3] if row[3] is not None else True,
    }


def _fetch_by_code(conn, code: str) -> dict | None:
    row = conn.execute(
        "SELECT code, name, unit, higher_is_better FROM indicators_metadata WHERE code = %s",
        (code,),
    ).fetchone()
    return _row_to_meta(row) if row else None


def _fuzzy_match(conn, name: str) -> dict | None:
    """Falls back to closest-name matching when substring search finds nothing."""
    rows = conn.execute("SELECT code, name, unit, higher_is_better FROM indicators_metadata").fetchall()
    names = [r[1] for r in rows]
    close = difflib.get_close_matches(name, names, n=1, cutoff=FUZZY_CUTOFF)
    if not close:
        return None
    match = next(r for r in rows if r[1] == close[0])
    return _row_to_meta(match)


def resolve_indicator(name: str) -> dict | None:
    """
    Finds the best matching indicator from metadata by natural language name.
    Resolution order:
      0. Curated alias override (exact phrase match, case-insensitive)
      1. Substring search, ranked by:
         a. Exact name match
         b. Word boundary match (query term appears as a whole word)
         c. Has cached data (tie-break only among equally relevant matches)
         d. higher_is_better is known (not NULL)
         e. Shortest name
         f. Alphabetical
      2. Fuzzy closest-name match (only if substring search finds nothing)
    """
    alias_code = INDICATOR_ALIASES.get(name.strip().lower())
    if alias_code:
        with pool.connection() as conn:
            meta = _fetch_by_code(conn, alias_code)
        if meta:
            return meta

    with pool.connection() as conn:
        row = conn.execute("""
            SELECT m.code, m.name, m.unit, m.higher_is_better
            FROM indicators_metadata m
            WHERE m.name ILIKE %s
            ORDER BY
                CASE WHEN LOWER(m.name) = LOWER(%s) THEN 0 ELSE 1 END,
                CASE WHEN m.name ~* ('\\m' || %s || '\\M') THEN 0 ELSE 1 END,
                CASE WHEN EXISTS(
                    SELECT 1 FROM indicator_cache c WHERE c.indicator_code = m.code LIMIT 1
                ) THEN 0 ELSE 1 END,
                CASE WHEN m.higher_is_better IS NOT NULL THEN 0 ELSE 1 END,
                LENGTH(m.name),
                m.name
            LIMIT 1
        """, (f"%{name}%", name, name)).fetchone()

        if row:
            return _row_to_meta(row)

        return _fuzzy_match(conn, name)
