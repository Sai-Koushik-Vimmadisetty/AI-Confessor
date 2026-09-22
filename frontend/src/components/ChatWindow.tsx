import { useCallback, useEffect, useRef, useState } from 'react';
import { playReplyAudio, speakReplyText, startRecording, stopAllAudio, type Recorder } from '../lib/audio';
import { ChatSocket, fetchServerConfig, type ServerConfig, type ServerMessage } from '../lib/ws';

interface ChatMsg {
  id: number;
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
}

let idCounter = 1;
const nextId = () => idCounter++;

export default function ChatWindow() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [connected, setConnected] = useState(false);
  const [recording, setRecording] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [voiceOn, setVoiceOn] = useState(true);
  // Read via ref inside the socket message handler so toggling voice never
  // changes the handler's identity (which would reconnect the socket and
  // drop the session + conversation history).
  const voiceOnRef = useRef(voiceOn);
  // Tracks whether the server sent MP3 audio for the current turn. If it
  // didn't (TTS unavailable server-side), the browser speaks the reply text
  // itself on response_done so voice replies still work.
  const serverAudioRef = useRef(false);
  const [config, setConfig] = useState<ServerConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);

  const socketRef = useRef<ChatSocket | null>(null);
  const recorderRef = useRef<Recorder | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const patchStreaming = useCallback((token: string) => {
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.role === 'assistant' && last.streaming) {
        return [...prev.slice(0, -1), { ...last, text: last.text + token }];
      }
      return [...prev, { id: nextId(), role: 'assistant', text: token, streaming: true }];
    });
  }, []);

  const finalizeStreaming = useCallback((fullText: string) => {
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.role === 'assistant' && last.streaming) {
        return [...prev.slice(0, -1), { ...last, text: fullText, streaming: false }];
      }
      return [...prev, { id: nextId(), role: 'assistant', text: fullText }];
    });
    setThinking(false);
  }, []);

  const handleServerMessage = useCallback(
    (msg: ServerMessage) => {
      switch (msg.type) {
        case 'token':
          patchStreaming(msg.token);
          break;
        case 'audio':
          serverAudioRef.current = true;
          if (voiceOnRef.current) playReplyAudio(msg.data);
          break;
        case 'response_done':
          finalizeStreaming(msg.full_text);
          setLiveTranscript('');
          // Fallback: server sent no audio for this turn, so speak the text
          // with the device's built-in voice instead of staying silent.
          if (voiceOnRef.current && !serverAudioRef.current && msg.full_text) {
            speakReplyText(msg.full_text);
          }
          break;
        case 'transcript':
          setLiveTranscript(msg.text);
          if (msg.final && msg.text) {
            serverAudioRef.current = false;
            setMessages((prev) => [...prev, { id: nextId(), role: 'user', text: msg.text }]);
            setThinking(true);
          }
          break;
        case 'reset_done':
          setMessages([]);
          setLiveTranscript('');
          break;
        case 'error':
          setMessages((prev) => [...prev, { id: nextId(), role: 'assistant', text: `⚠️ ${msg.message}` }]);
          setThinking(false);
          break;
        default:
          break;
      }
    },
    [patchStreaming, finalizeStreaming],
  );

  useEffect(() => {
    const socket = new ChatSocket();
    socketRef.current = socket;
    socket.onMessage = handleServerMessage;
    socket.onClose = () => setConnected(false);
    socket.connect();

    // Consider "connected" once the socket opens.
    const timer = window.setInterval(() => {
      if (socket.connected) {
        setConnected(true);
        window.clearInterval(timer);
      }
    }, 300);

    fetchServerConfig()
      .then(setConfig)
      .catch((e: unknown) => setConfigError(e instanceof Error ? e.message : String(e)));

    // Keepalive.
    const ping = window.setInterval(() => {
      socket.ping();
    }, 25000);

    return () => {
      window.clearInterval(timer);
      window.clearInterval(ping);
      recorderRef.current?.stop();
      socket.close();
    };
  }, [handleServerMessage]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, liveTranscript]);

  const sendText = () => {
    const text = input.trim();
    if (!text || !socketRef.current) return;
    serverAudioRef.current = false;
    stopAllAudio();
    setMessages((prev) => [...prev, { id: nextId(), role: 'user', text }]);
    setInput('');
    setThinking(true);
    socketRef.current.sendText(text);
  };

  const toggleRecording = async () => {
    if (recording) {
      recorderRef.current?.stop();
      recorderRef.current = null;
      setRecording(false);
      socketRef.current?.endAudio();
      return;
    }
    try {
      const recorder = await startRecording((chunk) => socketRef.current?.sendAudioChunk(chunk));
      recorderRef.current = recorder;
      setRecording(true);
      setLiveTranscript('');
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: 'assistant', text: '⚠️ Microphone access was denied.' },
      ]);
    }
  };

  const resetChat = () => {
    stopAllAudio();
    socketRef.current?.reset();
  };

  return (
    <div className="chat-shell">
      <header className="chat-header">
        <div>
          <h1>🎙️ AI Confessor</h1>
          <p className="subtitle">
            {config ? (
              <>
                {config.mock_mode ? 'MOCK MODE' : config.llm_model} ·{' '}
                {config.stt_available ? 'voice on' : 'text only'} ·{' '}
                {connected ? 'connected' : 'connecting…'}
              </>
            ) : configError ? (
              `backend unreachable (${configError})`
            ) : (
              'connecting…'
            )}
          </p>
        </div>
        <div className="header-actions">
          <button
            className={voiceOn ? 'btn small active' : 'btn small'}
            onClick={() => {
              const next = !voiceOnRef.current;
              voiceOnRef.current = next;
              setVoiceOn(next);
              if (!next) stopAllAudio();
            }}
            title="Toggle spoken replies"
          >
            🔊 Voice {voiceOn ? 'on' : 'off'}
          </button>
          <button className="btn small" onClick={resetChat} title="Clear conversation">
            ↺ Reset
          </button>
        </div>
      </header>

      <main className="messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <p>Unburden yourself. Type below — or hold the mic and speak.</p>
            <p className="hint">Everything you say stays in this session.</p>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            <div className="bubble">
              {m.text}
              {m.streaming && <span className="caret">▍</span>}
            </div>
          </div>
        ))}
        {liveTranscript && !thinking && (
          <div className="msg user">
            <div className="bubble interim">{liveTranscript} …</div>
          </div>
        )}
        {thinking && <div className="thinking">The Confessor is listening…</div>}
        <div ref={bottomRef} />
      </main>

      <footer className="composer">
        <button
          className={recording ? 'mic recording' : 'mic'}
          onClick={toggleRecording}
          disabled={!config?.stt_available}
          title={config?.stt_available ? 'Hold a conversation by voice' : 'Voice unavailable'}
        >
          {recording ? '⏹' : '🎤'}
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendText()}
          placeholder={recording ? 'Listening… tap ⏹ when done' : 'Confess something…'}
          disabled={recording}
        />
        <button className="btn" onClick={sendText} disabled={!input.trim()}>
          Send
        </button>
      </footer>
    </div>
  );
}
