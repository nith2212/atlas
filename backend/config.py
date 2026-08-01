"""
Configuration — infrastructure constants only.
Business data (indicator definitions) lives in the database, not here.
"""

import os

DB_PATH      = os.path.join(os.path.dirname(__file__), "health_signals.db")
WHO_BASE_URL = "https://ghoapi.azureedge.net/api"
DATABASE_URL = os.getenv("DATABASE_URL")

# Indicators to preload into indicator_cache on first deploy.
# These are WHO codes. Metadata for all WHO indicators comes from the metadata ETL.
PRELOAD_INDICATORS = [
    "WHOSIS_000001",  # Life Expectancy
    "WHS4_100",       # Hospital Bed Density
    "NCDMORT3070",    # NCD Mortality
    "SDGPM25",        # Air Pollution PM2.5
]
