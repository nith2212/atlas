"""
Central Configuration for etl-mcp-health.
Swap or add WHO OData indicator codes here without altering server logic.
"""

import os
DB_PATH = os.path.join(os.path.dirname(__file__), "health_signals.db")
WHO_BASE_URL = "https://ghoapi.azureedge.net/api"

INDICATORS = {
    "NCD_MORTALITY_PROB": "NCDMORT3070",        # Premature NCD/Cancer mortality probability (%) ages 30-70
    "AIR_POLLUTION_PM25": "SDGPM25",            # Fine particulate matter PM2.5 concentration
    "HOSPITAL_BED_DENSITY": "WHS4_100",         # Hospital beds per 10,000 population
    "LIFE_EXPECTANCY": "WHOSIS_000001"          # Life expectancy at birth (years)
}