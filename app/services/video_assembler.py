"""M3 (part 2) — Video assembler.

Static illustrated background + episode audio -> 1080p MP4, now with:
  - burned-in live captions (.ass, synced to the real per-turn timings)
  - an animated audio waveform (bottom center), like the big podcast channels

Encoded with libx264 + yuv420p + AAC + faststart — the flags that keep the file
playable everywhere and previewable on YouTube.
"""

import asyncio
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.core import media
from app.core.config import get_settings
from app.models.episode import Episode, EpisodeStatus
from app.services.captions import build_ass, estimate_timings

logger = logging.getLogger("app.video")


def _ffmpeg_filter_path(p: str) -> str:
    """Escape a Windows path for use inside an ffmpeg filter argument."""
    return Path(p).resolve().as_posix().replace(":", r"\:")


def _build_ffmpeg_cmd(
    image: str,
    audio: str,
    out: str,
    captions: str | None,
    intro_image: str | None = None,
    intro_seconds: float = 0.0,
) -> list[str]:
    s = get_settings()
    w, h = s.image_width, s.image_height
    intro = intro_image is not None and intro_seconds > 0

    chain = f"[0:v]scale={w}:{h},setsar=1[bg]"
    last = "bg"
    audio_src = "1:a"
    if intro:
        # Silent intro: show the topic title card while the audio is delayed, then
        # switch to the talking scene exactly when the voices start.
        delay_ms = int(intro_seconds * 1000)
        chain += (
            f";[2:v]scale={w}:{h},setsar=1[intro]"
            f";[{last}][intro]overlay=0:0:enable='lt(t,{intro_seconds})'[vi]"
            f";[1:a]adelay={delay_ms}:all=1[aud]"
        )
        last = "vi"
        audio_src = "[aud]"
    if s.video_waveform:
        wave_enable = f":enable='gte(t,{intro_seconds})'" if intro else ""
        wave_in = "[aud]asplit[a1][a2];[a2]" if intro else "[1:a]"
        chain += (
            f";{wave_in}showwaves=s={s.waveform_width}x{s.waveform_height}"
            f":mode=cline:rate={s.video_fps}:colors={s.waveform_color}@0.85[wave]"
            f";[{last}][wave]overlay=(W-w)/2:H-h-{s.waveform_margin_bottom}"
            f":format=auto{wave_enable}[wv]"
        )
        last = "wv"
        if intro:
            audio_src = "[a1]"
    if captions:
        chain += f";[{last}]subtitles=filename='{_ffmpeg_filter_path(captions)}'[cap]"
        last = "cap"
    chain += f";[{last}]format=yuv420p[vout]"

    cmd_inputs = [
        "-loop", "1",
        "-framerate", str(s.video_fps),
        "-i", image,
        "-i", audio,
    ]
    if intro:
        cmd_inputs += ["-loop", "1", "-framerate", str(s.video_fps), "-i", intro_image]

    return [
        media.ffmpeg_exe(),
        "-y",
        *cmd_inputs,
        "-filter_complex", chain,
        "-map", "[vout]",
        "-map", audio_src,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", str(s.video_crf),
        "-c:a", "aac",
        "-b:a", s.video_audio_bitrate,
        "-shortest",
        "-movflags", "+faststart",  # web-streamable: moov atom at the front
        out,
    ]


async def assemble_video(
    image_path: str,
    audio_path: str,
    out_path: str,
    *,
    captions_path: str | None = None,
    intro_image_path: str | None = None,
    intro_seconds: float = 0.0,
) -> None:
    """Run ffmpeg to produce the MP4. Raises RuntimeError with ffmpeg's stderr on failure."""
    for label, p in (("image", image_path), ("audio", audio_path)):
        if not Path(p).exists():
            raise FileNotFoundError(f"Missing {label}: {p}")
    if intro_image_path and not Path(intro_image_path).exists():
        intro_image_path = None  # missing intro card is non-fatal

    # Render to a temp name, promote on success — an interrupted render must never
    # leave a half-written file that looks like a finished video.
    tmp_path = str(Path(out_path).with_suffix(".part.mp4"))
    cmd = _build_ffmpeg_cmd(
        image_path, audio_path, tmp_path, captions_path, intro_image_path, intro_seconds
    )
    logger.info(
        "Assembling video -> %s (captions=%s, intro=%.1fs)",
        out_path, bool(captions_path), intro_seconds if intro_image_path else 0,
    )
    # Plain subprocess in a worker thread: asyncio subprocesses are NOT supported by
    # the selector event loop uvicorn uses on Windows (raises NotImplementedError).
    # CREATE_NEW_PROCESS_GROUP shields ffmpeg from a Ctrl+C aimed at the server.
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = await asyncio.to_thread(
        subprocess.run, cmd,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=flags,
    )
    if proc.returncode != 0:
        Path(tmp_path).unlink(missing_ok=True)
        tail = proc.stderr.decode(errors="ignore")[-1500:]
        raise RuntimeError(f"ffmpeg failed (code {proc.returncode}):\n{tail}")
    Path(tmp_path).replace(out_path)


def _write_captions(episode: Episode, offset: float = 0.0) -> str | None:
    """Build the .ass file for this episode; None if captions are disabled/no script."""
    if not get_settings().video_captions or not episode.script:
        return None
    timings = episode.turn_timings
    if not timings:  # audio predates timing capture — estimate from word share
        duration = episode.audio_duration_seconds or 0
        if not duration:
            return None
        timings = estimate_timings(episode.script, duration)
    ass_text = build_ass(episode.script, timings, episode.hosts, offset=offset)
    d = media.media_root() / "captions"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{episode.id}.ass"
    path.write_text(ass_text, encoding="utf-8")
    return str(path)


async def run_video_stage(episode: Episode) -> Episode:
    """State-machine stage: image_done -> video_done."""
    if not episode.audio_path:
        raise ValueError("Episode has no audio to assemble.")
    if not episode.image_path:
        raise ValueError("Episode has no image to assemble.")

    try:
        s = get_settings()
        intro_image = episode.thumbnail_path
        intro_seconds = s.video_intro_seconds if intro_image else 0.0
        captions_path = _write_captions(episode, offset=intro_seconds)
        out_path = media.video_path_for(str(episode.id))
        await assemble_video(
            episode.image_path, episode.audio_path, str(out_path),
            captions_path=captions_path,
            intro_image_path=intro_image,
            intro_seconds=intro_seconds,
        )

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
        episode.error = f"video: {type(exc).__name__}: {exc}"
        episode.retry_count += 1
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        raise
