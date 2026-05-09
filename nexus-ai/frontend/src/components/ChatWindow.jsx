import React, { useEffect, useRef } from 'react';

/**
 * Scrollable transcript + composer for user ↔ Nexus exchanges.
 */
export default function ChatWindow({ messages, onSend, busy }) {
  const bottomRef = useRef(null);
  const [text, setText] = React.useState('');

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  function submit(e) {
    e.preventDefault();
    const t = text.trim();
    if (!t || busy) return;
    onSend(t);
    setText('');
  }

  return (
    <section className="flex h-full min-h-[420px] flex-col rounded-2xl border border-teal-500/20 bg-slate-900/40 p-4 shadow-glow backdrop-blur-md">
      <header className="mb-3 flex items-center justify-between border-b border-teal-500/10 pb-2">
        <div>
          <h2 className="font-display text-lg tracking-wide text-teal-300">Neural Chat</h2>
          <p className="text-xs text-slate-500">Voice + text unified session</p>
        </div>
        <span className="rounded-full bg-teal-500/10 px-3 py-1 text-[10px] uppercase tracking-widest text-teal-200">
          Live
        </span>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto rounded-xl bg-slate-950/50 p-3 ring-1 ring-white/5">
        {messages.length === 0 && (
          <p className="text-center text-sm text-slate-500">
            Command Nexus to orchestrate your desktop, browser, and memory — try “Open YouTube” or “Remember
            this: …”.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[92%] rounded-2xl px-4 py-2 text-sm leading-relaxed ${
              m.role === 'user'
                ? 'ml-auto bg-teal-600/20 text-teal-50 ring-1 ring-teal-400/30'
                : 'mr-auto bg-slate-800/80 text-slate-100 ring-1 ring-white/10'
            }`}
          >
            <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">
              {m.role === 'user' ? 'You' : 'Nexus'}
            </div>
            <div className="whitespace-pre-wrap">{m.content}</div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={submit} className="mt-3 flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={busy ? 'Processing... you can keep typing your next directive' : 'Type a directive...'}
          className="flex-1 rounded-xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-slate-100 outline-none ring-teal-400/30 placeholder:text-slate-600 focus:border-teal-400/40 focus:ring"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded-xl bg-gradient-to-br from-teal-400 to-cyan-500 px-5 py-3 font-display text-sm font-semibold text-slate-950 shadow-lg shadow-teal-500/20 transition hover:brightness-110 disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </section>
  );
}
