import React, { useEffect, useState } from 'react';

/**
 * Compact slice of recent operator commands for quick recall during demos.
 */
export default function CommandHistory() {
  const [cmds, setCmds] = useState([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch('/api/tasks/recent?limit=12');
        const data = await res.json();
        const list = (data.items || []).map((t) => t.command).reverse();
        if (!cancelled) setCmds(list);
      } catch {
        if (!cancelled) setCmds([]);
      }
    }
    load();
    const id = setInterval(load, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <section className="rounded-2xl border border-teal-500/15 bg-slate-900/40 p-4 backdrop-blur-md">
      <h3 className="font-display text-sm text-teal-100">Command Recall</h3>
      <ul className="mt-3 max-h-48 space-y-2 overflow-y-auto text-[11px] text-slate-400">
        {cmds.length === 0 && <li className="text-slate-600">Awaiting first directive…</li>}
        {cmds.map((c, i) => (
          <li key={i} className="rounded-lg bg-slate-950/50 px-2 py-1 ring-1 ring-white/5">
            {c}
          </li>
        ))}
      </ul>
    </section>
  );
}
