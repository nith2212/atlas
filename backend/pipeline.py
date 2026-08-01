"""
ETL pipeline — fetches WHO GHO OData JSON, cleans it, and populates health_signals.db.
"""

import sqlite3
import requests
from config import DB_PATH, WHO_BASE_URL, INDICATORS

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS disease_indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator_name TEXT NOT NULL,
            country_code TEXT NOT NULL,
            year INTEGER NOT NULL,
            numeric_value REAL NOT NULL,
            UNIQUE(indicator_name, country_code, year)
        )
    """)
    conn.commit()
    return conn

def fetch_and_clean(indicator_key, indicator_code):
    url = f"{WHO_BASE_URL}/{indicator_code}"
    params = {"$filter": "SpatialDimType eq 'COUNTRY' and TimeDim ge 2015"}

    print(f"[ETL] Fetching '{indicator_key}' ({indicator_code})... (may take 30–60s)")
    response = requests.get(url, params=params, timeout=120)
    response.raise_for_status()
    print(f"[ETL] Downloaded {len(response.content) // 1024} KB. Parsing...")
    
    raw_data = response.json().get("value", [])
    cleaned_rows = []
    
    AGGREGATE_DIM1 = {None, "BTSX", "SEX_BTSX", "TOTL", "RESIDENCEAREATYPE_TOTL", "BOTH"}

    for row in raw_data:
        val = row.get("NumericValue")
        if val is None:
            continue

        dim1 = row.get("Dim1")
        if dim1 not in AGGREGATE_DIM1:
            continue

        try:
            cleaned_val = float(val)
            year = int(row.get("TimeDim"))
            country = row.get("SpatialDim")

            if country and year:
                cleaned_rows.append((indicator_key, country, year, cleaned_val))
        except (ValueError, TypeError):
            continue
            
    print(f"[ETL] Parsed {len(cleaned_rows)} clean records for '{indicator_key}'.")
    return cleaned_rows

def run_pipeline():
    conn = init_db()
    cursor = conn.cursor()
    total_inserted = 0
    
    for label, meta in INDICATORS.items():
        rows = fetch_and_clean(label, meta["code"])
        cursor.executemany("""
            INSERT OR IGNORE INTO disease_indicators 
            (indicator_name, country_code, year, numeric_value)
            VALUES (?, ?, ?, ?)
        """, rows)
        inserted = cursor.rowcount
        conn.commit()
        total_inserted += inserted
        print(f"[ETL] Committed {inserted} new records for '{label}'.")
        
    conn.close()
    print(f"\n[SUCCESS] Pipeline complete. Loaded {total_inserted} new records into {DB_PATH}.")

if __name__ == "__main__":
    run_pipeline()