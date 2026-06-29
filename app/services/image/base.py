"""Image provider contract (same swappable pattern as TTS)."""

from abc import ABC, abstractmethod


class ImageProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, *, quality: str) -> bytes:
        """Return raw image bytes (PNG) for the given prompt. Aspect is landscape."""
        raise NotImplementedError
