# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    Optional,
    TypedDict,
    Union,
    cast,
)

from starlette.exceptions import HTTPException

from marimo import _loggers
from marimo._ai._convert import (
    convert_to_ai_sdk_messages,
)
from marimo._ai._types import ChatMessage
from marimo._dependencies.dependencies import DependencyManager
from marimo._server.ai.config import AnyProviderConfig
from marimo._server.api.status import HTTPStatus

if TYPE_CHECKING:
    from openai.types.chat import (  # type: ignore[import-not-found]
        ChatCompletionChunk,
    )

FinishReason = Literal[
    "stop", "length", "tool_calls", "content_filter", "function_call"
]

# Types for extract_content method return
DictContent = tuple[
    dict[str, Any],
    Literal["tool_call_start", "tool_call_end", "reasoning_signature"],
]
TextContent = tuple[str, Literal["text", "reasoning", "tool_call_delta"]]
ExtractedContent = Union[TextContent, DictContent]

# Types for format_stream method parameter
FinishContent = tuple[FinishReason, Literal["finish_reason"]]
# StreamContent
StreamTextContent = tuple[str, Literal["text", "reasoning"]]
StreamDictContent = tuple[
    dict[str, Any],
    Literal[
        "tool_call_start",
        "tool_call_end",
        "tool_result",
        "tool_call_delta",
        "reasoning_signature",
    ],
]
StreamContent = Union[StreamTextContent, StreamDictContent, FinishContent]


class TypedToolFunction(TypedDict):
    """Typed tool dict for any-llm."""

    name: str
    description: str
    parameters: dict[str, Any]


class TypedToolDict(TypedDict):
    """Typed tool dict for any-llm."""

    type: Literal["function"]
    function: TypedToolFunction


class DraftToolCall(TypedDict):
    id: str
    name: str
    arguments: str


LOGGER = _loggers.marimo_logger()


@dataclass
class StreamOptions:
    """Options for streaming a response.

    Args:
        text_only: Whether to only stream text content. StreamDictContent (e.g. tools and reasoning) are dropped.
        format_stream: Whether to format the stream into a string.
    """

    text_only: bool = False
    format_stream: bool = False


class AnyLLMProvider:
    """Unified provider using any-llm library for all LLM providers."""

    def __init__(self, model: str, config: AnyProviderConfig):
        self.model = model
        self.config = config

    def _format_stream(self, content: StreamContent) -> str:
        """Format a response into stream protocol string."""
        content_text, content_type = content
        if content_type in [
            "text",
            "reasoning",
            "reasoning_signature",
            "tool_call_start",
            "tool_call_delta",
            "tool_call_end",
            "tool_result",
            "finish_reason",
        ]:
            return convert_to_ai_sdk_messages(content_text, content_type)
        return ""

    def collect_stream(self, response: Iterator[ChatCompletionChunk]) -> str:
        """Collect a stream into a single string."""
        return "".join(
            self.as_stream_response(response, StreamOptions(text_only=True))
        )

    def _content_to_string(
        self, content_data: Union[str, dict[str, Any]]
    ) -> str:
        """Convert content data to string for buffer operations."""
        return (
            json.dumps(content_data)
            if isinstance(content_data, dict)
            else str(content_data)
        )

    def _create_stream_content(
        self, content_data: Union[str, dict[str, Any]], content_type: str
    ) -> StreamContent:
        """Create type-safe StreamContent tuple for format_stream method."""
        # String content types
        if isinstance(content_data, str):
            if content_type == "text":
                return (content_data, "text")
            elif content_type == "reasoning":
                return (content_data, "reasoning")

        # Dict content types
        if isinstance(content_data, dict):
            if content_type == "tool_call_start":
                return (content_data, "tool_call_start")
            elif content_type == "tool_call_end":
                return (content_data, "tool_call_end")
            elif content_type == "tool_call_delta":
                return (content_data, "tool_call_delta")
            elif content_type == "reasoning_signature":
                return (content_data, "reasoning_signature")

        # Fallback - convert to string content
        content_str = self._content_to_string(content_data)
        return (content_str, "text")

    def _validate_tool_call_args(
        self, tool_call_args: str
    ) -> Optional[dict[str, Any]]:
        """Validate tool call arguments."""
        if not tool_call_args:
            return None
        try:
            result = (
                json.loads(tool_call_args)
                if isinstance(tool_call_args, str)
                else tool_call_args
            )
            return result if isinstance(result, dict) else None
        except Exception as e:
            LOGGER.error(
                f"Failed to parse tool call arguments: {tool_call_args} (error: {e})"
            )
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Invalid tool call arguments: malformed JSON: {tool_call_args}",
            ) from e

    def as_stream_response(
        self,
        response: Iterator[ChatCompletionChunk],
        options: Optional[StreamOptions] = None,
    ) -> Generator[str, None, None]:
        """Convert a stream to a generator of strings."""
        # original_content = ""
        # buffer = ""
        options = options or StreamOptions()

        draft_tool_calls: list[DraftToolCall] = []
        draft_tool_calls_index = -1
        available_tools: dict[str, Callable[..., Any]] = {}

        # If text_only is True, we only yield text content
        if options.text_only:
            for chunk in response:
                for choice in chunk.choices:
                    if choice.delta.content:
                        yield choice.delta.content
            return

        if not options.format_stream and options.text_only:
            LOGGER.warning(
                "format_stream=False is not supported for text_only=True"
            )

        for chunk in response:
            # If the chunk has no choices, it's a finish reason
            if not chunk.choices:
                yield self._format_stream(
                    (
                        "tool_calls" if len(draft_tool_calls) > 0 else "stop",
                        "finish_reason",
                    )
                )
                return

            choice = chunk.choices[0]

            # If the chunk has a finish reason, yield it
            if choice.finish_reason == "stop":
                yield self._format_stream(
                    (
                        "tool_calls" if len(draft_tool_calls) > 0 else "stop",
                        "finish_reason",
                    )
                )
                return

            # Handle tool calls
            if choice.finish_reason == "tool_calls":
                for tool_call in draft_tool_calls:
                    yield self._format_stream(
                        (
                            {
                                "toolCallId": tool_call["id"],
                                "toolName": tool_call["name"],
                                "args": tool_call["arguments"],
                            },
                            "tool_call_end",
                        )
                    )

                for tool_call in draft_tool_calls:
                    if tool_call["name"] in available_tools:
                        tool_result: Any = available_tools[tool_call["name"]](
                            **json.loads(tool_call["arguments"])
                        )

                        yield self._format_stream(
                            (
                                {
                                    "toolCallId": tool_call["id"],
                                    "toolName": tool_call["name"],
                                    "args": tool_call["arguments"],
                                    "result": json.dumps(tool_result),
                                },
                                "tool_result",
                            )
                        )

            elif choice.delta.tool_calls:
                # Collect tool call args
                for tool_call in choice.delta.tool_calls:
                    if not tool_call.function:
                        continue

                    tool_id: str | None = tool_call.id
                    name = tool_call.function.name
                    arguments = tool_call.function.arguments

                    if tool_id is not None:
                        draft_tool_calls_index += 1
                        draft_tool_calls.append(
                            {
                                "id": tool_id,
                                "name": name or "unknown",
                                "arguments": "",
                            }
                        )
                    else:
                        draft_tool_calls[draft_tool_calls_index][
                            "arguments"
                        ] += arguments or ""

            else:
                if choice.delta.content:
                    yield self._format_stream((choice.delta.content, "text"))

    def _prepare_messages(
        self, messages: list[ChatMessage], system_prompt: str
    ) -> list[dict[str, Any]]:
        """Convert ChatMessage objects to any-llm format."""
        formatted_messages: list[dict[str, Any]] = []

        # Add system message if provided
        if system_prompt:
            formatted_messages.append(
                {"role": "system", "content": system_prompt}
            )

        # Convert ChatMessage objects to dict format
        for msg in messages:
            formatted_messages.append(
                {"role": msg.role, "content": msg.content}
            )

        return formatted_messages

    def _prepare_tools(self) -> Optional[list[TypedToolDict]]:
        """Convert tools to any-llm format."""
        if not self.config.tools:
            return None

        # Convert tools from marimo format to OpenAI format
        # Since any-llm uses OpenAI-compatible tool format
        tools: list[TypedToolDict] = []
        for tool in self.config.tools:
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return tools

    def stream_completion(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        max_tokens: int,
    ) -> Iterator[ChatCompletionChunk]:
        DependencyManager.any_llm.require("for AI completions.")

        import any_llm

        # TODO: checks based on the provider

        # Prepare parameters
        formatted_messages = self._prepare_messages(messages, system_prompt)
        tools = self._prepare_tools()

        # Build completion parameters
        additional_params: dict[str, Any] = {
            "api_timeout": 15,
            "max_tokens": max_tokens,
        }

        # Add tools if available
        if tools:
            additional_params["tools"] = tools

        # Add API key if available
        if self.config.api_key:
            additional_params["api_key"] = self.config.api_key

        # Add base URL if available
        if self.config.base_url:
            additional_params["api_base"] = self.config.base_url

        # Gemini does not like max_tokens or api_timeout
        if self.model.startswith("google/"):
            additional_params.pop("max_tokens")
            additional_params.pop("api_timeout")

        # Thinking models do not like max_tokens
        if self.model.startswith("openai/o"):
            additional_params.pop("max_tokens")

        try:
            response = any_llm.completion(
                model=self.model,
                messages=formatted_messages,
                stream=True,
                **additional_params,
            )
            return cast(Iterator["ChatCompletionChunk"], response)
        except Exception as e:
            LOGGER.error(f"AI request failed: {e}")
            raise HTTPException(
                status_code=HTTPStatus.SERVER_ERROR,
                detail=f"AI request failed: {str(e)}",
            ) from e

    def _get_finish_reason(
        self, response: ChatCompletionChunk
    ) -> Optional[FinishReason]:
        if not response.choices:
            return None
        return response.choices[0].finish_reason


def get_completion_provider(
    config: AnyProviderConfig, model: str
) -> AnyLLMProvider:
    """Get a completion provider using any-llm unified interface."""
    return AnyLLMProvider(model, config)


# Utils


def merge_backticks(chunks: Iterator[str]) -> Generator[str, None, None]:
    buffer: Optional[str] = None

    for chunk in chunks:
        if buffer is None:
            buffer = chunk
        else:
            # If buffer contains backticks, keep merging until we have no backticks,
            # encounter a newline, or run out of chunks
            if "`" in buffer:
                buffer += chunk
                # If we've hit a newline or no more backticks, yield the buffer
                if "\n" in chunk or "`" not in buffer:
                    yield buffer
                    buffer = None
            else:
                # No backticks in buffer, yield it separately
                yield buffer
                buffer = chunk

    # Return the last chunk if there's anything left
    if buffer is not None:
        yield buffer


def without_wrapping_backticks(
    chunks: Iterator[str],
) -> Generator[str, None, None]:
    """
    Removes the first and last backticks (```) from a stream of text chunks.

    Args:
        chunks: An iterator of text chunks

    Yields:
        Text chunks with the first and last backticks removed if they exist
    """

    # First, merge backticks across chunks
    chunks = merge_backticks(chunks)

    langs = ["python", "sql"]

    first_chunk = True
    buffer: Optional[str] = None
    has_starting_backticks = False

    for chunk in chunks:
        # Handle the first chunk
        if first_chunk:
            first_chunk = False
            # Check for language-specific fences first
            for lang in langs:
                if chunk.startswith(f"```{lang}"):
                    has_starting_backticks = True
                    chunk = chunk[
                        3 + len(lang) :
                    ]  # Remove the starting backticks with lang
                    # Also remove starting newline if present
                    if chunk.startswith("\n"):
                        chunk = chunk[1:]
                    break
            # If no language-specific fence was found, check for plain backticks
            else:
                if chunk.startswith("```"):
                    has_starting_backticks = True
                    chunk = chunk[3:]  # Remove the starting backticks
                    # Also remove starting newline if present
                    if chunk.startswith("\n"):
                        chunk = chunk[1:]

        # If we have a buffered chunk, yield it now
        if buffer is not None:
            yield buffer

        # Store the current chunk as buffer for the next iteration
        buffer = chunk

    # Handle the last chunk
    if buffer is not None:
        # Remove ending newline if present
        if buffer.endswith("\n```"):
            buffer = buffer[:-4]  # Remove the ending newline and backticks
        elif has_starting_backticks and buffer.endswith("```"):
            buffer = buffer[:-3]  # Remove just the ending backticks
        yield buffer
