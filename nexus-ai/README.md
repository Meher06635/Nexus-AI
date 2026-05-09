# Nexus AI

Production-style **personal desktop agent** that listens to voice or text, reasons with a **local Ollama LLM** via **LangChain**, and executes **desktop + browser automation** (PyAutoGUI + Playwright). Includes **SQLite memory**, **Whisper STT**, **pyttsx3 TTS**, and a **React + Tailwind** control UI.

## Architecture

| Layer | Stack |
|-------|--------|
| UI | React 18, Vite 5, TailwindCSS |
| API | FastAPI + Uvicorn |
| Agent | LangChain tool-calling agent + ChatOllama |
| Voice | Whisper (local), pyttsx3 |
| Automation | PyAutoGUI, Playwright |
| Memory | SQLite (`conversations`, `tasks`, `memories`) |

### Repository layout

```
nexus-ai/
├── backend/
│   ├── main.py              # FastAPI app & routes
│   ├── config.py            # Pydantic Settings / .env
│   ├── agent/nexus_agent.py # LangChain orchestration
│   ├── tools/registry.py    # Tool definitions
│   ├── memory/
│   ├── automation/          # desktop + Playwright
│   ├── voice/
│   └── database/
├── frontend/                # React dashboard
├── screenshots/
├── logs/
├── notes/                   # create_note output
├── requirements.txt
└── README.md
```

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for the frontend)
- **Ollama** — default targets **low-memory PCs**: run `ollama pull llama3.2:1b` (often \<2 GB for weights).  
  On machines with **8 GB+ free RAM**, you can use `ollama pull mistral` and set `OLLAMA_MODEL=mistral:latest` in `.env`.
- **ffmpeg**: Nexus prepends the binary bundled with **`imageio-ffmpeg`** so browser WebM usually works without a separate install. You can still add system ffmpeg to `PATH` if you prefer.
- **Google Chrome / Edge** optional — Playwright can use `DEFAULT_BROWSER_CHANNEL=chrome`

## Backend setup

From the `nexus-ai` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env
```

Edit `.env` (model name, paths, headless mode).

Run the API (must be executed with project root on `PYTHONPATH`; from `nexus-ai`):

```powershell
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: `http://127.0.0.1:8000/api/health`

## Frontend setup

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` — Vite proxies `/api/*` to FastAPI on port **8000**.

## Agent workflow

1. Receive command (voice → Whisper, or typed).
2. Inject **memories** + short **chat history** into the system prompt.
3. **LangChain** `AgentExecutor` calls **ChatOllama** with structured tools.
4. Tools perform desktop/browser automation; observations return to the model.
5. Final natural-language reply is persisted to SQLite (`conversations` + `tasks`).

## Example commands

| Say / type | Behavior |
|------------|-----------|
| “Open YouTube” | Playwright opens YouTube |
| “Search AI news” | Google search in default browser |
| “Create notes for DBMS …” | Writes `notes/<title>.txt` |
| “Take screenshot” | PNG under `screenshots/` |
| “Remember this: my laptop PIN is …” | **Don’t store secrets** — illustration only; stored via `remember_this` tool |
| “Send a WhatsApp message to Rahul saying I am late” | Opens WhatsApp Web, searches chat, sends text (**requires logged-in WA Web**) |

## WhatsApp Web automation

WhatsApp’s DOM changes frequently. Nexus ships **best-effort selectors** in `backend/automation/browser.py`. After scanning QR once in the Playwright browser profile, flows are more reliable. For production hardening, pin selectors via fixtures or accessibility snapshots.

## Security & safety notes

- This project can **control your mouse/keyboard** and **drive browsers**. Run only on trusted machines.
- PyAutoGUI **failsafe**: move mouse to a screen corner to abort during development.
- Never ask the agent to store secrets; demo “remember this” with non-sensitive facts only.

## Troubleshooting

| Issue | Mitigation |
|-------|------------|
| `pip install` WinError 32 on `torch` | Stop other pip/Python processes and rerun `pip install -r requirements.txt` once. |
| `model requires more system memory … GiB` (HTTP 500) | Your **Ollama model is too large** for free RAM. Use `OLLAMA_MODEL=llama3.2:1b` or `tinyllama`, run `ollama pull llama3.2:1b`, restart Nexus; set `WHISPER_MODEL=tiny` if needed. |
| Ollama unreachable | Start Ollama service; verify `OLLAMA_BASE_URL` |
| Whisper errors on upload | Install ffmpeg; try shorter clips |
| Empty tool calls | Switch to `llama3` / newer Mistral builds with tool support |
| Playwright launch fails | Run `python -m playwright install` or clear `DEFAULT_BROWSER_CHANNEL` |

Always run the API via **Uvicorn** (or another ASGI server) so FastAPI **lifespan** wiring runs — otherwise voice singletons stay uninitialized.

## License

MIT — showcase / hackathon use; tune responsibly for production.
