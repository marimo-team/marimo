# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import dataclasses
import mimetypes
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Optional,
    TypedDict,
    Union,
    cast,
)

import msgspec

from marimo import _loggers
from marimo._utils.parse_dataclass import parse_raw

LOGGER = _loggers.marimo_logger()


class ChatAttachmentDict(TypedDict):
    url: str
    content_type: Optional[str]
    name: Optional[str]


class TextPartDict(TypedDict):
    type: Literal["text"]
    text: str


class FilePartDict(TypedDict):
    type: Literal["file"]
    media_type: str
    filename: Optional[str]
    url: str


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


ChatPartDict = Union[
    TextPartDict, ReasoningPartDict, ToolInvocationPartDict, FilePartDict
]


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
    text: str
    details: Optional[list[ReasoningDetails]] = None


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
    output: Optional[Any] = None

    @property
    def tool_name(self) -> str:
        return self.type.split("-", 1)[1]


@dataclass
class FilePart:
    """Represents a FileUIPart from the AI SDK."""

    type: Literal["file"]
    media_type: str
    url: str
    filename: Optional[str] = None


@dataclass
class ReasoningData:
    signature: str


@dataclass
class DataReasoningPart:
    type: Literal["data-reasoning-signature"]
    data: ReasoningData


if TYPE_CHECKING:
    ChatPart = Union[
        TextPart,
        ReasoningPart,
        ToolInvocationPart,
        FilePart,
        DataReasoningPart,
    ]
else:
    ChatPart = dict[str, Any]

PART_TYPES = [
    TextPart,
    ReasoningPart,
    ToolInvocationPart,
    FilePart,
    DataReasoningPart,
]


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

    def __post_init__(self) -> None:
        # Hack: msgspec only supports discriminated unions. This is a hack to just
        # iterate through possible part variants and decode until one works.
        if self.parts:
            parts = []
            for part in self.parts:
                if converted := self._convert_part(part):
                    parts.append(converted)
            self.parts = parts

    def _convert_part(self, part: Any) -> Optional[ChatPart]:
        PartType = None
        for PartType in PART_TYPES:
            try:
                if dataclasses.is_dataclass(part):
                    return cast(ChatPart, part)
                return parse_raw(part, cls=PartType, allow_unknown_keys=True)
            except Exception:
                continue

        LOGGER.error(f"Could not decode part as {PartType}, for part {part}")
        return None


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
