"""OpenAI image provider — uses gpt-image-1 (best), with an automatic fallback to
dall-e-3 if gpt-image-1 isn't available for the account (e.g. org not verified).

The two models take slightly different params, so we branch on the model name.
"""

import base64
import logging

from openai import AsyncOpenAI

from app.services.image.base import ImageProvider

logger = logging.getLogger("app.image")


class OpenAIImageProvider(ImageProvider):
    def __init__(self, api_key: str, model: str, fallback_model: str = "dall-e-3"):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._fallback = fallback_model
        self.last_model: str = model  # which model actually produced the last image

    async def generate(self, prompt: str, *, quality: str) -> bytes:
        try:
            return await self._call(self._model, prompt, quality)
        except Exception as exc:  # noqa: BLE001 - try the fallback before giving up
            if self._fallback and self._fallback != self._model:
                logger.warning(
                    "Image model %s failed (%s); falling back to %s",
                    self._model, exc, self._fallback,
                )
                return await self._call(self._fallback, prompt, quality)
            raise

    async def _call(self, model: str, prompt: str, quality: str) -> bytes:
        kwargs: dict = {"model": model, "prompt": prompt, "n": 1}
        if model.startswith("gpt-image"):
            kwargs["size"] = "1536x1024"  # landscape
            kwargs["quality"] = quality if quality in {"low", "medium", "high", "auto"} else "medium"
            kwargs["output_format"] = "png"
        else:  # dall-e-3
            kwargs["size"] = "1792x1024"  # ~16:9
            kwargs["quality"] = "hd" if quality in {"high", "hd", "medium"} else "standard"
            kwargs["response_format"] = "b64_json"

        resp = await self._client.images.generate(**kwargs)
        self.last_model = model
        return base64.b64decode(resp.data[0].b64_json)
