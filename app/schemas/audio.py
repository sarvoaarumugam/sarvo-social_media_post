"""Audio (M2) response DTO for the review checkpoint."""

from pydantic import BaseModel

from app.models.episode import EpisodeStatus


class AudioRead(BaseModel):
    episode_id: str
    status: EpisodeStatus
    audio_path: str | None
    duration_seconds: float | None
    est_minutes: float | None
    cost_usd: float
    voices: dict[str, str]
