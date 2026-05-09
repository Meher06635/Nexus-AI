"""
Text-to-speech via pyttsx3 (offline, uses OS voices).
Can speak immediately or render to a WAV file for download by the React client.
"""

from __future__ import annotations

import tempfile
from pathlib import Path


class TextToSpeech:
    def __init__(self) -> None:
        self._engine = None

    def _engine_lazy(self):
        if self._engine is None:
            import pyttsx3

            self._engine = pyttsx3.init()
        return self._engine

    def speak(self, text: str) -> None:
        """Blocking speak on the default output device."""
        engine = self._engine_lazy()
        engine.say(text)
        engine.runAndWait()

    def save_wav(self, text: str, out_path: str | Path | None = None) -> Path:
        """Save speech to WAV; returns path to file."""
        engine = self._engine_lazy()
        if out_path is None:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            tmp.close()
            out_path = Path(tmp.name)
        else:
            out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        engine.save_to_file(text, str(out_path))
        engine.runAndWait()
        return out_path
