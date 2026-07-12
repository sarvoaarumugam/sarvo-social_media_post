"""M4 (part 2) — YouTube uploader.

Resumable upload via YouTube Data API v3, then sets the thumbnail and privacy.

Auth model (Desktop app OAuth):
- First run opens a browser once; you approve; token.json is saved.
- Every later run refreshes silently -> fully unattended uploads.

The Google client library is synchronous, so all network work runs in a worker
thread (asyncio.to_thread) to keep the API responsive.

Quota note: one upload costs ~1600 units of the 10,000/day default -> ~6 uploads/day.
"""

import asyncio
import logging
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from PIL import Image

from app.core.config import get_settings
from app.models.episode import Episode, EpisodeStatus

logger = logging.getLogger("app.youtube")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_credentials() -> Credentials:
    """Load/refresh token.json; run the one-time browser consent if needed."""
    settings = get_settings()
    token_path = Path(settings.youtube_token_file)
    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    elif not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            settings.youtube_client_secret_file, SCOPES
        )
        creds = flow.run_local_server(port=0, prompt="consent")
        token_path.write_text(creds.to_json(), encoding="utf-8")
        logger.info("YouTube OAuth complete; token saved to %s", token_path)

    return creds


def _thumbnail_jpeg(image_path: str) -> bytes:
    """YouTube thumbnails must be <2MB; convert our PNG to a compact JPEG."""
    img = Image.open(image_path).convert("RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue()


def _upload_sync(episode: Episode) -> str:
    settings = get_settings()
    youtube = build("youtube", "v3", credentials=get_credentials())

    body = {
        "snippet": {
            "title": episode.metadata.title,
            "description": episode.metadata.description,
            "tags": episode.metadata.tags,
            "categoryId": settings.youtube_category_id,
        },
        "status": {
            "privacyStatus": episode.privacy or settings.default_privacy,
            "selfDeclaredMadeForKids": settings.youtube_made_for_kids,
        },
    }

    media = MediaFileUpload(
        episode.video_path, mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True
    )
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info("Upload progress: %d%%", int(status.progress() * 100))
    video_id = response["id"]
    logger.info("Uploaded video id=%s", video_id)

    # Thumbnail (non-fatal if it fails — the video is already up).
    thumb_src = episode.thumbnail_path or episode.image_path
    if thumb_src and Path(thumb_src).exists():
        try:
            thumb = MediaIoBaseUpload(
                BytesIO(_thumbnail_jpeg(thumb_src)), mimetype="image/jpeg"
            )
            youtube.thumbnails().set(videoId=video_id, media_body=thumb).execute()
            logger.info("Thumbnail set for %s", video_id)
        except HttpError as exc:
            if exc.resp.status == 403:
                logger.warning(
                    "Custom thumbnail rejected for %s: the channel isn't verified for "
                    "advanced features yet. Enable 'Intermediate features' at "
                    "youtube.com/features (can take up to 24h after phone verification). "
                    "The video uploaded fine.",
                    video_id,
                )
            else:
                logger.warning("Thumbnail failed for %s (video is fine): %s", video_id, exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Thumbnail failed for %s (video is fine): %s", video_id, exc)

    return video_id


async def run_upload_stage(episode: Episode) -> Episode:
    """State-machine stage: metadata_done -> uploaded."""
    if not episode.video_path or not Path(episode.video_path).exists():
        raise ValueError("Episode has no video file to upload.")
    if not episode.metadata.title:
        raise ValueError("Episode has no metadata (title) — generate metadata first.")

    try:
        video_id = await asyncio.to_thread(_upload_sync, episode)
        episode.youtube_video_id = video_id
        episode.status = EpisodeStatus.uploaded
        episode.error = None
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        return episode
    except Exception as exc:  # noqa: BLE001 - persist + re-raise
        logger.exception("Upload failed for episode %s", episode.id)
        episode.status = EpisodeStatus.failed
        episode.error = f"upload: {exc}"
        episode.retry_count += 1
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        raise
