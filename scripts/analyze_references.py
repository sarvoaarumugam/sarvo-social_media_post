"""Distill reference transcripts into the Style DNA.

Drop transcripts of videos you admire (each as a .txt file) into the references/
folder, then run:

    uv run python scripts/analyze_references.py

It analyzes WHY they work (hooks, loop placement, pacing, emotional beats) and
rewrites the `dna` block in prompts/style_dna.yaml. The pipeline picks the new
DNA up automatically on the next generation — no code changes.
"""

import asyncio
from pathlib import Path

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.pricing import text_cost

REFERENCES_DIR = Path("references")
STYLE_DNA_PATH = Path("prompts/style_dna.yaml")

ANALYSIS_PROMPT = """\
You are a world-class YouTube retention analyst. Below are transcripts of highly \
successful videos. Extract the transferable PRINCIPLES that make them hold attention — \
NOT their topics, names, or wording.

Analyze: how the hooks are built, where and how open loops are planted and closed, \
how often the pattern changes and with what devices, how concrete details/stories are \
used, the emotional rhythm, how stakes are raised, and how they close.

Write the result as a numbered list of 8-12 sharp, actionable principles titled \
'RETENTION DNA (distilled from reference videos):'. Each principle must be a directive \
a scriptwriter can follow (imperative voice), niche-agnostic, with no references to \
the specific videos. Output ONLY the list, no preamble.

TRANSCRIPTS:
{transcripts}
"""

HEADER = """\
# ============================================================
#  STYLE DNA — the distilled "why top videos win" principles.
#  Injected into BOTH the strategist and the scriptwriter.
#
#  This block was distilled from the transcripts in references/
#  by scripts/analyze_references.py. Re-run it anytime you add
#  new reference transcripts.
# ============================================================

dna: |
"""


async def main() -> None:
    settings = get_settings()
    files = sorted(REFERENCES_DIR.glob("*.txt"))
    if not files:
        REFERENCES_DIR.mkdir(exist_ok=True)
        raise SystemExit(
            f"No transcripts found. Put .txt transcripts of videos you admire into "
            f"{REFERENCES_DIR.resolve()} and re-run."
        )

    print(f"Analyzing {len(files)} reference transcript(s):")
    chunks = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore").strip()
        print(f"  - {f.name} ({len(text.split())} words)")
        chunks.append(f"--- {f.name} ---\n{text[:24000]}")  # cap very long ones

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    completion = await client.chat.completions.create(
        model=settings.openai_script_model,
        temperature=0.4,  # analysis should be precise, not creative
        messages=[{
            "role": "user",
            "content": ANALYSIS_PROMPT.format(transcripts="\n\n".join(chunks)),
        }],
    )
    dna = completion.choices[0].message.content.strip()
    usage = completion.usage
    cost = text_cost(settings.openai_script_model, usage.prompt_tokens, usage.completion_tokens)

    indented = "\n".join(f"  {line}" if line.strip() else "" for line in dna.splitlines())
    STYLE_DNA_PATH.write_text(HEADER + indented + "\n", encoding="utf-8")

    print("-" * 60)
    print(f"Style DNA updated -> {STYLE_DNA_PATH}  (cost ${cost:.4f})")
    print("Next script/blueprint generation will use it automatically.")


if __name__ == "__main__":
    asyncio.run(main())
