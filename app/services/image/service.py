"""M3 (part 1, upgraded) — Image service.

audio_done -> generate an AI cover image (gpt-image-1) -> overlay the title ->
image_done. The user reviews it and can REGENERATE with their own feedback before
the video is assembled.

Entry points:
    render_episode_image(...)         -> pure: returns png bytes + prompt + cost.
    run_image_stage(episode)          -> first generation (audio_done -> image_done).
    run_image_regeneration(ep, text)  -> regenerate using the user's feedback.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core import media, prompts
from app.core.config import get_settings
from app.core.pricing import image_cost
from app.models.episode import Episode, EpisodeStatus
from app.services.image import get_image_provider
from app.services.image.overlay import compose_background, compose_thumbnail_card

logger = logging.getLogger("app.image")


@dataclass
class ImageRenderResult:
    background_png: bytes  # clean scene used inside the video
    thumbnail_png: bytes  # title-overlay variant for the YouTube thumbnail
    prompt: str | None
    cost_usd: float


async def render_episode_image(
    *, title: str, topic: str, hosts: list[str], feedback: str | None = None
) -> ImageRenderResult:
    """Generate the AI background (unless provider is 'pillow') and overlay the title."""
    s = get_settings()

    base_png: bytes | None = None
    prompt: str | None = None
    cost = 0.0

    if s.image_provider.lower() != "pillow":
        if feedback:
            prompt = prompts.render(
                "image", "regeneration",
                topic=topic, brand=s.channel_brand_name, style=s.image_style, feedback=feedback,
            )
        else:
            prompt = prompts.render(
                "image", "generation",
                topic=topic, brand=s.channel_brand_name, style=s.image_style,
            )
        provider = get_image_provider()
        base_png = await provider.generate(prompt, quality=s.image_quality)
        cost = image_cost(getattr(provider, "last_model", s.openai_image_model), s.image_quality)

    background = _make_background(base_png)
    thumbnail = compose_thumbnail_card(base_png, title)
    return ImageRenderResult(
        background_png=background, thumbnail_png=thumbnail, prompt=prompt, cost_usd=cost
    )


def _make_background(ai_png: bytes | None) -> bytes:
    """Fixed background from assets/ if present (brand mark top-left), else AI art."""
    s = get_settings()
    custom_bg = Path(s.background_image_file)
    if custom_bg.exists():
        logger.info("Using fixed background: %s", custom_bg)
        return compose_background(custom_bg.read_bytes(), brand=s.background_brand_text)
    return compose_background(ai_png, brand=s.background_brand_text)


async def _produce(episode: Episode, feedback: str | None) -> Episode:
    title = episode.metadata.title or episode.topic
    result = await render_episode_image(
        title=title, topic=episode.topic, hosts=episode.hosts, feedback=feedback
    )
    out_path = media.image_path_for(str(episode.id))
    out_path.write_bytes(result.background_png)
    thumb_path = out_path.with_name(f"{episode.id}_thumb.png")
    thumb_path.write_bytes(result.thumbnail_png)

    episode.image_path = str(out_path)
    episode.thumbnail_path = str(thumb_path)
    episode.image_prompt = result.prompt
    episode.cost_log.image = result.cost_usd
    episode.status = EpisodeStatus.image_done
    episode.error = None
    episode.updated_at = datetime.now(timezone.utc)
    await episode.save()
    logger.info("Image ready for episode %s (regen=%s) -> %s", episode.id, bool(feedback), out_path)
    return episode


async def run_image_stage(episode: Episode) -> Episode:
    """First image generation: audio_done -> image_done."""
    try:
        return await _produce(episode, feedback=None)
    except Exception as exc:  # noqa: BLE001 - persist + re-raise
        logger.exception("Image stage failed for episode %s", episode.id)
        episode.status = EpisodeStatus.failed
        episode.error = f"image: {exc}"
        episode.retry_count += 1
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        raise


def list_preset_thumbnails() -> list[str]:
    """Preset thumbnail designs the user dropped into assets/ (thumbnail_*.png|jpg)."""
    assets = Path(get_settings().background_image_file).parent
    names = [p.name for p in assets.glob("thumbnail_*.png")]
    names += [p.name for p in assets.glob("thumbnail_*.jpg")]
    return sorted(names)


def preset_path(name: str) -> Path:
    """Resolve a preset name safely (no path traversal — must be a listed file)."""
    if name not in list_preset_thumbnails():
        raise FileNotFoundError(f"Unknown preset thumbnail: {name}")
    return Path(get_settings().background_image_file).parent / name


async def run_image_preset_stage(episode: Episode, preset_name: str) -> Episode:
    """Use a preset design from assets/ as this episode's thumbnail (topic drawn
    top-center) — zero AI cost. Background comes from assets/ as usual."""
    try:
        base = preset_path(preset_name).read_bytes()
        title = episode.metadata.title or episode.topic

        out_path = media.image_path_for(str(episode.id))
        out_path.write_bytes(_make_background(None))
        thumb_path = out_path.with_name(f"{episode.id}_thumb.png")
        thumb_path.write_bytes(compose_thumbnail_card(base, title))

        episode.image_path = str(out_path)
        episode.thumbnail_path = str(thumb_path)
        episode.image_prompt = f"preset: {preset_name}"
        episode.cost_log.image = 0.0
        episode.status = EpisodeStatus.image_done
        episode.error = None
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        logger.info("Preset thumbnail %s applied to episode %s", preset_name, episode.id)
        return episode
    except Exception as exc:  # noqa: BLE001 - persist + re-raise
        logger.exception("Preset image failed for episode %s", episode.id)
        episode.status = EpisodeStatus.failed
        episode.error = f"image: {type(exc).__name__}: {exc}"
        episode.retry_count += 1
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        raise


async def run_image_regeneration(episode: Episode, feedback: str) -> Episode:
    """Regenerate the image using the user's feedback, then return to image_done."""
    try:
        return await _produce(episode, feedback=feedback)
    except Exception as exc:  # noqa: BLE001 - persist + re-raise
        logger.exception("Image regeneration failed for episode %s", episode.id)
        episode.status = EpisodeStatus.failed
        episode.error = f"image: {exc}"
        episode.retry_count += 1
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        raise
