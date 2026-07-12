"""LinkedIn post generation: caption (step 1) + square graphic (step 2).

Reuses the OpenAI text + image stacks. The image is generated square and resized
to the configured LinkedIn size. Posting is manual (see the UI).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO

from openai import AsyncOpenAI
from PIL import Image

from app.core import media, prompts
from app.core.config import get_settings
from app.core.llm import temperature_kwargs
from app.core.pricing import image_cost, text_cost
from app.models.linkedin import LinkedInPost
from app.services.image import get_image_provider

logger = logging.getLogger("app.linkedin")


@dataclass
class CaptionResult:
    caption: str
    cost_usd: float


@dataclass
class PostImageResult:
    png: bytes
    prompt: str
    cost_usd: float


async def generate_caption(brief: str) -> CaptionResult:
    """Generate a LinkedIn caption from the user's brief. Pure: no DB writes."""
    settings = get_settings()
    model = settings.openai_script_model
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    completion = await client.chat.completions.create(
        model=model,
        **temperature_kwargs(model, 0.8),
        messages=[
            {
                "role": "system",
                "content": prompts.render(
                    "linkedin", "caption_system", brand=settings.channel_brand_name, brief=brief
                ),
            },
            {"role": "user", "content": prompts.render("linkedin", "caption_user", brief=brief)},
        ],
    )
    caption = (completion.choices[0].message.content or "").strip()
    if not caption:
        raise RuntimeError("Model returned no caption.")
    usage = completion.usage
    cost = text_cost(model, usage.prompt_tokens if usage else 0,
                     usage.completion_tokens if usage else 0)
    logger.info("Caption done: %d chars, $%.4f", len(caption), cost)
    return CaptionResult(caption=caption, cost_usd=cost)


async def generate_post_image(caption: str, image_brief: str, *, feedback: str | None = None
                              ) -> PostImageResult:
    """Generate the square post graphic from the caption + the user's visual brief."""
    s = get_settings()
    key = "image_regeneration" if feedback else "image_generation"
    prompt = prompts.render(
        "linkedin", key, style=s.linkedin_image_style,
        caption=caption[:1200], brief=image_brief or "no specific request",
        feedback=feedback or "",
    )
    provider = get_image_provider()
    raw = await provider.generate(prompt, quality=s.image_quality, aspect="square")
    cost = image_cost(getattr(provider, "last_model", s.openai_image_model), s.image_quality)

    # Normalize to the configured square size.
    img = Image.open(BytesIO(raw)).convert("RGB")
    size = s.linkedin_image_size
    if img.size != (size, size):
        img = img.resize((size, size), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return PostImageResult(png=buf.getvalue(), prompt=prompt, cost_usd=cost)


# ---- state-machine stages (persist to DB) ----

async def run_caption_stage(post: LinkedInPost) -> LinkedInPost:
    try:
        result = await generate_caption(post.brief)
        post.caption = result.caption
        post.cost_caption = result.cost_usd
        post.status = "caption_done"
        post.error = None
        post.updated_at = datetime.now(timezone.utc)
        await post.save()
        return post
    except Exception as exc:  # noqa: BLE001 - persist + re-raise
        logger.exception("Caption failed for post %s", post.id)
        post.error = f"caption: {type(exc).__name__}: {exc}"
        post.updated_at = datetime.now(timezone.utc)
        await post.save()
        raise


async def run_image_stage(post: LinkedInPost, image_brief: str, *, feedback: str | None = None
                          ) -> LinkedInPost:
    if not post.caption:
        raise ValueError("Generate the caption before the image.")
    try:
        result = await generate_post_image(post.caption, image_brief, feedback=feedback)
        out_path = media.linkedin_image_path_for(str(post.id))
        out_path.write_bytes(result.png)

        post.image_brief = image_brief
        post.image_path = str(out_path)
        post.image_prompt = result.prompt
        post.cost_image = result.cost_usd
        post.status = "image_done"
        post.error = None
        post.updated_at = datetime.now(timezone.utc)
        await post.save()
        logger.info("LinkedIn image ready for post %s -> %s", post.id, out_path)
        return post
    except Exception as exc:  # noqa: BLE001 - persist + re-raise
        logger.exception("LinkedIn image failed for post %s", post.id)
        post.error = f"image: {type(exc).__name__}: {exc}"
        post.updated_at = datetime.now(timezone.utc)
        await post.save()
        raise
