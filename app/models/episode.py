"""The `episodes` collection — the single source of truth that drives the whole
state-machine pipeline. Every stage picks up episodes at a given `status`, does
its work, and advances the status. This is what makes each stage idempotent and
resumable.

status flow:
    queued -> scripting -> scripted -> audio_done -> image_done
    -> video_done -> metadata_done -> uploaded
(any stage may set `failed` with an error + retry_count)
"""

from datetime import datetime, timezone
from enum import Enum

from beanie import Document
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EpisodeStatus(str, Enum):
    queued = "queued"
    scripting = "scripting"
    scripted = "scripted"
    audio_done = "audio_done"
    image_done = "image_done"
    video_done = "video_done"
    metadata_done = "metadata_done"
    uploaded = "uploaded"
    failed = "failed"


class DialogueTurn(BaseModel):
    speaker: str
    text: str


class EpisodeMetadata(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    chapters: list[str] = Field(default_factory=list)


class CostLog(BaseModel):
    script: float = 0.0
    tts: float = 0.0
    image: float = 0.0


class Episode(Document):
    topic: str
    hosts: list[str] = Field(default_factory=lambda: ["Anna", "Jake"])
    target_minutes: float = 10.0  # desired episode length; drives script word count

    status: EpisodeStatus = EpisodeStatus.queued
    retry_count: int = 0
    error: str | None = None

    script: list[DialogueTurn] = Field(default_factory=list)

    audio_path: str | None = None
    audio_duration_seconds: float | None = None
    image_path: str | None = None
    image_prompt: str | None = None  # the prompt that produced the current image
    video_path: str | None = None

    metadata: EpisodeMetadata = Field(default_factory=EpisodeMetadata)
    youtube_video_id: str | None = None
    privacy: str = "unlisted"

    cost_log: CostLog = Field(default_factory=CostLog)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "episodes"
        use_state_management = True
