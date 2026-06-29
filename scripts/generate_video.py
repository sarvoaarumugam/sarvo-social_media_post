"""M3 preview CLI — build a playable 1080p MP4 (title card + audio).

To test M3 cheaply, point it at an audio file you already generated:
    uv run python scripts/generate_video.py "My Episode Title" --audio media/preview.mp3

Full pipeline from scratch (script -> audio -> image -> video, costs API calls):
    uv run python scripts/generate_video.py "Topic" --minutes 2 --full
"""

import argparse
import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.services.image.overlay import compose
from app.services.video_assembler import assemble_video


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Preview the M3 image + video assembly.")
    p.add_argument("title", help="Title shown on the card (use your topic)")
    p.add_argument("--audio", default="media/preview.mp3", help="Existing audio to use")
    p.add_argument("--minutes", type=float, default=2.0, help="Only used with --full")
    p.add_argument("--full", action="store_true", help="Also generate script + audio (costs $)")
    p.add_argument("--out", default="media/preview.mp4")
    return p.parse_args()


async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    hosts = settings.default_hosts
    audio_path = args.audio

    if args.full:
        from app.services.script_generator import generate_script
        from app.services.tts.service import synthesize_script

        print("1/3 Script + audio (OpenAI)...")
        script = await generate_script(
            args.title, hosts, target_words=settings.words_for_minutes(args.minutes)
        )
        audio = await synthesize_script(script.turns, hosts)
        audio_path = "media/preview.mp3"
        Path(audio_path).write_bytes(audio.audio_bytes)
        print(f"    audio -> {audio_path} ({audio.duration_seconds:.0f}s)")

    if not Path(audio_path).exists():
        raise SystemExit(f"Audio not found: {audio_path}. Run with --full or pass --audio.")

    print("2/3 Rendering title card (Pillow overlay, free)...")
    png = compose(None, args.title, settings.channel_brand_name, hosts)
    img_path = "media/preview.png"
    Path(img_path).write_bytes(png)
    print(f"    image -> {img_path}  ({settings.image_width}x{settings.image_height})")

    print("3/3 Assembling MP4 (ffmpeg)...")
    out = args.out
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    await assemble_video(img_path, audio_path, out)

    print("-" * 60)
    print(f"Saved : {Path(out).resolve()}")
    print(">> Open it and watch — that's the M3 deliverable: a playable 1080p video.")


if __name__ == "__main__":
    asyncio.run(main())
