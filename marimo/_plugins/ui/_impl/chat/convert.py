# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Dict, List

from marimo._plugins.ui._impl.chat.types import ChatMessage


def convert_to_openai_messages(
    messages: List[ChatMessage],
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


def convert_to_anthropic_messages(
    messages: List[ChatMessage],
) -> List[Dict[Any, Any]]:
    anthropic_messages: List[Dict[Any, Any]] = []

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

        anthropic_messages.append({"role": message.role, "content": parts})

    return anthropic_messages


def convert_to_google_messages(
    messages: List[ChatMessage],
) -> List[Dict[Any, Any]]:
    google_messages: List[Dict[Any, Any]] = []

    for message in messages:
        content = message.content
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type.startswith("image"):
                    content += f"\n[Image: {attachment.url}]"
                elif attachment.content_type.startswith("text"):
                    content += f"\n[Text: {attachment.url}]"

        google_messages.append(
            {
                "role": "user" if message.role == "user" else "model",
                "parts": [content],
            }
        )

    return google_messages
