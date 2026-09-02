"""
Analytical computation layer.
All health metric calculations live here — percentiles, distribution stats,
trend classification. No DB access, no MCP concerns. Pure computation.
"""

import statistics
from database.postgres import pool


def get_global_distribution(indicator_code: str, year: int) -> list[float]:
    """All country values for an indicator/year — basis for percentile and stats."""
    with pool.connection() as conn:
        rows = conn.execute("""
            SELECT value FROM indicator_cache
            WHERE indicator_code = %s AND year = %s
        """, (indicator_code, year)).fetchall()
    return [r[0] for r in rows]


def compute_percentile(value: float, distribution: list[float]) -> float:
    """Raw percentile: % of countries with value <= this one."""
    if not distribution:
        return 0.0
    return round(sum(1 for v in distribution if v <= value) / len(distribution) * 100, 1)


def health_percentile(value: float, distribution: list[float], higher_is_better: bool) -> float:
    """
    Health-adjusted percentile: always higher = healthier outcome.
    Inverts raw percentile for lower_is_better indicators (e.g. PM2.5, NCD mortality)
    so a country with very low pollution gets a high health percentile.
    """
    raw = compute_percentile(value, distribution)
    return raw if higher_is_better else round(100 - raw, 1)


def distribution_stats(values: list[float]) -> dict:
    """Mean, median, min, max, stdev over a distribution."""
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
    Classifies a time series as: improving / declining / volatile / stable / insufficient_data.

    - Fewer than 4 points → insufficient_data
    - Tolerance = 1% of first value — filters out noise
    - No significant changes → stable
    - More than 1 direction flip → volatile
    - Otherwise → improving or declining, adjusted for higher_is_better direction
    """
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
