"""Metadata + upload (M4) DTOs for the review checkpoints."""

from pydantic import BaseModel

from app.models.episode import EpisodeStatus


class MetadataRead(BaseModel):
    episode_id: str
    status: EpisodeStatus
    title: str | None
    description: str | None
    tags: list[str]
    chapters: list[str]
    cost_usd: float


class MetadataUpdate(BaseModel):
    """Manual corrections — only the fields you send get replaced."""

    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class UploadRead(BaseModel):
    episode_id: str
    status: EpisodeStatus
    youtube_video_id: str | None
    url: str | None
    privacy: str
