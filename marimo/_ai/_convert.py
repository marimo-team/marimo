# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from marimo._ai._types import ChatMessage

if TYPE_CHECKING:
    from google.generativeai.types import (  # type: ignore[import-not-found]
        ContentDict,
        PartType,
    )


def convert_to_openai_messages(
    messages: list[ChatMessage],
) -> list[dict[Any, Any]]:
    openai_messages: list[dict[Any, Any]] = []

    for message in messages:
        if not message.attachments:
            openai_messages.append(
                {"role": message.role, "content": message.content}
            )
            continue

        # Handle attachments
        parts: list[dict[Any, Any]] = []
        parts.append({"type": "text", "text": message.content})
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
                raise ValueError(f"Unsupported content type {content_type}")

        openai_messages.append({"role": message.role, "content": parts})

    return openai_messages


def convert_to_anthropic_messages(
    messages: list[ChatMessage],
) -> list[dict[Any, Any]]:
    anthropic_messages: list[dict[Any, Any]] = []

    for message in messages:
        if not message.attachments:
            anthropic_messages.append(
                {"role": message.role, "content": message.content}
            )
            continue

        # Handle attachments
        parts: list[dict[Any, Any]] = []
        parts.append({"type": "text", "text": message.content})
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
                raise ValueError(f"Unsupported content type {content_type}")

        anthropic_messages.append({"role": message.role, "content": parts})

    return anthropic_messages


def convert_to_groq_messages(
    messages: list[ChatMessage],
) -> list[dict[Any, Any]]:
    groq_messages: list[dict[Any, Any]] = []

    for message in messages:
        # Currently only supports text content (Llava is deprecated now)
        # See here - https://console.groq.com/docs/deprecations
        if message.attachments:
            # Convert attachments to text if possible
            text_content = str(message.content)  # Explicitly convert to string
            for attachment in message.attachments:
                content_type = attachment.content_type or "text/plain"
                if content_type.startswith("text"):
                    text_content += "\n" + _extract_text(attachment.url)

            groq_messages.append(
                {"role": message.role, "content": text_content}
            )
        else:
            groq_messages.append(
                {
                    "role": message.role,
                    "content": str(
                        message.content
                    ),  # Explicitly convert to string
                }
            )

    return groq_messages


def convert_to_google_messages(
    messages: list[ChatMessage],
) -> list[ContentDict]:
    google_messages: list[ContentDict] = []

    for message in messages:
        parts: list[PartType] = [str(message.content)]
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
