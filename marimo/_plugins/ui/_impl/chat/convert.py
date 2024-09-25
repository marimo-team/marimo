from __future__ import annotations

from typing import Any, Dict, List

from marimo._plugins.ui._impl.chat.types import ChatClientMessage


def convert_to_openai_messages(
    messages: List[ChatClientMessage],
) -> List[Dict[Any, Any]]:
    openai_messages: List[Dict[Any, Any]] = []

    for message in messages:
        parts: List[Dict[Any, Any]] = []

        parts.append({"type": "text", "text": message.content})

        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type.startswith("image"):
                    parts.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": attachment.url},
                        }
                    )

                elif attachment.content_type.startswith("text"):
                    parts.append({"type": "text", "text": attachment.url})

        openai_messages.append({"role": message.role, "content": parts})

    return openai_messages
