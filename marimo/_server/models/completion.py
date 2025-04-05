# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Union

from marimo._ai._types import ChatMessage


@dataclass
class SchemaColumn:
    name: str
    type: str
    sample_values: list[Any]


@dataclass
class SchemaTable:
    name: str
    columns: list[SchemaColumn]


@dataclass
class VariableContext:
    name: str
    value_type: str
    preview_value: Any


@dataclass
class AiCompletionContext:
    schema: list[SchemaTable] = field(default_factory=list)
    variables: list[Union[VariableContext, str]] = field(default_factory=list)


Language = Literal["python", "markdown", "sql"]


@dataclass
class AiCompletionRequest:
    prompt: str
    include_other_code: str
    code: str
    selected_text: Optional[str] = None
    context: Optional[AiCompletionContext] = None
    language: Language = "python"


@dataclass
class AiInlineCompletionRequest:
    prefix: str
    suffix: str
    language: Language = "python"


@dataclass
class ChatRequest:
    context: AiCompletionContext
    include_other_code: str
    messages: list[ChatMessage]
    model: Optional[str] = None
    variables: Optional[list[Union[VariableContext, str]]] = None
