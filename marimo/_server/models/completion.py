# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional

from marimo._ai.types import ChatMessage


@dataclass
class SchemaColumn:
    name: str
    type: str


@dataclass
class SchemaTable:
    name: str
    columns: List[SchemaColumn]


@dataclass
class AiCompletionContext:
    schema: List[SchemaTable] = field(default_factory=list)


Language = Literal["python", "markdown", "sql"]


@dataclass
class AiCompletionRequest:
    prompt: str
    include_other_code: str
    code: str
    context: Optional[AiCompletionContext] = None
    language: Language = "python"


@dataclass
class ChatRequest:
    messages: List[ChatMessage]
    model: Optional[str] = None
    variables: Optional[List[str]] = None
    context: Optional[AiCompletionContext] = None
    include_other_code: str = ""
