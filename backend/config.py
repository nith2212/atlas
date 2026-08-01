"""
Central configuration — indicator definitions live here.
Add or swap indicators without touching any other file.

Each entry:
  code             - WHO GHO OData API code
  label            - Human-readable display name
  unit             - Unit string for UI rendering
  higher_is_better - Drives percentile direction, ranking sort order, and trend
                     classification across all tools. False for PM2.5 and NCD
                     mortality (lower value = better health outcome).
"""

import os
DB_PATH = os.path.join(os.path.dirname(__file__), "health_signals.db")
WHO_BASE_URL = "https://ghoapi.azureedge.net/api"

INDICATORS = {
    "LIFE_EXPECTANCY": {
        "code": "WHOSIS_000001",
        "label": "Life Expectancy",
        "unit": "years",
        "higher_is_better": True,
    },
    "HOSPITAL_BED_DENSITY": {
        "code": "WHS4_100",
        "label": "Hospital Bed Density",
        "unit": "per 10,000",
        "higher_is_better": True,
    },
    "NCD_MORTALITY_PROB": {
        "code": "NCDMORT3070",
        "label": "NCD Mortality",
        "unit": "%",
        "higher_is_better": False,
    },
    "AIR_POLLUTION_PM25": {
        "code": "SDGPM25",
        "label": "Air Pollution (PM2.5)",
        "unit": "µg/m³",
        "higher_is_better": False,
    },
}