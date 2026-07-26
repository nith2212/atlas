"""
Phase 2: FastMCP Tools Server
Exposes 4 deterministic SQL query tools over stdio to any MCP client.
All tools return typed structured JSON for direct frontend rendering.
"""

import json
import sqlite3
from mcp.server.fastmcp import FastMCP
from config import DB_PATH

mcp = FastMCP("etl-mcp-health")

INDICATOR_LABELS = {
    "NCD_MORTALITY_PROB": "NCD Mortality",
    "AIR_POLLUTION_PM25": "Air Pollution (PM2.5)",
    "HOSPITAL_BED_DENSITY": "Hospital Bed Density",
    "LIFE_EXPECTANCY": "Life Expectancy",
}

INDICATOR_UNITS = {
    "NCD_MORTALITY_PROB": "%",
    "AIR_POLLUTION_PM25": "µg/m³",
    "HOSPITAL_BED_DENSITY": "per 10,000",
    "LIFE_EXPECTANCY": "years",
}

def query_db(sql: str, params: tuple = ()):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


@mcp.tool()
def get_health_trend(country_code: str, indicator_name: str, start_year: int, end_year: int) -> str:
    """Gets time-series trend and calculates percentage change for a country metric over years."""
    sql = """
        SELECT year, numeric_value FROM disease_indicators
        WHERE country_code = ? AND indicator_name = ? AND year BETWEEN ? AND ?
        ORDER BY year ASC
    """
    results = query_db(sql, (country_code.upper(), indicator_name.upper(), start_year, end_year))
    if not results:
        return json.dumps({"type": "error", "message": f"No records found for {indicator_name} in {country_code} ({start_year}-{end_year})."})

    start_val = results[0]["numeric_value"]
    end_val = results[-1]["numeric_value"]
    pct_change = round(((end_val - start_val) / start_val) * 100, 2) if start_val else 0

    return json.dumps({
        "type": "trend",
        "country": country_code.upper(),
        "indicator": INDICATOR_LABELS.get(indicator_name.upper(), indicator_name),
        "unit": INDICATOR_UNITS.get(indicator_name.upper(), ""),
        "pct_change": pct_change,
        "points": [{"year": r["year"], "value": r["numeric_value"]} for r in results],
    })


@mcp.tool()
def compare_countries(country_a: str, country_b: str, indicator_name: str, year: int) -> str:
    """Compares a specific health indicator between two countries for a given year."""
    sql = """
        SELECT country_code, numeric_value FROM disease_indicators
        WHERE indicator_name = ? AND year = ? AND country_code IN (?, ?)
    """
    results = query_db(sql, (indicator_name.upper(), year, country_a.upper(), country_b.upper()))

    return json.dumps({
        "type": "comparison",
        "indicator": INDICATOR_LABELS.get(indicator_name.upper(), indicator_name),
        "unit": INDICATOR_UNITS.get(indicator_name.upper(), ""),
        "year": year,
        "values": [{"country": r["country_code"], "value": r["numeric_value"]} for r in results],
    })


@mcp.tool()
def get_country_health_profile(country_code: str, year: int) -> str:
    """Returns all available health indicators for a single country in a specific year."""
    sql = """
        SELECT indicator_name, numeric_value FROM disease_indicators
        WHERE country_code = ? AND year = ?
    """
    results = query_db(sql, (country_code.upper(), year))

    return json.dumps({
        "type": "profile",
        "country": country_code.upper(),
        "year": year,
        "metrics": [
            {
                "label": INDICATOR_LABELS.get(r["indicator_name"], r["indicator_name"]),
                "value": r["numeric_value"],
                "unit": INDICATOR_UNITS.get(r["indicator_name"], ""),
            }
            for r in results
        ],
    })


@mcp.tool()
def rank_countries_by_indicator(indicator_name: str, year: int, limit: int = 5) -> str:
    """Ranks top N countries by highest value for a given indicator and year."""
    sql = """
        SELECT country_code, numeric_value FROM disease_indicators
        WHERE indicator_name = ? AND year = ?
        ORDER BY numeric_value DESC LIMIT ?
    """
    results = query_db(sql, (indicator_name.upper(), year, limit))

    return json.dumps({
        "type": "ranking",
        "indicator": INDICATOR_LABELS.get(indicator_name.upper(), indicator_name),
        "unit": INDICATOR_UNITS.get(indicator_name.upper(), ""),
        "year": year,
        "ranks": [{"rank": i + 1, "country": r["country_code"], "value": r["numeric_value"]} for i, r in enumerate(results)],
    })


if __name__ == "__main__":
    mcp.run(transport="stdio")
