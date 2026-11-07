# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, get_args

from marimo import _loggers
from marimo._messaging.msgspec_encoder import asdict
from marimo._server.ai.tools.types import ToolDefinition, ToolSource
from marimo._server.models.completion import UIMessage as ServerUIMessage
from marimo._utils.data_uri import from_data_uri

if TYPE_CHECKING:
    from pydantic_ai import ModelProfile

LOGGER = _loggers.marimo_logger()
_BINARY_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0e-\x1f]")


def profile_get(profile: ModelProfile, key: str, default: Any) -> Any:
    """Read a field from a pydantic-ai `ModelProfile`.

    pydantic-ai v1 exposes profiles as dataclasses (attribute access); v2
    exposes them as TypedDicts (dict access).
    """
    if isinstance(profile, dict):
        return profile.get(key, default)
    return getattr(profile, key, default)


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pydantic_ai import FunctionToolset
    from pydantic_ai.ui.vercel_ai.request_types import UIMessage, UIMessagePart


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


# Wire `type` of the @-context data part emitted by the frontend
MARIMO_CONTEXT_PART_TYPE = "data-marimo-context"


def format_inline_context(plain_text: str) -> str:
    """Render @-context as a user-message text block."""
    return f"<context>\n{plain_text.strip()}\n</context>"


@dataclass(frozen=True)
class _ToolFunction:
    name: str
    source: ToolSource
    tool_invoker: Callable[[str, dict[str, Any]], Awaitable[Any]]

    async def __call__(self, **kwargs: Any) -> Any:
        if self.source == "frontend":
            from pydantic_ai import CallDeferred

            raise CallDeferred(
                metadata={
                    "source": "frontend",
                    "tool_name": self.name,
                    "kwargs": kwargs,
                }
            )

        result = await self.tool_invoker(self.name, kwargs)
        return asdict(result)


def form_toolsets(
    tools: list[ToolDefinition],
    tool_invoker: Callable[[str, dict[str, Any]], Awaitable[Any]],
) -> tuple[FunctionToolset, bool]:
    from pydantic_ai import FunctionToolset, Tool

    toolset = FunctionToolset()
    for tool in tools:
        toolset.add_tool(
            Tool.from_schema(
                function=_ToolFunction(
                    name=tool.name,
                    source=tool.source,
                    tool_invoker=tool_invoker,
                ),
                name=tool.name,
                description=tool.description,
                json_schema=tool.parameters,
            )
        )

    return toolset, any(tool.source == "frontend" for tool in tools)


def convert_to_pydantic_messages(
    messages: list[ServerUIMessage],
) -> list[UIMessage]:
    """
    The frontend SDK tends to generate messages with a messageId even though it's not valid.
    Remove them to prevent validation errors.
    """
    from pydantic_ai.ui.vercel_ai.request_types import UIMessage

    pydantic_messages: list[UIMessage] = []
    for message in messages:
        message_id = (
            message.get("messageId")
            or message.get("id")
            or generate_id("message")
        )
        role = message.get("role", "assistant")
        parts = _prepare_parts(message.get("parts", []))
        metadata = message.get("metadata")

        ui_message = UIMessage(
            id=message_id, role=role, parts=parts, metadata=metadata
        )

        ui_message.parts = [
            repair_incomplete_tool_call(part) for part in ui_message.parts
        ]

        if role == "user":
            ui_message.parts = [
                _inline_text_file(part) for part in ui_message.parts
            ]
        pydantic_messages.append(ui_message)

    return pydantic_messages


def _inline_text_file(part: UIMessagePart) -> UIMessagePart:
    from pydantic_ai.ui.vercel_ai.request_types import FileUIPart, TextUIPart

    # Inline local text files so text-only models can read them too.
    if not isinstance(part, FileUIPart) or not part.url.startswith("data:"):
        return part
    try:
        text = _decode_text_attachment(part.media_type, part.url)
    except Exception as error:
        LOGGER.error(
            "Error processing %s: %s",
            type(part).__name__,
            type(error).__name__,
        )
        return part
    if text is None:
        return part
    return TextUIPart(
        type="text",
        text=text,
        provider_metadata=part.provider_metadata,
    )


def _decode_text_attachment(media_type: str, url: str) -> str | None:
    media_type = media_type.split(";", 1)[0].strip().lower()
    if (
        media_type.startswith(("image/", "audio/", "video/"))
        or media_type == "application/pdf"
    ):
        return None
    is_text_mime_type = (
        media_type.startswith("text/")
        or media_type.endswith(("+json", "+xml"))
        or media_type
        in {
            "application/json",
            "application/xml",
            "application/toml",
            "application/yaml",
            "application/x-yaml",
        }
    )
    try:
        _, data = from_data_uri(url, validate=not is_text_mime_type)
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin1") if is_text_mime_type else None
    except ValueError:
        if is_text_mime_type:
            raise
        return None
    if not is_text_mime_type and _BINARY_CONTROL_CHARACTERS.search(text):
        return None
    return text


def _prepare_parts(raw_parts: list[Any]) -> list[Any]:
    """Normalize a message's raw parts for pydantic-ai validation."""
    parts: list[Any] = []
    for part in raw_parts:
        lowered = _expand_marimo_context_part(part)
        if lowered is None:
            continue  # empty context part, drop it
        parts.append(sanitize_part(lowered))
    return parts


def _expand_marimo_context_part(part: Any) -> Any:
    """Resolve a `data-marimo-context` part into a text part.

    The @-context is shipped inside the user message as a data part because
    pydantic-ai's VercelAIAdapter drops DataUIPart entirely.

    Returns the part unchanged when it isn't a context part, a text part when
    it carries non-empty context, or `None` to drop empty context parts.
    """
    if (
        not isinstance(part, dict)
        or part.get("type") != MARIMO_CONTEXT_PART_TYPE
    ):
        return part
    data = part.get("data")
    if not isinstance(data, dict):
        return None
    plain_text = (data.get("plainText") or "").strip()
    if not plain_text:
        return None
    return {"type": "text", "text": format_inline_context(plain_text)}


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


_INTERRUPTED_TOOL_MESSAGE = "Tool call was interrupted and did not complete."


def repair_incomplete_tool_call(part: UIMessagePart) -> UIMessagePart:
    """Give an interrupted tool call a terminal `output-error` result.

    A tool part left in `input-streaming`/`input-available` is a tool call with no result.
    Some providers like Anthropic expect a tool result, so stopping a stream mid-call would break the conversation.
    We rewrite the part to the matching `output-error` model so the conversion to pydantic-ai produces a tool result.

    A deferred call (approval-requested/approval-responded) is left alone.
    """
    from pydantic_ai.ui.vercel_ai.request_types import (
        DynamicToolInputAvailablePart,
        DynamicToolInputStreamingPart,
        DynamicToolOutputErrorPart,
        ToolInputAvailablePart,
        ToolInputStreamingPart,
        ToolOutputErrorPart,
    )

    if isinstance(part, (ToolInputStreamingPart, ToolInputAvailablePart)):
        return ToolOutputErrorPart(
            type=part.type,
            tool_call_id=part.tool_call_id,
            title=part.title,
            input=part.input,
            error_text=_INTERRUPTED_TOOL_MESSAGE,
            provider_executed=part.provider_executed,
            call_provider_metadata=part.call_provider_metadata,
            approval=part.approval,
        )
    if isinstance(
        part,
        (DynamicToolInputStreamingPart, DynamicToolInputAvailablePart),
    ):
        return DynamicToolOutputErrorPart(
            tool_name=part.tool_name,
            tool_call_id=part.tool_call_id,
            title=part.title,
            input=part.input,
            error_text=_INTERRUPTED_TOOL_MESSAGE,
            provider_executed=part.provider_executed,
            call_provider_metadata=part.call_provider_metadata,
            approval=part.approval,
        )
    return part


def sanitize_part(part: Any) -> Any:
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
