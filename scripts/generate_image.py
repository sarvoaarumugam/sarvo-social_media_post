"""M3 image preview CLI — generate an AI cover image, then optionally regenerate
it with your feedback. Saves PNGs so you can look at them.

    uv run python scripts/generate_image.py "Don't Waste Your Life"
    uv run python scripts/generate_image.py "Topic" --feedback "brighter, show a sunrise over a city"
"""

import argparse
import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.services.image.service import render_episode_image


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Preview AI cover image generation.")
    p.add_argument("title", help="Episode title/topic")
    p.add_argument("--feedback", default=None, help="Regenerate with this instruction")
    p.add_argument("--out", default="media/preview.png")
    return p.parse_args()


async def main() -> None:
    args = _parse_args()
    s = get_settings()

    print(f"\nTitle    : {args.title}")
    print(f"Provider : {s.image_provider}  ({s.openai_image_model}, quality={s.image_quality})")
    if args.feedback:
        print(f"Feedback : {args.feedback}")
    print("Generating image... (OpenAI)\n" + "-" * 60)

    result = await render_episode_image(
        title=args.title, topic=args.title, hosts=s.default_hosts, feedback=args.feedback
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(result.png)

    print(f"Saved : {out.resolve()}")
    print(f"Cost  : ${result.cost_usd:.4f}")
    print(f"Prompt: {result.prompt}")
    print("\n>> Open the image. To change it, re-run with --feedback \"your changes\".")


if __name__ == "__main__":
    asyncio.run(main())
