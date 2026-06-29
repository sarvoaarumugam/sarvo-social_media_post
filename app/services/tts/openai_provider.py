"""OpenAI TTS provider — uses gpt-4o-mini-tts, the model that accepts free-text
`instructions` to control delivery (the key to non-robotic, human speech).
"""

from openai import AsyncOpenAI

from app.services.tts.base import TTSProvider


class OpenAITTSProvider(TTSProvider):
    def __init__(self, api_key: str, model: str, response_format: str = "mp3"):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._format = response_format

    async def synthesize(self, text: str, *, voice: str, instructions: str | None = None) -> bytes:
        async with self._client.audio.speech.with_streaming_response.create(
            model=self._model,
            voice=voice,
            input=text,
            instructions=instructions or "",
            response_format=self._format,
        ) as response:
            return await response.read()
