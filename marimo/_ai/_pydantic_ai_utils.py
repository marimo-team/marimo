# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import abc
import json
import uuid
from typing import TYPE_CHECKING, Any, Callable

from marimo import _loggers
from marimo._ai._types import (
    ChatMessage,
    DataReasoningPart,
    FilePart as ChatFilePart,
    ReasoningPart as ChatReasoningPart,
    TextPart as ChatTextPart,
    ToolInvocationPart as ChatToolInvocationPart,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.msgspec_encoder import asdict
from marimo._server.ai.tools.types import ToolDefinition
from marimo._utils.assert_never import log_never
from marimo._utils.data_uri import from_data_uri

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from pydantic_ai import (
        FunctionToolset,
        ModelMessage,
        ModelRequestPart,
        ModelResponsePart,
        UserContent,
    )

# Classes for converting chat events to AI SDK v5 data SSE events
# https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol#data-stream-protocol


class AiSdkPart(abc.ABC):
    @abc.abstractmethod
    def payload(self) -> dict[str, Any]:
        pass

    def to_str(self) -> str:
        return f"data: {json.dumps(self.payload())}\n\n"


class MessageStartPart(AiSdkPart):
    def __init__(self, message_id: str):
        self.message_id = message_id

    def payload(self) -> dict[str, Any]:
        return {"type": "start", "messageId": self.message_id}


class TextStartPart(AiSdkPart):
    def __init__(self, text_id: str):
        self.text_id = text_id

    def payload(self) -> dict[str, Any]:
        return {"type": "text-start", "id": self.text_id}


class TextDeltaPart(AiSdkPart):
    def __init__(self, text_id: str, delta: str):
        self.text_id = text_id
        self.delta = delta

    def payload(self) -> dict[str, Any]:
        return {"type": "text-delta", "id": self.text_id, "delta": self.delta}


class TextEndPart(AiSdkPart):
    def __init__(self, text_id: str):
        self.text_id = text_id

    def payload(self) -> dict[str, Any]:
        return {"type": "text-end", "id": self.text_id}


class ReasoningStartPart(AiSdkPart):
    def __init__(self, reasoning_id: str):
        self.reasoning_id = reasoning_id

    def payload(self) -> dict[str, Any]:
        return {"type": "reasoning-start", "id": self.reasoning_id}


class ReasoningDeltaPart(AiSdkPart):
    def __init__(self, reasoning_id: str, delta: str):
        self.reasoning_id = reasoning_id
        self.delta = delta

    def payload(self) -> dict[str, Any]:
        return {
            "type": "reasoning-delta",
            "id": self.reasoning_id,
            "delta": self.delta,
        }


class ReasoningEndPart(AiSdkPart):
    def __init__(self, reasoning_id: str):
        self.reasoning_id = reasoning_id

    def payload(self) -> dict[str, Any]:
        return {"type": "reasoning-end", "id": self.reasoning_id}


# Source Parts (reference to external content sources)
class SourceUrlPart(AiSdkPart):
    """References to external URLs"""

    def __init__(self, source_id: str, url: str):
        self.source_id = source_id
        self.url = url

    def payload(self) -> dict[str, Any]:
        return {
            "type": "source-url",
            "sourceId": self.source_id,
            "url": self.url,
        }


class SourceDocumentPart(AiSdkPart):
    """References to documents or files"""

    def __init__(self, source_id: str):
        self.source_id = source_id

    def payload(self) -> dict[str, Any]:
        return {
            "type": "source-document",
            "sourceId": self.source_id,
            "mediaType": "file",
        }


class FileSdkPart(AiSdkPart):
    def __init__(self, url: str, media_type: str):
        self.url = url
        self.media_type = media_type

    def payload(self) -> dict[str, Any]:
        return {"type": "file", "url": self.url, "mediaType": self.media_type}


class DataPart(AiSdkPart):
    def __init__(self, data_type: str, data: dict[str, Any]):
        if not data_type.startswith("data-"):
            LOGGER.warning(f"Data type must start with 'data-': {data_type}")

        self.data_type = data_type
        self.data = data

    def payload(self) -> dict[str, Any]:
        return {"type": self.data_type, "data": self.data}


class ErrorPart(AiSdkPart):
    def __init__(self, error_text: str):
        self.error_text = error_text

    def payload(self) -> dict[str, Any]:
        return {"type": "error", "errorText": self.error_text}


class ToolInputStartPart(AiSdkPart):
    def __init__(self, tool_name: str, tool_call_id: str):
        self.tool_call_id = tool_call_id
        self.tool_name = tool_name

    def payload(self) -> dict[str, Any]:
        return {
            "type": "tool-input-start",
            "toolCallId": self.tool_call_id,
            "toolName": self.tool_name,
        }


class ToolInputDeltaPart(AiSdkPart):
    def __init__(self, tool_call_id: str, input_text_delta: str):
        self.tool_call_id = tool_call_id
        self.input_text_delta = input_text_delta

    def payload(self) -> dict[str, Any]:
        return {
            "type": "tool-input-delta",
            "toolCallId": self.tool_call_id,
            "inputTextDelta": self.input_text_delta,
        }


class ToolInputAvailablePart(AiSdkPart):
    def __init__(
        self, tool_call_id: str, tool_name: str, tool_input: dict[str, Any]
    ):
        self.tool_call_id = tool_call_id
        self.tool_name = tool_name
        self.tool_input = tool_input

    def payload(self) -> dict[str, Any]:
        return {
            "type": "tool-input-available",
            "toolCallId": self.tool_call_id,
            "toolName": self.tool_name,
            "input": self.tool_input,
        }


class ToolOutputAvailablePart(AiSdkPart):
    def __init__(self, tool_call_id: str, output: dict[str, Any] | str):
        self.tool_call_id = tool_call_id
        self.output = output

    def payload(self) -> dict[str, Any]:
        return {
            "type": "tool-output-available",
            "toolCallId": self.tool_call_id,
            "output": self.output,
        }


class StartStepPart(AiSdkPart):
    def payload(self) -> dict[str, Any]:
        return {"type": "start-step"}


class FinishStepPart(AiSdkPart):
    def payload(self) -> dict[str, Any]:
        return {"type": "finish-step"}


class FinishMessagePart(AiSdkPart):
    def payload(self) -> dict[str, Any]:
        return {"type": "finish"}


class StreamTerminationPart(AiSdkPart):
    def to_str(self) -> str:
        return "data: [DONE]\n\n"


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def form_message_history(messages: list[ChatMessage]) -> list[ModelMessage]:
    """Convert marimo chat messages (AI SDK v5) to pydantic_ai messages"""

    DependencyManager.pydantic_ai.require(
        why="to convert messages to pydantic_ai messages"
    )
    from pydantic_ai import (
        ModelRequest,
        ModelResponse,
        SystemPromptPart,
        TextPart,
        ThinkingPart,
        ToolCallPart,
        UserPromptPart,
    )

    model_messages: list[ModelMessage] = []

    for message in messages:
        if message.role == "system":
            if not message.parts:
                LOGGER.error(f"System message without parts: {message}")
                continue
            model_request_parts = []
            for part in message.parts:
                if isinstance(part, ChatTextPart):
                    model_request_parts.append(
                        SystemPromptPart(content=part.text)
                    )
                else:
                    LOGGER.error(f"System message with non-text part: {part}")
                    continue
            model_messages.append(ModelRequest(parts=model_request_parts))

        elif message.role == "user":
            if not message.parts:
                LOGGER.error(f"User message without parts: {message}")
                continue

            request_parts: list[ModelRequestPart] = []
            for part in message.parts:
                if isinstance(part, ChatTextPart):
                    request_parts.append(UserPromptPart(content=part.text))
                elif isinstance(part, ChatFilePart):
                    file_content = handle_file_part(part)
                    if file_content is None:
                        LOGGER.debug(f"Failed to handle file part: {part}")
                        continue
                    request_parts.append(
                        UserPromptPart(content=[file_content])
                    )
                else:
                    LOGGER.warning(f"User message with non-text part: {part}")
                    continue
            model_messages.append(ModelRequest(parts=request_parts))

        elif message.role == "assistant":
            # Model response parts
            if not message.parts:
                LOGGER.error(f"Assistant message without parts: {message}")
                continue

            reasoning_signatures: list[str] = []
            response_parts: list[ModelResponsePart] = []

            for part in message.parts:
                if isinstance(part, ChatTextPart):
                    response_parts.append(TextPart(content=part.text))
                elif isinstance(part, ChatReasoningPart):
                    if part.details:
                        for detail in part.details:
                            response_parts.append(
                                ThinkingPart(
                                    content=detail.text,
                                    signature=detail.signature,
                                )
                            )
                    else:
                        # check if there is a signature
                        signature = None
                        if reasoning_signatures:
                            signature = reasoning_signatures.pop(0)
                        response_parts.append(
                            ThinkingPart(
                                content=part.text, signature=signature
                            )
                        )
                elif isinstance(part, DataReasoningPart):
                    reasoning_signatures.append(part.data.signature)
                elif isinstance(part, ChatToolInvocationPart):
                    response_parts.append(
                        ToolCallPart(
                            tool_name=part.tool_name,
                            args=part.input,
                            tool_call_id=part.tool_call_id,
                        )
                    )
                elif isinstance(part, ChatFilePart):
                    LOGGER.warning(f"FilePart not supported yet: {part}")
                else:
                    log_never(part)

            if response_parts:
                model_messages.append(ModelResponse(parts=response_parts))
        else:
            log_never(message.role)

    return model_messages


def handle_file_part(part: ChatFilePart) -> UserContent | None:
    from pydantic_ai import BinaryContent

    if part.url.startswith("data:"):
        try:
            _, byte_data = from_data_uri(part.url)
            return BinaryContent(data=byte_data, media_type=part.media_type)
        except Exception as e:
            LOGGER.error(f"Failed to decode data URL to bytes: {e}")
            return None
    else:
        LOGGER.warning(f"FilePart not supported yet: {part}")


def form_toolsets(
    tools: list[ToolDefinition],
    tool_invoker: Callable[[str, dict[str, Any]], Any],
) -> FunctionToolset:
    """
    Because we have a list of tool definitions and call them in a separate event loop,
    we create a toolset that will call the tool invoker for each tool.
    Ref: https://ai.pydantic.dev/toolsets/#function-toolset
    """
    from pydantic_ai import FunctionToolset

    toolset = FunctionToolset()

    for tool in tools:
        # Create a closure that captures the tool function
        async def tool_fn(_tool_name: str = tool.name, **kwargs: Any) -> Any:
            result = await tool_invoker(_tool_name, kwargs)
            # Convert to JSON-serializable object
            return asdict(result)

        tool_fn.__name__ = tool.name
        toolset.add_function(
            tool_fn, name=tool.name, description=tool.description
        )
    return toolset
