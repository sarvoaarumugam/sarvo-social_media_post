"""Health / status endpoints."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.models.episode import Episode

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    settings = get_settings()
    count = await Episode.find_all().count()
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "db": settings.mongodb_db,
        "episodes": count,
    }
