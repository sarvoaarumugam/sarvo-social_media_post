"""MongoDB connection lifecycle + Beanie initialization.

Beanie 2.x uses pymongo's native async driver (AsyncMongoClient), not motor.
"""

import logging

from pymongo import AsyncMongoClient

from app.core.config import get_settings
from app.models.episode import Episode
from app.models.linkedin import LinkedInPost

logger = logging.getLogger("app.db")

_client: AsyncMongoClient | None = None


async def init_db() -> AsyncMongoClient:
    """Connect to Atlas and register document models with Beanie."""
    global _client
    settings = get_settings()
    _client = AsyncMongoClient(settings.mongodb_uri)

    from beanie import init_beanie

    await init_beanie(
        database=_client[settings.mongodb_db], document_models=[Episode, LinkedInPost]
    )
    logger.info("MongoDB connected: db=%s", settings.mongodb_db)
    return _client


async def close_db() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
        logger.info("MongoDB connection closed")


async def ping() -> bool:
    """Cheap connectivity check used by health endpoint and smoke tests."""
    settings = get_settings()
    client = AsyncMongoClient(settings.mongodb_uri)
    try:
        await client.admin.command("ping")
        return True
    finally:
        await client.close()
