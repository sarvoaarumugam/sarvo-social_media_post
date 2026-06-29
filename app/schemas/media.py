"""Image/Video (M3) response DTOs for the review checkpoints."""

from pydantic import BaseModel

from app.models.episode import EpisodeStatus


class ImageRead(BaseModel):
    episode_id: str
    status: EpisodeStatus
    image_path: str | None
    image_prompt: str | None = None
    cost_usd: float = 0.0


class ImageRegenerateRequest(BaseModel):
    """Your feedback for a new image, e.g. 'make it brighter, show a sunrise over a city'."""

    feedback: str


class VideoRead(BaseModel):
    episode_id: str
    status: EpisodeStatus
    video_path: str | None
    duration_seconds: float | None
