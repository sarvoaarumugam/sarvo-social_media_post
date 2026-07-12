"""LinkedIn post DTOs."""

from datetime import datetime

from pydantic import BaseModel

from app.models.linkedin import LinkedInPost


class LinkedInCreate(BaseModel):
    brief: str  # what the post should be about


class CaptionUpdate(BaseModel):
    caption: str


class ImageBriefRequest(BaseModel):
    brief: str = ""  # visual direction for the graphic


class ImageFeedbackRequest(BaseModel):
    feedback: str


class LinkedInRead(BaseModel):
    id: str
    brief: str
    caption: str | None
    image_brief: str | None
    image_path: str | None
    has_caption: bool
    has_image: bool
    status: str
    error: str | None = None
    cost_usd: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: LinkedInPost) -> "LinkedInRead":
        return cls(
            id=str(doc.id),
            brief=doc.brief,
            caption=doc.caption,
            image_brief=doc.image_brief,
            image_path=doc.image_path,
            has_caption=bool(doc.caption),
            has_image=bool(doc.image_path),
            status=doc.status,
            error=doc.error,
            cost_usd=round(doc.cost_caption + doc.cost_image, 6),
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
