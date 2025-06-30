# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any, Literal, Union, cast

from marimo import _loggers
from marimo._ai._types import (
    ChatMessage,
    ReasoningPart,
    TextPart,
    ToolInvocationPart,
)
from marimo._server.ai.tools import Tool

LOGGER = _loggers.marimo_logger()


if TYPE_CHECKING:
    from anthropic.types.message_param import (  # type: ignore[import-not-found]
        MessageParam,
    )
    from google.genai.types import (  # type: ignore[import-not-found]
        Content,
        Part,
    )
    from openai.types.chat import (  # type: ignore[import-not-found]
        ChatCompletionMessageParam,
    )


# Message conversions
def get_openai_messages_from_parts(
    role: Literal["system", "user", "assistant"],
    parts: list[Union[TextPart, ReasoningPart, ToolInvocationPart]],
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for part in parts:
        if isinstance(part, TextPart):
            message = {"role": role, "content": part.text}
            messages.append(message)
        elif isinstance(part, ToolInvocationPart):
            # Create two messages for the tool result
            assistant_message = {
                "role": role,
                "content": None,
                "tool_calls": [
                    {
                        "id": part.tool_invocation.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": part.tool_invocation.tool_name,
                            "arguments": str(part.tool_invocation.args)
                            if part.tool_invocation.args
                            else "{}",
                        },
                    }
                ],
            }
            messages.append(assistant_message)
            tool_result_message = {
                "role": "tool",
                "tool_call_id": part.tool_invocation.tool_call_id,
                "name": part.tool_invocation.tool_name,
                "content": str(part.tool_invocation.result),
            }
            messages.append(tool_result_message)
    return messages


def convert_to_openai_messages(
    messages: list[ChatMessage],
) -> list[ChatCompletionMessageParam]:
    openai_messages: list[dict[Any, Any]] = []

    for message in messages:
        # Handle message without attachments
        if not message.attachments:
            if not message.parts or len(message.parts) == 0:
                openai_messages.append(
                    {"role": message.role, "content": message.content}
                )
            else:
                parts_messages = get_openai_messages_from_parts(
                    message.role, message.parts
                )
                openai_messages.extend(parts_messages)
            continue

        # Handle attachments
        parts: list[dict[Any, Any]] = []
        if not message.parts or len(message.parts) == 0:
            parts.append({"type": "text", "text": message.content})
        else:
            parts.extend(
                get_openai_messages_from_parts(message.role, message.parts)
            )

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

    return cast("list[ChatCompletionMessageParam]", openai_messages)


def get_anthropic_messages_from_parts(
    role: Literal["system", "user", "assistant"],
    parts: list[Union[TextPart, ReasoningPart, ToolInvocationPart]],
) -> list[dict[Any, Any]]:
    messages: list[dict[Any, Any]] = []
    content_parts: list[dict[str, Any]] = []

    for part in parts:
        if isinstance(part, TextPart):
            content_parts.append({"type": "text", "text": part.text})
        elif isinstance(part, ReasoningPart):
            # Handle reasoning parts with proper Anthropic thinking type
            signature = ""
            if part.details and len(part.details) > 0:
                signature = part.details[0].signature or ""

            content_parts.append(
                {
                    "type": "thinking",
                    "thinking": part.reasoning,
                    "signature": signature,  # This should be the encrypted signature from Claude's response
                }
            )
        elif isinstance(part, ToolInvocationPart):
            # Add tool use to current message content
            content_parts.append(
                {
                    "type": "tool_use",
                    "id": part.tool_invocation.tool_call_id,
                    "name": part.tool_invocation.tool_name,
                    "input": part.tool_invocation.args,
                }
            )

            # Create the message with current content (including tool use)
            if content_parts:
                message_content = (
                    content_parts[0]["text"]
                    if len(content_parts) == 1
                    and content_parts[0]["type"] == "text"
                    else content_parts
                )
                messages.append({"role": role, "content": message_content})
                content_parts = []  # Reset for next message

            # Create separate tool result message
            tool_result_message = {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": part.tool_invocation.tool_call_id,
                        "content": str(part.tool_invocation.result),
                    }
                ],
            }
            messages.append(tool_result_message)

    # Add remaining content parts as a single message if any
    if content_parts:
        # If only one text part, use string format; otherwise use array format
        if len(content_parts) == 1 and content_parts[0]["type"] == "text":
            message_content = content_parts[0]["text"]
        else:
            message_content = content_parts

        messages.append({"role": role, "content": message_content})

    return messages


def convert_to_anthropic_messages(
    messages: list[ChatMessage],
) -> list[MessageParam]:
    anthropic_messages: list[dict[Any, Any]] = []

    for message in messages:
        if not message.attachments:
            if not message.parts or len(message.parts) == 0:
                anthropic_messages.append(
                    {"role": message.role, "content": message.content}
                )
            else:
                parts_messages = get_anthropic_messages_from_parts(
                    message.role, message.parts
                )
                anthropic_messages.extend(parts_messages)
            continue

        # Handle attachments
        parts: list[dict[Any, Any]] = []
        if not message.parts or len(message.parts) == 0:
            parts.append({"type": "text", "text": message.content})
        else:
            parts.extend(
                get_anthropic_messages_from_parts(message.role, message.parts)
            )
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

    return cast("list[MessageParam]", anthropic_messages)


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


def get_google_messages_from_parts(
    role: Literal["system", "user", "assistant"],
    parts: list[Union[TextPart, ReasoningPart, ToolInvocationPart]],
) -> list[Content]:
    messages: list[Content] = []

    for part in parts:
        if isinstance(part, TextPart):
            # Create a message with text content
            text_message: Content = {
                "role": "user" if role == "user" else "model",
                "parts": [{"text": part.text}],
            }
            messages.append(text_message)
        elif isinstance(part, ReasoningPart):
            # Google uses the "thought" field for reasoning content
            # According to Google's thinking models documentation
            reasoning_message: Content = {
                "role": "user" if role == "user" else "model",
                "parts": [{"text": part.reasoning, "thought": True}],
            }
            messages.append(reasoning_message)
        elif isinstance(part, ToolInvocationPart):
            # Create function call message for Google
            function_call_message: Content = {
                "role": "model",
                "parts": [
                    {
                        "function_call": {
                            "name": part.tool_invocation.tool_name,
                            "args": part.tool_invocation.args or {},
                        }
                    }
                ],
            }
            messages.append(function_call_message)

            # Create function response message
            function_response_message: Content = {
                "role": "user",
                "parts": [
                    {
                        "function_response": {
                            "name": part.tool_invocation.tool_name,
                            "response": {
                                "result": str(part.tool_invocation.result)
                            },
                        }
                    }
                ],
            }
            messages.append(function_response_message)

    return messages


def convert_to_google_messages(
    messages: list[ChatMessage],
) -> list[Content]:
    google_messages: list[Content] = []

    for message in messages:
        # Handle message without attachments
        if not message.attachments:
            if not message.parts or len(message.parts) == 0:
                google_messages.append(
                    {
                        "role": "user" if message.role == "user" else "model",
                        "parts": [{"text": str(message.content)}],
                    }
                )
            else:
                parts_messages = get_google_messages_from_parts(
                    message.role, message.parts
                )
                google_messages.extend(parts_messages)
            continue

        # Handle attachments
        parts: list[Part] = []
        if not message.parts or len(message.parts) == 0:
            parts.append({"text": str(message.content)})
        else:
            # Convert internal parts to Google parts format
            for parts_message in get_google_messages_from_parts(
                message.role, message.parts
            ):
                parts.extend(parts_message["parts"])

        for attachment in message.attachments:
            content_type = attachment.content_type or "text/plain"

            if content_type.startswith("image"):
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
            elif content_type.startswith("text"):
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
            else:
                raise ValueError(f"Unsupported content type {content_type}")

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
    content_text: Union[str, dict[str, Any]],
    content_type: Literal[
        "text",
        "reasoning",
        "reasoning_signature",
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
    REASON_SIGNATURE_PREFIX = "j:"
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

    elif content_type == "reasoning_signature" and isinstance(
        content_text, dict
    ):
        return f"{REASON_SIGNATURE_PREFIX}{json.dumps(content_text)}\n"

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
