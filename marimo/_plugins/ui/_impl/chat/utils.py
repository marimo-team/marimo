# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import List, Optional

from marimo._plugins.ui._impl.chat.types import (
    ChatAttachment,
    ChatMessage,
    ChatMessageDict,
)


def from_chat_message_dict(d: ChatMessageDict) -> ChatMessage:
    if isinstance(d, ChatMessage):
        return d

    attachments_dict = d.get("attachments", None)
    attachments: Optional[List[ChatAttachment]] = None
    if attachments_dict is not None:
        attachments = [
            ChatAttachment(
                name=attachment["name"] or "attachment",
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
