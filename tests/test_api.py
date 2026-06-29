"""End-to-end API tests against the real ASGI app (lifespan connects to Atlas)."""

import httpx
import pytest

from app.application import create_app
from app.core.config import get_settings


@pytest.fixture
async def client():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == get_settings().app_name


async def test_health(client):
    prefix = get_settings().api_v1_prefix
    resp = await client.get(f"{prefix}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # request-context middleware should stamp these headers
    assert "X-Request-ID" in resp.headers
    assert "X-Process-Time-ms" in resp.headers


async def test_episode_create_list_get(client):
    prefix = get_settings().api_v1_prefix

    created = await client.post(f"{prefix}/episodes", json={"topic": "pytest topic"})
    assert created.status_code == 201
    ep = created.json()
    assert ep["status"] == "queued"
    episode_id = ep["id"]

    fetched = await client.get(f"{prefix}/episodes/{episode_id}")
    assert fetched.status_code == 200
    assert fetched.json()["topic"] == "pytest topic"

    # cleanup
    from app.models.episode import Episode

    doc = await Episode.get(episode_id)
    if doc:
        await doc.delete()
