# frontend/src/components/

## ChatWindow.tsx

The entire UI: header, message list, and composer. One component owns the
socket lifecycle, recording state, and playback.

- Opens a `ChatSocket` on mount, fetches `/api/config` for the header
  (model name or MOCK MODE, voice/text-only, connection state), and sends a
  keepalive `ping` every 25 s.
- Renders streamed `token`s into the in-progress assistant bubble (with a
  caret), finalizes on `response_done`, and shows live interim transcripts
  while recording.
- Voice toggle: flipping it off stops all audio immediately; the toggle is
  read through a ref so it never changes the socket handler identity (which
  would reconnect and drop the session + history).
- Mic button: starts/stops recording; disabled when the server reports STT
  unavailable. Denied mic permission shows an inline warning.
- Reset button: stops audio and clears the server-side session history.
- Voice fallback: if the server sent no `audio` for a turn (TTS unavailable
  server-side), the reply text is spoken with the device's built-in voice on
  `response_done` instead of staying silent. Sending a new message or
  toggling voice off stops any speech in progress.
- iOS hardening: voices are warmed up on user gestures (send, mic start,
  voice toggle) because iOS Safari loads voices asynchronously and its
  speech engine can start paused or stall mid-utterance.
