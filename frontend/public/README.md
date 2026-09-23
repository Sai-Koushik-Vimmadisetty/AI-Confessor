# frontend/public/

Static assets served as-is (copied verbatim into the production build).

## pcm-processor.js

An `AudioWorkletProcessor` named `pcm-processor`. It runs on the browser's
audio thread, receives raw float32 mono mic samples, copies each buffer
(the underlying memory is reused by the audio thread, so the copy matters),
and posts it to the main thread. `audio.ts` loads it via
`audioWorklet.addModule('/pcm-processor.js')` and turns those samples into
the base64 16 kHz 16-bit PCM chunks the server's Vosk recognizer expects.
