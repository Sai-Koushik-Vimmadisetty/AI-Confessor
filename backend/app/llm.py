"""Pluggable LLM client with streaming.

Three providers behind one interface:
  - anthropic: Claude via the official `anthropic` Python SDK (ANTHROPIC_API_KEY,
    model from ANTHROPIC_MODEL). Async streaming via `messages.create(stream=True)`,
    parsing text deltas out of `content_block_delta` SSE events. (The 1.x SDK no
    longer exposes sampling params like temperature on the Messages API, so we
    stream with model defaults.)
  - openai: GPT-4 family via the official `openai` SDK (OPENAI_API_KEY,
    model from OPENAI_MODEL).
  - mock: canned streaming replies. Used when no key is present, so the whole
    voice -> AI -> voice loop can be exercised end-to-end without any key.

Provider selection (LLM_PROVIDER): "anthropic" | "openai" | "mock". When unset,
auto-select: anthropic if ANTHROPIC_API_KEY is present, else openai if
OPENAI_API_KEY is present, else mock.
"""
import asyncio
import logging
import random
from typing import AsyncIterator, Protocol

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from .config import Settings

log = logging.getLogger(__name__)


class LLMClient(Protocol):
    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        """Yield response tokens (or token-ish chunks) as they arrive."""
        ...


def _split_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Anthropic takes the system prompt as a separate parameter, so strip any
    system-role messages out of the turn list and return them joined."""
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    turns = [m for m in messages if m.get("role") in ("user", "assistant")]
    system = "\n\n".join(system_parts) if system_parts else None
    return system, turns


class AnthropicLLMClient:
    """Claude streaming client (async, text-only chunks)."""

    def __init__(self, settings: Settings):
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        system, turns = _split_system(messages)
        # `max_tokens` is required by the Anthropic API. Note: anthropic>=1.x
        # no longer exposes sampling params (temperature/top_p) on the Messages
        # API, so we stream with model defaults and `create(stream=True)`,
        # parsing text deltas out of the SSE event stream.
        stream = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=turns,
            stream=True,
        )
        async for event in stream:
            if event.type == "content_block_delta":
                delta = event.delta
                if getattr(delta, "type", None) == "text_delta":
                    text = getattr(delta, "text", "")
                    if text:
                        yield text


class OpenAILLMClient:
    def __init__(self, settings: Settings):
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
        self._model = settings.openai_model

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
# they exercise the streaming + TTS pipeline without pretending to be a live model.
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
    provider = settings.resolved_provider
    if provider == "anthropic":
        log.info("LLM: Anthropic provider, model=%s", settings.anthropic_model)
        return AnthropicLLMClient(settings)
    if provider == "openai":
        log.info("LLM: OpenAI provider, model=%s", settings.openai_model)
        return OpenAILLMClient(settings)
    if settings.llm_provider.strip().lower() not in ("mock", ""):
        log.warning(
            "LLM: LLM_PROVIDER=%r selected but no API key for it is set — running in MOCK mode",
            settings.llm_provider,
        )
    else:
        log.warning("LLM: no API key configured — running in MOCK mode")
    return MockLLMClient()
