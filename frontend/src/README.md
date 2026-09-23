# frontend/src/

React source. `main.tsx` mounts the app; everything else supports the chat
window.

- **main.tsx** - entry point. Creates the React root on `#root` and renders
  `ChatWindow` inside `React.StrictMode`.
- **styles.css** - all styling for the chat shell: header, message bubbles,
  streaming caret, composer, mic button states.
- **components/** - `ChatWindow.tsx`, the whole UI (see components/README.md).
- **lib/** - protocol and audio plumbing: `ws.ts` (typed WebSocket client)
  and `audio.ts` (mic capture, reply playback, device-speech fallback).
  See lib/README.md.
