"""M2 preview CLI — generate a script AND synthesize a human-sounding MP3, then
save it so you can listen. Makes real OpenAI calls (script + TTS).

Usage:
    uv run python scripts/generate_audio.py
    uv run python scripts/generate_audio.py "Your topic" --minutes 3
    uv run python scripts/generate_audio.py "Topic" --out sample.mp3
"""

import argparse
import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.services.script_generator import generate_script
from app.services.tts.service import synthesize_script

DEFAULT_TOPIC = (
    "Don't Waste Your Life | English Podcast for Easy Conversation in Daily Life | "
    "Learn English Fast"
)


def _parse_args() -> argparse.Namespace:
    settings = get_settings()
    p = argparse.ArgumentParser(description="Preview script + human-sounding audio.")
    p.add_argument("topic", nargs="?", default=DEFAULT_TOPIC)
    p.add_argument("--host1", default=settings.default_hosts[0])
    p.add_argument("--host2", default=settings.default_hosts[1])
    p.add_argument("--minutes", type=float, default=2.0, help="Keep short for a quick test")
    p.add_argument("--out", default="media/preview.mp3")
    return p.parse_args()


async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    hosts = [args.host1, args.host2]
    target_words = settings.words_for_minutes(args.minutes)

    print(f"\nTopic  : {args.topic}")
    print(f"Hosts  : {hosts[0]} ({settings.tts_voice_host1}) & {hosts[1]} ({settings.tts_voice_host2})")
    print(f"Length : ~{args.minutes} min  (~{target_words} words)")
    print("1/2 Writing script... (OpenAI)")
    script = await generate_script(args.topic, hosts, target_words=target_words)
    print(f"    -> {len(script.turns)} turns, {script.word_count} words, ${script.cost_usd:.4f}")

    print("2/2 Synthesizing audio... (OpenAI TTS, this is the quality gate)")
    audio = await synthesize_script(script.turns, hosts)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(audio.audio_bytes)

    print("-" * 60)
    print(f"Saved  : {out.resolve()}")
    print(f"Length : {audio.duration_seconds:.1f}s  (~{audio.duration_seconds / 60:.1f} min)")
    print(f"TTS cost: ${audio.cost_usd:.4f}   |   Total: ${script.cost_usd + audio.cost_usd:.4f}")
    print("\n>> Open the file above and listen. That's the M2 quality gate.")


if __name__ == "__main__":
    asyncio.run(main())
