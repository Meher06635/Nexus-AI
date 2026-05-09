import React, { useEffect, useState } from 'react';

/**
 * Polls backend health + Ollama readiness for operator clarity.
 */
export default function AIStatus() {
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const res = await fetch('/api/health');
        const json = await res.json();
        if (!cancelled) setData(json);
      } catch {
        if (!cancelled) setData({ status: 'error' });
      }
    }
    poll();
    const id = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const ollamaOk = data?.ollama?.reachable;
  const model = data?.ollama?.model || '—';
  const modelOk = data?.ollama?.model_installed;
  const pullHint = data?.ollama?.hint;

  return (
    <section className="rounded-2xl border border-cyan-500/20 bg-slate-900/50 p-4 backdrop-blur-sm">
      <h3 className="font-display text-sm tracking-wide text-cyan-200">Core Status</h3>
      <dl className="mt-3 space-y-2 text-xs text-slate-300">
        <div className="flex justify-between gap-4">
          <dt className="text-slate-500">API</dt>
          <dd className={data?.status === 'ok' ? 'text-emerald-300' : 'text-red-300'}>
            {data?.status === 'ok' ? 'Online' : 'Offline'}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate-500">Ollama</dt>
          <dd className={ollamaOk ? 'text-emerald-300' : 'text-amber-300'}>
            {ollamaOk ? 'Reachable' : 'Unreachable'}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate-500">Model</dt>
          <dd
            className={`truncate text-right ${modelOk === false ? 'text-amber-300' : 'text-slate-100'}`}
            title={model}
          >
            {model}
            {ollamaOk && modelOk === false && ' (!)'}
          </dd>
        </div>
        {pullHint && (
          <p className="rounded-lg bg-amber-500/10 p-2 text-[10px] leading-snug text-amber-200/90">{pullHint}</p>
        )}
        <div className="flex justify-between gap-4">
          <dt className="text-slate-500">Voice</dt>
          <dd className="text-slate-100">
            STT {data?.voice?.stt ? '✓' : '✗'} · TTS {data?.voice?.tts ? '✓' : '✗'}
          </dd>
        </div>
      </dl>
    </section>
  );
}
