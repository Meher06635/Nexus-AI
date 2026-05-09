"""
Speech-to-text using OpenAI Whisper (local).
Model loads lazily to keep API startup fast and optional when voice is disabled.

Browser uploads are usually WebM/Opus; Whisper decodes via ffmpeg. On Windows, PATH often
lacks ffmpeg — we prepend imageio-ffmpeg's bundled binary so transcription works out of the box.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


def _prepend_bundled_ffmpeg_to_path() -> str | None:
    """
    Whisper shells out to `ffmpeg`. Return the ffmpeg directory added to PATH, or None if unavailable.
    """
    try:
        import imageio_ffmpeg

        exe = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
        if not exe.exists():
            return None

        # imageio-ffmpeg ships filenames like "ffmpeg-win-x86_64-v7.0.exe", but Whisper
        # invokes the plain command name "ffmpeg". Create a stable alias once.
        alias_dir = exe.parent / "nexus_ffmpeg"
        alias_dir.mkdir(parents=True, exist_ok=True)
        alias = alias_dir / "ffmpeg.exe"
        if not alias.exists():
            shutil.copy2(exe, alias)

        bin_dir = str(alias_dir)
        path = os.environ.get("PATH", "")
        if bin_dir not in path.split(os.pathsep):
            os.environ["PATH"] = bin_dir + os.pathsep + path
        return bin_dir
    except Exception:
        return None


class SpeechToText:
    """
    Wraps whisper.load_model once and transcribes audio files.
    Prefer bundled ffmpeg (see above); users can still install system ffmpeg for overrides.
    """

    def __init__(self, model_size: str = "base") -> None:
        self.model_size = model_size
        self._model: Any = None

    def _ensure_model(self) -> None:
        if self._model is None:
            import whisper

            _prepend_bundled_ffmpeg_to_path()
            self._model = whisper.load_model(self.model_size)

    def transcribe_file(self, path: str | Path) -> dict[str, Any]:
        """Transcribe audio file; returns whisper result dict (includes 'text')."""
        _prepend_bundled_ffmpeg_to_path()
        self._ensure_model()
        path = Path(path)
        assert self._model is not None
        return self._model.transcribe(str(path))

    def transcribe_upload(self, content: bytes, suffix: str = ".wav") -> str:
        """Write upload bytes to temp file and return plain transcript text."""
        if len(content) < 64:
            raise ValueError(
                "Audio clip is empty or too short — hold the mic longer or check browser microphone permissions."
            )

        suffix = suffix if suffix.startswith(".") else f".{suffix}"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            result = self.transcribe_file(tmp_path)
            return (result.get("text") or "").strip()
        except FileNotFoundError as exc:
            raise RuntimeError(
                "ffmpeg not found — install ffmpeg and add it to PATH, or reinstall deps so "
                "`imageio-ffmpeg` can bundle it."
            ) from exc
        finally:
            Path(tmp_path).unlink(missing_ok=True)
