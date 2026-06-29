"""Episode endpoints: enqueue a topic, list, and fetch one.

These are thin controllers — they only touch persistence/state. The actual
pipeline work (scripting, tts, video, upload) lives in app/services and is driven
by the orchestrator, keeping the API layer free of business logic.
"""

from datetime import datetime, timezone
from pathlib import Path

from beanie import PydanticObjectId
from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.exceptions.handlers import AppError
from app.models.episode import Episode, EpisodeStatus
from app.schemas.audio import AudioRead
from app.schemas.episode import EpisodeCreate, EpisodeRead
from app.schemas.media import ImageRead, ImageRegenerateRequest, VideoRead
from app.schemas.script import ScriptGenerateRequest, ScriptRead, ScriptUpdate
from app.services.image.service import run_image_regeneration, run_image_stage
from app.services.script_generator import count_words, run_scripting_stage
from app.services.tts.service import run_audio_stage, voice_map
from app.services.video_assembler import run_video_stage

router = APIRouter(prefix="/episodes", tags=["episodes"])


async def _get_or_404(episode_id: PydanticObjectId) -> Episode:
    episode = await Episode.get(episode_id)
    if episode is None:
        raise AppError("Episode not found", status_code=404)
    return episode


def _to_script_read(episode: Episode) -> ScriptRead:
    settings = get_settings()
    words = count_words(episode.script)
    return ScriptRead(
        episode_id=str(episode.id),
        status=episode.status,
        topic=episode.topic,
        hosts=episode.hosts,
        target_minutes=episode.target_minutes,
        word_count=words,
        est_minutes=round(words / settings.words_per_minute, 1),
        cost_usd=episode.cost_log.script,
        turns=episode.script,
    )


@router.post("", response_model=EpisodeRead, status_code=201)
async def create_episode(payload: EpisodeCreate):
    settings = get_settings()
    episode = Episode(
        topic=payload.topic,
        hosts=payload.hosts or settings.default_hosts,
        target_minutes=payload.duration_minutes or settings.default_duration_minutes,
        privacy=settings.default_privacy,
    )
    await episode.insert()
    return EpisodeRead.from_doc(episode)


@router.get("", response_model=list[EpisodeRead])
async def list_episodes():
    episodes = await Episode.find_all().sort(-Episode.created_at).to_list()
    return [EpisodeRead.from_doc(e) for e in episodes]


@router.get("/{episode_id}", response_model=EpisodeRead)
async def get_episode(episode_id: PydanticObjectId):
    return EpisodeRead.from_doc(await _get_or_404(episode_id))


# --- Scripting stage (M1) — the human review checkpoint ---


@router.post("/{episode_id}/script", response_model=ScriptRead)
async def generate_episode_script(
    episode_id: PydanticObjectId, payload: ScriptGenerateRequest | None = None
):
    """Generate (or regenerate) the two-host script, then return it for your review.

    Optionally send {"duration_minutes": N} to change the target length for this run
    (it also updates the episode's stored duration).
    """
    episode = await _get_or_404(episode_id)
    if payload and payload.duration_minutes is not None:
        episode.target_minutes = payload.duration_minutes
        await episode.save()
    episode = await run_scripting_stage(episode)
    return _to_script_read(episode)


@router.get("/{episode_id}/script", response_model=ScriptRead)
async def get_episode_script(episode_id: PydanticObjectId):
    """View the current stored script."""
    return _to_script_read(await _get_or_404(episode_id))


@router.put("/{episode_id}/script", response_model=ScriptRead)
async def update_episode_script(episode_id: PydanticObjectId, payload: ScriptUpdate):
    """Apply your manual corrections — replaces the dialogue, keeps it `scripted`."""
    episode = await _get_or_404(episode_id)
    if not payload.turns:
        raise AppError("Script must contain at least one turn.", status_code=422)
    episode.script = payload.turns
    episode.status = EpisodeStatus.scripted
    episode.updated_at = datetime.now(timezone.utc)
    await episode.save()
    return _to_script_read(episode)


# --- Audio stage (M2) — the human listen-and-approve checkpoint ---


def _to_audio_read(episode: Episode) -> AudioRead:
    dur = episode.audio_duration_seconds
    return AudioRead(
        episode_id=str(episode.id),
        status=episode.status,
        audio_path=episode.audio_path,
        duration_seconds=dur,
        est_minutes=round(dur / 60, 1) if dur else None,
        cost_usd=episode.cost_log.tts,
        voices=voice_map(episode.hosts),
    )


@router.post("/{episode_id}/audio", response_model=AudioRead)
async def generate_episode_audio(episode_id: PydanticObjectId):
    """Synthesize the human-sounding MP3 from the (approved) script."""
    episode = await _get_or_404(episode_id)
    if not episode.script:
        raise AppError("Generate a script before audio.", status_code=409)
    episode = await run_audio_stage(episode)
    return _to_audio_read(episode)


@router.get("/{episode_id}/audio", response_model=AudioRead)
async def get_episode_audio(episode_id: PydanticObjectId):
    """View audio metadata (path, duration, cost)."""
    return _to_audio_read(await _get_or_404(episode_id))


@router.get("/{episode_id}/audio/file")
async def download_episode_audio(episode_id: PydanticObjectId):
    """Stream the generated MP3 so you can listen in the browser."""
    episode = await _get_or_404(episode_id)
    if not episode.audio_path or not Path(episode.audio_path).exists():
        raise AppError("Audio not generated yet.", status_code=404)
    return FileResponse(
        episode.audio_path,
        media_type="audio/mpeg",
        filename=f"episode-{episode_id}.mp3",
    )


# --- Image stage (M3) — generate, review, regenerate with your input ---


def _to_image_read(episode: Episode) -> ImageRead:
    return ImageRead(
        episode_id=str(episode.id),
        status=episode.status,
        image_path=episode.image_path,
        image_prompt=episode.image_prompt,
        cost_usd=episode.cost_log.image,
    )


@router.post("/{episode_id}/image", response_model=ImageRead)
async def generate_episode_image(episode_id: PydanticObjectId):
    """Generate the AI cover image (gpt-image-1) with the title overlaid."""
    episode = await _get_or_404(episode_id)
    if not episode.audio_path:
        raise AppError("Generate audio before the image.", status_code=409)
    return _to_image_read(await run_image_stage(episode))


@router.post("/{episode_id}/image/regenerate", response_model=ImageRead)
async def regenerate_episode_image(episode_id: PydanticObjectId, payload: ImageRegenerateRequest):
    """Regenerate the image using your feedback (e.g. 'brighter, show a sunrise')."""
    episode = await _get_or_404(episode_id)
    if not payload.feedback.strip():
        raise AppError("Feedback is required to regenerate.", status_code=422)
    return _to_image_read(await run_image_regeneration(episode, payload.feedback.strip()))


@router.get("/{episode_id}/image", response_model=ImageRead)
async def get_episode_image(episode_id: PydanticObjectId):
    return _to_image_read(await _get_or_404(episode_id))


@router.get("/{episode_id}/image/file")
async def download_episode_image(episode_id: PydanticObjectId):
    episode = await _get_or_404(episode_id)
    if not episode.image_path or not Path(episode.image_path).exists():
        raise AppError("Image not generated yet.", status_code=404)
    return FileResponse(episode.image_path, media_type="image/png")


# --- Video stage (M3) — the watch-and-approve checkpoint ---


@router.post("/{episode_id}/video", response_model=VideoRead)
async def generate_episode_video(episode_id: PydanticObjectId):
    """Assemble image + audio into the final 1080p MP4."""
    episode = await _get_or_404(episode_id)
    if not episode.audio_path:
        raise AppError("Generate audio before video.", status_code=409)
    if not episode.image_path:
        raise AppError("Generate the image before video.", status_code=409)
    episode = await run_video_stage(episode)
    return VideoRead(
        episode_id=str(episode.id),
        status=episode.status,
        video_path=episode.video_path,
        duration_seconds=episode.audio_duration_seconds,
    )


@router.get("/{episode_id}/video", response_model=VideoRead)
async def get_episode_video(episode_id: PydanticObjectId):
    episode = await _get_or_404(episode_id)
    return VideoRead(
        episode_id=str(episode.id),
        status=episode.status,
        video_path=episode.video_path,
        duration_seconds=episode.audio_duration_seconds,
    )


@router.get("/{episode_id}/video/file")
async def download_episode_video(episode_id: PydanticObjectId):
    """Stream the final MP4 so you can watch it in the browser."""
    episode = await _get_or_404(episode_id)
    if not episode.video_path or not Path(episode.video_path).exists():
        raise AppError("Video not generated yet.", status_code=404)
    return FileResponse(
        episode.video_path,
        media_type="video/mp4",
        filename=f"episode-{episode_id}.mp4",
    )
