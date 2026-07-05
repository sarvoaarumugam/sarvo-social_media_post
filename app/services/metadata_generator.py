"""M4 (part 1) — Metadata generator: the packaging stage.

script + blueprint -> final title, SEO description with chapter timestamps, tags.

Chapter timestamps are COMPUTED here, not guessed by the model: the model only says
at which dialogue turn each chapter starts; we convert that to a time offset using
each turn's share of the total word count against the real audio duration.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core import prompts
from app.core.config import get_settings
from app.core.pricing import text_cost
from app.models.episode import Episode, EpisodeMetadata, EpisodeStatus
from app.services.strategy_generator import blueprint_to_text, load_style_dna

logger = logging.getLogger("app.metadata")


class ChapterPoint(BaseModel):
    turn_index: int
    title: str


class GeneratedMetadata(BaseModel):
    """Strict schema the packaging model must fill."""

    title: str
    description: str
    tags: list[str]
    chapters: list[ChapterPoint]


@dataclass
class MetadataResult:
    metadata: EpisodeMetadata
    cost_usd: float


def _fmt_ts(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def _chapter_lines(
    chapters: list[ChapterPoint], turn_words: list[int], duration_s: float,
    offset_s: float = 0.0,
) -> list[str]:
    """Turn 'starts at turn N' into 'MM:SS Title' lines using word-share timing.

    `offset_s` shifts chapters for the silent intro card at the video start.
    YouTube rules honored: first chapter at 00:00, ascending, >=10s apart.
    """
    total_words = sum(turn_words) or 1
    cum = [0]
    for w in turn_words:
        cum.append(cum[-1] + w)

    lines: list[str] = []
    last_ts = -10.0
    for i, ch in enumerate(sorted(chapters, key=lambda c: c.turn_index)):
        idx = min(max(ch.turn_index, 0), len(turn_words) - 1)
        ts = 0.0 if i == 0 else (cum[idx] / total_words) * duration_s + offset_s
        if ts - last_ts < 10:  # YouTube requires >=10s between chapters
            continue
        lines.append(f"{_fmt_ts(ts)} {ch.title.strip()}")
        last_ts = ts
    return lines


async def generate_metadata(episode: Episode) -> MetadataResult:
    """Produce the final packaging. Pure: no DB writes."""
    settings = get_settings()
    if not episode.script:
        raise ValueError("Episode has no script to package.")

    model = settings.openai_script_model
    numbered_script = "\n".join(
        f"[{i}] {t.speaker}: {t.text}" for i, t in enumerate(episode.script)
    )
    blueprint_text = (
        blueprint_to_text(episode.blueprint) if episode.blueprint else "(no blueprint)"
    )

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    completion = await client.chat.completions.parse(
        model=model,
        temperature=0.7,
        messages=[
            {
                "role": "system",
                "content": prompts.render(
                    "metadata",
                    "system",
                    brand=settings.channel_brand_name,
                    language=settings.show_language,
                    style_dna=load_style_dna(),
                ),
            },
            {
                "role": "user",
                "content": prompts.render(
                    "metadata",
                    "user",
                    topic=episode.topic,
                    blueprint=blueprint_text,
                    script=numbered_script,
                ),
            },
        ],
        response_format=GeneratedMetadata,
    )

    parsed = completion.choices[0].message.parsed
    if parsed is None or not parsed.title:
        raise RuntimeError("Model returned no metadata.")

    turn_words = [len(t.text.split()) for t in episode.script]
    duration = episode.audio_duration_seconds or (sum(turn_words) / 150) * 60
    intro = settings.video_intro_seconds if episode.thumbnail_path else 0.0
    chapter_lines = _chapter_lines(parsed.chapters, turn_words, duration, intro)

    description = parsed.description.strip()
    if len(chapter_lines) >= 3:  # YouTube needs >=3 to render chapters
        description += "\n\nCHAPTERS:\n" + "\n".join(chapter_lines)

    usage = completion.usage
    cost = text_cost(model, usage.prompt_tokens if usage else 0,
                     usage.completion_tokens if usage else 0)

    metadata = EpisodeMetadata(
        title=parsed.title.strip()[:100],  # YouTube hard limit
        description=description[:4900],  # stay under the 5000-char limit
        tags=[t.strip().lower() for t in parsed.tags if t.strip()][:20],
        chapters=chapter_lines,
    )
    logger.info("Metadata done: %r, %d tags, %d chapters, $%.4f",
                metadata.title, len(metadata.tags), len(chapter_lines), cost)
    return MetadataResult(metadata=metadata, cost_usd=cost)


async def run_metadata_stage(episode: Episode) -> Episode:
    """State-machine stage: video_done -> metadata_done (also runnable earlier)."""
    try:
        result = await generate_metadata(episode)
        episode.metadata = result.metadata
        episode.cost_log.metadata += result.cost_usd
        if episode.status == EpisodeStatus.video_done:
            episode.status = EpisodeStatus.metadata_done
        episode.error = None
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        return episode
    except Exception as exc:  # noqa: BLE001 - persist + re-raise
        logger.exception("Metadata stage failed for episode %s", episode.id)
        episode.status = EpisodeStatus.failed
        episode.error = f"metadata: {exc}"
        episode.retry_count += 1
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        raise
