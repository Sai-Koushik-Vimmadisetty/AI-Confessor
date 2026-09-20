/* Microphone capture: streams 16 kHz 16-bit mono PCM as base64 chunks.
   Vosk on the server expects exactly this format. */

export const TARGET_SAMPLE_RATE = 16000;

function floatTo16BitPCM(float32: Float32Array): Int16Array {
  const out = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function downsample(buffer: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return buffer;
  const ratio = fromRate / toRate;
  const newLen = Math.floor(buffer.length / ratio);
  const out = new Float32Array(newLen);
  for (let i = 0; i < newLen; i++) {
    out[i] = buffer[Math.floor(i * ratio)];
  }
  return out;
}

function int16ToBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength);
  let binary = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode.apply(null, Array.from(bytes.subarray(i, i + CHUNK)));
  }
  return btoa(binary);
}

export interface Recorder {
  stop: () => void;
}

export async function startRecording(onChunk: (base64pcm: string) => void): Promise<Recorder> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  // Request 16 kHz; Chrome honors it, others may not — we downsample below if needed.
  const ctx = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
  await ctx.audioWorklet.addModule('/pcm-processor.js');

  const source = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, 'pcm-processor');
  node.port.onmessage = (e: MessageEvent<Float32Array>) => {
    const resampled = downsample(e.data, ctx.sampleRate, TARGET_SAMPLE_RATE);
    onChunk(int16ToBase64(floatTo16BitPCM(resampled)));
  };
  source.connect(node);
  // Worklet nodes need a destination connection in some browsers to run.
  // Route through a zero-gain node so the mic is NOT played back through
  // the speakers (that would cause live feedback / howling).
  const mute = ctx.createGain();
  mute.gain.value = 0;
  node.connect(mute);
  mute.connect(ctx.destination);

  return {
    stop: () => {
      node.disconnect();
      source.disconnect();
      stream.getTracks().forEach((t) => t.stop());
      void ctx.close();
    },
  };
}

/* Playback: backend sends base64 MP3. Queued so replies never overlap. */
const queue: string[] = [];
let playing = false;
let currentAudio: HTMLAudioElement | null = null;

function playNext() {
  if (playing) return;
  const next = queue.shift();
  if (!next) return;
  playing = true;
  const bytes = Uint8Array.from(atob(next), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: 'audio/mpeg' }));
  const audio = new Audio(url);
  currentAudio = audio;
  const done = () => {
    URL.revokeObjectURL(url);
    if (currentAudio === audio) currentAudio = null;
    playing = false;
    playNext();
  };
  audio.onended = audio.onerror = done;
  void audio.play().catch(done);
}

export function playReplyAudio(base64mp3: string) {
  queue.push(base64mp3);
  playNext();
}

export function stopAllAudio() {
  queue.length = 0;
  // Also stop the reply currently playing, not just the queued ones.
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.removeAttribute('src');
    currentAudio = null;
  }
  playing = false;
}
