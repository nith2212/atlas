"""
Configuration — infrastructure constants only.
Business data (indicator definitions) lives in the database, not here.
"""

import os

WHO_BASE_URL = "https://ghoapi.azureedge.net/api"
DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

# v1 SQLite DB — source for the one-time cache_pipeline.py migration.
DB_PATH = os.path.join(os.path.dirname(__file__), "health_signals.db")

# Curated phrase -> WHO code overrides, checked before substring/fuzzy matching.
# WHO indicator names often don't contain the natural-language phrase users say
# (e.g. SDGPM25 is named "Concentrations of fine particulate matter (PM2.5)",
# not "air pollution"), so ILIKE alone can resolve to the wrong indicator.
INDICATOR_ALIASES = {
    "air pollution": "SDGPM25",
    "pm2.5": "SDGPM25",
    "particulate matter": "SDGPM25",
}


# Indicators to preload into indicator_cache on first deploy.
# These are WHO codes. Metadata for all WHO indicators comes from the metadata ETL.
PRELOAD_INDICATORS = [
    # Already cached
    "WHOSIS_000001",              # Life expectancy at birth
    "WHS4_100",                   # Hospital bed density
    "NCDMORT3070",                # NCD mortality (cardiovascular, cancer, diabetes, respiratory)
    "SDGPM25",                    # Air pollution PM2.5
    "NCD_BMI_30C",                # Obesity prevalence (BMI >= 30)
    # Mortality
    "MDG_0000000001",             # Infant mortality rate
    "MDG_0000000026",             # Maternal mortality ratio
    "SDGSUICIDE",                 # Suicide rate (per 100 000)
    "RS_198",                     # Road traffic death rate
    "WHS2_131",                   # Age-standardized NCD mortality rate
    # Disease prevalence
    "NCD_DIABETES_PREVALENCE_CRUDE",  # Diabetes prevalence
    "NCD_HYP_PREVALENCE_C",       # Hypertension prevalence
    "HIV_0000000026",             # New HIV infections
    "TB_c_newinc",                # Tuberculosis new cases
    "MALARIA_PRES_CASES",         # Malaria cases
    "GDO_q35",                    # Depression prevalence
    # Nutrition
    "NCD_BMI_PLUS2C",             # Childhood obesity
    "stunt5",                     # Stunting under 5
    "wast5",                      # Wasting under 5
    "NUTRITION_ANAEMIA_CHILDREN_PREV",  # Anaemia in children
    # Health system
    "HRH_26",                     # Physician density
    "GHED_CHE_pc_US_SHA2011",     # Health expenditure per capita
    "WHS6_102",                   # Hospital beds per 10 000
    # Lifestyle risk factors
    "NCD_CHOL_MEANTOTALCHOL_C",   # Mean total cholesterol
    # Water & sanitation
    "WSH_SANITATION_BASIC",       # Basic sanitation access
    # Healthy life expectancy
    "WHOSIS_000002",              # HALE at birth
]
