"""Wire pydub to the bundled ffmpeg binary (no host install required) and provide
helpers for where generated media lives.

Importing this module configures pydub as a side effect, so any module that builds
audio should `import app.core.media` (or import a helper from it) first.
"""

from pathlib import Path

import imageio_ffmpeg
from pydub import AudioSegment

from app.core.config import get_settings

# Point pydub at the ffmpeg shipped with imageio-ffmpeg.
_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
AudioSegment.converter = _FFMPEG
AudioSegment.ffmpeg = _FFMPEG


def ffmpeg_exe() -> str:
    """Absolute path to the ffmpeg binary (also used by the video stage in M3)."""
    return _FFMPEG


def media_root() -> Path:
    root = Path(get_settings().media_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def audio_path_for(episode_id: str) -> Path:
    return _sub("audio") / f"{episode_id}.{get_settings().tts_format}"


def image_path_for(episode_id: str) -> Path:
    return _sub("images") / f"{episode_id}.png"


def video_path_for(episode_id: str) -> Path:
    return _sub("video") / f"{episode_id}.mp4"


def _sub(name: str) -> Path:
    d = media_root() / name
    d.mkdir(parents=True, exist_ok=True)
    return d
