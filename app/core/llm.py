"""Small helpers for talking to OpenAI chat models across model generations.

Newer models (the GPT-5 family and the o-series reasoning models) only accept the
default temperature (1) and reject any custom value. Older models (gpt-4o, gpt-4.1)
accept a custom temperature. This helper lets the pipeline set a preferred
temperature that is silently dropped when the chosen model doesn't support it — so
switching OPENAI_SCRIPT_MODEL between generations never breaks the request.
"""


def supports_custom_temperature(model: str) -> bool:
    m = model.lower()
    fixed_temp_prefixes = ("gpt-5", "o1", "o3", "o4")
    return not m.startswith(fixed_temp_prefixes)


def temperature_kwargs(model: str, temperature: float) -> dict:
    """`{"temperature": ...}` if the model supports it, else `{}` (use the default)."""
    if supports_custom_temperature(model):
        return {"temperature": temperature}
    return {}
