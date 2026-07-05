"""Aggregates all versioned routers into a single api_router."""

from fastapi import APIRouter

from app.api.v1 import assets, episodes, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(episodes.router)
api_router.include_router(assets.router)
