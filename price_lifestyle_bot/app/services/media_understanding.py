from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class MediaSettings(Protocol):
    media_enabled: bool
    media_api_base_url: str
    media_api_key: str
    media_stt_model: str
    media_vision_model: str
    media_max_file_bytes: int
    llm_openrouter_api_key: str
    llm_timeout_seconds: float


@dataclass(frozen=True)
class MediaResult:
    text: str
    model: str


class MediaUnderstandingClient:
    def __init__(
        self,
        settings: MediaSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport

    @property
    def configured(self) -> bool:
        return self.settings.media_enabled and bool(self._api_key)

    async def transcribe_voice(
        self,
        *,
        content: bytes,
        audio_format: str = "ogg",
    ) -> MediaResult | None:
        if not self.configured or not self.settings.media_stt_model.strip():
            return None
        if len(content) > self.settings.media_max_file_bytes:
            raise ValueError("Голосовое сообщение слишком большое для обработки.")
        payload = {
            "model": self.settings.media_stt_model,
            "input_audio": {
                "data": base64.b64encode(content).decode("ascii"),
                "format": audio_format,
            },
            "language": "ru",
            "temperature": 0,
        }
        response = await self._post_json("/audio/transcriptions", payload)
        text = str(response.get("text", "")).strip()
        return MediaResult(text=text, model=self.settings.media_stt_model) if text else None

    async def extract_receipt(
        self,
        *,
        content: bytes,
        mime_type: str = "image/jpeg",
    ) -> MediaResult | None:
        if not self.configured or not self.settings.media_vision_model.strip():
            return None
        if len(content) > self.settings.media_max_file_bytes:
            raise ValueError("Фотография слишком большая для обработки.")
        image_url = f"data:{mime_type};base64,{base64.b64encode(content).decode('ascii')}"
        payload = {
            "model": self.settings.media_vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Распознай кассовый чек. Верни только строки в формате:\n"
                                "магазин: <название>\n<товар> <цена>\n"
                                "Не добавляй пояснения, markdown и итоговую сумму."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": 700,
            "stream": False,
        }
        response = await self._post_json("/chat/completions", payload)
        try:
            text = str(response["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError):
            return None
        text = text.removeprefix("```text").removeprefix("```").removesuffix("```").strip()
        return MediaResult(text=text, model=self.settings.media_vision_model) if text else None

    @property
    def _api_key(self) -> str:
        return self.settings.media_api_key.strip() or self.settings.llm_openrouter_api_key.strip()

    async def _post_json(self, endpoint: str, payload: dict[str, object]) -> dict[str, Any]:
        base = self.settings.media_api_base_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(
            timeout=self.settings.llm_timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.post(f"{base}{endpoint}", json=payload, headers=headers)
        if response.status_code >= 400:
            raise ValueError(f"Media provider error: HTTP {response.status_code}.")
        raw = response.json()
        if not isinstance(raw, dict):
            raise ValueError("Media provider returned an invalid response.")
        return raw
