# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Callable

from marimo import _loggers
from marimo._messaging.msgspec_encoder import asdict
from marimo._server.ai.tools.types import ToolDefinition
from marimo._server.models.completion import UIMessage as ServerUIMessage

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
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
        parts = message.get("parts", [])
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
