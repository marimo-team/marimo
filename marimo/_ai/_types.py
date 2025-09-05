# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import mimetypes
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Optional, TypedDict, Union

import msgspec


class ChatAttachmentDict(TypedDict):
    url: str
    content_type: Optional[str]
    name: Optional[str]


class TextPartDict(TypedDict):
    type: Literal["text"]
    text: str


class ReasoningPartDict(TypedDict):
    type: Literal["reasoning"]
    reasoning: str
    details: list[ReasoningDetailsDict]


class ReasoningDetailsDict(TypedDict):
    type: Literal["text"]
    text: str
    signature: Optional[str]


class ToolInvocationPartDict(TypedDict):
    type: str
    tool_call_id: str
    state: str
    input: dict[str, Any]
    output: Optional[Any]


ChatPartDict = Union[TextPartDict, ReasoningPartDict, ToolInvocationPartDict]


class ChatMessageDict(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str
    attachments: Optional[list[ChatAttachmentDict]]
    parts: Optional[list[ChatPartDict]]


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


@dataclass
class ReasoningPart:
    """Represents a reasoning content part."""

    type: Literal["reasoning"]
    reasoning: str
    details: list[ReasoningDetails]


@dataclass
class ReasoningDetails:
    type: Literal["text"]
    text: str
    signature: Optional[str] = None


@dataclass
class ToolInvocationPart:
    """Represents a tool invocation part from the AI SDK."""

    type: str  # Starts with "tool-"
    tool_call_id: str
    state: Union[str, Literal["output-available"]]
    input: dict[str, Any]
    output: Optional[Any]

    @property
    def tool_name(self) -> str:
        return self.type.split("-", 1)[1]


@dataclass
class FilePart:
    """Represents a FileUIPart from the AI SDK."""

    type: Literal["file"]
    media_type: str
    filename: Optional[str]
    url: str


if TYPE_CHECKING:
    ChatPart = Union[TextPart, ReasoningPart, ToolInvocationPart, FilePart]
else:
    ChatPart = dict[str, Any]


class ChatMessage(msgspec.Struct):
    """
    A message in a chat.
    """

    # The role of the message.
    role: Literal["user", "assistant", "system"]

    # The content of the message.
    content: Any

    # Optional attachments to the message.
    # TODO: Deprecate in favour of parts
    attachments: Optional[list[ChatAttachment]] = None

    # Parts from AI SDK. (see types above)
    # TODO: Make this required
    parts: Optional[list[ChatPart]] = None


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
