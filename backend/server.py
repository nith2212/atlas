"""
MCP tools server — exposes 4 analytical tools over stdio.
Each tool performs real computation (percentiles, distribution stats, trend
classification) so the LLM receives findings, not raw rows.
"""

import json
import sqlite3
import statistics
from mcp.server.fastmcp import FastMCP
from config import DB_PATH, INDICATORS

mcp = FastMCP("etl-mcp-health")


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def query_db(sql: str, params: tuple = ()):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Analytical helpers
# ---------------------------------------------------------------------------

def get_global_distribution(indicator_name: str, year: int) -> list[float]:
    """Returns all country values for an indicator/year — used for percentile and stats."""
    rows = query_db(
        "SELECT numeric_value FROM disease_indicators WHERE indicator_name = ? AND year = ?",
        (indicator_name.upper(), year),
    )
    return [r["numeric_value"] for r in rows]


def compute_percentile(value: float, distribution: list[float]) -> float:
    """Raw percentile: % of countries with a value <= this one."""
    if not distribution:
        return 0.0
    return round(sum(1 for v in distribution if v <= value) / len(distribution) * 100, 1)


def health_percentile(value: float, distribution: list[float], higher_is_better: bool) -> float:
    """
    Health-adjusted percentile: always higher = healthier.
    For lower_is_better indicators (PM2.5, NCD mortality), raw percentile is inverted
    so a country with very low PM2.5 gets a high health percentile.
    """
    raw = compute_percentile(value, distribution)
    return raw if higher_is_better else round(100 - raw, 1)


def distribution_stats(values: list[float]) -> dict:
    """Mean, median, min, max, stdev computed in Python (SQLite has no STDEV)."""
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
    """
    Classifies a time series as improving / declining / volatile / stable / insufficient_data.

    Rules:
    - Fewer than 4 data points → insufficient_data (slope is not meaningful)
    - Tolerance is fixed at 1% of the first value in the range (global anchor, not per-segment)
      so tiny noise doesn't register as a direction change
    - If no change exceeds the tolerance band → stable
    - More than 1 sign flip in significant changes → volatile
    - Otherwise → improving or declining based on last significant move, adjusted for direction.
      For lower_is_better indicators (PM2.5, NCD mortality), a rising value is declining health,
      so the label is inverted: value going up = "declining", value going down = "improving".
    """
    if len(points) < 4:
        return "insufficient_data"

    changes = [points[i + 1]["value"] - points[i]["value"] for i in range(len(points) - 1)]
    # Fixed tolerance anchored to range start value
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
def get_country_health_profile(country_code: str, year: int) -> str:
    """
    Returns a full health profile for a country in a given year.
    For each indicator: value, unit, and health-adjusted global percentile.
    Identifies the country's strongest and weakest indicators by percentile.
    Flags indicators with missing data for that year.
    """
    country = country_code.upper()
    rows = query_db(
        "SELECT indicator_name, numeric_value FROM disease_indicators WHERE country_code = ? AND year = ?",
        (country, year),
    )

    found = {r["indicator_name"]: r["numeric_value"] for r in rows}
    metrics = []
    health_percentiles = {}

    for key, meta in INDICATORS.items():
        value = found.get(key)
        if value is None:
            metrics.append({"indicator": key, "label": meta["label"], "missing": True})
            continue

        dist = get_global_distribution(key, year)
        hp = health_percentile(value, dist, meta["higher_is_better"])
        health_percentiles[key] = hp

        metrics.append({
            "indicator": key,
            "label":     meta["label"],
            "value":     round(value, 2),
            "unit":      meta["unit"],
            "health_percentile": hp,
            "missing":   False,
        })

    best  = max(health_percentiles, key=health_percentiles.get) if health_percentiles else None
    worst = min(health_percentiles, key=health_percentiles.get) if health_percentiles else None

    return json.dumps({
        "type":     "profile",
        "country":  country,
        "year":     year,
        "metrics":  metrics,
        "strongest_indicator": best,
        "weakest_indicator":   worst,
    })


# ---------------------------------------------------------------------------
# Tool 2: compare_countries
# ---------------------------------------------------------------------------

@mcp.tool()
def compare_countries(country_a: str, country_b: str, year: int) -> str:
    """
    Compares two countries across ALL health indicators for a given year.
    For each indicator: both values, absolute difference, which country leads,
    and each country's health-adjusted global percentile.
    Identifies the indicator with the largest gap between the two countries.
    """
    ca, cb = country_a.upper(), country_b.upper()

    rows = query_db(
        "SELECT indicator_name, country_code, numeric_value FROM disease_indicators "
        "WHERE country_code IN (?, ?) AND year = ?",
        (ca, cb, year),
    )

    # Pivot into {indicator: {country: value}}
    data: dict[str, dict] = {}
    for r in rows:
        data.setdefault(r["indicator_name"], {})[r["country_code"]] = r["numeric_value"]

    comparisons = []
    gaps = {}

    for key, meta in INDICATORS.items():
        val_a = data.get(key, {}).get(ca)
        val_b = data.get(key, {}).get(cb)

        if val_a is None or val_b is None:
            comparisons.append({
                "indicator": key,
                "label":     meta["label"],
                "missing":   True,
                country_a:   round(val_a, 2) if val_a is not None else None,
                country_b:   round(val_b, 2) if val_b is not None else None,
            })
            continue

        dist = get_global_distribution(key, year)
        hp_a = health_percentile(val_a, dist, meta["higher_is_better"])
        hp_b = health_percentile(val_b, dist, meta["higher_is_better"])

        diff = round(abs(val_a - val_b), 2)
        gaps[key] = diff

        # "leads" means better health outcome on this indicator
        if meta["higher_is_better"]:
            leader = ca if val_a > val_b else cb
        else:
            leader = ca if val_a < val_b else cb

        comparisons.append({
            "indicator":  key,
            "label":      meta["label"],
            "unit":       meta["unit"],
            "missing":    False,
            ca: {"value": round(val_a, 2), "health_percentile": hp_a},
            cb: {"value": round(val_b, 2), "health_percentile": hp_b},
            "difference": diff,
            "leader":     leader,
        })

    largest_gap = max(gaps, key=gaps.get) if gaps else None

    return json.dumps({
        "type":        "comparison",
        "countries":   [ca, cb],
        "year":        year,
        "comparisons": comparisons,
        "largest_gap_indicator": largest_gap,
    })


# ---------------------------------------------------------------------------
# Tool 3: get_health_trend
# ---------------------------------------------------------------------------

@mcp.tool()
def get_health_trend(country_code: str, indicator_name: str, start_year: int, end_year: int) -> str:
    """
    Returns a time-series trend for a country/indicator over a year range.
    Computes: overall % change, year-over-year changes, best/worst year,
    and classifies the trend as improving / declining / volatile / stable / insufficient_data.
    Trend classification requires at least 4 data points to be meaningful.
    """
    key = indicator_name.upper()
    country = country_code.upper()

    rows = query_db(
        "SELECT year, numeric_value FROM disease_indicators "
        "WHERE country_code = ? AND indicator_name = ? AND year BETWEEN ? AND ? "
        "ORDER BY year ASC",
        (country, key, start_year, end_year),
    )

    if not rows:
        return json.dumps({
            "type":    "error",
            "message": f"No records found for {key} in {country} ({start_year}–{end_year}).",
        })

    meta   = INDICATORS.get(key, {})
    points = [{"year": r["year"], "value": r["numeric_value"]} for r in rows]

    start_val = points[0]["value"]
    end_val   = points[-1]["value"]
    pct_change = round(((end_val - start_val) / start_val) * 100, 2) if start_val else 0

    yoy = []
    for i in range(1, len(points)):
        prev, curr = points[i - 1]["value"], points[i]["value"]
        yoy.append({
            "from_year": points[i - 1]["year"],
            "to_year":   points[i]["year"],
            "change":    round(curr - prev, 2),
            "pct":       round(((curr - prev) / prev) * 100, 2) if prev else 0,
        })

    higher_is_better = meta.get("higher_is_better", True)

    # best_outcome_year = year with highest value for higher_is_better indicators,
    # year with lowest value for lower_is_better indicators (e.g. least pollution = best year)
    if higher_is_better:
        best_outcome_year  = max(points, key=lambda p: p["value"])["year"]
        worst_outcome_year = min(points, key=lambda p: p["value"])["year"]
    else:
        best_outcome_year  = min(points, key=lambda p: p["value"])["year"]
        worst_outcome_year = max(points, key=lambda p: p["value"])["year"]

    return json.dumps({
        "type":               "trend",
        "country":            country,
        "indicator":          meta.get("label", key),
        "unit":               meta.get("unit", ""),
        "higher_is_better":   higher_is_better,
        "start_year":         start_year,
        "end_year":           end_year,
        "pct_change":         pct_change,
        "trend":              classify_trend(points, higher_is_better),
        "best_outcome_year":  best_outcome_year,
        "worst_outcome_year": worst_outcome_year,
        "points":             points,
        "yoy":                yoy,
    })


# ---------------------------------------------------------------------------
# Tool 4: rank_countries_by_indicator
# ---------------------------------------------------------------------------

@mcp.tool()
def rank_countries_by_indicator(indicator_name: str, year: int, limit: int = 10) -> str:
    """
    Ranks the top N countries by best health outcome for a given indicator and year.
    Sort direction is determined by higher_is_better: DESC for positive indicators
    (life expectancy, hospital beds), ASC for negative ones (PM2.5, NCD mortality).
    Includes each country's health-adjusted percentile and global distribution stats
    (mean, median, min, max, stdev) so rankings have distributional context.
    """
    key  = indicator_name.upper()
    meta = INDICATORS.get(key)

    if not meta:
        return json.dumps({"type": "error", "message": f"Unknown indicator: {key}"})

    order = "DESC" if meta["higher_is_better"] else "ASC"
    rows  = query_db(
        f"SELECT country_code, numeric_value FROM disease_indicators "
        f"WHERE indicator_name = ? AND year = ? ORDER BY numeric_value {order} LIMIT ?",
        (key, year, limit),
    )

    if not rows:
        return json.dumps({"type": "error", "message": f"No data for {key} in {year}."})

    dist  = get_global_distribution(key, year)
    stats = distribution_stats(dist)

    ranks = [
        {
            "rank":              i + 1,
            "country":           r["country_code"],
            "value":             round(r["numeric_value"], 2),
            "unit":              meta["unit"],
            "health_percentile": health_percentile(r["numeric_value"], dist, meta["higher_is_better"]),
        }
        for i, r in enumerate(rows)
    ]

    return json.dumps({
        "type":               "ranking",
        "indicator":          meta["label"],
        "unit":               meta["unit"],
        "year":               year,
        "higher_is_better":   meta["higher_is_better"],
        "ranks":              ranks,
        "global_stats":       stats,
    })


if __name__ == "__main__":
    mcp.run(transport="stdio")
