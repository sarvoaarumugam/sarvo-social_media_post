"""The TTS provider contract.

The whole pipeline depends ONLY on this interface, never on a concrete provider.
Swapping OpenAI for ElevenLabs (or anything else) means adding one class and a
factory entry — no pipeline code changes. This is the M2 non-negotiable.
"""

from abc import ABC, abstractmethod


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, *, voice: str, instructions: str | None = None) -> bytes:
        """Render a single chunk of text to audio bytes (in the configured format).

        `voice` selects the speaker; `instructions` steers HOW it's spoken (pacing,
        warmth, pauses) — providers that don't support steering may ignore it.
        """
        raise NotImplementedError
