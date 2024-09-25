from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Union


@dataclass
class ClientAttachment:
    # The name of the attachment, usually the file name.
    name: str

    # A string indicating the [media type](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type).
    # By default, it's extracted from the pathname's extension.
    content_type: str

    # The URL of the attachment. It can either be a URL to a hosted file or a
    # [Data URL](https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/Data_URLs).
    url: str


@dataclass
class ChatClientMessage:
    role: Literal["user", "assistant", "system"]
    content: str
    attachments: Optional[List[ClientAttachment]] = None

    @staticmethod
    def from_dict(
        d: Dict[str, Union[str, list[Dict[str, str]]]],
    ) -> ChatClientMessage:
        if isinstance(d, ChatClientMessage):
            return d

        if "attachments" in d:
            attachments = [
                ClientAttachment(
                    name=attachment["name"],
                    content_type=attachment["content_type"],
                    url=attachment["url"],
                )
                for attachment in d["attachments"]
            ]
        else:
            attachments = None

        return ChatClientMessage(
            role=d["role"],
            content=d["content"],
            attachments=attachments,
        )


@dataclass
class ChatModelConfig:
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None


@dataclass
class SendMessageRequest:
    messages: List[ChatClientMessage]
    config: ChatModelConfig


# class ModelRegistry(abc.ABC):
#     @abc.abstractmethod
#     def get_model(self, model_name: str):
#         pass

#     @abc.abstractmethod
#     def has_model(self):
#         pass


class ChatModel(abc.ABC):
    @abc.abstractmethod
    def generate_text(
        self, message: List[ChatClientMessage], config: ChatModelConfig
    ) -> object:
        pass
