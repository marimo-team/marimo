# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Literal

import msgspec

from marimo._server.ai.tools.types import ToolDefinition


class SchemaColumn(msgspec.Struct, rename="camel"):
    name: str
    type: str
    sample_values: list[Any]


class SchemaTable(msgspec.Struct, rename="camel"):
    name: str
    columns: list[SchemaColumn]


class VariableContext(msgspec.Struct, rename="camel"):
    name: str
    value_type: str
    preview_value: Any


class AiCompletionContext(msgspec.Struct, rename="camel"):
    schema: list[SchemaTable] = msgspec.field(default_factory=list)
    variables: list[VariableContext | str] = msgspec.field(
        default_factory=list
    )
    plain_text: str = ""


Language = Literal["python", "markdown", "sql"]


UIMessage = dict[str, Any]


class AiCompletionRequest(msgspec.Struct, rename="camel"):
    """
    UIMessages are expected to be AI SDK messages.
    See pydantic_ai.ui.vercel_ai.request_types.UIMessage or Vercel AI SDK documentation.
    """

    prompt: str
    include_other_code: str
    code: str
    ui_messages: list[UIMessage] = []
    selected_text: str | None = None
    context: AiCompletionContext | None = None
    language: Language = "python"


class AiInlineCompletionRequest(msgspec.Struct, rename="camel"):
    prefix: str
    suffix: str
    language: Language = "python"


class ChatRequest(msgspec.Struct, rename="camel"):
    """
    UIMessages are expected to be AI SDK messages.
    See pydantic_ai.ui.vercel_ai.request_types.UIMessage or Vercel AI SDK documentation.
    """

    context: AiCompletionContext
    include_other_code: str
    ui_messages: list[UIMessage]
    tools: list[ToolDefinition] | None = None
    model: str | None = None
    variables: list[VariableContext | str] | None = None
