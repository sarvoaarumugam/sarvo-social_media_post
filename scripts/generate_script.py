"""M1 preview CLI — generate a script for a topic and print it for review.

This is the "show it to me" step: it makes a real OpenAI call and prints the
two-host dialogue, word count, and cost. No database writes (pure preview).

Usage:
    uv run python scripts/generate_script.py
    uv run python scripts/generate_script.py "Your topic here"
    uv run python scripts/generate_script.py "Topic" --host1 Anna --host2 Jake
"""

import argparse
import asyncio

from app.core.config import get_settings
from app.services.script_generator import generate_script

DEFAULT_TOPIC = (
    "Don't Waste Your Life | English Podcast for Easy Conversation in Daily Life | "
    "Learn English Fast"
)


def _parse_args() -> argparse.Namespace:
    settings = get_settings()
    h1, h2 = settings.default_hosts[0], settings.default_hosts[1]
    p = argparse.ArgumentParser(description="Preview a generated podcast script.")
    p.add_argument("topic", nargs="?", default=DEFAULT_TOPIC, help="Episode topic")
    p.add_argument("--host1", default=h1)
    p.add_argument("--host2", default=h2)
    p.add_argument(
        "--minutes",
        type=float,
        default=settings.default_duration_minutes,
        help="Desired episode length in minutes",
    )
    return p.parse_args()


async def main() -> None:
    args = _parse_args()
    hosts = [args.host1, args.host2]
    target_words = get_settings().words_for_minutes(args.minutes)

    print(f"\nTopic : {args.topic}")
    print(f"Hosts : {hosts[0]} & {hosts[1]}")
    print(f"Length: ~{args.minutes} min  (~{target_words} words)")
    print("Generating... (calling OpenAI)\n" + "-" * 70)

    result = await generate_script(args.topic, hosts, target_words=target_words)

    for turn in result.turns:
        print(f"\n{turn.speaker}: {turn.text}")

    print("\n" + "-" * 70)
    print(f"Turns      : {len(result.turns)}")
    print(f"Word count : {result.word_count}  (~{result.word_count / 150:.1f} min @150 wpm)")
    print(f"Tokens     : in={result.input_tokens}  out={result.output_tokens}")
    print(f"Model      : {result.model}")
    print(f"Cost       : ${result.cost_usd:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
