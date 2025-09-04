# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
from typing import Any, Literal, Optional, Union

import msgspec

from marimo._ai._types import ChatMessage


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
    variables: list[Union[VariableContext, str]] = msgspec.field(
        default_factory=list
    )
    plain_text: str = ""


Language = Literal["python", "markdown", "sql"]


class AiCompletionRequest(msgspec.Struct, rename="camel"):
    prompt: str
    include_other_code: str
    code: str
    selected_text: Optional[str] = None
    context: Optional[AiCompletionContext] = None
    language: Language = "python"


class AiInlineCompletionRequest(msgspec.Struct, rename="camel"):
    prefix: str
    suffix: str
    language: Language = "python"


@dataclasses.dataclass
class ChatRequest:
    context: AiCompletionContext
    include_other_code: str
    messages: list[ChatMessage]
    model: Optional[str] = None
    variables: Optional[list[Union[VariableContext, str]]] = None
