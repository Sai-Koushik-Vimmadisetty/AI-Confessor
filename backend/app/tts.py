"""Text-to-speech via Microsoft Edge TTS (free, no API key required).

Synthesizes assistant replies to MP3 bytes which are sent to the browser for
playback. If synthesis fails (e.g. no network), the caller falls back to
text-only — the conversation never breaks because of TTS.
"""
import asyncio
import logging

import edge_tts

log = logging.getLogger(__name__)


class TTSError(Exception):
    pass


async def synthesize(text: str, voice: str = "en-US-AriaNeural") -> bytes:
    """Return MP3 audio bytes for the given text. Raises TTSError on failure."""
    text = text.strip()
    if not text:
        raise TTSError("empty text")

    communicate = edge_tts.Communicate(text, voice)
    chunks: list[bytes] = []
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio" and chunk["data"]:
                chunks.append(chunk["data"])
    except Exception as exc:  # network issues, voice errors, etc.
        raise TTSError(f"edge-tts failed: {exc}") from exc

    audio = b"".join(chunks)
    if not audio:
        raise TTSError("edge-tts returned no audio")
    return audio


def synthesize_blocking(text: str, voice: str) -> bytes:
    """Synchronous wrapper for contexts without a running event loop."""
    return asyncio.run(synthesize(text, voice))
