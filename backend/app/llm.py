"""Pluggable LLM client with streaming.

Live provider: OpenAI (GPT-4 family). If OPENAI_API_KEY is not set, the app
runs in MOCK mode with canned streaming responses so the entire voice -> AI ->
voice loop can be exercised end-to-end without a key.
"""
import asyncio
import logging
import random
from typing import AsyncIterator, Protocol

from openai import AsyncOpenAI

from .config import Settings

log = logging.getLogger(__name__)

SYSTEM_ROLE = "system"


class LLMClient(Protocol):
    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        """Yield response tokens (or token-ish chunks) as they arrive."""
        ...


class OpenAILLMClient:
    def __init__(self, settings: Settings):
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
        self._model = settings.llm_model

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
            temperature=0.7,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# Canned replies used when no API key is configured. Kept short on purpose —
# they exercise the streaming + TTS pipeline without pretending to be GPT-4.
MOCK_REPLIES = [
    "I hear you. Tell me more about what's weighing on your mind — I'm listening.",
    "That's a lot to carry. What part of it feels heaviest right now?",
    "Interesting. And how did that make you feel, honestly?",
    "I'm here for all of it — the messy parts especially. Go on.",
    "It sounds like you've been thinking about this for a while. What's the piece you haven't said out loud yet?",
]


class MockLLMClient:
    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        reply = random.choice(MOCK_REPLIES)
        # Stream word-by-word to mimic real token streaming.
        for word in reply.split(" "):
            yield word + " "
            await asyncio.sleep(0.03)


def get_llm_client(settings: Settings) -> LLMClient:
    provider = settings.llm_provider.lower()
    if provider == "openai":
        if settings.openai_api_key:
            log.info("LLM: OpenAI provider, model=%s", settings.llm_model)
            return OpenAILLMClient(settings)
        log.warning("LLM: OPENAI_API_KEY not set — running in MOCK mode")
        return MockLLMClient()
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider!r}")
