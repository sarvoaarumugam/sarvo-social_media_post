"""Image/Video (M3) response DTOs for the review checkpoints."""

from pydantic import BaseModel

from app.models.episode import EpisodeStatus


class ImageRead(BaseModel):
    episode_id: str
    status: EpisodeStatus
    image_path: str | None  # clean background used inside the video
    thumbnail_path: str | None = None  # title-overlay variant for YouTube
    image_prompt: str | None = None
    cost_usd: float = 0.0


class ImageRegenerateRequest(BaseModel):
    """Your feedback for a new image, e.g. 'make it brighter, show a sunrise over a city'."""

    feedback: str


class ImagePresetRequest(BaseModel):
    """Pick a preset thumbnail design from the assets/ folder by file name."""

    name: str


class VideoRead(BaseModel):
    episode_id: str
    status: EpisodeStatus
    video_path: str | None
    duration_seconds: float | None
