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


class TurnTiming(BaseModel):
    """When each dialogue turn starts/ends in the final audio (drives captions)."""

    index: int
    start: float  # seconds
    end: float


class OutlineSection(BaseModel):
    """One planned section of the episode, with its retention devices."""

    heading: str
    beats: list[str]  # concrete talking points (example/story/number/scenario)
    pattern_interrupt: str  # the change-up planned inside this section
    open_loop: str  # the tease into the NEXT section


class Blueprint(BaseModel):
    """The strategist's plan (stage 1) that the scriptwriter (stage 2) must follow."""

    titles: list[str]  # 3 click-worthy title options
    thumbnail_concept: str
    hooks: list[str]  # 3 cold-open variants
    chosen_hook_index: int  # which hook the script should use (default 0)
    big_loop: str  # question opened at the hook, closed near the end
    outline: list[OutlineSection]
    takeaway: str
    cta: str


class EpisodeMetadata(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    chapters: list[str] = Field(default_factory=list)


class CostLog(BaseModel):
    script: float = 0.0
    tts: float = 0.0
    image: float = 0.0
    metadata: float = 0.0


def _default_hosts() -> list[str]:
    # Single source of truth: settings.default_hosts (change hosts in .env/config).
    from app.core.config import get_settings

    return list(get_settings().default_hosts)


class Episode(Document):
    topic: str
    hosts: list[str] = Field(default_factory=_default_hosts)
    target_minutes: float = 10.0  # desired episode length; drives script word count
    user_context: str | None = None  # creator's own knowledge/notes to ground the content

    status: EpisodeStatus = EpisodeStatus.queued
    retry_count: int = 0
    error: str | None = None

    blueprint: Blueprint | None = None  # strategist's plan (stage 1)
    script: list[DialogueTurn] = Field(default_factory=list)

    audio_path: str | None = None
    audio_duration_seconds: float | None = None
    turn_timings: list[TurnTiming] = Field(default_factory=list)
    image_path: str | None = None  # clean background used inside the video
    thumbnail_path: str | None = None  # title-overlay variant used as YouTube thumbnail
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
