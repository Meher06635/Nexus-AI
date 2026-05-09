"""
Cross-platform desktop helpers: launch apps, open URLs, type text, screenshots.
Windows-focused shortcuts for common browsers and shell commands.
"""

from __future__ import annotations

import platform
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

import pyautogui

# Fail-safe: dragging mouse to corner aborts — useful during development.
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15


class DesktopAutomation:
    def __init__(self, screenshots_dir: Path) -> None:
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self._system = platform.system().lower()

    def open_url(self, url: str) -> str:
        """Open URL in default browser."""
        webbrowser.open(url, new=2)
        return f"Opened URL in default browser: {url}"

    def google_search(self, query: str) -> str:
        """Search Google in default browser."""
        q = quote_plus(query)
        url = f"https://www.google.com/search?q={q}"
        return self.open_url(url)

    def open_application(self, name: str) -> str:
        """
        Best-effort launch by OS shell.
        On Windows uses 'start'; elsewhere tries name as command.
        """
        name = name.strip()
        try:
            if self._system == "windows":
                # 'start' launches registered apps by name when possible
                subprocess.Popen(
                    ["cmd", "/c", "start", "", name],
                    shell=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen([name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Launch requested for: {name}"
        except Exception as exc:  # noqa: BLE001 — surface to agent
            return f"Failed to launch '{name}': {exc}"

    def open_path(self, path: str) -> str:
        """Open folder or file with OS default handler."""
        p = Path(path).expanduser()
        if not p.exists():
            return f"Path does not exist: {p}"
        try:
            if self._system == "windows":
                import os

                os.startfile(str(p))  # type: ignore[attr-defined]
            elif self._system == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
            return f"Opened path: {p}"
        except Exception as exc:  # noqa: BLE001
            return f"Failed to open path '{p}': {exc}"

    def create_note(self, title: str, body: str, notes_dir: Path) -> str:
        """Write a UTF-8 text note under notes_dir."""
        notes_dir = Path(notes_dir)
        notes_dir.mkdir(parents=True, exist_ok=True)
        safe_title = "".join(c if c.isalnum() or c in "._- " else "_" for c in title).strip() or "note"
        path = notes_dir / f"{safe_title}.txt"
        path.write_text(f"{title}\n\n{body}", encoding="utf-8")
        return f"Created note at {path}"

    def type_text(self, text: str, interval: float = 0.02) -> str:
        """Type Unicode text at the current focus using clipboard fallback when needed."""
        try:
            pyautogui.write(text, interval=interval)
            return "Typed text into focused window."
        except Exception:
            # Fallback for non-ASCII: clipboard paste simulation
            try:
                import pyperclip

                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")
                return "Pasted text via clipboard into focused window."
            except Exception as exc:  # noqa: BLE001
                return f"Could not type text: {exc}"

    def screenshot(self, prefix: str = "nexus") -> str:
        """Save full-screen PNG under screenshots_dir."""
        path = self.screenshots_dir / f"{prefix}_{time.time_ns()}.png"
        img = pyautogui.screenshot()
        img.save(path)
        return f"Screenshot saved: {path}"
