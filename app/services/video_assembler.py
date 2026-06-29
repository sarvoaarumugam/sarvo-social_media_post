"""M3 (part 2) — Video assembler.

Combines the static title card + the episode audio into a 1080p MP4 using the
bundled ffmpeg. Encodes with libx264 + yuv420p + AAC + faststart — the flags
that keep the file playable everywhere and previewable on YouTube.
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.core import media
from app.core.config import get_settings
from app.models.episode import Episode, EpisodeStatus

logger = logging.getLogger("app.video")


def _build_ffmpeg_cmd(image: str, audio: str, out: str) -> list[str]:
    s = get_settings()
    return [
        media.ffmpeg_exe(),
        "-y",
        "-loop", "1",
        "-framerate", str(s.video_fps),
        "-i", image,
        "-i", audio,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-pix_fmt", "yuv420p",  # REQUIRED or many players / YouTube preview break
        "-crf", str(s.video_crf),
        "-c:a", "aac",
        "-b:a", s.video_audio_bitrate,
        "-shortest",  # video length follows the audio
        "-movflags", "+faststart",  # web-streamable: moov atom at the front
        out,
    ]


async def assemble_video(image_path: str, audio_path: str, out_path: str) -> None:
    """Run ffmpeg to produce the MP4. Raises RuntimeError with ffmpeg's stderr on failure."""
    for label, p in (("image", image_path), ("audio", audio_path)):
        if not Path(p).exists():
            raise FileNotFoundError(f"Missing {label}: {p}")

    cmd = _build_ffmpeg_cmd(image_path, audio_path, out_path)
    logger.info("Assembling video -> %s", out_path)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        tail = stderr.decode(errors="ignore")[-1500:]
        raise RuntimeError(f"ffmpeg failed (code {proc.returncode}):\n{tail}")


async def run_video_stage(episode: Episode) -> Episode:
    """State-machine stage: image_done -> video_done."""
    if not episode.audio_path:
        raise ValueError("Episode has no audio to assemble.")
    if not episode.image_path:
        raise ValueError("Episode has no image to assemble.")

    try:
        out_path = media.video_path_for(str(episode.id))
        await assemble_video(episode.image_path, episode.audio_path, str(out_path))

        episode.video_path = str(out_path)
        episode.status = EpisodeStatus.video_done
        episode.error = None
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        logger.info("Video done for episode %s -> %s", episode.id, out_path)
        return episode
    except Exception as exc:  # noqa: BLE001 - persist + re-raise
        logger.exception("Video stage failed for episode %s", episode.id)
        episode.status = EpisodeStatus.failed
        episode.error = f"video: {exc}"
        episode.retry_count += 1
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        raise
