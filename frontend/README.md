# frontend/

React 18 + TypeScript + Vite single-page chat UI. Captures mic audio, renders
streamed replies, and plays spoken replies. Served in production by nginx,
which also proxies `/api` and `/ws` to the backend.

```
frontend/
├── src/
│   ├── main.tsx                 # React entry: mounts ChatWindow
│   ├── styles.css               # all UI styling
│   ├── components/
│   │   └── ChatWindow.tsx       # the chat UI (see components/README.md)
│   └── lib/
│       ├── ws.ts                # typed WebSocket client (see lib/README.md)
│       └── audio.ts             # mic capture, MP3 playback queue, speech fallback
├── public/
│   └── pcm-processor.js         # AudioWorklet that forwards raw PCM (see public/README.md)
├── index.html                   # mounts #root
├── nginx.conf                   # serves the build; proxies /api + /ws to backend:8000
├── Dockerfile                   # multi-stage: node build -> nginx:alpine serve
├── vite.config.ts               # dev server on :5173, proxies /api + /ws to localhost:8000
├── package.json / package-lock.json
└── tsconfig.json
```

## Build and run

```bash
cd frontend && npm install
npm run dev     # http://localhost:5173 (proxies to a local backend)
npm run build   # type-checks (tsc --noEmit) then emits dist/
```

In Docker Compose the `dist/` output is served by nginx on port 80
(published as :3000), with `/ws/chat` upgraded for the WebSocket protocol.
