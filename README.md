# 🎙️ AI Confessor - Conversational AI Platform

A real-time conversational AI platform: speak into your mic, get a spoken AI
reply back. FastAPI + WebSockets stream tokens from Claude or GPT-4 with low
latency, Vosk transcribes your voice on the server, and Edge TTS voices the
reply. Text chat works as a fallback. Everything runs in Docker with one
command.

```
Browser (mic / chat UI)
   │  WebSocket /ws/chat (JSON: text, audio chunks, tokens, mp3 audio)
   ▼
FastAPI backend ──► Vosk STT (server-side) ──► Claude / GPT-4 (streaming) ──► Edge TTS ──► 🔊
   │ per-connection session state (conversation history, sliding window)
```

## Quick start

```bash
cp .env.example .env          # add ANTHROPIC_API_KEY or OPENAI_API_KEY, or leave empty for MOCK mode
docker compose up --build     # first run downloads the ~40 MB Vosk model automatically
```

Open **http://localhost:3000**, allow mic access, and talk.

Without any API key the app runs in **MOCK mode**: canned streaming
replies exercise the entire voice → AI → voice loop end-to-end.

## Project layout

```
ai-confessor/
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI app, /ws/chat protocol, REST endpoints
│   │   ├── config.py      # env-driven settings (no hardcoded secrets)
│   │   ├── llm.py         # pluggable LLM client: Anthropic (Claude) / OpenAI streaming / mock
│   │   ├── stt.py         # Vosk STT (server-side), auto-downloads small EN model
│   │   ├── tts.py         # Edge TTS (free, keyless) -> MP3 bytes
│   │   └── sessions.py    # per-connection session state + history window
│   ├── tests/             # pytest suite (mock streaming, sessions, WS round-trip)
│   ├── requirements.txt   # pinned
│   └── Dockerfile
├── frontend/              # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/ChatWindow.tsx  # chat UI, streaming display
│   │   └── lib/
│   │       ├── ws.ts      # typed WebSocket client
│   │       └── audio.ts   # mic capture (16 kHz PCM) + reply playback + speech fallback
│   ├── public/pcm-processor.js        # AudioWorklet PCM capture
│   ├── nginx.conf         # serves UI, proxies /api + /ws to backend
│   └── Dockerfile         # multi-stage build -> nginx
├── docker-compose.yml     # one-command local run
├── .env.example           # every variable, no secrets
├── .gitignore             # venv, node_modules, dist, .env, caches
├── LICENSE
├── aws/                   # EC2 deployment: script plus notes on the executed deployment
└── docs/                  # final report, presentation deck, style reference
```

## Configuration

All settings come from environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | _(empty)_ | `anthropic` \| `openai` \| `mock`. Empty = auto-select: `ANTHROPIC_API_KEY` set → anthropic, else `OPENAI_API_KEY` set → openai, else mock |
| `ANTHROPIC_API_KEY` | _(empty)_ | Claude key - wins auto-select when set |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Any Claude model ID |
| `OPENAI_API_KEY` | _(empty)_ | OpenAI key - used when set and no Anthropic key present |
| `OPENAI_MODEL` | `gpt-4o` | Any OpenAI chat model |
| `OPENAI_BASE_URL` | _(empty)_ | Proxy / Azure-compatible endpoint |
| `VOSK_MODEL_NAME` | `vosk-model-small-en-us-0.15` | STT model (auto-downloaded) |
| `TTS_ENABLED` | `true` | Spoken replies on/off |
| `TTS_VOICE` | `en-US-AriaNeural` | Edge TTS voice |
| `MAX_HISTORY_MESSAGES` | `20` | Sliding history window per session |

To add a new LLM provider: implement the `LLMClient` protocol in
`backend/app/llm.py` and register it in `get_llm_client()`.

## WebSocket protocol

`ws://localhost:8000/ws/chat` (via nginx at `/ws/chat` in compose).

Client → server: `hello` · `text` · `audio_chunk` (base64 16 kHz/16-bit/mono PCM)
· `end_audio` · `reset` · `ping`

Server → client: `session` · `transcript` (partial + final) · `token` (streamed)
· `audio` (base64 MP3 reply) · `response_done` · `reset_done` · `pong` · `error`

## Local dev (without Docker)

```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000

# frontend
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## Tests

```bash
cd backend && source .venv/bin/activate
pytest tests/ -v
```

Covers: mock-mode streaming, session isolation (concurrent users), WebSocket
round-trip, and that no secrets leak through public endpoints. STT/TTS are
faked in the test suite (no model download, no network); the real Vosk model
was verified separately (it transcribed a test clip exactly).

## AWS deployment

Actually deployed and running: EC2 `t3.medium` in `us-east-1` (Ubuntu 24.04),
Docker Compose (backend + frontend/nginx), with free public HTTPS via a
Cloudflare quick tunnel (browsers require HTTPS for mic access). The Claude
API key lives server-side only in the backend `.env` (never in frontend code
or Git). Live at https://passed-tampa-single-efforts.trycloudflare.com
(quick-tunnel URLs change on redeploy). See `aws/README.md` for the full
story, including how the deployment was automated.
