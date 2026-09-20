"""Tests for AI Confessor backend.

Covers: mock-mode LLM streaming, session isolation across concurrent users,
the WebSocket text round-trip (tokens -> audio -> response_done), and that no
secrets leak through public endpoints. Network-dependent STT/TTS are faked.
"""
import base64
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import main  # noqa: E402
from app.llm import MOCK_REPLIES, MockLLMClient, get_llm_client  # noqa: E402
from app.sessions import SessionManager  # noqa: E402


@pytest.mark.asyncio
async def test_mock_llm_streams_multiple_chunks():
    client = MockLLMClient()
    chunks = [c async for c in client.stream_chat([{"role": "user", "content": "hi"}])]
    full = "".join(chunks).strip()
    assert len(chunks) > 3, "mock should stream word-by-word"
    assert full in MOCK_REPLIES


def test_get_llm_client_uses_mock_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.config import Settings

    s = Settings(_env_file=None)
    assert isinstance(get_llm_client(s), MockLLMClient)


@pytest.mark.asyncio
async def test_session_isolation():
    mgr = SessionManager("sys", max_history=10)
    a = await mgr.create()
    b = await mgr.create()
    await a.add_message("user", "hello from A")
    await a.add_message("assistant", "reply to A")

    a_msgs = await a.get_messages()
    b_msgs = await b.get_messages()
    assert any(m["content"] == "hello from A" for m in a_msgs)
    assert not any(m["content"] == "hello from A" for m in b_msgs)
    assert a.id != b.id


@pytest.mark.asyncio
async def test_session_sliding_window():
    mgr = SessionManager("sys", max_history=4)
    s = await mgr.create()
    for i in range(10):
        await s.add_message("user", f"msg {i}")
    msgs = await s.get_messages()
    assert msgs[0]["role"] == "system"
    assert len(msgs) == 5  # system + 4 recent
    assert msgs[-1]["content"] == "msg 9"


class _NoSTT:
    def __init__(self, *a, **k):
        raise RuntimeError("no model in tests")


async def _fake_synthesize(text, voice):
    return b"fake-mp3-bytes"


@pytest.fixture()
def test_client(monkeypatch):
    monkeypatch.setattr(main, "STTEngine", _NoSTT)  # skip real Vosk download
    monkeypatch.setattr(main, "synthesize", _fake_synthesize)
    with TestClient(main.app) as client:
        yield client


def _read_until(ws, want_type, limit=50):
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["type"] == want_type:
            return msg
    raise AssertionError(f"never received {want_type}")


def test_health_reports_mock_mode(test_client):
    r = test_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mock_mode"] is True


def test_config_leaks_no_secrets(test_client):
    r = test_client.get("/api/config")
    assert r.status_code == 200
    text = r.text
    assert "ANTHROPIC_API_KEY" not in text
    assert "OPENAI_API_KEY" not in text
    assert "sk-" not in text


def test_websocket_text_roundtrip(test_client):
    with test_client.websocket_connect("/ws/chat") as ws:
        session = ws.receive_json()
        assert session["type"] == "session" and session["session_id"]

        ws.send_json({"type": "text", "text": "hello confessor"})

        tokens: list[str] = []
        audio_b64 = None
        done = None
        for _ in range(100):
            msg = ws.receive_json()
            if msg["type"] == "token":
                tokens.append(msg["token"])
            elif msg["type"] == "audio":
                audio_b64 = msg["data"]
                assert msg["format"] == "mp3"
            elif msg["type"] == "response_done":
                done = msg
                break
        assert tokens, "expected streamed tokens"
        assert done and done["full_text"].strip()
        assert "".join(tokens).strip() == done["full_text"].strip()
        assert audio_b64 and base64.b64decode(audio_b64) == b"fake-mp3-bytes"

        # history reset
        ws.send_json({"type": "reset"})
        assert _read_until(ws, "reset_done")["type"] == "reset_done"

        # unknown message type -> error, connection stays alive
        ws.send_json({"type": "bogus"})
        err = _read_until(ws, "error")
        assert "Unknown message type" in err["message"]


def test_websocket_concurrent_sessions_isolated(test_client):
    with test_client.websocket_connect("/ws/chat") as ws1:
        with test_client.websocket_connect("/ws/chat") as ws2:
            s1 = ws1.receive_json()["session_id"]
            s2 = ws2.receive_json()["session_id"]
            assert s1 != s2

            ws1.send_json({"type": "text", "text": "first user"})
            ws2.send_json({"type": "text", "text": "second user"})

            d1 = _read_until(ws1, "response_done")
            d2 = _read_until(ws2, "response_done")
            assert d1["full_text"].strip()
            assert d2["full_text"].strip()
