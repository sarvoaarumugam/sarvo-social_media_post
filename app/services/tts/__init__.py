"""TTS provider factory — the one place that knows which concrete provider to build.

Add a new provider by implementing TTSProvider and adding a branch here.
"""

from app.core.config import get_settings
from app.services.tts.base import TTSProvider
from app.services.tts.openai_provider import OpenAITTSProvider


def get_tts_provider() -> TTSProvider:
    settings = get_settings()
    provider = settings.tts_provider.lower()

    if provider == "openai":
        # Request lossless WAV per chunk so we can stitch without re-compression and
        # decode with the stdlib (no ffprobe needed). Final episode is encoded once.
        return OpenAITTSProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_tts_model,
            response_format="wav",
        )

    # elif provider == "elevenlabs":
    #     return ElevenLabsTTSProvider(...)

    raise ValueError(f"Unknown TTS provider: {settings.tts_provider!r}")
