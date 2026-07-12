"""LinkedIn post — a separate content type from video episodes.

Two-step flow: caption first (from the user's brief), then a square graphic
(from the caption + the user's visual brief). Posting is done manually by the
user; this model just tracks the generated assets.
"""

from datetime import datetime, timezone

from beanie import Document
from pydantic import Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LinkedInPost(Document):
    brief: str  # what the user wants the post to be about (caption input)
    caption: str | None = None  # generated (and optionally edited) caption

    image_brief: str | None = None  # user's visual direction for the graphic
    image_path: str | None = None
    image_prompt: str | None = None

    status: str = "queued"  # queued -> caption_done -> image_done
    error: str | None = None

    cost_caption: float = 0.0
    cost_image: float = 0.0

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "linkedin_posts"
        use_state_management = True
