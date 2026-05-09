"""
Central configuration loaded from environment variables and optional .env file.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths (resolved relative to nexus-ai project root when defaults used)
    project_root: Path = Path(__file__).resolve().parents[1]
    database_path: Path | None = None
    screenshots_dir: Path | None = None
    logs_dir: Path | None = None
    notes_dir: Path | None = None

    # Ollama / LangChain — default is small so Nexus runs on ~4 GB RAM laptops.
    # Override with e.g. mistral:latest on machines with 8 GB+ free for the model.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"
    ollama_keep_alive: str = "30m"
    ollama_num_ctx: int = 2048
    ollama_num_predict: int = 120
    ollama_temperature: float = 0.1

    # Whisper (speech-to-text) — use tiny on very low-RAM systems alongside Ollama.
    whisper_model: str = "base"

    # Browser automation
    playwright_headless: bool = False
    default_browser_channel: str = "chrome"  # empty = bundled Chromium

    # Feature toggles
    enable_voice_stt: bool = True
    enable_voice_tts: bool = True
    auto_voice_task_completion: bool = True

    def resolved_db_path(self) -> Path:
        base = self.database_path or (self.project_root / "backend" / "database" / "nexus.db")
        base.parent.mkdir(parents=True, exist_ok=True)
        return Path(base)

    def resolved_screenshots_dir(self) -> Path:
        d = self.screenshots_dir or (self.project_root / "screenshots")
        d.mkdir(parents=True, exist_ok=True)
        return Path(d)

    def resolved_logs_dir(self) -> Path:
        d = self.logs_dir or (self.project_root / "logs")
        d.mkdir(parents=True, exist_ok=True)
        return Path(d)

    def resolved_notes_dir(self) -> Path:
        d = self.notes_dir or (self.project_root / "notes")
        d.mkdir(parents=True, exist_ok=True)
        return Path(d)


settings = Settings()
