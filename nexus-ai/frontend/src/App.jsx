import React, { useCallback, useEffect, useMemo, useState } from 'react';
import AIStatus from './components/AIStatus.jsx';
import ChatWindow from './components/ChatWindow.jsx';
import CommandHistory from './components/CommandHistory.jsx';
import TaskLogs from './components/TaskLogs.jsx';
import VoiceButton from './components/VoiceButton.jsx';

const SESSION_KEY = 'nexus_ai_session';

/**
 * Root shell: orchestrates chat transport, optional spoken replies, and dashboard widgets.
 */
export default function App() {
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) || '');
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const CHAT_TIMEOUT_MS = 60000;
  const [sessionBusy, setSessionBusy] = useState(false);

  const ensureSession = useCallback(async () => {
    if (sessionId || sessionBusy) return sessionId;
    setSessionBusy(true);
    try {
      const res = await fetch('/api/session/new', { method: 'POST' });
      if (!res.ok) {
        throw new Error(`Session init failed (${res.status})`);
      }
      const data = await res.json();
      const sid = data.session_id;
      localStorage.setItem(SESSION_KEY, sid);
      setSessionId(sid);
      return sid;
    } finally {
      setSessionBusy(false);
    }
  }, [sessionId, sessionBusy]);

  useEffect(() => {
    ensureSession().catch((e) => {
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: `Session setup failed: ${e.message || e}` },
      ]);
    });
  }, [ensureSession]);

  const speak = useCallback(async (text) => {
    if (!text) return;
    try {
      const url = `/api/voice/speak?text=${encodeURIComponent(text)}`;
      const audio = new Audio(url);
      await audio.play();
    } catch {
      /* TTS optional — swallow playback errors for silent fallback */
    }
  }, []);

  const sendMessage = useCallback(
    async (text) => {
      let sid = sessionId;
      if (!sid) {
        try {
          sid = await ensureSession();
        } catch (e) {
          setMessages((m) => [
            ...m,
            { role: 'assistant', content: `Cannot send yet: ${e.message || e}` },
          ]);
          return;
        }
      }
      if (busy) return;
      setBusy(true);
      setMessages((m) => [...m, { role: 'user', content: text }]);
      let timeoutId = null;
      try {
        const controller = new AbortController();
        timeoutId = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, session_id: sid }),
          signal: controller.signal,
        });
        const data = await res.json();
        const reply = data.reply || data.error || 'No response.';
        setMessages((m) => [...m, { role: 'assistant', content: reply }]);
        if (autoSpeak) await speak(reply);
      } catch (e) {
        const message =
          e?.name === 'AbortError'
            ? 'Request timed out. Backend took too long, please try again.'
            : `Request failed: ${e.message || e}`;
        setMessages((m) => [
          ...m,
          { role: 'assistant', content: message },
        ]);
      } finally {
        if (timeoutId) clearTimeout(timeoutId);
        setBusy(false);
      }
    },
    [sessionId, autoSpeak, speak, busy, ensureSession],
  );

  const onVoiceTranscript = useCallback(
    (t) => {
      if (t) sendMessage(t);
    },
    [sendMessage],
  );

  const headerSubtitle = useMemo(
    () => 'Personal desktop agent · Whisper · Ollama · LangChain · Playwright',
    [],
  );

  return (
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-4 py-8 lg:px-10">
      <header className="flex flex-col gap-4 border-b border-white/10 pb-6 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-teal-300/80">Nexus AI</p>
          <h1 className="font-display text-4xl font-bold text-white md:text-5xl">Control Plane</h1>
          <p className="mt-2 max-w-xl text-sm text-slate-400">{headerSubtitle}</p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={autoSpeak}
              onChange={(e) => setAutoSpeak(e.target.checked)}
              className="accent-teal-400"
            />
            Auto voice reply
          </label>
          <button
            type="button"
            onClick={() => {
              localStorage.removeItem(SESSION_KEY);
              window.location.reload();
            }}
            className="rounded-xl border border-white/10 px-4 py-2 text-xs uppercase tracking-widest text-slate-300 hover:border-teal-400/40"
          >
            New session
          </button>
        </div>
      </header>

      <main className="grid flex-1 gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="flex flex-col gap-4">
          <ChatWindow messages={messages} onSend={sendMessage} busy={busy} />
          <div className="flex items-center justify-center gap-6 rounded-2xl border border-white/5 bg-slate-900/30 p-4">
            <VoiceButton onTranscript={onVoiceTranscript} disabled={busy || sessionBusy} />
            <p className="max-w-sm text-xs text-slate-500">
              Tap the mic to capture a directive. Nexus transcribes locally via Whisper, reasons with your Ollama
              model, then dispatches Playwright / PyAutoGUI tools.
            </p>
          </div>
        </div>

        <aside className="flex flex-col gap-4">
          <AIStatus />
          <CommandHistory />
          <TaskLogs />
        </aside>
      </main>

      <footer className="pb-6 text-center text-[11px] text-slate-600">
        Hackathon-ready stack · FastAPI backend on :8000 · Vite UI on :5173 · Keep Playwright browsers installed.
      </footer>
    </div>
  );
}
