# backend/

FastAPI (Python 3.12) service. Owns the WebSocket protocol, LLM streaming,
server-side speech recognition (Vosk) and speech synthesis (Edge TTS), and
per-session conversation state.

```
backend/
├── app/               # the service itself (see app/README.md)
│   ├── main.py        # FastAPI app, /ws/chat protocol, REST endpoints
│   ├── config.py      # env-driven settings, no hardcoded secrets
│   ├── llm.py         # pluggable LLM client: Anthropic / OpenAI / mock
│   ├── stt.py         # Vosk STT (server-side), auto-downloads small EN model
│   ├── tts.py         # Edge TTS (free, keyless) -> MP3 bytes
│   └── sessions.py    # per-connection session state + sliding history window
├── tests/             # pytest suite (see tests/README.md)
├── requirements.txt   # pinned dependencies
└── Dockerfile         # python:3.12-slim, uvicorn on :8000, healthcheck on /health
```

## Endpoints

- `GET /health` - status, provider/model, STT availability, active sessions.
- `GET /api/config` - public runtime config for the frontend (no secrets).
- `WS /ws/chat` - the conversation protocol (see the root README for the
  message types).

## How a turn works

1. Browser streams mic audio as base64 16 kHz/16-bit/mono PCM `audio_chunk`
   messages; Vosk (running on this server, not on the device) returns partial
   and final transcripts.
2. On `text` or `end_audio`, the session history (sliding window of the last
   20 messages plus system prompt) goes to the LLM, whose tokens stream back
   as `token` messages.
3. The full reply is synthesized with Edge TTS to MP3 and sent as an `audio`
   message, then `response_done` closes the turn. If TTS fails, the text
   reply still goes through (the frontend can speak it with the device voice).

## Run it

```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload   # http://localhost:8000
```

Or with Docker: `docker compose up --build` from the repo root. The Vosk
model (~40 MB) downloads automatically on first run and persists in the
`vosk-models` volume.
