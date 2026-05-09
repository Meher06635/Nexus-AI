"""
Registers callable tools exposed to the LangChain agent.
Each tool wraps desktop or Playwright automation with clear docstrings (used as LLM hints).
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from backend.automation.browser import (
    PlaywrightController,
    open_gmail,
    open_whatsapp_web,
    open_youtube,
    whatsapp_send_message,
    youtube_search,
)
from backend.automation.desktop import DesktopAutomation
from backend.config import Settings
from backend.memory.memory_service import MemoryService


class OpenApplicationArgs(BaseModel):
    name: str = Field(description="Application display name or executable, e.g. 'notepad', 'chrome'")


class OpenWebsiteArgs(BaseModel):
    url: str = Field(description="Full https URL to open")


class GoogleSearchArgs(BaseModel):
    query: str = Field(description="Search keywords")


class CreateNoteArgs(BaseModel):
    title: str = Field(description="Short note title / filename stem")
    body: str = Field(description="Note body text")


class OpenPathArgs(BaseModel):
    path: str = Field(description="Absolute or user-relative path to folder or file")


class TypeTextArgs(BaseModel):
    text: str = Field(description="Unicode text to type into the currently focused window")


class WhatsAppSendArgs(BaseModel):
    contact_query: str = Field(description="Contact name as shown in WhatsApp search")
    message: str = Field(description="Message body to send")


class YouTubeSearchArgs(BaseModel):
    query: str = Field(description="Video search query")


class RememberArgs(BaseModel):
    content: str = Field(description="Fact or snippet the user wants stored long-term")


@dataclass
class ToolRegistry:
    settings: Settings
    desktop: DesktopAutomation
    browser: PlaywrightController
    memory: MemoryService


def build_nexus_tools(reg: ToolRegistry) -> list[StructuredTool]:
    """Materialize StructuredTool list bound to live automation instances."""

    def open_application_tool(name: str) -> str:
        return reg.desktop.open_application(name)

    def open_website_tool(url: str) -> str:
        return reg.desktop.open_url(url)

    def google_search_tool(query: str) -> str:
        return reg.desktop.google_search(query)

    def create_note_tool(title: str, body: str) -> str:
        return reg.desktop.create_note(title, body, reg.settings.resolved_notes_dir())

    def open_path_tool(path: str) -> str:
        return reg.desktop.open_path(path)

    def type_text_tool(text: str) -> str:
        return reg.desktop.type_text(text)

    def screenshot_tool() -> str:
        return reg.desktop.screenshot()

    def whatsapp_open_tool() -> str:
        return open_whatsapp_web(reg.browser)

    def whatsapp_send_tool(contact_query: str, message: str) -> str:
        return whatsapp_send_message(reg.browser, contact_query, message)

    def youtube_open_tool() -> str:
        return open_youtube(reg.browser)

    def youtube_search_tool_fn(query: str) -> str:
        return youtube_search(reg.browser, query)

    def gmail_open_tool() -> str:
        return open_gmail(reg.browser)

    def remember_tool(content: str) -> str:
        ack = reg.memory.remember_phrase(content)
        return f"Stored memory id={ack['id']}: {ack['content']}"

    return [
        StructuredTool.from_function(
            name="open_application",
            description="Launch a desktop application by name (OS-dependent).",
            args_schema=OpenApplicationArgs,
            func=open_application_tool,
        ),
        StructuredTool.from_function(
            name="open_website",
            description="Open any URL in the default browser.",
            args_schema=OpenWebsiteArgs,
            func=open_website_tool,
        ),
        StructuredTool.from_function(
            name="google_search",
            description="Run a Google search in the default browser.",
            args_schema=GoogleSearchArgs,
            func=google_search_tool,
        ),
        StructuredTool.from_function(
            name="create_note",
            description="Create a local UTF-8 text note in the Nexus notes folder.",
            args_schema=CreateNoteArgs,
            func=create_note_tool,
        ),
        StructuredTool.from_function(
            name="open_folder_or_file",
            description="Open a folder or file with the OS default handler.",
            args_schema=OpenPathArgs,
            func=open_path_tool,
        ),
        StructuredTool.from_function(
            name="type_text",
            description="Type or paste text into whatever window currently has keyboard focus.",
            args_schema=TypeTextArgs,
            func=type_text_tool,
        ),
        StructuredTool.from_function(
            name="take_screenshot",
            description="Capture the full screen and save PNG under Nexus screenshots/.",
            func=screenshot_tool,
        ),
        StructuredTool.from_function(
            name="open_whatsapp_web",
            description="Open WhatsApp Web in Playwright; user must scan QR if not logged in.",
            func=whatsapp_open_tool,
        ),
        StructuredTool.from_function(
            name="send_whatsapp_message",
            description=(
                "Search a WhatsApp Web chat by contact name and send a message. "
                "Ensure WhatsApp Web is logged in."
            ),
            args_schema=WhatsAppSendArgs,
            func=whatsapp_send_tool,
        ),
        StructuredTool.from_function(
            name="open_youtube",
            description="Open YouTube homepage in the automation browser.",
            func=youtube_open_tool,
        ),
        StructuredTool.from_function(
            name="youtube_search",
            description="Open YouTube search results for a query.",
            args_schema=YouTubeSearchArgs,
            func=youtube_search_tool_fn,
        ),
        StructuredTool.from_function(
            name="open_gmail",
            description="Open Gmail in the automation browser.",
            func=gmail_open_tool,
        ),
        StructuredTool.from_function(
            name="remember_this",
            description='Persist a fact when the user explicitly asks to "remember" something.',
            args_schema=RememberArgs,
            func=remember_tool,
        ),
    ]
