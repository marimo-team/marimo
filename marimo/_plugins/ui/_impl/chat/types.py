from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import List, Literal, Optional, TypedDict


class ChatAttachmentDict(TypedDict):
    name: str
    content_type: str
    url: str


class ChatMessageDict(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str
    attachments: Optional[List[ChatAttachmentDict]]


# NOTE: The following classes are public API.
# Any changes must be backwards compatible.


@dataclass
class ChatAttachment:
    # The name of the attachment, usually the file name.
    name: str

    # A string indicating the [media type](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type).
    # By default, it's extracted from the pathname's extension.
    content_type: str

    # The URL of the attachment. It can either be a URL to a hosted file or a
    # [Data URL](https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/Data_URLs).
    url: str


@dataclass
class ChatMessage:
    role: Literal["user", "assistant", "system"]
    content: str
    attachments: Optional[List[ChatAttachment]] = None


@dataclass
class ChatModelConfig:
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None


class ChatModel(abc.ABC):
    @abc.abstractmethod
    def __call__(
        self, messages: List[ChatMessage], config: ChatModelConfig
    ) -> object:
        pass
