from __future__ import annotations

import json

import httpx
import pytest
from app.config import Settings
from app.services.media_understanding import MediaUnderstandingClient


@pytest.mark.asyncio
async def test_media_client_transcribes_voice_with_configured_provider() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"text": "добавь задачу оплатить интернет"})

    client = MediaUnderstandingClient(
        Settings(
            media_enabled=True,
            media_api_key="secret",
            media_stt_model="speech-model",
            media_max_file_bytes=100_000,
        ),
        transport=httpx.MockTransport(handler),
    )

    result = await client.transcribe_voice(content=b"audio")

    assert result is not None
    assert result.text == "добавь задачу оплатить интернет"
    assert requests[0]["model"] == "speech-model"


@pytest.mark.asyncio
async def test_media_client_extracts_receipt_text_and_enforces_size() -> None:
    client = MediaUnderstandingClient(
        Settings(
            media_enabled=True,
            media_api_key="secret",
            media_vision_model="vision-model",
            media_max_file_bytes=100_000,
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"choices": [{"message": {"content": "магазин: Магнит\nмолоко 89.90"}}]},
            )
        ),
    )

    result = await client.extract_receipt(content=b"image")

    assert result is not None
    assert "молоко 89.90" in result.text
    with pytest.raises(ValueError, match="слишком большая"):
        await client.extract_receipt(content=b"x" * 100_001)
