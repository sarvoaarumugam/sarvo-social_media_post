"""Approximate OpenAI pricing so every episode logs its real cost from day one.

Prices are USD per 1,000,000 tokens. Update these when OpenAI changes pricing —
they are intentionally in one obvious place. If a model isn't listed, cost falls
back to 0.0 (tokens are still logged by the caller).
"""

# Text models: (input_per_1m, output_per_1m). More specific ids first so prefix
# matching (see text_cost) resolves to the right entry.
TEXT_PRICES: dict[str, dict[str, float]] = {
    "gpt-5.5": {"input": 5.00, "output": 30.00},
    "gpt-5.2": {"input": 0.875, "output": 7.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
}


def text_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost for a text completion. Tolerates dated model ids via prefix match."""
    price = TEXT_PRICES.get(model)
    if price is None:
        for known, p in TEXT_PRICES.items():
            if model.startswith(known):
                price = p
                break
    if price is None:
        return 0.0
    cost = (input_tokens / 1_000_000) * price["input"] + (
        output_tokens / 1_000_000
    ) * price["output"]
    return round(cost, 6)


def tts_cost(audio_seconds: float, per_minute_usd: float) -> float:
    """Approximate TTS cost based on the duration of audio produced."""
    return round((audio_seconds / 60.0) * per_minute_usd, 6)


# Approximate USD per generated image (landscape). Update if pricing changes.
IMAGE_PRICES: dict[str, dict[str, float]] = {
    "gpt-image-1": {"low": 0.016, "medium": 0.063, "high": 0.25, "auto": 0.063},
    "dall-e-3": {"standard": 0.080, "hd": 0.120},
}


def image_cost(model: str, quality: str) -> float:
    table = IMAGE_PRICES.get(model)
    if table is None:
        for known, t in IMAGE_PRICES.items():
            if model.startswith(known):
                table = t
                break
    if table is None:
        return 0.0
    return table.get(quality, next(iter(table.values())))
