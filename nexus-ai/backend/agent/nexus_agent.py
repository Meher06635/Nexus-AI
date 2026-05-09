"""
Nexus LangChain agent: ChatOllama + tool calling + explicit step-by-step reasoning instructions.
Runs sync chains inside asyncio.to_thread from FastAPI handlers.
"""

from __future__ import annotations

import re
import traceback
from typing import Any

# LangChain v1 routes classic agents through langchain-classic (pulled by langchain-community).
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_ollama import ChatOllama

from backend.config import Settings
from backend.database.db import Database
from backend.memory.memory_service import MemoryService
from backend.tools.registry import ToolRegistry, build_nexus_tools


SYSTEM_PROMPT = """You are Nexus AI, a production-grade desktop copilot.

Reasoning policy:
1. Think step-by-step in silent analysis before choosing tools.
2. Prefer the safest minimal sequence of tools (fewer actions is better).
3. Confirm prerequisites (e.g., WhatsApp Web login, focused window for typing).
4. After tools run, summarize outcomes clearly for the user.

Operational notes:
- For opening websites, prefer open_website with full https URL when known.
- For search intents, use google_search unless the user names YouTube explicitly.
- WhatsApp: call open_whatsapp_web first if session likely cold; then send_whatsapp_message.
- When the user asks to remember something, call remember_this.

Saved memories (facts the user asked to store):
{memories}
"""

# Short direct replies without spinning the tool agent (avoids long loops on tiny models).
DIRECT_CHAT_SYSTEM = """You are Nexus AI, a helpful desktop copilot.
Be concise and friendly. You can describe what you are capable of (open apps, browser automation,
WhatsApp Web, screenshots, notes) when asked.
Do not claim you already performed an action unless the user asked for it in this message.

Saved memories:
{memories}
"""

_AUTOMATION_HINTS = (
    "open ",
    "launch ",
    "start ",
    "search ",
    "google ",
    "youtube",
    "whatsapp",
    "gmail",
    "screenshot",
    "screenshots",
    "take a pic",
    "type this",
    "type text",
    "click ",
    "browser",
    "http://",
    "https://",
    "remember this",
    "remember that",
    "save this",
    "create note",
    "write a note",
    "folder ",
    "playwright",
    "automate",
    "send a message",
    "send whatsapp",
)

_INSTANT_REPLIES: dict[str, str] = {
    "hi": "Hi! I am Nexus AI. Tell me a task and I will run it.",
    "hello": "Hello! I am ready. Try: Open YouTube, Search AI news, or Take screenshot.",
    "hey": "Hey! What would you like me to do?",
    "hi nexus": "Hi! I am online and ready.",
    "how are you": "Running smoothly. Give me a command and I will execute it.",
}


class NexusAgent:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        memory: MemoryService,
        tool_registry: ToolRegistry,
    ) -> None:
        self.settings = settings
        self.db = db
        self.memory = memory
        self.tool_registry = tool_registry
        self.tools = build_nexus_tools(tool_registry)
        self.llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=settings.ollama_temperature,
            keep_alive=settings.ollama_keep_alive,
            num_ctx=settings.ollama_num_ctx,
            num_predict=settings.ollama_num_predict,
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder("chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )

        agent_runnable = create_tool_calling_agent(self.llm, self.tools, prompt)
        self.executor = AgentExecutor(
            agent=agent_runnable,
            tools=self.tools,
            verbose=False,
            handle_parsing_errors=True,
            max_iterations=4,
        )

    def _messages_from_history(self, session_id: str) -> list[BaseMessage]:
        pairs = self.memory.chat_history_for_prompt(session_id)
        msgs: list[BaseMessage] = []
        for role, content in pairs:
            if role == "user":
                msgs.append(HumanMessage(content=content))
            elif role == "assistant":
                msgs.append(AIMessage(content=content))
        return msgs

    def _looks_like_automation_request(self, text: str) -> bool:
        """Heuristic: use the tool agent only when the user likely wants desktop/browser actions."""
        t = text.strip().lower()
        if len(t) > 500:
            return True
        for hint in _AUTOMATION_HINTS:
            if hint in t:
                return True
        # Explicit command style: "open X", single-word app names after verbs handled above
        if re.match(r"^(go to|navigate to|visit)\s+https?://", t):
            return True
        return False

    def _instant_smalltalk(self, text: str) -> str | None:
        """Return ultra-fast canned replies for common tiny greetings."""
        t = re.sub(r"\s+", " ", text.strip().lower())
        return _INSTANT_REPLIES.get(t)

    def _execute_fast_command(self, user_text: str) -> str | None:
        """Deterministic shortcuts for very common commands (no LLM roundtrip)."""
        raw = user_text.strip()
        t = raw.lower()
        desk = self.tool_registry.desktop

        m = re.match(r"^(?:open|go to|navigate to|visit)\s+(https?://\S+)\s*$", raw, flags=re.I)
        if m:
            return desk.open_url(m.group(1))
        if t.startswith("search "):
            return desk.google_search(raw[7:].strip())
        if t.startswith("google "):
            return desk.google_search(raw[7:].strip())
        if "open youtube" in t:
            return desk.open_url("https://www.youtube.com/")
        if "open gmail" in t:
            return desk.open_url("https://mail.google.com/")
        if "open whatsapp" in t:
            return desk.open_url("https://web.whatsapp.com/")
        if t.startswith("open "):
            # open <app-or-url>
            arg = raw[5:].strip()
            if arg.startswith(("http://", "https://")):
                return desk.open_url(arg)
            return desk.open_application(arg)
        if "take screenshot" in t or t == "screenshot":
            return desk.screenshot()
        return None

    def _direct_chat(self, user_text: str, memories: str, chat_history: list[BaseMessage]) -> str:
        """Single LLM call — fast path for greetings and Q&A without tools."""
        instant = self._instant_smalltalk(user_text)
        if instant:
            return instant
        sys_content = DIRECT_CHAT_SYSTEM.format(memories=memories)
        # Keep this path short for responsiveness.
        short_history = chat_history[-6:]
        full: list[BaseMessage] = [
            SystemMessage(content=sys_content),
            *short_history,
            HumanMessage(content=user_text),
        ]
        out = self.llm.invoke(full)
        content = getattr(out, "content", None) or str(out)
        return (content or "").strip()

    def run_turn(self, session_id: str, user_text: str) -> dict[str, Any]:
        """
        Execute one agent turn: builds prompt context, invokes executor, logs task trail.
        Returns structured payload for API/UI consumption.
        """
        memories = self.memory.memories_block()
        chat_history = self._messages_from_history(session_id)

        tool_trace: list[dict[str, Any]] = []

        try:
            fast = self._execute_fast_command(user_text)
            if fast is not None:
                tool_trace = [{"tool": "fast_path", "tool_input": user_text, "observation": fast}]
                self.memory.persist_exchange(session_id, user_text, fast)
                self.db.log_task(user_text, fast, status="ok", tool_trace=tool_trace)
                return {"ok": True, "reply": fast, "tool_trace": tool_trace, "error": None}

            if not self._looks_like_automation_request(user_text):
                output = self._direct_chat(user_text, memories, chat_history)
                self.memory.persist_exchange(session_id, user_text, output or "(empty)")
                self.db.log_task(user_text, output, status="ok", tool_trace=[])
                return {
                    "ok": True,
                    "reply": output,
                    "tool_trace": [],
                    "error": None,
                }

            result = self.executor.invoke(
                {
                    "input": user_text,
                    "chat_history": chat_history,
                    "memories": memories,
                }
            )
            output = (result.get("output") or "").strip()
            raw_steps = result.get("intermediate_steps") or []
            for step in raw_steps:
                if not isinstance(step, (list, tuple)) or len(step) != 2:
                    continue
                action, observation = step
                tool_trace.append(
                    {
                        "tool": getattr(action, "tool", None),
                        "tool_input": getattr(action, "tool_input", None),
                        "observation": str(observation),
                    }
                )

            self.memory.persist_exchange(session_id, user_text, output or "(empty)")
            self.db.log_task(user_text, output, status="ok", tool_trace=tool_trace)

            return {
                "ok": True,
                "reply": output,
                "tool_trace": tool_trace,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 — agent boundary
            err = f"{exc}\n{traceback.format_exc(limit=3)}"
            self.db.log_task(user_text, None, status="error", tool_trace=tool_trace + [{"error": err}])
            user_msg = str(exc)
            low = user_msg.lower()
            if "not found" in low and ("404" in low or "status code" in low):
                m = self.settings.ollama_model
                user_msg = (
                    f"Ollama does not have model '{m}' installed. "
                    f"In a terminal run: ollama pull {m} — then retry. "
                    "Or set OLLAMA_MODEL to a name from `ollama list`."
                )
            elif "gib" in low or "system memory" in low or "requires more" in low:
                user_msg += (
                    " — Use a smaller model: set OLLAMA_MODEL=llama3.2:1b (or tinyllama) in .env, "
                    "run `ollama pull llama3.2:1b`, restart the API, and close other heavy apps. "
                    "Optionally set WHISPER_MODEL=tiny to reduce load from speech-to-text."
                )
            return {"ok": False, "reply": "", "tool_trace": tool_trace, "error": user_msg}
