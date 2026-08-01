"""
MCP tools server — exposes 5 analytical tools over stdio.
All data reads from Neon (indicator_cache + indicators_metadata).
SQLite is no longer used.
"""

import json
import statistics
from mcp.server.fastmcp import FastMCP
from database.postgres import pool, init_db
from services.metadata_service import search_indicators as _search_indicators

mcp = FastMCP("atlas")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def query_cache(indicator_code: str, filters: dict = {}) -> list[dict]:
    """Fetch rows from indicator_cache with optional filters."""
    conditions = ["indicator_code = %s"]
    params = [indicator_code]

    if "country_code" in filters:
        conditions.append("country_code = %s")
        params.append(filters["country_code"])
    if "year" in filters:
        conditions.append("year = %s")
        params.append(filters["year"])
    if "year_gte" in filters:
        conditions.append("year >= %s")
        params.append(filters["year_gte"])
    if "year_between" in filters:
        conditions.append("year BETWEEN %s AND %s")
        params.extend(filters["year_between"])

    order = filters.get("order", "country_code, year")
    limit = filters.get("limit")

    sql = f"SELECT country_code, year, value FROM indicator_cache WHERE {' AND '.join(conditions)} ORDER BY {order}"
    if limit:
        sql += f" LIMIT {limit}"

    with pool.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [{"country_code": r[0], "year": r[1], "value": r[2]} for r in rows]


def get_indicator_meta(indicator_code: str) -> dict:
    """Fetch name, unit, higher_is_better from indicators_metadata."""
    with pool.connection() as conn:
        row = conn.execute("""
            SELECT name, unit, higher_is_better
            FROM indicators_metadata WHERE code = %s
        """, (indicator_code,)).fetchone()
    if not row:
        return {"name": indicator_code, "unit": "", "higher_is_better": True}
    return {"name": row[0], "unit": row[1] or "", "higher_is_better": row[2] if row[2] is not None else True}


# ---------------------------------------------------------------------------
# Analytical helpers
# ---------------------------------------------------------------------------

def get_global_distribution(indicator_code: str, year: int) -> list[float]:
    rows = query_cache(indicator_code, {"year": year})
    return [r["value"] for r in rows]


def compute_percentile(value: float, distribution: list[float]) -> float:
    if not distribution:
        return 0.0
    return round(sum(1 for v in distribution if v <= value) / len(distribution) * 100, 1)


def health_percentile(value: float, distribution: list[float], higher_is_better: bool) -> float:
    raw = compute_percentile(value, distribution)
    return raw if higher_is_better else round(100 - raw, 1)


def distribution_stats(values: list[float]) -> dict:
    if not values:
        return {}
    return {
        "mean":   round(statistics.mean(values), 2),
        "median": round(statistics.median(values), 2),
        "min":    round(min(values), 2),
        "max":    round(max(values), 2),
        "stdev":  round(statistics.stdev(values), 2) if len(values) >= 2 else None,
        "n":      len(values),
    }


def classify_trend(points: list[dict], higher_is_better: bool) -> str:
    if len(points) < 4:
        return "insufficient_data"
    changes = [points[i + 1]["value"] - points[i]["value"] for i in range(len(points) - 1)]
    tolerance = abs(points[0]["value"]) * 0.01
    significant = [c for c in changes if abs(c) > tolerance]
    if not significant:
        return "stable"
    direction_changes = sum(
        1 for i in range(len(significant) - 1)
        if significant[i] * significant[i + 1] < 0
    )
    if direction_changes > 1:
        return "volatile"
    value_went_up = significant[-1] > 0
    return "improving" if (value_went_up == higher_is_better) else "declining"


# ---------------------------------------------------------------------------
# Tool 1: get_country_health_profile
# ---------------------------------------------------------------------------

@mcp.tool()
def get_country_health_profile(country_code: str, year: int, indicator_codes: list[str]) -> str:
    """
    Returns a health profile for a country in a given year across specified indicators.
    For each indicator: value, unit, and health-adjusted global percentile.
    Identifies the strongest and weakest indicators by percentile.
    Use search_indicators first if you need to find the right WHO codes.
    """
    country = country_code.upper()
    metrics = []
    health_percentiles = {}

    for code in indicator_codes:
        meta = get_indicator_meta(code)
        rows = query_cache(code, {"country_code": country, "year": year})

        if not rows:
            metrics.append({"indicator": code, "label": meta["name"], "missing": True})
            continue

        value = rows[0]["value"]
        dist = get_global_distribution(code, year)
        hp = health_percentile(value, dist, meta["higher_is_better"])
        health_percentiles[code] = hp

        metrics.append({
            "indicator":         code,
            "label":             meta["name"],
            "value":             round(value, 2),
            "unit":              meta["unit"],
            "health_percentile": hp,
            "missing":           False,
        })

    best  = max(health_percentiles, key=health_percentiles.get) if health_percentiles else None
    worst = min(health_percentiles, key=health_percentiles.get) if health_percentiles else None

    return json.dumps({
        "type":                "profile",
        "country":             country,
        "year":                year,
        "metrics":             metrics,
        "strongest_indicator": best,
        "weakest_indicator":   worst,
    })


# ---------------------------------------------------------------------------
# Tool 2: compare_countries
# ---------------------------------------------------------------------------

@mcp.tool()
def compare_countries(country_a: str, country_b: str, year: int, indicator_codes: list[str]) -> str:
    """
    Compares two countries across specified indicators for a given year.
    For each indicator: both values, absolute difference, which country leads,
    and each country's health-adjusted global percentile.
    Use search_indicators first if you need to find the right WHO codes.
    """
    ca, cb = country_a.upper(), country_b.upper()
    comparisons = []
    gaps = {}

    for code in indicator_codes:
        meta = get_indicator_meta(code)

        rows_a = query_cache(code, {"country_code": ca, "year": year})
        rows_b = query_cache(code, {"country_code": cb, "year": year})

        val_a = rows_a[0]["value"] if rows_a else None
        val_b = rows_b[0]["value"] if rows_b else None

        if val_a is None or val_b is None:
            comparisons.append({
                "indicator": code, "label": meta["name"], "missing": True,
                ca: round(val_a, 2) if val_a is not None else None,
                cb: round(val_b, 2) if val_b is not None else None,
            })
            continue

        dist = get_global_distribution(code, year)
        hp_a = health_percentile(val_a, dist, meta["higher_is_better"])
        hp_b = health_percentile(val_b, dist, meta["higher_is_better"])
        diff = round(abs(val_a - val_b), 2)
        gaps[code] = diff
        leader = ca if (val_a > val_b) == meta["higher_is_better"] else cb

        comparisons.append({
            "indicator":  code,
            "label":      meta["name"],
            "unit":       meta["unit"],
            "missing":    False,
            ca:           {"value": round(val_a, 2), "health_percentile": hp_a},
            cb:           {"value": round(val_b, 2), "health_percentile": hp_b},
            "difference": diff,
            "leader":     leader,
        })

    return json.dumps({
        "type":                  "comparison",
        "countries":             [ca, cb],
        "year":                  year,
        "comparisons":           comparisons,
        "largest_gap_indicator": max(gaps, key=gaps.get) if gaps else None,
    })


# ---------------------------------------------------------------------------
# Tool 3: get_health_trend
# ---------------------------------------------------------------------------

@mcp.tool()
def get_health_trend(country_code: str, indicator_code: str, start_year: int, end_year: int) -> str:
    """
    Returns a time-series trend for a country/indicator over a year range.
    Computes overall % change, year-over-year changes, best/worst outcome year,
    and classifies the trend as improving/declining/volatile/stable/insufficient_data.
    Use search_indicators first if you need to find the right WHO code.
    """
    country = country_code.upper()
    meta = get_indicator_meta(indicator_code)

    rows = query_cache(indicator_code, {
        "country_code": country,
        "year_between": (start_year, end_year),
        "order": "year ASC",
    })

    if not rows:
        return json.dumps({"type": "error", "message": f"No data for {indicator_code} in {country} ({start_year}–{end_year})."})

    points = [{"year": r["year"], "value": r["value"]} for r in rows]
    start_val, end_val = points[0]["value"], points[-1]["value"]
    pct_change = round(((end_val - start_val) / start_val) * 100, 2) if start_val else 0

    yoy = [{
        "from_year": points[i - 1]["year"],
        "to_year":   points[i]["year"],
        "change":    round(points[i]["value"] - points[i - 1]["value"], 2),
        "pct":       round(((points[i]["value"] - points[i - 1]["value"]) / points[i - 1]["value"]) * 100, 2) if points[i - 1]["value"] else 0,
    } for i in range(1, len(points))]

    hib = meta["higher_is_better"]
    best_outcome_year  = (min if not hib else max)(points, key=lambda p: p["value"])["year"]
    worst_outcome_year = (max if not hib else min)(points, key=lambda p: p["value"])["year"]

    return json.dumps({
        "type":               "trend",
        "country":            country,
        "indicator":          meta["name"],
        "unit":               meta["unit"],
        "higher_is_better":   hib,
        "start_year":         start_year,
        "end_year":           end_year,
        "pct_change":         pct_change,
        "trend":              classify_trend(points, hib),
        "best_outcome_year":  best_outcome_year,
        "worst_outcome_year": worst_outcome_year,
        "points":             points,
        "yoy":                yoy,
    })


# ---------------------------------------------------------------------------
# Tool 4: rank_countries_by_indicator
# ---------------------------------------------------------------------------

@mcp.tool()
def rank_countries_by_indicator(indicator_code: str, year: int, limit: int = 10) -> str:
    """
    Ranks the top N countries by best health outcome for a given indicator and year.
    Use search_indicators first if you need to find the right WHO code.
    """
    meta = get_indicator_meta(indicator_code)
    dist = get_global_distribution(indicator_code, year)

    if not dist:
        return json.dumps({"type": "error", "message": f"No data for {indicator_code} in {year}."})

    rows = query_cache(indicator_code, {
        "year":  year,
        "order": f"value {'DESC' if meta['higher_is_better'] else 'ASC'}",
        "limit": limit,
    })

    ranks = [{
        "rank":              i + 1,
        "country":           r["country_code"],
        "value":             round(r["value"], 2),
        "unit":              meta["unit"],
        "health_percentile": health_percentile(r["value"], dist, meta["higher_is_better"]),
    } for i, r in enumerate(rows)]

    return json.dumps({
        "type":             "ranking",
        "indicator":        meta["name"],
        "unit":             meta["unit"],
        "year":             year,
        "higher_is_better": meta["higher_is_better"],
        "ranks":            ranks,
        "global_stats":     distribution_stats(dist),
    })


# ---------------------------------------------------------------------------
# Tool 5: search_indicators
# ---------------------------------------------------------------------------

@mcp.tool()
def search_indicators(query: str) -> str:
    """
    Searches the WHO indicator catalog by name.
    Use this when the user asks about an indicator you don't recognise or
    when you need to discover the correct WHO code for a topic.
    Returns up to 20 matching indicators with their code, name, and unit.
    """
    results = _search_indicators(query)
    if not results:
        return json.dumps({"type": "error", "message": f"No indicators found matching '{query}'"})
    return json.dumps({"type": "indicator_search", "query": query, "results": results})


if __name__ == "__main__":
    init_db()
    mcp.run(transport="stdio")
