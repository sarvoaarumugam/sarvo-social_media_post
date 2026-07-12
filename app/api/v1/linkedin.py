"""LinkedIn post endpoints: create -> caption -> image. Posting is manual."""

from datetime import datetime, timezone
from pathlib import Path

from beanie import PydanticObjectId
from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.exceptions.handlers import AppError
from app.models.linkedin import LinkedInPost
from app.schemas.linkedin import (
    CaptionUpdate,
    ImageBriefRequest,
    ImageFeedbackRequest,
    LinkedInCreate,
    LinkedInRead,
)
from app.services.linkedin_generator import run_caption_stage, run_image_stage

router = APIRouter(prefix="/linkedin", tags=["linkedin"])


async def _get_or_404(post_id: PydanticObjectId) -> LinkedInPost:
    post = await LinkedInPost.get(post_id)
    if post is None:
        raise AppError("LinkedIn post not found", status_code=404)
    return post


@router.post("", response_model=LinkedInRead, status_code=201)
async def create_post(payload: LinkedInCreate):
    if not payload.brief.strip():
        raise AppError("A brief is required.", status_code=422)
    post = LinkedInPost(brief=payload.brief.strip())
    await post.insert()
    return LinkedInRead.from_doc(post)


@router.get("", response_model=list[LinkedInRead])
async def list_posts():
    posts = await LinkedInPost.find_all().sort(-LinkedInPost.created_at).to_list()
    return [LinkedInRead.from_doc(p) for p in posts]


@router.get("/{post_id}", response_model=LinkedInRead)
async def get_post(post_id: PydanticObjectId):
    return LinkedInRead.from_doc(await _get_or_404(post_id))


# --- Step 1: caption ---


@router.post("/{post_id}/caption", response_model=LinkedInRead)
async def generate_post_caption(post_id: PydanticObjectId):
    return LinkedInRead.from_doc(await run_caption_stage(await _get_or_404(post_id)))


@router.put("/{post_id}/caption", response_model=LinkedInRead)
async def update_post_caption(post_id: PydanticObjectId, payload: CaptionUpdate):
    post = await _get_or_404(post_id)
    if not payload.caption.strip():
        raise AppError("Caption cannot be empty.", status_code=422)
    post.caption = payload.caption.strip()
    if post.status == "queued":
        post.status = "caption_done"
    post.updated_at = datetime.now(timezone.utc)
    await post.save()
    return LinkedInRead.from_doc(post)


# --- Step 2: image ---


@router.post("/{post_id}/image", response_model=LinkedInRead)
async def generate_post_image_endpoint(post_id: PydanticObjectId, payload: ImageBriefRequest):
    post = await _get_or_404(post_id)
    if not post.caption:
        raise AppError("Generate the caption before the image.", status_code=409)
    return LinkedInRead.from_doc(await run_image_stage(post, payload.brief.strip()))


@router.post("/{post_id}/image/regenerate", response_model=LinkedInRead)
async def regenerate_post_image(post_id: PydanticObjectId, payload: ImageFeedbackRequest):
    post = await _get_or_404(post_id)
    if not post.caption:
        raise AppError("Generate the caption before the image.", status_code=409)
    if not payload.feedback.strip():
        raise AppError("Feedback is required to regenerate.", status_code=422)
    return LinkedInRead.from_doc(
        await run_image_stage(post, post.image_brief or "", feedback=payload.feedback.strip())
    )


@router.get("/{post_id}/image/file")
async def download_post_image(post_id: PydanticObjectId):
    post = await _get_or_404(post_id)
    if not post.image_path or not Path(post.image_path).exists():
        raise AppError("Image not generated yet.", status_code=404)
    return FileResponse(post.image_path, media_type="image/png",
                        filename=f"linkedin-{post_id}.png")
