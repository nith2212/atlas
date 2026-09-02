"""
One-time warm-up: fetches every indicator in config.PRELOAD_INDICATORS into
Neon via the same cache-aside path used at query time (get_or_fetch).
Run manually before demos/testing — do NOT run this on API startup.
Safe to re-run: already-cached indicators are skipped instantly.
"""

import asyncio
from config import PRELOAD_INDICATORS
from database.postgres import init_db
from services.cache_service import get_or_fetch, is_cached


async def run():
    init_db()
    for code in PRELOAD_INDICATORS:
        if is_cached(code):
            print(f"[preload] {code} already cached, skipping")
            continue
        print(f"[preload] fetching {code} from WHO...")
        rows = await get_or_fetch(code)
        print(f"[preload] {code} -> {len(rows)} rows cached")


if __name__ == "__main__":
    asyncio.run(run())
