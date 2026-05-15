# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import uuid
from functools import lru_cache
from typing import TYPE_CHECKING, Any, get_args

from marimo import _loggers
from marimo._messaging.msgspec_encoder import asdict
from marimo._server.ai.tools.types import ToolDefinition
from marimo._server.models.completion import UIMessage as ServerUIMessage

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic_ai import FunctionToolset
    from pydantic_ai.ui.vercel_ai.request_types import UIMessage, UIMessagePart


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def form_toolsets(
    tools: list[ToolDefinition],
    tool_invoker: Callable[[str, dict[str, Any]], Any],
) -> tuple[FunctionToolset, bool]:
    """
    Because we have a list of tool definitions and call them in a separate event loop,
    we create a closure to invoke the tool (backend) or raise a CallDeferred (frontend).
    Ref: https://ai.pydantic.dev/toolsets/#function-toolset

    Returns a tuple of the toolset and whether deferred tool requests are needed.
    """
    from pydantic_ai import CallDeferred, FunctionToolset

    toolset = FunctionToolset()
    deferred_tool_requests = False

    for tool in tools:
        if tool.source == "frontend":
            deferred_tool_requests = True

            async def tool_fn(
                _tool_name: str = tool.name, **kwargs: Any
            ) -> Any:
                raise CallDeferred(
                    metadata={
                        "source": "frontend",
                        "tool_name": _tool_name,
                        "kwargs": kwargs,
                    }
                )
        else:

            async def tool_fn(
                _tool_name: str = tool.name, **kwargs: Any
            ) -> Any:
                result = await tool_invoker(_tool_name, kwargs)
                # Convert to JSON-serializable object
                return asdict(result)

        tool_fn.__name__ = tool.name
        toolset.add_function(
            tool_fn, name=tool.name, description=tool.description
        )
    return toolset, deferred_tool_requests


def convert_to_pydantic_messages(
    messages: list[ServerUIMessage],
    part_processor: Callable[[UIMessagePart], UIMessagePart] | None = None,
) -> list[UIMessage]:
    """
    The frontend SDK tends to generate messages with a messageId eventhough it's not valid.
    Remove them to prevent validation errors.
    If a part processor is provided, it will be applied to the parts of the message.
    """
    from pydantic_ai.ui.vercel_ai.request_types import UIMessage

    def safe_part_processor(
        part: UIMessagePart,
        part_processor: Callable[[UIMessagePart], UIMessagePart],
    ) -> UIMessagePart:
        try:
            return part_processor(part)
        except Exception as e:
            LOGGER.error(f"Error processing part {part}: {e}")
            return part

    pydantic_messages: list[UIMessage] = []
    for message in messages:
        message_id = (
            message.get("messageId")
            or message.get("id")
            or generate_id("message")
        )
        role = message.get("role", "assistant")
        parts = [_sanitize_part(part) for part in message.get("parts", [])]
        metadata = message.get("metadata")

        ui_message = UIMessage(
            id=message_id, role=role, parts=parts, metadata=metadata
        )

        # Process parts after casting so the processor will work on typed parts
        if ui_message.parts and part_processor:
            new_parts = [
                safe_part_processor(part, part_processor)
                for part in ui_message.parts
            ]
            ui_message.parts = new_parts
        pydantic_messages.append(ui_message)

    return pydantic_messages


def create_simple_prompt(text: str) -> UIMessage:
    from pydantic_ai.ui.vercel_ai.request_types import TextUIPart, UIMessage

    parts: list[UIMessagePart] = [TextUIPart(text=text)] if text else []
    return UIMessage(id=generate_id("message"), role="user", parts=parts)


@lru_cache(maxsize=1)
def _tool_part_allowed_fields() -> dict[tuple[bool, str], frozenset[str]]:
    """Build a lookup of allowed camelCase keys per (is_dynamic_tool, state).

    Reflects pydantic-ai's own tool-part models so we don't duplicate the
    schema and auto-track field changes on upgrade.
    """
    from pydantic_ai.ui.vercel_ai.request_types import (
        DynamicToolUIPart,
        ToolUIPart,
    )

    result: dict[tuple[bool, str], frozenset[str]] = {}
    for model in (*get_args(ToolUIPart), *get_args(DynamicToolUIPart)):
        state = model.model_fields["state"].default
        is_dynamic = model.model_fields["type"].default == "dynamic-tool"
        aliases = frozenset(
            (info.alias or name) for name, info in model.model_fields.items()
        )
        result[(is_dynamic, state)] = aliases
    return result


def _sanitize_part(part: Any) -> Any:
    """Drop fields the AI SDK spread onto a tool part during a state transition.

    The AI SDK transitions tool parts via `{ ...part, state, approval }`, which
    can leak stale fields (e.g. `output`, `errorText`) from a prior state.
    Pydantic-ai's `extra='forbid'` schema rightly rejects those leaks. We
    mirror the AI SDK's own `z.never().optional()` intent by keeping only the
    fields declared on the matching pydantic-ai model.

    Non-tool parts (text, reasoning, source, file, step-start, data-*) pass
    through unchanged.
    """
    if not isinstance(part, dict):
        return part
    part_type = part.get("type")
    state = part.get("state")
    if not isinstance(part_type, str) or not isinstance(state, str):
        return part

    is_dynamic = part_type == "dynamic-tool"
    is_static_tool = part_type.startswith("tool-")
    if not (is_dynamic or is_static_tool):
        return part

    allowed = _tool_part_allowed_fields().get((is_dynamic, state))
    if not allowed:
        return part
    return {k: v for k, v in part.items() if k in allowed}
