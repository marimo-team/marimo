# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import abc
import mimetypes
from collections.abc import Iterator
from dataclasses import asdict, dataclass, is_dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypedDict, cast

import msgspec

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.parse_dataclass import parse_raw

LOGGER = _loggers.marimo_logger()


class ChatAttachmentDict(TypedDict):
    url: str
    content_type: str | None
    name: str | None


class TextPartDict(TypedDict):
    type: Literal["text"]
    text: str


class FilePartDict(TypedDict):
    type: Literal["file"]
    media_type: str
    filename: str | None
    url: str


class ReasoningPartDict(TypedDict):
    type: Literal["reasoning"]
    reasoning: str
    details: list[ReasoningDetailsDict]


class ReasoningDetailsDict(TypedDict):
    type: Literal["text"]
    text: str
    signature: str | None


class ToolInvocationPartDict(TypedDict):
    type: str
    tool_call_id: str
    state: str
    input: dict[str, Any]
    output: Any | None


ChatPartDict = (
    TextPartDict | ReasoningPartDict | ToolInvocationPartDict | FilePartDict
)


class ChatMessageDict(TypedDict):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str | None
    attachments: list[ChatAttachmentDict] | None
    parts: list[ChatPartDict]
    metadata: Any | None


class ChatModelConfigDict(TypedDict, total=False):
    max_tokens: int | None
    temperature: float | None
    top_p: float | None
    top_k: int | None
    frequency_penalty: float | None
    presence_penalty: float | None


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
    content_type: str | None = None

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
    details: list[ReasoningDetails] | None = None


@dataclass
class ReasoningDetails:
    type: Literal["text"]
    text: str
    signature: str | None = None


@dataclass
class ToolInvocationPart:
    """Represents a tool invocation part from the AI SDK."""

    type: str  # Starts with "tool-"
    tool_call_id: str
    state: str | Literal["output-available"]
    input: dict[str, Any]
    output: Any | None = None

    @property
    def tool_name(self) -> str:
        return self.type.split("-", 1)[1]


@dataclass
class FilePart:
    """Represents a FileUIPart from the AI SDK."""

    type: Literal["file"]
    media_type: str
    url: str
    filename: str | None = None


@dataclass
class ReasoningData:
    signature: str


@dataclass
class DataReasoningPart:
    type: Literal["data-reasoning-signature"]
    data: ReasoningData


@dataclass
class StepStartPart:
    type: Literal["step-start"]


if TYPE_CHECKING:
    from collections.abc import Iterator

    ChatPart = (
        TextPart
        | ReasoningPart
        | ToolInvocationPart
        | FilePart
        | DataReasoningPart
        | StepStartPart
    )
else:
    ChatPart = dict[str, Any]

PART_TYPES = [
    TextPart,
    ReasoningPart,
    ToolInvocationPart,
    FilePart,
    DataReasoningPart,
    StepStartPart,
]


class ChatMessage(msgspec.Struct, eq=False, dict=True):
    """
    A message in a chat.
    """

    # The role of the message.
    role: Literal["user", "assistant", "system"]

    # The content of the message.
    # This can be a rich Python object.
    content: Any

    # The id of the message.
    id: str = ""

    # Parts from AI SDK Stream Protocol (must be serializable to JSON)
    parts: list[ChatPart] = []

    # Optional attachments to the message.
    # TODO: Deprecate in favour of parts
    attachments: list[ChatAttachment] | None = None

    metadata: Any | None = None

    def __post_init__(self) -> None:
        # Non-struct attributes (via dict=True) so they never reach the wire.
        # Snapshots are aligned with the original input order; SDK fields the
        # typed dataclasses don't model are preserved even when the input is
        # a mix of dicts and typed parts. `_parts_idx[i]` is the index of the
        # converted part in `self.parts` (or None when conversion dropped it).
        self._raw_parts: list[dict[str, Any] | None] | None = None
        self._parts_idx: list[int | None] | None = None
        if self.parts:
            snapshots: list[dict[str, Any] | None] = []
            idx_map: list[int | None] = []
            parts: list[ChatPart] = []
            for part in self.parts:
                is_dict = isinstance(part, dict)
                snapshots.append(
                    cast(dict[str, Any], part) if is_dict else None
                )
                if converted := self._convert_part(part):
                    idx_map.append(len(parts))
                    parts.append(converted)
                else:
                    idx_map.append(None)
            if any(s is not None for s in snapshots):
                self._raw_parts = snapshots
                self._parts_idx = idx_map
            self.parts = parts

    # Fields excluded from equality. Add anything here that is a cache /
    # representation detail rather than part of the message's identity, so
    # `__eq__` keeps comparing every "real" field automatically as the
    # struct grows.
    _EQ_EXCLUDE: ClassVar[frozenset[str]] = frozenset()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChatMessage):
            return NotImplemented
        return all(
            getattr(self, name) == getattr(other, name)
            for name in self.__struct_fields__
            if name not in self._EQ_EXCLUDE
        )

    def _convert_part(self, part: Any) -> ChatPart | None:
        # If we receive a Vercel AI SDK part (through pydantic-ai), return it as is.
        if DependencyManager.pydantic_ai.imported():
            from pydantic_ai.ui.vercel_ai.request_types import UIMessagePart

            if isinstance(part, UIMessagePart):
                return cast(ChatPart, part)

        PartType = None
        for PartType in PART_TYPES:
            try:
                if is_dataclass(part):
                    return cast(ChatPart, part)
                return parse_raw(part, cls=PartType, allow_unknown_keys=True)
            except Exception:
                continue

        LOGGER.debug(
            f"Could not decode part {part}. Ignore if it's a Vercel UI message part."
        )
        return None

    def raw_or_dumped_parts(self) -> list[dict[str, Any]]:
        """Return parts in dict form, preferring the original wire payload."""
        raw_parts = self._raw_parts
        idx_map = self._parts_idx

        ui_message_part_cls: Any = None
        if DependencyManager.pydantic_ai.imported():
            from pydantic_ai.ui.vercel_ai.request_types import UIMessagePart

            ui_message_part_cls = UIMessagePart

        def dump(part: Any) -> dict[str, Any] | None:
            if is_dataclass(part):
                return asdict(part)
            if ui_message_part_cls is not None and isinstance(
                part, ui_message_part_cls
            ):
                return part.model_dump(by_alias=True, exclude_none=True)
            if isinstance(part, dict):
                return cast(dict[str, Any], part)
            return None

        if raw_parts is None or idx_map is None:
            return [d for p in self.parts if (d := dump(p)) is not None]

        result: list[dict[str, Any]] = []
        last_used = -1
        for snap, parts_idx in zip(raw_parts, idx_map, strict=True):
            if snap is not None:
                result.append(snap)
                if parts_idx is not None:
                    last_used = max(last_used, parts_idx)
            elif parts_idx is not None and parts_idx < len(self.parts):
                if (d := dump(self.parts[parts_idx])) is not None:
                    result.append(d)
                    last_used = max(last_used, parts_idx)
        # Parts appended after __post_init__ aren't in idx_map; dump them live.
        for part in self.parts[last_used + 1 :]:
            if (d := dump(part)) is not None:
                result.append(d)
        return result

    def __iter__(self) -> Iterator[tuple[str, Any]]:
        """Allow dict(message) to build the serialized dict."""
        out: ChatMessageDict = {
            "role": self.role,
            "id": self.id,
            "content": self.content,
            "parts": cast(list[ChatPartDict], self.raw_or_dumped_parts()),
            "attachments": [
                cast(ChatAttachmentDict, asdict(a)) for a in self.attachments
            ]
            if self.attachments
            else None,
            "metadata": self.metadata,
        }
        return iter(out.items())

    @classmethod
    def create(
        cls,
        *,
        role: Literal["user", "assistant", "system"],
        message_id: str,
        content: str | None,
        parts: list[ChatPart],
        part_validator_class: Any | None = None,
    ) -> ChatMessage:
        """
        Helper method to create a ChatMessage object.
        If part_validator_class is provided, the parts will be converted to the given class.
        """

        if part_validator_class:
            # Lazy import: `_pydantic_ai_utils` pulls in `marimo._server.*`,
            # which we don't want to load just to define the types module.
            from marimo._ai._pydantic_ai_utils import sanitize_part

            validated_parts = []
            for part in parts:
                if isinstance(part, part_validator_class):
                    validated_parts.append(part)
                elif isinstance(part, dict):
                    sanitized_part = sanitize_part(part)
                    # Try pydantic validation for dict -> class conversion
                    try:
                        from pydantic import TypeAdapter

                        adapter = TypeAdapter(part_validator_class)
                        validated_parts.append(
                            adapter.validate_python(sanitized_part)
                        )
                    except ImportError:
                        LOGGER.debug(
                            "Pydantic not installed, skipping dict validation"
                        )
                    except Exception:
                        LOGGER.debug("Part %r could not be validated", part)
                else:
                    LOGGER.debug(
                        "Part %r (type=%s) is not an instance of %s and not a dict, dropping",
                        part,
                        type(part).__name__,
                        part_validator_class.__name__,
                    )
            parts = validated_parts

        return cls(role=role, id=message_id, content=content, parts=parts)


@dataclass
class ChatModelConfig:
    # Maximum number of tokens.
    max_tokens: int | None = None

    # Temperature for the model (randomness).
    temperature: float | None = None

    # Restriction on the cumulative probability of prediction candidates.
    top_p: float | None = None

    # Number of top prediction candidates to consider.
    top_k: int | None = None

    # Penalty for tokens which appear frequently.
    frequency_penalty: float | None = None

    # Penalty for tokens which already appeared at least once.
    presence_penalty: float | None = None


class ChatModel(abc.ABC):
    @abc.abstractmethod
    def __call__(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> object:
        pass
