"""Stage 1 — Content Strategist.

topic -> Blueprint (titles, thumbnail concept, hooks, outline with open loops and
pattern interrupts, big loop, takeaway, CTA).

This runs BEFORE the script is written, because packaging + retention structure —
not prose — is what decides whether a video can reach millions of views. The
scriptwriter (stage 2) then follows this plan.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from openai import AsyncOpenAI

from app.core import prompts
from app.core.config import get_settings
from app.core.pricing import text_cost
from app.models.episode import Blueprint, Episode

logger = logging.getLogger("app.strategy")


@dataclass
class BlueprintResult:
    blueprint: Blueprint
    cost_usd: float
    model: str


def load_style_dna() -> str:
    """The distilled retention principles, editable in prompts/style_dna.yaml."""
    return prompts.render("style_dna", "dna")


def context_block(user_context: str | None) -> str:
    """Format the creator's own knowledge/notes for injection into prompts.
    Empty string when none was provided (the prompt reads naturally either way)."""
    if not user_context or not user_context.strip():
        return ""
    return (
        "\nCREATOR'S OWN KNOWLEDGE (important — treat this as the primary source of "
        "truth for the episode; ground facts, examples and explanations in it, and "
        "only supplement with general knowledge where it has gaps):\n"
        f"{user_context.strip()}\n"
    )


async def generate_blueprint(
    topic: str,
    hosts: list[str],
    *,
    minutes: float,
    context: str | None = None,
    model: str | None = None,
) -> BlueprintResult:
    """Produce the episode blueprint. Pure: no DB writes."""
    settings = get_settings()
    model = model or settings.openai_script_model
    target_words = settings.words_for_minutes(minutes)

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    logger.info("Generating blueprint: topic=%r model=%s", topic, model)

    completion = await client.chat.completions.parse(
        model=model,
        temperature=0.9,  # strategy benefits from bolder ideas
        messages=[
            {
                "role": "system",
                "content": prompts.render(
                    "strategy",
                    "system",
                    brand=settings.channel_brand_name,
                    host1=hosts[0],
                    host2=hosts[1],
                    language=settings.show_language,
                    tone=settings.show_tone,
                    minutes=minutes,
                    target_words=target_words,
                    style_dna=load_style_dna(),
                ),
            },
            {
                "role": "user",
                "content": prompts.render(
                    "strategy", "user", topic=topic, context=context_block(context)
                ),
            },
        ],
        response_format=Blueprint,
    )

    blueprint = completion.choices[0].message.parsed
    if blueprint is None or not blueprint.outline:
        raise RuntimeError("Strategist returned no blueprint.")
    # Guard the hook index against model drift.
    if not 0 <= blueprint.chosen_hook_index < len(blueprint.hooks):
        blueprint.chosen_hook_index = 0

    usage = completion.usage
    cost = text_cost(model, usage.prompt_tokens if usage else 0,
                     usage.completion_tokens if usage else 0)
    logger.info(
        "Blueprint done: %d sections, %d titles, $%.4f",
        len(blueprint.outline), len(blueprint.titles), cost,
    )
    return BlueprintResult(blueprint=blueprint, cost_usd=cost, model=model)


def blueprint_to_text(bp: Blueprint) -> str:
    """Readable form of the blueprint, injected into the scriptwriter's prompt."""
    hook = bp.hooks[bp.chosen_hook_index]
    lines = [
        f"WORKING TITLE: {bp.titles[0]}",
        f"COLD-OPEN HOOK (use this, verbatim or improved): {hook}",
        f"BIG LOOP (open at the hook, close only near the end): {bp.big_loop}",
        "",
        "SECTIONS:",
    ]
    for i, sec in enumerate(bp.outline, 1):
        lines.append(f"{i}. {sec.heading}")
        for beat in sec.beats:
            lines.append(f"   - beat: {beat}")
        lines.append(f"   - pattern interrupt: {sec.pattern_interrupt}")
        lines.append(f"   - open loop into next: {sec.open_loop}")
    lines += ["", f"TAKEAWAY: {bp.takeaway}", f"CTA: {bp.cta}"]
    return "\n".join(lines)


async def run_blueprint_stage(episode: Episode) -> Episode:
    """Generate (or regenerate) the blueprint for an episode and persist it."""
    try:
        result = await generate_blueprint(
            episode.topic,
            episode.hosts,
            minutes=episode.target_minutes,
            context=episode.user_context,
        )
        episode.blueprint = result.blueprint
        episode.cost_log.script += result.cost_usd
        episode.error = None
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        return episode
    except Exception as exc:  # noqa: BLE001 - persist + re-raise
        logger.exception("Blueprint failed for episode %s", episode.id)
        episode.error = f"blueprint: {exc}"
        episode.retry_count += 1
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        raise
