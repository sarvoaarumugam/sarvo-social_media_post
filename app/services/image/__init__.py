"""Image provider factory."""

from app.core.config import get_settings
from app.services.image.base import ImageProvider
from app.services.image.openai_provider import OpenAIImageProvider


def get_image_provider() -> ImageProvider:
    settings = get_settings()
    if settings.image_provider.lower() == "openai":
        return OpenAIImageProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_image_model,
        )
    raise ValueError(f"Unknown image provider: {settings.image_provider!r}")
