# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any, Literal

from marimo._ai._types import ChatMessage
from marimo._server.ai.tools import Tool

if TYPE_CHECKING:
    from google.genai.types import (  # type: ignore[import-not-found]
        Content,
        Part,
    )


# Message conversions
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
) -> list[Content]:
    google_messages: list[Content] = []

    for message in messages:
        parts: list[Part] = [{"text": str(message.content)}]
        if message.attachments:
            for attachment in message.attachments:
                content_type = attachment.content_type or "text/plain"

                parts.append(
                    {
                        "inline_data": {
                            "mime_type": content_type,
                            "data": base64.b64decode(
                                _extract_data(attachment.url)
                            ),
                        },
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


def convert_to_ai_sdk_messages(
    content_text: str | dict[str, Any],
    content_type: Literal[
        "text",
        "reasoning",
        "tool_call_start",
        "tool_call_delta",
        "tool_call_end",
        "tool_result",
        "finish_reason",
    ],
) -> str:
    """
    Format text events for the AI SDK stream protocol.
    See: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol
    """
    TEXT_PREFIX = "0:"
    REASON_PREFIX = "g:"
    TOOL_CALL_START_PREFIX = "b:"
    TOOL_CALL_DELTA_PREFIX = "c:"
    TOOL_CALL_PREFIX = "9:"
    TOOL_RESULT_PREFIX = "a:"
    FINISH_REASON_PREFIX = "d:"

    # Text events
    if content_type == "text" and isinstance(content_text, str):
        return f"{TEXT_PREFIX}{json.dumps(content_text)}\n"
    elif content_type == "reasoning" and isinstance(content_text, str):
        return f"{REASON_PREFIX}{json.dumps(content_text)}\n"

    # Tool use events
    elif content_type == "tool_call_start" and isinstance(content_text, dict):
        return f"{TOOL_CALL_START_PREFIX}{json.dumps(content_text)}\n"
    elif content_type == "tool_call_delta" and isinstance(content_text, dict):
        return f"{TOOL_CALL_DELTA_PREFIX}{json.dumps(content_text)}\n"
    elif content_type == "tool_call_end" and isinstance(content_text, dict):
        return f"{TOOL_CALL_PREFIX}{json.dumps(content_text)}\n"
    elif content_type == "tool_result" and isinstance(content_text, dict):
        return f"{TOOL_RESULT_PREFIX}{json.dumps(content_text)}\n"

    # Other events
    elif content_type == "finish_reason" and content_text in [
        "tool_calls",
        "stop",
    ]:
        # Emit the finishReason as a JSON object with usage (default 0s)
        # TODO: Add usage (promptTokens, completionTokens)
        return f'{FINISH_REASON_PREFIX}{{"finishReason": "{content_text}", "usage": {{"promptTokens": 0, "completionTokens": 0}}}}\n'

    else:
        # Default to text for unknown types
        return f"{TEXT_PREFIX}{json.dumps(content_text)}\n"


# Tool conversions
def convert_to_openai_tools(tools: list[Tool]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


def convert_to_anthropic_tools(tools: list[Tool]) -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }
        for tool in tools
    ]


def convert_to_google_tools(tools: list[Tool]) -> list[dict[str, Any]]:
    return [
        {
            "function_declarations": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            ]
        }
        for tool in tools
    ]
