"""
Nexus AI FastAPI entrypoint: REST API for chat, voice transcription, TTS, logs, and task history.
Voice/STT loads lazily; Playwright shuts down cleanly on application lifespan exit.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.agent.nexus_agent import NexusAgent
from backend.automation.browser import PlaywrightController
from backend.automation.desktop import DesktopAutomation
from backend.config import settings
from backend.database.db import Database
from backend.memory.memory_service import MemoryService
from backend.tools.registry import ToolRegistry
from backend.voice.stt import SpeechToText
from backend.voice.tts import TextToSpeech


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    ok: bool
    reply: str
    session_id: str
    tool_trace: list[dict[str, Any]]
    error: str | None = None


class RememberRequest(BaseModel):
    content: str = Field(..., min_length=1)


def _new_session_id() -> str:
    return str(uuid.uuid4())


db: Database | None = None
memory_service: MemoryService | None = None
desktop: DesktopAutomation | None = None
browser_ctl: PlaywrightController | None = None
agent: NexusAgent | None = None
stt: SpeechToText | None = None
tts: TextToSpeech | None = None


def _should_auto_speak_completion(ok: bool, tool_trace: list[dict[str, Any]], reply: str) -> bool:
    """Speak only after successful command execution (tool-backed) with a non-empty reply."""
    return ok and bool(reply.strip()) and bool(tool_trace)


def _tts_completion_line(reply: str) -> str:
    """Keep spoken acknowledgment short and clear."""
    compact = " ".join(reply.split())
    if len(compact) > 220:
        compact = compact[:217].rstrip() + "..."
    return f"Task completed. {compact}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Wire singleton dependencies and release Playwright on shutdown."""
    global db, memory_service, desktop, browser_ctl, agent, stt, tts

    db_path = settings.resolved_db_path()
    db = Database(db_path)
    memory_service = MemoryService(db)
    desktop = DesktopAutomation(settings.resolved_screenshots_dir())
    browser_ctl = PlaywrightController(settings)
    registry = ToolRegistry(settings=settings, desktop=desktop, browser=browser_ctl, memory=memory_service)
    agent = NexusAgent(settings=settings, db=db, memory=memory_service, tool_registry=registry)

    if settings.enable_voice_stt:
        try:
            stt = SpeechToText(model_size=settings.whisper_model)
        except Exception:
            stt = None
    if settings.enable_voice_tts:
        try:
            tts = TextToSpeech()
        except Exception:
            tts = None

    yield

    if browser_ctl:
        browser_ctl.close()


app = FastAPI(title="Nexus AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ollama_model_in_tags(tags_body: dict[str, Any] | None, wanted: str) -> bool:
    """Return True if `wanted` matches an Ollama /api/tags model name."""
    if not tags_body or "models" not in tags_body:
        return False
    wanted = (wanted or "").strip().lower()
    for m in tags_body.get("models") or []:
        name = (m.get("name") or "").lower()
        if name == wanted or name.startswith(wanted + ":"):
            return True
    return False


@app.get("/api/health")
async def health() -> dict[str, Any]:
    """Service mesh friendly probe + optional Ollama reachability and model install check."""
    ollama_ok = False
    tags: dict[str, Any] | None = None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            ollama_ok = r.status_code == 200
            if ollama_ok:
                tags = r.json()
    except Exception:
        ollama_ok = False

    model_name = settings.ollama_model
    model_installed = _ollama_model_in_tags(tags, model_name) if ollama_ok else False

    return {
        "status": "ok",
        "ollama": {
            "reachable": ollama_ok,
            "model": model_name,
            "model_installed": model_installed,
            "hint": (
                None
                if model_installed or not ollama_ok
                else (f"Run: ollama pull {model_name}" if model_name else "Run: ollama pull llama3.2:1b")
            ),
        },
        "voice": {"stt": stt is not None, "tts": tts is not None},
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Primary agent endpoint — delegates to LangChain executor on a thread."""
    if not agent or not memory_service:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    sid = req.session_id or _new_session_id()
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: agent.run_turn(sid, req.message))

    ok = bool(result.get("ok"))
    err = result.get("error")
    reply = str(result.get("reply") or "")
    # Surface failures in the chat bubble (UI reads `reply`; empty looked like a generic "error").
    if not ok and err and not reply:
        reply = str(err)
    trace = list(result.get("tool_trace") or [])

    # Non-blocking voice acknowledgment for completed tool-execution tasks.
    if (
        settings.enable_voice_tts
        and settings.auto_voice_task_completion
        and tts is not None
        and _should_auto_speak_completion(ok=ok, tool_trace=trace, reply=reply)
    ):
        async def _speak_completion() -> None:
            try:
                await asyncio.to_thread(tts.speak, _tts_completion_line(reply))
            except Exception:
                # Voice feedback should never break the command response path.
                pass

        asyncio.create_task(_speak_completion())

    return ChatResponse(
        ok=ok,
        reply=reply,
        session_id=sid,
        tool_trace=trace,
        error=err if isinstance(err, str) else None,
    )


@app.post("/api/session/new")
async def new_session() -> dict[str, str]:
    return {"session_id": _new_session_id()}


@app.post("/api/memory/remember")
async def remember(body: RememberRequest) -> dict[str, Any]:
    if not memory_service:
        raise HTTPException(status_code=503, detail="Memory unavailable")
    return memory_service.remember_phrase(body.content)


@app.get("/api/memory/list")
async def list_memory(limit: int = 30) -> dict[str, Any]:
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"items": db.list_memories(limit=limit)}


@app.get("/api/tasks/recent")
async def recent_tasks(limit: int = 50) -> dict[str, Any]:
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"items": db.recent_tasks(limit=limit)}


@app.get("/api/history/{session_id}")
async def session_history(session_id: str, limit: int = 40) -> dict[str, Any]:
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"items": db.recent_messages(session_id, limit=limit)}


@app.post("/api/voice/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict[str, str]:
    """Upload audio (wav/webm/mp3) and receive Whisper transcript text."""
    if not settings.enable_voice_stt or not stt:
        raise HTTPException(status_code=503, detail="Speech-to-text disabled or unavailable")

    data = await audio.read()
    suffix = Path(audio.filename or "upload.wav").suffix or ".wav"

    loop = asyncio.get_running_loop()
    try:
        text = await loop.run_in_executor(None, lambda: stt.transcribe_upload(data, suffix=suffix))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Transcription failed: {exc}") from exc

    return {"text": text}


@app.get("/api/voice/speak")
async def speak(text: str) -> FileResponse:
    """Render TTS to a temporary WAV and stream it to the client."""
    if not settings.enable_voice_tts or not tts:
        raise HTTPException(status_code=503, detail="TTS disabled or unavailable")

    loop = asyncio.get_running_loop()

    def _render() -> Path:
        return tts.save_wav(text)

    path = await loop.run_in_executor(None, _render)
    return FileResponse(path, media_type="audio/wav", filename="nexus_reply.wav")

