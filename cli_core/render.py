from __future__ import annotations

import json
import sys
import textwrap
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage


@dataclass
class RendererConfig:
    assistant_label: str = "Assistant"
    user_label: str = "You"
    tool_label: str = "Tool Output"
    width: int = 72
    indent: str = "  "


def render_header(label: str) -> None:
    line = f"---- {label} ----"
    print(f"\n{line}")


def wrap_paragraphs(text: str, width: int, indent: str) -> str:
    paragraphs = [p.strip() for p in text.split("\n")]
    wrapped: List[str] = []
    for paragraph in paragraphs:
        if not paragraph:
            wrapped.append("")
            continue
        wrapped.append(
            textwrap.fill(
                paragraph,
                width=width,
                initial_indent=indent,
                subsequent_indent=indent,
            )
        )
    return "\n".join(wrapped)


def print_bordered_block(text: str) -> None:
    lines = text.splitlines() or [""]
    width = max(len(line) for line in lines)
    border = "+" + "-" * (width + 2) + "+"
    print(border)
    for line in lines:
        print(f"| {line.ljust(width)} |")
    print(border)


def format_tool_payload(payload: str) -> str:
    stripped = payload.strip()
    if not stripped:
        return ""
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped
    return json.dumps(parsed, indent=2)


def message_to_dict(message: BaseMessage) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "type": message.type,
        "content": message.content,
    }
    if isinstance(message, AIMessage) and message.tool_calls:
        data["tool_calls"] = message.tool_calls
    if isinstance(message, ToolMessage):
        data["tool_name"] = message.name
    return data


def pretty_print_assistant(messages: List[BaseMessage], config: RendererConfig) -> None:
    tool_payloads: List[str] = []
    text_chunks: List[str] = []
    for msg in messages:
        data = message_to_dict(msg)
        if data.get("type") == "ai":
            content = data.get("content")
            if isinstance(content, str) and content.strip():
                text_chunks.append(content.strip())
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "text" and part.get("text"):
                        text_chunks.append(str(part["text"]).strip())
        if data.get("type") == "tool":
            tool_payloads.append(str(data.get("content", "")).strip())

    if text_chunks:
        render_header(config.assistant_label)
        combined = "\n\n".join(chunk.strip() for chunk in text_chunks if chunk.strip())
        wrapped = wrap_paragraphs(combined, width=config.width, indent=config.indent)
        if wrapped:
            print(wrapped)
    if tool_payloads:
        print(f"\n  {config.tool_label}:")
        for payload in tool_payloads:
            formatted = format_tool_payload(payload)
            if formatted:
                print_bordered_block(formatted)


def print_user_block(text: str, config: RendererConfig) -> None:
    render_header(config.user_label)
    wrapped = wrap_paragraphs(text, width=config.width, indent=config.indent)
    if wrapped:
        print(wrapped)


def start_thinking_indicator(stop_event: threading.Event) -> threading.Thread:
    def thinking_indicator() -> None:
        dots = 0
        while not stop_event.is_set():
            dots = (dots % 3) + 1
            sys.stdout.write("\rThinking" + "." * dots + "   ")
            sys.stdout.flush()
            time.sleep(0.35)

    indicator_thread = threading.Thread(target=thinking_indicator, daemon=True)
    indicator_thread.start()
    return indicator_thread


def clear_line() -> None:
    sys.stdout.write("\r" + " " * 40 + "\r")
    sys.stdout.flush()


def clear_previous_line() -> None:
    # Removes the last input line so user text only appears in the rendered block.
    sys.stdout.write("\x1b[1A\r\x1b[2K")
    sys.stdout.flush()
