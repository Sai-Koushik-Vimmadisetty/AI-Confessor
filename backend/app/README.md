# backend/app/

The service modules. Each file owns one piece of the pipeline.

- **main.py** - FastAPI app wiring. Defines `GET /health`, `GET /api/config`,
  and the `WS /ws/chat` handler: accepts the socket, creates a session,
  routes client messages (`hello`, `text`, `audio_chunk`, `end_audio`,
  `reset`, `ping`) and emits server messages (`session`, `transcript`,
  `token`, `audio`, `response_done`, `reset_done`, `pong`, `error`).
  `_handle_user_message` runs one turn: appends the user text to the session,
  streams LLM tokens, saves the assistant reply, then best-effort
  synthesizes it to MP3. Vosk is optional at boot: if the model cannot load,
  the app still starts (text chat keeps working, voice input is disabled).
- **config.py** - `Settings` (pydantic-settings): every knob is an env var,
  nothing secret is hardcoded. Provider resolution lives here: explicit
  `LLM_PROVIDER`, otherwise auto-select by key availability (Anthropic key
  → anthropic, else OpenAI key → openai, else mock). Also holds the system
  prompt, Vosk/TTS settings, and the 20-message sliding window size.
- **llm.py** - one `LLMClient` protocol, three implementations behind
  `get_llm_client()`: `AnthropicLLMClient` (Claude, async streaming via the
  official SDK, system prompt passed separately), `OpenAILLMClient`
  (chat-completions streaming), and `MockLLMClient` (canned replies streamed
  word-by-word so the full pipeline works with no key).
- **stt.py** - Vosk speech-to-text, running on this server. `ensure_model`
  downloads `vosk-model-small-en-us-0.15` (~40 MB) on first run.
  `STTEngine` loads the model once and hands each session its own
  `SessionSTT` recognizer (Vosk recognizers are not thread-safe, so one per
  session is the correct pattern for concurrent users). Expects 16 kHz
  16-bit mono PCM, which is exactly what the frontend sends.
- **tts.py** - `synthesize(text, voice)`: Edge TTS (free, no key) → MP3
  bytes. Raises `TTSError` on failure (network issues, empty audio); the
  caller treats voice as best-effort so a TTS outage never breaks the text
  conversation.
- **sessions.py** - `SessionManager` + `Session`: one isolated conversation
  history per WebSocket connection, guarded by asyncio locks. History is a
  sliding window (system prompt + the most recent turns, capped at
  `MAX_HISTORY_MESSAGES`). Sessions are in-memory, so multi-worker setups
  would need Redis (not implemented).
