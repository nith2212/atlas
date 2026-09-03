"""
LLM utility calls — lightweight inference tasks that don't belong in the agent loop.
Currently: infer higher_is_better direction for WHO indicators.
"""

import os
from groq import Groq
from database.postgres import pool
from config import GROQ_MODEL

_client = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


def infer_and_store_direction(indicator_code: str, indicator_name: str) -> bool:
    """
    Asks the LLM whether a higher value is better or worse for a health indicator.
    Stores the result in indicators_metadata and returns the boolean.
    Falls back to True on any failure.
    """
    try:
        resp = _get_client().chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a public health expert. "
                        "Answer with exactly one word: HIGHER or LOWER. No explanation."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"For the WHO health indicator '{indicator_name}', "
                        "is a higher numeric value better or worse for population health? "
                        "Answer HIGHER if more is better (e.g. life expectancy, vaccination rate). "
                        "Answer LOWER if less is better (e.g. mortality rate, disease prevalence)."
                    ),
                },
            ],
            temperature=0,
            max_tokens=5,
        )
        answer = resp.choices[0].message.content.strip().upper()
        higher_is_better = answer.startswith("HIGHER")
    except Exception as e:
        print(f"[llm_service] direction inference failed for {indicator_code}: {e}")
        higher_is_better = True  # safe fallback

    with pool.connection() as conn:
        conn.execute(
            "UPDATE indicators_metadata SET higher_is_better = %s WHERE code = %s",
            (higher_is_better, indicator_code),
        )
        conn.commit()

    print(f"[llm_service] {indicator_code} → higher_is_better={higher_is_better}")
    return higher_is_better
