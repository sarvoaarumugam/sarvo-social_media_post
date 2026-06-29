"""M2 — Audio service. THE quality gate.

script (turns) -> per-turn TTS in each host's voice -> stitched with natural
turn-taking gaps -> loudness-normalized -> a single human-sounding MP3.

Two entry points (same pattern as scripting):
    synthesize_script(...)   -> pure: returns audio bytes + duration (no DB).
    run_audio_stage(episode) -> state-machine stage: scripted -> audio_done.
"""

import asyncio
import logging
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO

from pydub import AudioSegment
from pydub.effects import normalize as _peak_normalize

# Importing `media` configures pydub to use the bundled ffmpeg (import side effect).
from app.core import media, prompts
from app.core.config import get_settings
from app.core.pricing import tts_cost
from app.models.episode import DialogueTurn, Episode, EpisodeStatus
from app.services.tts import get_tts_provider
from app.services.tts.base import TTSProvider

logger = logging.getLogger("app.tts")


@dataclass
class AudioResult:
    audio_bytes: bytes
    duration_seconds: float
    cost_usd: float
    voices: dict[str, str]


def voice_map(hosts: list[str]) -> dict[str, str]:
    settings = get_settings()
    voices = [settings.tts_voice_host1, settings.tts_voice_host2]
    return {host: voices[i % len(voices)] for i, host in enumerate(hosts)}


def _instructions_map(hosts: list[str]) -> dict[str, str]:
    settings = get_settings()
    personas = [settings.tts_persona_host1, settings.tts_persona_host2]
    return {
        host: prompts.render("audio", "delivery", persona=personas[i % len(personas)])
        for i, host in enumerate(hosts)
    }


def _wav_bytes_to_segment(data: bytes) -> AudioSegment:
    """Decode WAV bytes via the stdlib (no ffprobe). Providers return WAV per chunk."""
    with wave.open(BytesIO(data), "rb") as w:
        return AudioSegment(
            data=w.readframes(w.getnframes()),
            sample_width=w.getsampwidth(),
            frame_rate=w.getframerate(),
            channels=w.getnchannels(),
        )


def _normalize_loudness(seg: AudioSegment, target_dbfs: float) -> AudioSegment:
    """Peak-normalize, then bring overall loudness to a consistent target dBFS."""
    seg = _peak_normalize(seg)
    if seg.dBFS == float("-inf"):
        return seg
    return seg.apply_gain(target_dbfs - seg.dBFS)


async def synthesize_script(
    turns: list[DialogueTurn],
    hosts: list[str],
    *,
    provider: TTSProvider | None = None,
) -> AudioResult:
    """Render a full script to one normalized MP3 (returned as bytes). No DB writes."""
    if not turns:
        raise ValueError("Cannot synthesize audio: script has no turns.")

    settings = get_settings()
    provider = provider or get_tts_provider()
    voices = voice_map(hosts)
    instructions = _instructions_map(hosts)
    sem = asyncio.Semaphore(settings.tts_concurrency)

    async def _render(index: int, turn: DialogueTurn) -> tuple[int, AudioSegment]:
        async with sem:
            audio = await provider.synthesize(
                turn.text,
                voice=voices[turn.speaker],
                instructions=instructions[turn.speaker],
            )
        return index, _wav_bytes_to_segment(audio)

    logger.info("Synthesizing %d turns (concurrency=%d)", len(turns), settings.tts_concurrency)
    rendered = await asyncio.gather(*(_render(i, t) for i, t in enumerate(turns)))
    rendered.sort(key=lambda pair: pair[0])

    # Stitch with natural gaps: a small gap mid-speaker, a slightly longer one when
    # the conversation hands over to the other host.
    final = AudioSegment.empty()
    prev_speaker: str | None = None
    for (idx, segment), turn in zip(rendered, turns):
        if prev_speaker is not None:
            gap = (
                settings.tts_pause_same_ms
                if turn.speaker == prev_speaker
                else settings.tts_pause_turn_ms
            )
            final += AudioSegment.silent(duration=gap)
        final += segment
        prev_speaker = turn.speaker

    final = _normalize_loudness(final, settings.tts_target_dbfs)

    buffer = BytesIO()
    final.export(buffer, format=settings.tts_format, bitrate="128k")
    duration = len(final) / 1000.0
    cost = tts_cost(duration, settings.tts_cost_per_minute)
    logger.info("Audio done: %.1fs, $%.4f", duration, cost)

    return AudioResult(
        audio_bytes=buffer.getvalue(),
        duration_seconds=round(duration, 2),
        cost_usd=cost,
        voices=voices,
    )


async def run_audio_stage(episode: Episode) -> Episode:
    """State-machine stage: scripted episode -> audio_done.

    Persists the mp3 to disk, records path/duration/cost, or records the error and
    bumps retry_count on failure (never crashes the queue).
    """
    if not episode.script:
        raise ValueError("Episode has no script to synthesize.")

    episode.updated_at = datetime.now(timezone.utc)
    await episode.save()

    try:
        result = await synthesize_script(episode.script, episode.hosts)

        out_path = media.audio_path_for(str(episode.id))
        out_path.write_bytes(result.audio_bytes)

        episode.audio_path = str(out_path)
        episode.audio_duration_seconds = result.duration_seconds
        episode.cost_log.tts = result.cost_usd
        episode.status = EpisodeStatus.audio_done
        episode.error = None
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        return episode
    except Exception as exc:  # noqa: BLE001 - persist + re-raise
        logger.exception("Audio stage failed for episode %s", episode.id)
        episode.status = EpisodeStatus.failed
        episode.error = f"audio: {exc}"
        episode.retry_count += 1
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        raise
