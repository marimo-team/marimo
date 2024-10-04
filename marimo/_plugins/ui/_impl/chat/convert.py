# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
from typing import Any, Dict, List, TypedDict

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
                content_type = attachment.content_type or "text/plain"

                if content_type.startswith("image"):
                    parts.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": attachment.url},
                        }
                    )
                elif content_type.startswith("text"):
                    parts.append(
                        {"type": "text", "text": _extract_text(attachment.url)}
                    )
                else:
                    raise ValueError(
                        f"Unsupported content type {content_type}"
                    )

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
                content_type = attachment.content_type or "text/plain"
                if content_type.startswith("image"):
                    parts.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": content_type,
                                "data": _extract_data(attachment.url),
                            },
                        }
                    )

                elif content_type.startswith("text"):
                    parts.append(
                        {"type": "text", "text": _extract_text(attachment.url)}
                    )

                else:
                    raise ValueError(
                        f"Unsupported content type {content_type}"
                    )

        anthropic_messages.append({"role": message.role, "content": parts})

    return anthropic_messages


# Matches from google.generativeai.types import content_types
class BlobDict(TypedDict):
    mime_type: str
    data: bytes


def convert_to_google_messages(
    messages: List[ChatMessage],
) -> List[Dict[Any, Any]]:
    google_messages: List[Dict[Any, Any]] = []

    for message in messages:
        parts: List[str | BlobDict] = [message.content]
        if message.attachments:
            for attachment in message.attachments:
                content_type = attachment.content_type or "text/plain"

                parts.append(
                    {
                        "mime_type": content_type,
                        "data": base64.b64decode(
                            _extract_data(attachment.url)
                        ),
                    }
                )

        google_messages.append(
            {
                "role": "user" if message.role == "user" else "model",
                "parts": parts,
            }
        )

    return google_messages


def _extract_text(url: str) -> str:
    if url.startswith("data:"):
        # extract base64 encoding from url
        data = url.split(",")[1]
        return base64.b64decode(data).decode("utf-8")
    else:
        return url


def _extract_data(url: str) -> str:
    if url.startswith("data:"):
        return url.split(",")[1]
    else:
        return url
