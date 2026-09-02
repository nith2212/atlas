"""
Fetches the full WHO GHO indicator catalog via paginated requests
and populates indicators_metadata in Neon.
Also patches higher_is_better for known indicators.
Run once on deploy, then on a schedule to pick up new WHO indicators.
"""

import requests
from datetime import datetime, timezone
from database.postgres import pool, init_db

WHO_INDICATORS_URL = "https://ghoapi.azureedge.net/api/Indicator"
PAGE_SIZE = 200

# Known direction flags — extend as you add more indicators
HIGHER_IS_BETTER = {
    "WHOSIS_000001":  True,   # Life Expectancy
    "WHS4_100":       True,   # Hospital Bed Density
    "NCDMORT3070":    False,  # NCD Mortality
    "SDGPM25":        False,  # Air Pollution PM2.5
    "NCD_BMI_30C":    False,  # Obesity prevalence (BMI >= 30)
    "NCD_BMI_PLUS2C": False,  # Overweight+obesity prevalence
    "EQ_OVERWEIGHTADULT": False,  # Overweight adults
}


def fetch_who_catalog() -> list[dict]:
    all_indicators = []
    skip = 0
    while True:
        resp = requests.get(
            WHO_INDICATORS_URL,
            params={"$top": PAGE_SIZE, "$skip": skip},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json().get("value", [])
        if not page:
            break
        all_indicators.extend(page)
        skip += PAGE_SIZE
        print(f"  fetched {len(all_indicators)} indicators so far...")
    return all_indicators


def _extract_category(ind: dict) -> str | None:
    """Extract a normalized category from the WHO catalog payload."""
    raw = (
        ind.get("Category")
        or ind.get("Group")
        or ind.get("Topic")
        or ind.get("IndicatorType")
        or ind.get("ParentIndicator")
    )

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                value = item.get("Name") or item.get("name") or item.get("label")
                if value:
                    return str(value).strip()
            elif item:
                return str(item).strip()
        return None

    if isinstance(raw, dict):
        for key in ("Name", "name", "label", "value"):
            value = raw.get(key)
            if value:
                return str(value).strip()
        return None

    if raw:
        return str(raw).strip()

    name = str(ind.get("IndicatorName") or "").lower()
    keyword_categories = (
        ("Risk factors", ("risk", "tobacco", "smoking", "alcohol", "obesity", "overweight", "pollution")),
        ("Mortality", ("mortality", "death", "fatal", "suicide")),
        ("Disease prevalence", ("prevalence", "incidence", "cases", "disease", "diabetes", "cancer")),
        ("Health system", ("hospital", "physician", "health expenditure", "health worker", "bed density")),
        ("Nutrition", ("nutrition", "anaemia", "anemia", "stunting", "wasting")),
        ("Water and sanitation", ("sanitation", "drinking water", "hygiene", "wastewater")),
        ("Life expectancy", ("life expectancy", "healthy life", "hale")),
    )
    for category, keywords in keyword_categories:
        if any(keyword in name for keyword in keywords):
            return category
    return "Other indicators"


def run():
    init_db()

    # Ensure schema columns exist (safe to run multiple times)
    with pool.connection() as conn:
        conn.execute("""
            ALTER TABLE indicators_metadata
            ADD COLUMN IF NOT EXISTS higher_is_better BOOLEAN,
            ADD COLUMN IF NOT EXISTS category TEXT,
            ADD COLUMN IF NOT EXISTS unit TEXT
        """)
        conn.commit()

    print("Fetching WHO indicator catalog...")
    indicators = fetch_who_catalog()
    print(f"Total: {len(indicators)} indicators")

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO indicators_metadata (code, name, category, unit, higher_is_better, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE
                    SET name             = EXCLUDED.name,
                        category         = COALESCE(EXCLUDED.category, indicators_metadata.category),
                        unit             = COALESCE(EXCLUDED.unit, indicators_metadata.unit),
                        higher_is_better = COALESCE(EXCLUDED.higher_is_better, indicators_metadata.higher_is_better),
                        last_updated     = EXCLUDED.last_updated
            """, [
                (
                    ind["IndicatorCode"],
                    ind["IndicatorName"],
                    _extract_category(ind),
                    ind.get("Unit") or ind.get("Units") or ind.get("IndicatorUnit") or None,
                    HIGHER_IS_BETTER.get(ind["IndicatorCode"]),
                    datetime.now(timezone.utc),
                )
                for ind in indicators
                if ind.get("IndicatorCode")
            ])
        conn.commit()

    print(f"indicators_metadata populated with {len(indicators)} rows")


if __name__ == "__main__":
    run()
