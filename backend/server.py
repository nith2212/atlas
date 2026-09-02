"""
MCP tools server — 4 composite analytical tools + 1 search tool.
Tools accept natural language indicator names — WHO code resolution happens
internally so the LLM never has to remember opaque identifiers.
"""

import sys
import json
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
from mcp.server.fastmcp import FastMCP
from database.postgres import pool, init_db
from services.metadata_service import (
    search_indicators as _search_indicators,
    resolve_indicator,
    list_categories,
)
from services.cache_service import get_indicator_value as _get_indicator_value, get_or_fetch, get_coverage
from services.health_service import (
    get_global_distribution,
    health_percentile,
    distribution_stats,
    classify_trend,
)

mcp = FastMCP("atlas")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def query_cache(indicator_code: str, filters: dict = {}) -> tuple[list[dict], str | None]:
    """
    Queries indicator_cache with filters.
    For single-year lookups: falls back to nearest year (±2) if exact year missing.
    Returns (rows, warning) where warning describes any fallback or missing reason.
    """
    conditions = ["indicator_code = %s", "country_code != '__NOCOVERAGE__'"]
    params = [indicator_code]

    country = filters.get("country_code")
    year    = filters.get("year")

    if country:
        conditions.append("country_code = %s")
        params.append(country)
    if "year_between" in filters:
        conditions.append("year BETWEEN %s AND %s")
        params.extend(filters["year_between"])
    if year:
        conditions.append("year = %s")
        params.append(year)

    order = filters.get("order", "country_code, year")
    limit = filters.get("limit")
    sql   = f"SELECT country_code, year, value FROM indicator_cache WHERE {' AND '.join(conditions)} ORDER BY {order}"
    if limit:
        sql += f" LIMIT {limit}"

    with pool.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    result = [{"country_code": r[0], "year": r[1], "value": r[2]} for r in rows]

    # Nearest-year fallback for single country+year lookups
    if not result and country and year and "year_between" not in filters:
        coverage = get_coverage(indicator_code)
        if coverage and coverage["country_count"] == 0:
            return [], "no_data_for_indicator"
        if coverage and country not in coverage.get("countries", []):
            return [], "no_data_for_country"

        # Try ±2 years
        for delta in [1, -1, 2, -2]:
            fallback_year = year + delta
            with pool.connection() as conn:
                row = conn.execute("""
                    SELECT country_code, year, value FROM indicator_cache
                    WHERE indicator_code = %s AND country_code = %s AND year = %s
                """, (indicator_code, country, fallback_year)).fetchone()
            if row:
                return [
                    {"country_code": row[0], "year": row[1], "value": row[2],
                     "note": f"{year} not available, showing {row[1]}"}
                ], f"year_fallback:{row[1]}"

        return [], "no_data_for_year"

    return result, None


async def resolve_and_fetch(indicator_name: str) -> tuple[dict, str] | tuple[None, str]:
    """Resolve natural language name → meta dict. Fetch into cache if needed. Returns (meta, error)."""
    meta = resolve_indicator(indicator_name)
    if not meta:
        return None, f"No indicator found matching '{indicator_name}'. Try search_indicators to explore."
    await get_or_fetch(meta["code"])
    return meta, None


# ---------------------------------------------------------------------------
# Tool 1: get_country_health_profile
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_country_health_profile(country_code: str, year: int, indicators: list[str]) -> str:
    """
    Returns a health profile for a country in a given year.
    'indicators' is a list of plain English names e.g. ["life expectancy", "air pollution"].
    For each indicator: value, unit, health-adjusted global percentile.
    Identifies the strongest and weakest indicators by percentile.
    """
    country = country_code.upper()
    metrics = []
    health_percentiles = {}
    indicator_names = {}

    for ind_name in indicators:
        meta, err = await resolve_and_fetch(ind_name)
        if err:
            metrics.append({"indicator": ind_name, "missing": True, "reason": err})
            continue

        rows, warning = query_cache(meta["code"], {"country_code": country, "year": year})
        if not rows:
            metrics.append({"indicator": meta["name"], "missing": True, "reason": warning or "no_data"})
            continue

        value = rows[0]["value"]
        dist  = get_global_distribution(meta["code"], year)
        hp    = health_percentile(value, dist, meta["higher_is_better"])
        health_percentiles[meta["code"]] = hp
        indicator_names[meta["code"]] = meta["name"]

        entry = {
            "indicator":         meta["code"],
            "label":             meta["name"],
            "value":             round(value, 2),
            "unit":              meta["unit"],
            "health_percentile": hp,
            "missing":           False,
        }
        if rows[0].get("note"):
            entry["note"] = rows[0]["note"]
        metrics.append(entry)

    best  = max(health_percentiles, key=health_percentiles.get) if health_percentiles else None
    worst = min(health_percentiles, key=health_percentiles.get) if health_percentiles else None

    return json.dumps({
        "type":                "profile",
        "country":             country,
        "year":                year,
        "metrics":             metrics,
        "strongest_indicator": indicator_names.get(best),
        "weakest_indicator":   indicator_names.get(worst),
    })


# ---------------------------------------------------------------------------
# Tool 2: get_indicator_value
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_indicator_value(indicator: str, country_code: str, year: int) -> str:
    """Returns a categorical indicator value for one country and year.
    Use this for yes/no or status indicators such as program implementation.
    Numeric indicators should use the profile, comparison, ranking, or trend tools.
    """
    meta, err = await resolve_and_fetch(indicator)
    if err:
        return json.dumps({"type": "error", "message": err})

    row = _get_indicator_value(meta["code"], country_code, year)
    if not row:
        return json.dumps({
            "type": "error",
            "message": f"No data for {meta['name']} in {country_code.upper()} ({year}).",
        })
    if row["value_text"] is None:
        return json.dumps({
            "type": "error",
            "message": f"{meta['name']} is numeric; use a numeric data tool instead.",
        })

    return json.dumps({
        "type": "categorical_result",
        "indicator": meta["name"],
        "indicator_code": meta["code"],
        "country": row["country_code"],
        "year": row["year"],
        "value": row["value_text"],
    })


# ---------------------------------------------------------------------------
# Tool 2: compare_countries
# ---------------------------------------------------------------------------

@mcp.tool()
async def compare_countries(country_a: str, country_b: str, year: int, indicators: list[str]) -> str:
    """
    Compares two countries across specified indicators for a given year.
    'indicators' is a list of plain English names e.g. ["obesity", "life expectancy"].
    Returns values, percentiles, gap, and which country leads for each indicator.
    """
    ca, cb = country_a.upper(), country_b.upper()
    comparisons = []
    gaps = {}
    indicator_names = {}

    for ind_name in indicators:
        meta, err = await resolve_and_fetch(ind_name)
        if err:
            comparisons.append({"indicator": ind_name, "missing": True, "reason": err})
            continue

        rows_a, warn_a = query_cache(meta["code"], {"country_code": ca, "year": year})
        rows_b, warn_b = query_cache(meta["code"], {"country_code": cb, "year": year})
        val_a = rows_a[0]["value"] if rows_a else None
        val_b = rows_b[0]["value"] if rows_b else None

        if val_a is None or val_b is None:
            comparisons.append({
                "indicator":   meta["name"],
                "resolved_as": meta["code"],
                "missing":     True,
                "reason_a":    warn_a,
                "reason_b":    warn_b,
                ca:            round(val_a, 2) if val_a is not None else None,
                cb:            round(val_b, 2) if val_b is not None else None,
            })
            continue

        note_a = rows_a[0].get("note") if rows_a else None
        note_b = rows_b[0].get("note") if rows_b else None

        dist   = get_global_distribution(meta["code"], year)
        hp_a = health_percentile(val_a, dist, meta["higher_is_better"])
        hp_b = health_percentile(val_b, dist, meta["higher_is_better"])
        diff = round(abs(val_a - val_b), 2)
        gaps[meta["code"]] = diff
        indicator_names[meta["code"]] = meta["name"]
        leader = ca if (val_a > val_b) == meta["higher_is_better"] else cb

        entry = {
            "indicator":  meta["code"],
            "label":      meta["name"],
            "unit":       meta["unit"],
            "missing":    False,
            ca:           {"value": round(val_a, 2), "health_percentile": hp_a},
            cb:           {"value": round(val_b, 2), "health_percentile": hp_b},
            "difference": diff,
            "leader":     leader,
        }
        if note_a: entry[f"note_{ca}"] = note_a
        if note_b: entry[f"note_{cb}"] = note_b
        comparisons.append(entry)

    largest_gap_code = max(gaps, key=gaps.get) if gaps else None
    return json.dumps({
        "type":                  "comparison",
        "countries":             [ca, cb],
        "year":                  year,
        "comparisons":           comparisons,
        "largest_gap_indicator": indicator_names.get(largest_gap_code),
    })


# ---------------------------------------------------------------------------
# Tool 3: get_health_trend
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_health_trend(country_code: str, indicator: str, start_year: int, end_year: int) -> str:
    """
    Returns a time-series trend for a country and indicator over a year range.
    'indicator' is a plain English name e.g. "life expectancy".
    Computes overall % change, year-over-year changes, best/worst outcome year,
    and classifies the trend as improving/declining/volatile/stable/insufficient_data.
    """
    country = country_code.upper()
    meta, err = await resolve_and_fetch(indicator)
    if err:
        return json.dumps({"type": "error", "message": err})

    rows, _ = query_cache(meta["code"], {
        "country_code": country,
        "year_between": (start_year, end_year),
        "order": "year ASC",
    })

    if not rows:
        return json.dumps({"type": "error", "message": f"No data for {meta['name']} in {country} ({start_year}–{end_year})."})

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
    best_outcome_year  = (max if hib else min)(points, key=lambda p: p["value"])["year"]
    worst_outcome_year = (min if hib else max)(points, key=lambda p: p["value"])["year"]

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
async def rank_countries_by_indicator(indicator: str, year: int, limit: int = 10) -> str:
    """
    Ranks the top N countries by best health outcome for a given indicator and year.
    'indicator' is a plain English name e.g. "hospital bed density".
    """
    meta, err = await resolve_and_fetch(indicator)
    if err:
        return json.dumps({"type": "error", "message": err})

    dist = get_global_distribution(meta["code"], year)
    if not dist:
        return json.dumps({"type": "error", "message": f"No data for {meta['name']} in {year}."})

    rows, _ = query_cache(meta["code"], {
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
def search_indicators(query: str, category: str | None = None) -> str:
    """
    Searches the WHO indicator catalog by name.
    Optional category scope narrows to a metadata bucket like 'Health status' or 'Risk factors'.
    Use this only when the user wants to explore what indicators are available.
    """
    results = _search_indicators(query, category=category)
    if not results:
        return json.dumps({"type": "error", "message": f"No indicators found matching '{query}'"})
    return json.dumps({"type": "indicator_search", "query": query, "category": category, "results": results})


@mcp.tool()
def browse_categories() -> str:
    """Lists the category buckets in the WHO catalog and how many indicators sit in each."""
    categories = list_categories()
    if not categories:
        return json.dumps({"type": "error", "message": "No indicator categories are available yet."})
    return json.dumps({"type": "category_browser", "categories": categories})


if __name__ == "__main__":
    init_db()
    mcp.run(transport="stdio")
