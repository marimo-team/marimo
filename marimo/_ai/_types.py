# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import abc
import mimetypes
from collections.abc import Iterator
from dataclasses import asdict, dataclass, is_dataclass
from typing import TYPE_CHECKING, Any, Literal, TypedDict, cast

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

    from pydantic_ai.ui.vercel_ai.request_types import UIMessagePart

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


class ChatMessage(msgspec.Struct, dict=True):
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
        # Non-struct attribute (via `dict=True`) so it isn't serialized.
        # Snapshots raw dict inputs 1:1 with `self.parts` so SDK fields the
        # typed dataclasses don't model survive the round-trip.
        self._raw_parts: list[dict[str, Any] | None] | None = None
        if not self.parts:
            return
        snapshots: list[dict[str, Any] | None] = []
        typed: list[ChatPart] = []
        for part in self.parts:
            converted = self._convert_part(part)
            if converted is None:
                continue
            snapshots.append(
                cast(dict[str, Any], part) if isinstance(part, dict) else None
            )
            typed.append(converted)
        if any(s is not None for s in snapshots):
            self._raw_parts = snapshots
        self.parts = typed

    def _convert_part(self, part: Any) -> ChatPart | None:
        if DependencyManager.pydantic_ai.imported():
            from pydantic_ai.ui.vercel_ai.request_types import UIMessagePart

            if isinstance(part, UIMessagePart):
                return cast(ChatPart, part)

        if is_dataclass(part) and not isinstance(part, type):
            return cast(ChatPart, part)

        # Unknown dicts pass through verbatim so future SDK part types still
        # round-trip.
        if isinstance(part, dict):
            for PartType in PART_TYPES:
                try:
                    return parse_raw(
                        part, cls=PartType, allow_unknown_keys=True
                    )
                except Exception:
                    continue
            return cast(ChatPart, part)

        LOGGER.debug("Dropping unrecognized part %r", part)
        return None

    def raw_or_dumped_parts(self) -> list[dict[str, Any]]:
        """Return parts in dict form, preferring the original wire payload."""
        ui_message_part_cls: type[UIMessagePart] | None = None
        if DependencyManager.pydantic_ai.imported():
            from pydantic_ai.ui.vercel_ai.request_types import UIMessagePart

            # `UIMessagePart` is a union type alias; the runtime value works
            # with `isinstance` but doesn't match `type[...]` statically.
            ui_message_part_cls = UIMessagePart  # type: ignore[assignment]  # pyright: ignore[reportAssignmentType]

        def dump(part: Any) -> dict[str, Any] | None:
            if is_dataclass(part) and not isinstance(part, type):
                return asdict(part)
            if ui_message_part_cls is not None and isinstance(
                part, ui_message_part_cls
            ):
                return part.model_dump(by_alias=True, exclude_none=True)  # type: ignore[no-any-return]
            if isinstance(part, dict):
                return cast(dict[str, Any], part)
            return None

        raws = self._raw_parts
        result: list[dict[str, Any]] = []
        for i, part in enumerate(self.parts):
            snap = raws[i] if raws is not None and i < len(raws) else None
            if snap is not None:
                result.append(snap)
            elif (d := dump(part)) is not None:
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
