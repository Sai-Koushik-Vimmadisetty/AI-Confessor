/* Typed WebSocket client for the /ws/chat protocol. */

export type ServerMessage =
  | { type: 'session'; session_id: string }
  | { type: 'transcript'; text: string; final: boolean }
  | { type: 'token'; token: string }
  | { type: 'audio'; format: string; data: string }
  | { type: 'response_done'; full_text: string }
  | { type: 'reset_done' }
  | { type: 'pong' }
  | { type: 'error'; message: string };

export interface ServerConfig {
  mock_mode: boolean;
  tts_enabled: boolean;
  stt_available: boolean;
  stt_sample_rate: number;
  llm_model: string;
}

export function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws/chat`;
}

export async function fetchServerConfig(): Promise<ServerConfig> {
  const res = await fetch('/api/config');
  if (!res.ok) throw new Error(`config fetch failed: ${res.status}`);
  return res.json() as Promise<ServerConfig>;
}

export class ChatSocket {
  private ws: WebSocket | null = null;
  onMessage: (msg: ServerMessage) => void = () => {};
  onClose: () => void = () => {};

  connect() {
    this.ws = new WebSocket(wsUrl());
    this.ws.onmessage = (e: MessageEvent) => {
      try {
        this.onMessage(JSON.parse(e.data as string) as ServerMessage);
      } catch {
        /* ignore malformed frames */
      }
    };
    this.ws.onclose = () => this.onClose();
    this.ws.onerror = () => this.ws?.close();
  }

  private send(obj: unknown) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }

  sendText(text: string) {
    this.send({ type: 'text', text });
  }
  sendAudioChunk(base64pcm: string) {
    this.send({ type: 'audio_chunk', data: base64pcm });
  }
  endAudio() {
    this.send({ type: 'end_audio' });
  }
  reset() {
    this.send({ type: 'reset' });
  }
  ping() {
    this.send({ type: 'ping' });
  }
  close() {
    this.ws?.close();
    this.ws = null;
  }

  get connected(): boolean {
    return !!this.ws && this.ws.readyState === WebSocket.OPEN;
  }
}
