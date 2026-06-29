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

from app.core import media, prompts
from app.core.config import get_settings
from app.core.pricing import image_cost
from app.models.episode import Episode, EpisodeStatus
from app.services.image import get_image_provider
from app.services.image.overlay import compose

logger = logging.getLogger("app.image")


@dataclass
class ImageRenderResult:
    png: bytes
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

    png = compose(base_png, title, s.channel_brand_name, hosts, overlay_text=s.image_overlay_text)
    return ImageRenderResult(png=png, prompt=prompt, cost_usd=cost)


async def _produce(episode: Episode, feedback: str | None) -> Episode:
    title = episode.metadata.title or episode.topic
    result = await render_episode_image(
        title=title, topic=episode.topic, hosts=episode.hosts, feedback=feedback
    )
    out_path = media.image_path_for(str(episode.id))
    out_path.write_bytes(result.png)

    episode.image_path = str(out_path)
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
