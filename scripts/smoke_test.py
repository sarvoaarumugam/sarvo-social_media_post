"""M0 smoke test: verify config loads, Atlas connects, Beanie registers Episode,
and a full create -> read -> status-transition -> delete round-trip works.
Run: uv run python scripts/smoke_test.py
"""

import asyncio

from app.core.config import get_settings
from app.db.mongodb import close_db, init_db, ping
from app.models.episode import Episode, EpisodeStatus


async def main() -> None:
    settings = get_settings()
    print(f"[1] Config loaded. brand={settings.channel_brand_name!r} db={settings.mongodb_db!r}")

    ok = await ping()
    print(f"[2] Atlas ping: {'OK' if ok else 'FAILED'}")

    await init_db()
    print("[3] Beanie initialized (Episode registered).")

    ep = Episode(topic="Don't Waste Your Life | English Podcast (smoke test)")
    await ep.insert()
    print(f"[4] Inserted episode _id={ep.id} status={ep.status.value}")

    fetched = await Episode.get(ep.id)
    assert fetched is not None and fetched.status == EpisodeStatus.queued
    print(f"[5] Read back: topic={fetched.topic[:40]!r}...")

    fetched.status = EpisodeStatus.scripting
    await fetched.save()
    print(f"[6] Status transition -> {fetched.status.value}")

    await fetched.delete()
    print("[7] Cleaned up test episode.")

    total = await Episode.find_all().count()
    print(f"[8] Episodes remaining in collection: {total}")

    await close_db()
    print("\nM0 OK — config, Atlas, Beanie, and CRUD all working.")


if __name__ == "__main__":
    asyncio.run(main())
