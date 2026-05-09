import React, { useEffect, useState } from 'react';

/**
 * Automation ledger — surfaces SQLite-backed task rows + tool traces for demos.
 */
export default function TaskLogs() {
  const [items, setItems] = useState([]);
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch('/api/tasks/recent?limit=40');
        const data = await res.json();
        if (!cancelled) setItems(data.items || []);
      } catch {
        if (!cancelled) setItems([]);
      }
    }
    load();
    const id = setInterval(load, 8000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  function toggle(id) {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  return (
    <section className="flex max-h-[340px] flex-col rounded-2xl border border-white/10 bg-slate-900/40 p-4 backdrop-blur-md">
      <header className="mb-2 flex items-center justify-between">
        <div>
          <h3 className="font-display text-sm text-slate-100">Task Ledger</h3>
          <p className="text-[10px] text-slate-500">SQLite-backed automation history</p>
        </div>
      </header>
      <div className="flex-1 space-y-2 overflow-y-auto pr-1 text-xs">
        {items.length === 0 && <p className="text-slate-500">No tasks recorded yet.</p>}
        {items.map((t) => (
          <div key={t.id} className="rounded-xl bg-slate-950/60 p-3 ring-1 ring-white/5">
            <div className="flex items-start justify-between gap-2">
              <p className="flex-1 font-medium text-teal-100">{t.command}</p>
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] uppercase ${
                  t.status === 'ok'
                    ? 'bg-emerald-500/15 text-emerald-200'
                    : 'bg-red-500/15 text-red-200'
                }`}
              >
                {t.status}
              </span>
            </div>
            {t.result && <p className="mt-2 text-[11px] text-slate-400">{t.result}</p>}
            <button
              type="button"
              onClick={() => toggle(t.id)}
              className="mt-2 text-[10px] uppercase tracking-wider text-cyan-300 hover:text-cyan-100"
            >
              {expanded[t.id] ? 'Hide trace' : 'Tool trace'}
            </button>
            {expanded[t.id] && (
              <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-black/40 p-2 text-[10px] text-slate-400">
                {JSON.stringify(t.tool_trace || [], null, 2)}
              </pre>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
