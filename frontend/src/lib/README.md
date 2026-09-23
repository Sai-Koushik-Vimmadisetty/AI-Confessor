# frontend/src/lib/

Protocol and audio plumbing used by `ChatWindow`.

## ws.ts

Typed client for the `/ws/chat` protocol. `ChatSocket` wraps a native
WebSocket: `connect()` (picks `ws:`/`wss:` from the page protocol),
`onMessage`/`onClose` callbacks, and send helpers (`sendText`,
`sendAudioChunk`, `endAudio`, `reset`, `ping`, `close`). `ServerMessage`
types every server frame (`session`, `transcript`, `token`, `audio`,
`response_done`, `reset_done`, `pong`, `error`). `fetchServerConfig()` loads
`/api/config` (mock mode, TTS/STT flags, model name).

## audio.ts

Two halves: capture and playback.

**Capture** - `startRecording(onChunk)`: requests mic access, creates an
`AudioContext` at 16 kHz, loads the `pcm-processor` AudioWorklet, downsamples
if the device ran at a different rate, converts to 16-bit PCM, and emits
base64 chunks. The worklet output routes through a zero-gain node so the mic
is never played back through the speakers (no feedback howl). `stop()`
disconnects everything and closes the context.

**Playback** - server MP3 replies arrive base64-encoded; `playReplyAudio`
queues them so replies never overlap, and `stopAllAudio` clears the queue,
stops the current element, and cancels any device speech.

**Device-speech fallback** - `speakReplyText(text)`: when the server sent no
audio for a turn, the browser speaks the reply text itself with a built-in
voice (English preferred, markdown stripped). iOS hardening included:
`warmUpVoices()` enumerates voices on user gestures, `onvoiceschanged` is
handled, a paused engine is resumed immediately, and a 1-second watchdog
keeps resuming while the utterance is active (capped at ~60 s so it cannot
leak). Starting new speech, stopping audio, or toggling voice off cancels
everything.
