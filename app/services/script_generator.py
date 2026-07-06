"""M1 — Script generator.

topic -> a structured two-host conversation (list of {speaker, text}).

Design notes:
- Output is a STRICT structured schema (GeneratedScript), so the model cannot
  return malformed dialogue — no fragile text parsing.
- Nothing niche-specific is hardcoded. Brand, hosts, language and tone all come
  from config/args, so the same code can produce ESL or finance episodes.
- Two entry points:
    generate_script(...)      -> pure generation (no DB), used by the CLI/preview.
    run_scripting_stage(ep)   -> state-machine stage: scripting -> scripted, logs
                                 cost, records errors without crashing the queue.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from openai import AsyncOpenAI

from app.core import prompts
from app.core.config import get_settings
from app.core.pricing import text_cost
from app.models.episode import Blueprint, DialogueTurn, Episode, EpisodeStatus
from app.schemas.script import GeneratedScript
from app.services.strategy_generator import (
    blueprint_to_text,
    context_block,
    generate_blueprint,
    load_style_dna,
)

logger = logging.getLogger("app.script")


@dataclass
class ScriptGenerationResult:
    turns: list[DialogueTurn]
    word_count: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str


def count_words(turns: list[DialogueTurn]) -> int:
    return sum(len(turn.text.split()) for turn in turns)


def _normalize_speakers(turns: list[DialogueTurn], hosts: list[str]) -> list[DialogueTurn]:
    """Guarantee every turn is attributed to one of the two configured hosts.
    If the model ever invents a name, fall back to strict alternation.
    """
    valid = {h.lower(): h for h in hosts}
    normalized: list[DialogueTurn] = []
    for i, turn in enumerate(turns):
        speaker = valid.get(turn.speaker.strip().lower())
        if speaker is None:
            speaker = hosts[i % len(hosts)]
        normalized.append(DialogueTurn(speaker=speaker, text=turn.text.strip()))
    return normalized


def _build_system_prompt(
    brand: str, hosts: list[str], language: str, tone: str, target_words: int
) -> str:
    return prompts.render(
        "script",
        "system",
        brand=brand,
        host1=hosts[0],
        host2=hosts[1],
        language=language,
        tone=tone,
        target_words=target_words,
        floor=int(target_words * 0.9),
        style_dna=load_style_dna(),
    )


def _turns_to_text(turns: list[DialogueTurn]) -> str:
    return "\n".join(f"{t.speaker}: {t.text}" for t in turns)


def _build_expansion_messages(
    turns: list[DialogueTurn], target_words: int, current_words: int
) -> list[dict]:
    """Ask the model to rewrite the script LONGER and richer, returning the full
    revised script — so there is never a double-ending or stitched-on tail.
    """
    return [
        {
            "role": "system",
            "content": prompts.render(
                "script",
                "expansion_system",
                target_words=target_words,
                floor=int(target_words * 0.9),
            ),
        },
        {
            "role": "user",
            "content": prompts.render(
                "script",
                "expansion_user",
                current_words=current_words,
                target_words=target_words,
                dialogue=_turns_to_text(turns),
            ),
        },
    ]


def _build_user_prompt(
    topic: str, hosts: list[str], blueprint: Blueprint, context: str | None = None
) -> str:
    return prompts.render(
        "script",
        "user",
        topic=topic,
        host1=hosts[0],
        host2=hosts[1],
        blueprint=blueprint_to_text(blueprint),
        context=context_block(context),
    )


async def generate_script(
    topic: str,
    hosts: list[str],
    *,
    blueprint: Blueprint | None = None,
    context: str | None = None,
    brand: str | None = None,
    language: str | None = None,
    tone: str | None = None,
    target_words: int | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> ScriptGenerationResult:
    """Generate a two-host script for `topic`, following the strategist's blueprint.
    If no blueprint is passed, one is generated first (its cost is included).
    Pure: no DB writes.
    """
    settings = get_settings()
    brand = brand or settings.channel_brand_name
    language = language or settings.show_language
    tone = tone or settings.show_tone
    target_words = target_words or settings.words_for_minutes(settings.default_duration_minutes)
    model = model or settings.openai_script_model
    temperature = settings.script_temperature if temperature is None else temperature

    if len(hosts) < 2:
        raise ValueError("Exactly two hosts are required for the conversation.")

    blueprint_cost = 0.0
    if blueprint is None:
        bp_result = await generate_blueprint(
            topic,
            hosts,
            minutes=target_words / settings.words_per_minute,
            context=context,
            model=model,
        )
        blueprint = bp_result.blueprint
        blueprint_cost = bp_result.cost_usd

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    floor = int(target_words * 0.85)
    in_tok = out_tok = 0

    async def _complete(messages: list[dict]) -> list[DialogueTurn]:
        nonlocal in_tok, out_tok
        completion = await client.chat.completions.parse(
            model=model,
            temperature=temperature,
            messages=messages,
            response_format=GeneratedScript,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None or not parsed.turns:
            raise RuntimeError("Model returned no dialogue.")
        if completion.usage:
            in_tok += completion.usage.prompt_tokens
            out_tok += completion.usage.completion_tokens
        return _normalize_speakers(parsed.turns, hosts)

    logger.info("Generating script: topic=%r model=%s target=%dw", topic, model, target_words)
    turns = await _complete(
        [
            {
                "role": "system",
                "content": _build_system_prompt(brand, hosts, language, tone, target_words),
            },
            {"role": "user", "content": _build_user_prompt(topic, hosts, blueprint, context)},
        ]
    )
    words = count_words(turns)
    logger.info("Draft: %d turns, %d words", len(turns), words)

    # Safety net: models routinely under-deliver on length. Expand until we reach
    # ~10 minutes, but cap the passes so cost stays bounded.
    for attempt in range(1, 3):
        if words >= floor:
            break
        logger.info("Below floor (%d < %d) — expansion pass %d", words, floor, attempt)
        expanded = await _complete(_build_expansion_messages(turns, target_words, words))
        if count_words(expanded) <= words:
            break  # no improvement; keep what we have
        turns, words = expanded, count_words(expanded)

    cost = round(text_cost(model, in_tok, out_tok) + blueprint_cost, 6)
    logger.info("Script done: %d turns, %d words, $%.4f", len(turns), words, cost)
    return ScriptGenerationResult(
        turns=turns,
        word_count=words,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=cost,
        model=model,
    )


async def run_scripting_stage(episode: Episode) -> Episode:
    """State-machine stage: take a `queued` episode -> `scripted`.

    Idempotent-friendly and safe: records the script + cost on success, or records
    the error + bumps retry_count on failure (never lets one bad episode crash a sweep).
    """
    settings = get_settings()
    episode.status = EpisodeStatus.scripting
    episode.updated_at = datetime.now(timezone.utc)
    await episode.save()

    try:
        # Stage 1: strategist blueprint (reuse if already generated/reviewed).
        if episode.blueprint is None:
            bp_result = await generate_blueprint(
                episode.topic,
                episode.hosts,
                minutes=episode.target_minutes,
                context=episode.user_context,
            )
            episode.blueprint = bp_result.blueprint
            episode.cost_log.script += bp_result.cost_usd
            await episode.save()

        # Stage 2: scriptwriter follows the blueprint.
        target_words = settings.words_for_minutes(episode.target_minutes)
        result = await generate_script(
            episode.topic,
            episode.hosts,
            blueprint=episode.blueprint,
            context=episode.user_context,
            target_words=target_words,
        )
        episode.script = result.turns
        episode.cost_log.script += result.cost_usd
        episode.status = EpisodeStatus.scripted
        episode.error = None
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        return episode
    except Exception as exc:  # noqa: BLE001 - we persist the error and re-raise
        logger.exception("Scripting failed for episode %s", episode.id)
        episode.status = EpisodeStatus.failed
        episode.error = f"scripting: {exc}"
        episode.retry_count += 1
        episode.updated_at = datetime.now(timezone.utc)
        await episode.save()
        raise
