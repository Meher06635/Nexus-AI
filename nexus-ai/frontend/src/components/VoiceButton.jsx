import React, { useCallback, useRef, useState } from 'react';

/**
 * Push-to-talk helper: records microphone audio, uploads to Whisper backend.
 */
export default function VoiceButton({ onTranscript, disabled }) {
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState('');
  const mediaRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);

  const stopRecorder = useCallback(
    (recorder) =>
      new Promise((resolve) => {
        recorder.onstop = () => resolve();
        recorder.stop();
      }),
    [],
  );

  async function toggle() {
    setError('');
    if (!recording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRef.current = stream;
        const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm';
        const recorder = new MediaRecorder(stream, { mimeType: mime });
        chunksRef.current = [];
        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunksRef.current.push(e.data);
        };
        /* Periodic chunks so short clips still yield data before stop() on all browsers */
        recorder.start(250);
        recorderRef.current = recorder;
        setRecording(true);
      } catch {
        setError('Mic permission denied or unavailable.');
      }
      return;
    }

    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      await stopRecorder(recorder);
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
      mediaRef.current?.getTracks().forEach((t) => t.stop());

      if (!blob.size) {
        setError('No audio captured — speak longer, then tap stop.');
        setRecording(false);
        return;
      }

      const fd = new FormData();
      fd.append('audio', blob, 'voice.webm');

      try {
        const res = await fetch('/api/voice/transcribe', { method: 'POST', body: fd });
        const raw = await res.text();
        if (!res.ok) {
          let msg = raw;
          try {
            const j = JSON.parse(raw);
            const d = j.detail;
            msg =
              typeof d === 'string'
                ? d
                : Array.isArray(d)
                  ? d.map((x) => x.msg || JSON.stringify(x)).join(' ')
                  : raw;
          } catch {
            /* keep raw */
          }
          throw new Error(msg);
        }
        const data = JSON.parse(raw);
        onTranscript(data.text || '');
      } catch (err) {
        const hint = err?.message || String(err);
        setError(hint.length > 120 ? `${hint.slice(0, 117)}…` : hint);
        console.error(err);
      }
    }
    setRecording(false);
  }

  return (
    <div className="flex flex-col items-center gap-1">
      <button
        type="button"
        onClick={toggle}
        disabled={disabled}
        className={`relative flex h-14 w-14 items-center justify-center rounded-full border text-xs font-display uppercase tracking-widest transition ${
          recording
            ? 'border-red-400 bg-red-500/20 text-red-200 shadow-[0_0_30px_rgba(248,113,113,0.35)]'
            : 'border-teal-400/40 bg-teal-500/10 text-teal-100 hover:bg-teal-500/20'
        } disabled:opacity-40`}
        title={recording ? 'Stop & transcribe' : 'Start voice'}
      >
        <span className="pointer-events-none absolute inset-0 animate-pulseSlow rounded-full opacity-30 ring-2 ring-teal-400/40" />
        🎙
      </button>
      <span className="text-[10px] text-slate-500">{recording ? 'Listening…' : 'Voice'}</span>
      {error && <span className="max-w-[140px] text-center text-[10px] text-red-300">{error}</span>}
    </div>
  );
}
