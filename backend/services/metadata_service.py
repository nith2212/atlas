"""
Query helpers for indicators_metadata.
Used by the search_indicators MCP tool.
"""

from database.postgres import pool


def search_indicators(query: str, limit: int = 20) -> list[dict]:
    """Full-text search on indicator name using ILIKE."""
    with pool.connection() as conn:
        rows = conn.execute("""
            SELECT code, name, category, unit
            FROM indicators_metadata
            WHERE name ILIKE %s
            ORDER BY name
            LIMIT %s
        """, (f"%{query}%", limit)).fetchall()
    return [{"code": r[0], "name": r[1], "category": r[2], "unit": r[3]} for r in rows]


def get_indicator_by_code(code: str) -> dict | None:
    with pool.connection() as conn:
        row = conn.execute("""
            SELECT code, name, category, unit
            FROM indicators_metadata
            WHERE code = %s
        """, (code.upper(),)).fetchone()
    if not row:
        return None
    return {"code": row[0], "name": row[1], "category": row[2], "unit": row[3]}
