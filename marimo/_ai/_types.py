# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import mimetypes
from dataclasses import dataclass
from typing import Any, Literal, Optional, TypedDict, Union


class ChatAttachmentDict(TypedDict):
    url: str
    content_type: Optional[str]
    name: Optional[str]


class ChatMessageDict(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str
    attachments: Optional[list[ChatAttachmentDict]]


class ChatModelConfigDict(TypedDict, total=False):
    max_tokens: Optional[int]
    temperature: Optional[float]
    top_p: Optional[float]
    top_k: Optional[int]
    frequency_penalty: Optional[float]
    presence_penalty: Optional[float]


# NOTE: The following classes are public API.
# Any changes must be backwards compatible.


@dataclass
class ChatAttachment:
    # The URL of the attachment. It can either be a URL to a hosted file or a
    # [Data URL](https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/Data_URLs).
    url: str

    # The name of the attachment, usually the file name.
    name: str = "attachment"

    # A string indicating the [media type](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type).
    # By default, it's extracted from the pathname's extension.
    content_type: Optional[str] = None

    def __post_init__(self) -> None:
        if self.content_type is None:
            self.content_type = mimetypes.guess_type(self.url)[0]


# AI SDK part type definitions (based on actual frontend structure)
@dataclass
class TextPart:
    """Represents a text content part."""

    type: Literal["text"]
    text: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextPart:
        """Create TextPart from dictionary data."""
        return cls(**data)


@dataclass
class ReasoningPart:
    """Represents a reasoning content part."""

    type: Literal["reasoning"]
    reasoning: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReasoningPart:
        """Create ReasoningPart from dictionary data."""
        return cls(**data)


@dataclass
class ToolInvocationCall:
    """Represents a tool invocation call part from the AI SDK."""

    state: Literal["call", "partial-call"]
    toolCallId: str
    toolName: str
    args: Optional[Any] = None
    step: Optional[Any] = None


@dataclass
class ToolInvocationResult:
    """Represents a tool invocation result part from the AI SDK."""

    state: Literal["call", "partial-call", "result"]
    result: Any
    toolCallId: str
    toolName: str
    args: Optional[Any] = None
    step: Optional[Any] = None


@dataclass
class ToolInvocationPart:
    """Represents a tool invocation part from the AI SDK."""

    type: Literal["tool-invocation"]
    toolInvocation: Union[ToolInvocationCall, ToolInvocationResult]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolInvocationPart:
        """Create ToolInvocationPart from dictionary data."""
        tool_invocation_data = data["toolInvocation"]

        tool_invocation: Union[ToolInvocationCall, ToolInvocationResult]
        if tool_invocation_data["state"] == "result":
            tool_invocation = ToolInvocationResult(**tool_invocation_data)
        else:  # "call" or "partial-call"
            tool_invocation = ToolInvocationCall(**tool_invocation_data)

        return cls(type=data["type"], toolInvocation=tool_invocation)


@dataclass
class ChatMessage:
    """
    A message in a chat.
    """

    # The role of the message
    role: Literal["user", "assistant", "system"]

    # The content of the message
    content: object

    # Optional attachments to the message.
    attachments: Optional[list[ChatAttachment]] = None

    # Optional parts from AI SDK (see types above)
    parts: Optional[list[Any]] = None


@dataclass
class ChatModelConfig:
    # Maximum number of tokens.
    max_tokens: Optional[int] = None

    # Temperature for the model (randomness).
    temperature: Optional[float] = None

    # Restriction on the cumulative probability of prediction candidates.
    top_p: Optional[float] = None

    # Number of top prediction candidates to consider.
    top_k: Optional[int] = None

    # Penalty for tokens which appear frequently.
    frequency_penalty: Optional[float] = None

    # Penalty for tokens which already appeared at least once.
    presence_penalty: Optional[float] = None


class ChatModel(abc.ABC):
    @abc.abstractmethod
    def __call__(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> object:
        pass


# AI Tool Request/Response types for API endpoints
@dataclass
class InvokeAiToolRequest:
    """Request to invoke an AI tool."""

    tool_name: str
    arguments: dict[str, Any]


@dataclass
class InvokeAiToolResponse:
    """Response from invoking an AI tool."""

    tool_name: str
    result: Any
    error: Optional[str] = None


def create_part_from_dict(
    data: dict[str, Any],
) -> Union[TextPart, ReasoningPart, ToolInvocationPart]:
    """Factory function to create the appropriate part type from dictionary data."""
    part_type = data.get("type")

    if part_type == "text":
        return TextPart.from_dict(data)
    elif part_type == "reasoning":
        return ReasoningPart.from_dict(data)
    elif part_type == "tool-invocation":
        return ToolInvocationPart.from_dict(data)
    else:
        raise ValueError(f"Unknown part type: {part_type}")
