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


@dataclass
class ChatAttachment:
    """
    @public
    """

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
    """
    @public
    """

    role: Literal["user", "assistant", "system"]
    content: str
    attachments: Optional[List[ChatAttachment]] = None


@dataclass
class ChatModelConfig:
    """
    @public
    """

    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None


# class ModelRegistry(abc.ABC):
#     @abc.abstractmethod
#     def get_model(self, model_name: str):
#         pass

#     @abc.abstractmethod
#     def has_model(self):
#         pass


class ChatModel(abc.ABC):
    """
    @public
    """

    @abc.abstractmethod
    def generate_text(
        self, message: List[ChatMessage], config: ChatModelConfig
    ) -> object:
        pass


def from_chat_message_dict(d: ChatMessageDict) -> ChatMessage:
    if isinstance(d, ChatMessage):
        return d

    attachments_dict = d.get("attachments", None)
    attachments: Optional[List[ChatAttachment]] = None
    if attachments_dict is not None:
        attachments = [
            ChatAttachment(
                name=attachment["name"],
                content_type=attachment["content_type"],
                url=attachment["url"],
            )
            for attachment in attachments_dict
        ]
    else:
        attachments = None

    return ChatMessage(
        role=d["role"],
        content=d["content"],
        attachments=attachments,
    )
