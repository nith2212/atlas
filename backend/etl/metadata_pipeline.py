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
    "WHOSIS_000001": True,   # Life Expectancy
    "WHS4_100":      True,   # Hospital Bed Density
    "NCDMORT3070":   False,  # NCD Mortality
    "SDGPM25":       False,  # Air Pollution PM2.5
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


def run():
    init_db()

    # Ensure higher_is_better column exists (safe to run multiple times)
    with pool.connection() as conn:
        conn.execute("""
            ALTER TABLE indicators_metadata
            ADD COLUMN IF NOT EXISTS higher_is_better BOOLEAN
        """)
        conn.commit()

    print("Fetching WHO indicator catalog...")
    indicators = fetch_who_catalog()
    print(f"Total: {len(indicators)} indicators")

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO indicators_metadata (code, name, higher_is_better, last_updated)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE
                    SET name             = EXCLUDED.name,
                        higher_is_better = COALESCE(EXCLUDED.higher_is_better, indicators_metadata.higher_is_better),
                        last_updated     = EXCLUDED.last_updated
            """, [
                (
                    ind["IndicatorCode"],
                    ind["IndicatorName"],
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
