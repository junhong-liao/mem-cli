from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    message_chunk_to_message,
)
from pydantic import ValidationError

from .render import (
    RendererConfig,
    clear_line,
    clear_previous_line,
    pretty_print_assistant,
    print_user_block,
    start_thinking_indicator,
)
from .tools import ToolRegistry
from .tracing import build_langsmith_run_config, maybe_trace_request_payload
from .providers.base import ProviderAdapter


@dataclass
class RuntimeContext:
    adapter: ProviderAdapter
    history: List[BaseMessage] = field(default_factory=list)
    state: Any = None
    trace_requests: bool = False


CommandHandler = Callable[[RuntimeContext, str], bool]
PromptBuilder = Callable[[RuntimeContext], str]
ToolPostprocessor = Callable[[str, Any, Dict[str, Any], RuntimeContext], Any]


@dataclass
class RuntimeOptions:
    prompt_builder: PromptBuilder
    tool_registry: ToolRegistry
    command_handlers: Dict[str, CommandHandler] = field(default_factory=dict)
    on_start: Optional[Callable[[RuntimeContext], None]] = None
    on_reset: Optional[Callable[[RuntimeContext], Optional[str]]] = None
    on_before_turn: Optional[Callable[[RuntimeContext, str], None]] = None
    on_after_turn: Optional[Callable[[RuntimeContext, List[BaseMessage]], None]] = None
    tool_postprocessor: Optional[ToolPostprocessor] = None
    trace_requests: bool = False
    renderer: RendererConfig = field(default_factory=RendererConfig)


def stream_model_turn(
    bound_model: Any,
    messages: List[BaseMessage],
    run_config: Optional[Dict[str, Any]] = None,
) -> AIMessage:
    stop_event = __import__("threading").Event()
    indicator_thread = start_thinking_indicator(stop_event)
    chunk_accumulator: Optional[AIMessageChunk] = None

    if run_config:
        stream_iter = bound_model.stream(messages, config=run_config)
    else:
        stream_iter = bound_model.stream(messages)
    for chunk in stream_iter:
        if chunk_accumulator is None:
            chunk_accumulator = chunk
        else:
            chunk_accumulator += chunk

    stop_event.set()
    indicator_thread.join(timeout=1)
    clear_line()
    if chunk_accumulator is None:
        return AIMessage(content="")
    return message_chunk_to_message(chunk_accumulator)  # type: ignore[return-value]


def run_agent_turn(
    context: RuntimeContext,
    system_prompt: str,
    tool_registry: ToolRegistry,
    tool_postprocessor: Optional[ToolPostprocessor] = None,
) -> List[BaseMessage]:
    tools_by_name = tool_registry.by_name()
    model = context.adapter.build_model()
    maybe_trace_request_payload(model, context.trace_requests)
    bound_model = context.adapter.bind_tools(model, tool_registry.all())
    messages: List[BaseMessage] = list(context.history)
    system_message = SystemMessage(content=system_prompt)
    run_config = build_langsmith_run_config(context.adapter)

    for _attempt in range(5):
        start_ms = time.perf_counter_ns()
        ai_message = stream_model_turn(
            bound_model,
            [system_message, *messages],
            run_config,
        )
        if context.trace_requests:
            elapsed_ms = (time.perf_counter_ns() - start_ms) / 1_000_000
            print(f"[trace] model stream {elapsed_ms:.0f} ms")
        messages.append(ai_message)
        tool_calls = ai_message.tool_calls or []
        if tool_calls:
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                tool = tools_by_name.get(tool_name)
                if tool is None:
                    tool_output: Any = f"Unknown tool: {tool_name}"
                else:
                    try:
                        tool_output = tool.invoke(tool_call.get("args", {}))
                    except ValidationError as exc:
                        tool_output = f"Tool error: {exc}"
                    except Exception as exc:  # noqa: BLE001
                        tool_output = f"Tool error: {exc}"
                if tool_postprocessor:
                    tool_output = tool_postprocessor(
                        tool_name or "",
                        tool_output,
                        tool_call,
                        context,
                    )
                messages.append(
                    ToolMessage(
                        content=str(tool_output),
                        tool_call_id=tool_call.get("id", ""),
                        name=tool_name or "tool",
                    )
                )
            continue
        break
    return messages


def _read_paste_input() -> Optional[str]:
    print("Paste mode: enter lines, then a single '.' on its own line to send.")
    lines: List[str] = []
    while True:
        line = input()
        if line.strip() == ".":
            break
        lines.append(line)
    content = "\n".join(lines).strip()
    if not content:
        print("Paste mode cancelled (empty input).")
        return None
    return content


def run_cli(adapter: ProviderAdapter, options: RuntimeOptions, state: Any = None) -> None:
    context = RuntimeContext(
        adapter=adapter,
        history=[],
        state=state,
        trace_requests=options.trace_requests,
    )
    if options.on_start:
        options.on_start(context)

    while True:
        user_text = input("\n> ").strip()
        if not user_text:
            continue
        clear_previous_line()
        normalized = user_text.strip().lower()
        cmd = normalized.split()[0].rstrip("].,;:") if normalized.startswith("/") else ""

        if cmd == "/paste":
            pasted = _read_paste_input()
            if pasted is None:
                continue
            user_text = pasted
            normalized = user_text.strip().lower()
            cmd = normalized.split()[0].rstrip("].,;:") if normalized.startswith("/") else ""

        if cmd in {"/exit", "/quit"}:
            print("Bye.")
            break

        if cmd == "/reset":
            if options.on_reset:
                message = options.on_reset(context)
            else:
                context.history = []
                message = "History cleared."
            print(message)
            continue

        handler = options.command_handlers.get(cmd) if cmd else None
        if handler and handler(context, user_text):
            continue

        print_user_block(user_text, options.renderer)
        print()
        context.history.append(HumanMessage(content=user_text))
        prior_count = len(context.history)
        start_ms = time.perf_counter_ns()

        if options.on_before_turn:
            options.on_before_turn(context, user_text)

        system_prompt = options.prompt_builder(context)
        updated_history = run_agent_turn(
            context=context,
            system_prompt=system_prompt,
            tool_registry=options.tool_registry,
            tool_postprocessor=options.tool_postprocessor,
        )
        new_messages = updated_history[prior_count:]
        context.history = updated_history
        pretty_print_assistant(new_messages, options.renderer)

        if options.on_after_turn:
            options.on_after_turn(context, new_messages)

        elapsed_ms = (time.perf_counter_ns() - start_ms) / 1_000_000
        print(f"\nTime: {elapsed_ms:.0f} ms")
