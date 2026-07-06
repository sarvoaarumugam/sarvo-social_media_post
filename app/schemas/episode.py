"""API-facing DTOs. Kept separate from the Beanie DB model so the wire contract
and the storage schema can evolve independently.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.episode import Episode, EpisodeStatus


class EpisodeCreate(BaseModel):
    topic: str
    hosts: list[str] | None = None
    # Desired video length in minutes (1-30). Omit to use the configured default.
    duration_minutes: float | None = Field(default=None, ge=1, le=30)
    # Optional: your own knowledge/notes about the topic — the AI grounds the
    # episode in this instead of relying only on its general knowledge.
    context: str | None = Field(default=None, max_length=20000)


class EpisodeRead(BaseModel):
    id: str
    topic: str
    hosts: list[str]
    target_minutes: float
    user_context: str | None = None
    status: EpisodeStatus
    error: str | None = None
    # Progress flags — what artifacts exist (drives step unlocking in the UI).
    has_blueprint: bool = False
    has_script: bool = False
    has_audio: bool = False
    has_image: bool = False
    has_video: bool = False
    has_metadata: bool = False
    youtube_video_id: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: Episode) -> "EpisodeRead":
        return cls(
            id=str(doc.id),
            topic=doc.topic,
            hosts=doc.hosts,
            target_minutes=doc.target_minutes,
            user_context=doc.user_context,
            status=doc.status,
            error=doc.error,
            has_blueprint=doc.blueprint is not None,
            has_script=bool(doc.script),
            has_audio=bool(doc.audio_path),
            has_image=bool(doc.image_path),
            has_video=bool(doc.video_path),
            has_metadata=bool(doc.metadata.title),
            youtube_video_id=doc.youtube_video_id,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
