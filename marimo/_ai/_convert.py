# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
import json
import uuid
from typing import TYPE_CHECKING, Any, Literal, Optional, Union, cast

from marimo._ai._types import (
    ChatMessage,
    ChatPart,
    FilePart,
    ReasoningPart,
    TextPart,
    ToolInvocationPart,
)
from marimo._messaging.msgspec_encoder import asdict
from marimo._server.ai.tools.types import Tool

if TYPE_CHECKING:
    from anthropic.types import (  # type: ignore[import-not-found]
        ContentBlock,
        DocumentBlockParam,
        ImageBlockParam,
        MessageParam,
        RedactedThinkingBlockParam,
        ServerToolUseBlockParam,
        TextBlockParam,
        ThinkingBlockParam,
        ToolResultBlockParam,
        ToolUseBlockParam,
        WebSearchToolResultBlockParam,
    )
    from google.genai.types import (  # type: ignore[import-not-found]
        BlobDict,
        ContentDict,
        ContentUnionDict,
        PartDict,
    )
    from openai.types.chat import (  # type: ignore[import-not-found]
        ChatCompletionMessageParam,
    )


# Message conversions
def get_openai_messages_from_parts(
    role: Literal["system", "user", "assistant"],
    parts: list[ChatPart],
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
                        "id": part.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": part.tool_name,
                            "arguments": str(part.input)
                            if part.input
                            else "{}",
                        },
                    }
                ],
            }
            messages.append(assistant_message)
            tool_result_message = {
                "role": "tool",
                "tool_call_id": part.tool_call_id,
                "name": part.tool_name,
                "content": str(part.output),
            }
            messages.append(tool_result_message)
    return messages


def convert_to_openai_messages(
    messages: list[ChatMessage],
) -> list[ChatCompletionMessageParam]:
    openai_messages: list[dict[Any, Any]] = []

    for message in messages:
        parts: list[dict[Any, Any]] = []
        if not message.parts or len(message.parts) == 0:
            parts.append({"type": "text", "text": message.content})
        else:
            for part in message.parts:
                if isinstance(part, FilePart):
                    if part.media_type.startswith("image"):
                        parts.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": part.url},
                            }
                        )
                    elif part.media_type.startswith("text"):
                        parts.append(
                            {"type": "text", "text": _extract_text(part.url)}
                        )
                    else:
                        raise ValueError(
                            f"Unsupported content type {part.media_type}"
                        )
                else:
                    parts.append(asdict(part))

        openai_messages.append({"role": message.role, "content": parts})

    return cast("list[ChatCompletionMessageParam]", openai_messages)


AnthropicParts = Union[
    "ServerToolUseBlockParam",
    "WebSearchToolResultBlockParam",
    "TextBlockParam",
    "ImageBlockParam",
    "ToolUseBlockParam",
    "ToolResultBlockParam",
    "DocumentBlockParam",
    "ThinkingBlockParam",
    "RedactedThinkingBlockParam",
    "ContentBlock",
]


def get_anthropic_parts_from_chat_parts(
    parts: list[ChatPart],
) -> list[AnthropicParts]:
    anthropic_parts: list[AnthropicParts] = []

    for part in parts:
        if isinstance(part, TextPart):
            text_block: TextBlockParam = {
                "type": "text",
                "text": part.text,
            }
            anthropic_parts.append(text_block)
        elif isinstance(part, ReasoningPart):
            # Handle reasoning parts with proper Anthropic thinking type
            signature = ""
            if part.details and len(part.details) > 0:
                signature = part.details[0].signature or ""

            thinking_message: ThinkingBlockParam = {
                "type": "thinking",
                "thinking": part.reasoning,
                "signature": signature,
            }
            anthropic_parts.append(thinking_message)
        elif isinstance(part, FilePart):
            media_type = part.media_type
            if media_type.strip() in [
                "image/jpeg",
                "image/png",
                "image/gif",
                "image/webp",
            ]:
                image_message: ImageBlockParam = {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,  # type: ignore
                        "data": _extract_data(part.url),
                    },
                }
                anthropic_parts.append(image_message)
            elif media_type.startswith("text"):
                text_block_file: TextBlockParam = {
                    "type": "text",
                    "text": _extract_text(part.url),
                }
                anthropic_parts.append(text_block_file)
            else:
                raise ValueError(f"Unsupported content type {media_type}")
        elif isinstance(part, ToolInvocationPart):
            # Add tool use to current message content
            tool_use_message: ToolUseBlockParam = {
                "type": "tool_use",
                "id": part.tool_call_id,
                "name": part.tool_name,
                "input": part.input,
            }
            anthropic_parts.append(tool_use_message)

            # Create separate tool result message
            tool_result_message: ToolResultBlockParam = {
                "tool_use_id": part.tool_call_id,
                "type": "tool_result",
                "content": [
                    {
                        "type": "text",
                        "text": str(part.output),
                    }
                ],
            }
            anthropic_parts.append(tool_result_message)

    return anthropic_parts


def convert_to_anthropic_messages(
    messages: list[ChatMessage],
) -> list[MessageParam]:
    anthropic_messages: list[MessageParam] = []

    for message in messages:
        parts: list[AnthropicParts] = []
        if not message.parts:
            # Convert content to string
            text_block: TextBlockParam = {
                "type": "text",
                "text": str(message.content),
            }
            parts.append(text_block)
        else:
            parts.extend(get_anthropic_parts_from_chat_parts(message.parts))

        anthropic_role = (
            "assistant" if message.role == "system" else message.role
        )
        anthropic_messages.append({"role": anthropic_role, "content": parts})
    return anthropic_messages


def convert_to_groq_messages(
    messages: list[ChatMessage],
) -> list[dict[Any, Any]]:
    groq_messages: list[dict[Any, Any]] = []

    for message in messages:
        if message.parts:
            # Currently only supports text content (Llava is deprecated now)
            # See here - https://console.groq.com/docs/deprecations
            file_parts = [
                part for part in message.parts if isinstance(part, FilePart)
            ]
            # Convert attachments to text if possible
            text_content = str(message.content)  # Explicitly convert to string
            for file in file_parts:
                if file.media_type.startswith("text"):
                    text_content += "\n" + _extract_text(file.url)
                else:
                    raise ValueError(
                        f"Unsupported content type {file.media_type}. Only text content is supported."
                    )

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
    parts: list[ChatPart],
) -> list[ContentDict]:
    messages: list[ContentDict] = []

    for part in parts:
        if isinstance(part, TextPart):
            # Create a message with text content
            text_message: ContentDict = {
                "role": "user" if role == "user" else "model",
                "parts": [{"text": part.text}],
            }
            messages.append(text_message)
        elif isinstance(part, ReasoningPart):
            # Google uses the "thought" field for reasoning content
            # According to Google's thinking models documentation
            reasoning_message: ContentDict = {
                "role": "user" if role == "user" else "model",
                "parts": [{"text": part.reasoning, "thought": True}],
            }
            messages.append(reasoning_message)
        elif isinstance(part, FilePart):
            media_type = part.media_type
            if not media_type.startswith(("image", "text")):
                raise ValueError(f"Unsupported content type {media_type}")
            inline_data: BlobDict = {
                "mime_type": media_type,
                "data": base64.b64decode(_extract_data(part.url)),
            }
            messages.append(
                {
                    "role": "user" if role == "user" else "model",
                    "parts": [{"inline_data": inline_data}],
                }
            )
        elif isinstance(part, ToolInvocationPart):
            # Create function call message for Google
            function_call_message: ContentDict = {
                "role": "model",
                "parts": [
                    {
                        "function_call": {
                            "name": part.tool_name,
                            "args": part.input or {},
                        }
                    }
                ],
            }
            messages.append(function_call_message)

            # Create function response message
            function_response_message: ContentDict = {
                "role": "user",
                "parts": [
                    {
                        "function_response": {
                            "name": part.tool_name,
                            "response": {"result": str(part.output)},
                        }
                    }
                ],
            }
            messages.append(function_response_message)

    return messages


def convert_to_google_messages(
    messages: list[ChatMessage],
) -> list[ContentUnionDict]:
    google_messages: list[ContentUnionDict] = []

    for message in messages:
        parts: list[PartDict] = []
        if not message.parts or len(message.parts) == 0:
            parts.append({"text": str(message.content)})
        else:
            # Convert internal parts to Google parts format
            for parts_message in get_google_messages_from_parts(
                message.role, message.parts
            ):
                if "parts" in parts_message:
                    parts.extend(parts_message["parts"] or [])

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
        raw = base64.b64decode(data)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            # fallback: try latin1
            return raw.decode("latin1")
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
        "text_start",
        "text_end",
        "reasoning",
        "reasoning_start",
        "reasoning_end",
        "reasoning_signature",
        "tool_call_start",
        "tool_call_delta",
        "tool_call_end",
        "tool_result",
        "finish_reason",
        "error",
    ],
    text_id: Optional[str] = None,
) -> str:
    """
    Format events for the AI SDK v5 stream protocol using Server-Sent Events.
    This follows the data-stream v1 protocol with SSE format.
    See: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol
    """

    # Text events - use start/delta/end pattern with unique IDs
    if content_type == "text" and isinstance(content_text, str):
        if text_id is None:
            text_id = f"text_{uuid.uuid4().hex}"
        return f"data: {json.dumps({'type': 'text-delta', 'id': text_id, 'delta': content_text})}\n\n"

    elif content_type == "text_start":
        if text_id is None:
            text_id = f"text_{uuid.uuid4().hex}"
        return f"data: {json.dumps({'type': 'text-start', 'id': text_id})}\n\n"

    elif content_type == "text_end" and text_id is not None:
        return f"data: {json.dumps({'type': 'text-end', 'id': text_id})}\n\n"

    # Reasoning events - use start/delta/end pattern with unique IDs
    elif content_type == "reasoning" and isinstance(content_text, str):
        if text_id is None:
            text_id = f"reasoning_{uuid.uuid4().hex}"
        return f"data: {json.dumps({'type': 'reasoning-delta', 'id': text_id, 'delta': content_text})}\n\n"

    elif content_type == "reasoning_start":
        if text_id is None:
            text_id = f"reasoning_{uuid.uuid4().hex}"
        return f"data: {json.dumps({'type': 'reasoning-start', 'id': text_id})}\n\n"

    elif content_type == "reasoning_end" and text_id is not None:
        return (
            f"data: {json.dumps({'type': 'reasoning-end', 'id': text_id})}\n\n"
        )

    # Tool use events
    elif content_type == "tool_call_start" and isinstance(content_text, dict):
        return f"data: {json.dumps({'type': 'tool-input-start', **content_text})}\n\n"

    elif content_type == "tool_call_delta" and isinstance(content_text, dict):
        return f"data: {json.dumps({'type': 'tool-input-delta', **content_text})}\n\n"

    elif content_type == "tool_call_end" and isinstance(content_text, dict):
        return f"data: {json.dumps({'type': 'tool-input-available', **content_text})}\n\n"

    elif content_type == "tool_result" and isinstance(content_text, dict):
        return f"data: {json.dumps({'type': 'tool-output-available', **content_text})}\n\n"

    # Finish events
    elif content_type == "finish_reason":
        return f"data: {json.dumps({'type': 'finish'})}\n\n"

    # Error events
    elif content_type == "error" and isinstance(content_text, str):
        return f"data: {json.dumps({'type': 'error', 'errorText': content_text})}\n\n"

    # Reasoning signature (for Anthropic thinking models)
    elif content_type == "reasoning_signature" and isinstance(
        content_text, dict
    ):
        # This might be handled differently in the new protocol
        return f"data: {json.dumps({'type': 'data-reasoning-signature', 'data': content_text})}\n\n"

    else:
        # Default to text delta for unknown types
        if text_id is None:
            text_id = f"text_{uuid.uuid4().hex}"
        return f"data: {json.dumps({'type': 'text-delta', 'id': text_id, 'delta': str(content_text)})}\n\n"


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
                    "parameters": {
                        # Pydantic will raise validation errors if unknown keys are present
                        # So we only include necessary keys
                        "type": tool.parameters.get("type", "object"),
                        "properties": tool.parameters.get("properties", {}),
                        "required": tool.parameters.get("required", []),
                    },
                }
            ]
        }
        for tool in tools
    ]
