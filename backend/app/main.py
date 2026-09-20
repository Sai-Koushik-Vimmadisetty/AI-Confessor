"""AI Confessor backend — FastAPI + WebSockets.

WebSocket protocol (JSON messages) on /ws/chat:

  Client -> server:
    {"type": "hello"}                                  handshake, returns session id
    {"type": "text", "text": "..."}                    user typed message
    {"type": "audio_chunk", "data": "<base64 pcm16 16kHz mono>"}
    {"type": "end_audio"}                              user stopped speaking
    {"type": "reset"}                                  clear conversation history
    {"type": "ping"}

  Server -> client:
    {"type": "session", "session_id": "..."}
    {"type": "transcript", "text": "...", "final": bool}
    {"type": "token", "token": "..."}                  streamed LLM output
    {"type": "audio", "data": "<base64 mp3>", "format": "mp3"}
    {"type": "response_done", "full_text": "..."}
    {"type": "reset_done"}
    {"type": "pong"}
    {"type": "error", "message": "..."}
"""
import base64
import binascii
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .llm import get_llm_client
from .sessions import SessionManager
from .stt import STTEngine
from .tts import TTSError, synthesize

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

session_manager = SessionManager(settings.system_prompt, settings.max_history_messages)
llm_client = get_llm_client(settings)
stt_engine: STTEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global stt_engine
    try:
        stt_engine = STTEngine(settings.vosk_model_dir, settings.vosk_model_name, settings.stt_sample_rate)
    except Exception as exc:
        # STT is optional for text chat; the app still boots without it.
        log.error("Vosk STT unavailable (voice input disabled): %s", exc)
        stt_engine = None
    yield


app = FastAPI(title="AI Confessor", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mock_mode": settings.mock_mode,
        "llm_provider": settings.resolved_provider,
        "llm_model": settings.resolved_model,
        "stt_available": stt_engine is not None,
        "tts_enabled": settings.tts_enabled,
        "active_sessions": session_manager.count(),
    }


@app.get("/api/config")
async def client_config():
    """Public runtime config the frontend needs (no secrets)."""
    return {
        "mock_mode": settings.mock_mode,
        "tts_enabled": settings.tts_enabled,
        "stt_available": stt_engine is not None,
        "stt_sample_rate": settings.stt_sample_rate,
        "llm_provider": settings.resolved_provider,
        "llm_model": settings.resolved_model,
    }


async def _handle_user_message(ws: WebSocket, session, user_text: str) -> None:
    """Run one conversational turn: stream LLM tokens, then speak the reply."""
    user_text = user_text.strip()
    if not user_text:
        await ws.send_json({"type": "error", "message": "Empty message — nothing to respond to."})
        return

    await session.add_message("user", user_text)
    messages = await session.get_messages()

    full_reply_parts: list[str] = []
    try:
        async for token in llm_client.stream_chat(messages):
            full_reply_parts.append(token)
            await ws.send_json({"type": "token", "token": token})
    except Exception as exc:
        log.exception("LLM streaming failed")
        await ws.send_json({"type": "error", "message": f"AI request failed: {exc}"})
        return

    full_reply = "".join(full_reply_parts).strip()
    await session.add_message("assistant", full_reply)

    # Speak the reply (best-effort: text chat works even if TTS fails).
    if settings.tts_enabled and full_reply:
        try:
            audio = await synthesize(full_reply, settings.tts_voice)
            await ws.send_json({
                "type": "audio",
                "format": "mp3",
                "data": base64.b64encode(audio).decode("ascii"),
            })
        except TTSError as exc:
            log.warning("TTS skipped: %s", exc)

    await ws.send_json({"type": "response_done", "full_text": full_reply})


@app.websocket("/ws/chat")
async def chat_websocket(ws: WebSocket):
    await ws.accept()
    session = await session_manager.create()
    recognizer = stt_engine.new_session() if stt_engine else None
    await ws.send_json({"type": "session", "session_id": session.id})
    log.info("ws connected, session=%s", session.id)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON message."})
                continue

            mtype = msg.get("type")

            if mtype == "hello":
                await ws.send_json({"type": "session", "session_id": session.id})

            elif mtype == "ping":
                await ws.send_json({"type": "pong"})

            elif mtype == "reset":
                await session.reset()
                await ws.send_json({"type": "reset_done"})

            elif mtype == "text":
                await _handle_user_message(ws, session, msg.get("text", ""))

            elif mtype == "audio_chunk":
                if recognizer is None:
                    await ws.send_json({"type": "error", "message": "Voice input unavailable (STT not loaded)."})
                    continue
                try:
                    pcm = base64.b64decode(msg.get("data", ""))
                except (binascii.Error, ValueError):
                    await ws.send_json({"type": "error", "message": "Malformed audio chunk."})
                    continue
                text, is_final = recognizer.accept_audio(pcm)
                if text:
                    await ws.send_json({"type": "transcript", "text": text, "final": is_final})

            elif mtype == "end_audio":
                if recognizer is None:
                    await ws.send_json({"type": "error", "message": "Voice input unavailable (STT not loaded)."})
                    continue
                transcript = recognizer.flush()
                await ws.send_json({"type": "transcript", "text": transcript, "final": True})
                # Fresh recognizer for the next utterance.
                recognizer = stt_engine.new_session() if stt_engine else None
                await _handle_user_message(ws, session, transcript)

            else:
                await ws.send_json({"type": "error", "message": f"Unknown message type: {mtype!r}"})

    except WebSocketDisconnect:
        log.info("ws disconnected, session=%s", session.id)
    finally:
        await session_manager.remove(session.id)


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
