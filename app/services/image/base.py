"""Image provider contract (same swappable pattern as TTS)."""

from abc import ABC, abstractmethod


class ImageProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, *, quality: str, aspect: str = "landscape") -> bytes:
        """Return raw image bytes (PNG). `aspect` is 'landscape' | 'square' | 'portrait'."""
        raise NotImplementedError
