# backend/tests/

Pytest suite (`test_app.py`). All tests run in mock mode with STT/TTS faked,
so no model download and no network calls happen here.

What is covered:

- Mock LLM streams multiple word-by-word chunks that join into a full reply.
- Provider auto-select falls back to mock when no API key is set.
- Session isolation: two sessions keep separate histories.
- Sliding window: old turns are trimmed, the system prompt is kept.
- `GET /health` reports mock mode.
- `GET /api/config` leaks no secrets (asserts no key names or `sk-` prefix
  in the response).
- Full WebSocket text round-trip: `text` → streamed `token`s → `audio`
  (fake MP3) → `response_done` whose `full_text` matches the joined tokens;
  plus `reset` clears history and unknown message types return an error
  without killing the connection.
- Two concurrent WebSocket sessions get different session IDs and both
  complete turns independently.

Run it:

```bash
cd backend && source .venv/bin/activate
pytest tests/ -v
```

The suite passed 8/8. Real Vosk and the voice fallback were verified outside
this suite (Vosk transcribed a test clip exactly).
