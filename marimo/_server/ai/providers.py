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

    # OpenAI reasoning effort configuration
    # Medium effort provides a balance between speed and accuracy
    # https://openai.com/index/openai-o3-mini/
    DEFAULT_REASONING_EFFORT = "medium"

    # Anthropic temperature configurations
    # Temperature of 0.2 was recommended for coding and data science in these links:
    # https://community.openai.com/t/cheat-sheet-mastering-temperature-and-top-p-in-chatgpt-api/172683
    # https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-latency?utm_source=chatgpt.com
    DEFAULT_TEMPERATURE = 0.2

    # Extended thinking defaults based on:
    # Extended thinking requires temperature of 1
    DEFAULT_EXTENDED_THINKING_TEMPERATURE = 1
    # 1024 tokens is the minimum budget for extended thinking
    DEFAULT_EXTENDED_THINKING_BUDGET_TOKENS = 1024

    # Thinking models configuration (provider-specific)
    # Anthropic extended thinking models that support temperature=1 and thinking budget
    # https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
    ANTHROPIC_EXTENDED_THINKING_MODEL_PREFIXES = [
        "anthropic/claude-opus-4-1",
        "anthropic/claude-opus-4",
        "anthropic/claude-sonnet-4",
        "anthropic/claude-3-7-sonnet",
    ]

    # Google thinking models that support thinking_config
    # Based on the docs: https://cloud.google.com/vertex-ai/generative-ai/docs/thinking
    GOOGLE_THINKING_MODEL_PREFIXES = [
        "google/gemini-2.5-pro",
        "google/gemini-2.5-flash",
        "google/gemini-2.5-flash-lite",
    ]

    def __init__(self, model: str, config: AnyProviderConfig):
        self.model = model
        self.config = config

    @classmethod
    def _is_openai_thinking_model(cls, model: str) -> bool:
        """Check if this is an OpenAI thinking model (o-series)."""
        return model.startswith("openai/o")

    @classmethod
    def _is_anthropic_thinking_model(cls, model: str) -> bool:
        """Check if this is an Anthropic extended thinking model."""
        return any(
            model.startswith(prefix)
            for prefix in cls.ANTHROPIC_EXTENDED_THINKING_MODEL_PREFIXES
        )

    @classmethod
    def _is_google_thinking_model(cls, model: str) -> bool:
        """Check if this is a Google thinking model."""
        return any(
            model.startswith(prefix)
            for prefix in cls.GOOGLE_THINKING_MODEL_PREFIXES
        )

    @classmethod
    def _get_temperature(cls, model: str) -> float:
        """Get the appropriate temperature for the model."""
        return (
            cls.DEFAULT_EXTENDED_THINKING_TEMPERATURE
            if cls._is_anthropic_thinking_model(model)
            else cls.DEFAULT_TEMPERATURE
        )

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

    def _validate_provider_dependencies(self) -> None:
        """Validate provider dependencies."""
        DependencyManager.any_llm.require("for AI completions.")

        if self.model.startswith("google/"):
            DependencyManager.google_ai.require(
                "to use Google for AI completions."
            )
        elif self.model.startswith("openai/") or self.model.startswith(
            "openai_compatible/"
        ):
            DependencyManager.openai.require(
                "to use OpenAI for AI completions."
            )
        elif self.model.startswith("anthropic/"):
            DependencyManager.anthropic.require(
                "to use Anthropic for AI completions."
            )
        elif self.model.startswith("ollama/"):
            DependencyManager.ollama.require(
                "to use Ollama for AI completions."
            )
        elif self.model.startswith("bedrock/"):
            DependencyManager.boto3.require(
                "to use Bedrock for AI completions."
            )

    def as_stream_response(
        self,
        response: Iterator[ChatCompletionChunk],
        options: Optional[StreamOptions] = None,
    ) -> Generator[str, None, None]:
        """Convert a stream to a generator of strings."""
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
        self._validate_provider_dependencies()

        import any_llm

        # Prepare parameters
        formatted_messages = self._prepare_messages(messages, system_prompt)
        tools = self._prepare_tools()

        # Build completion parameters
        additional_params: dict[str, Any] = {
            "api_timeout": 15,
            "max_tokens": max_tokens,
            # Default, will be overridden by provider-specific config
            "temperature": self.DEFAULT_TEMPERATURE,
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

        # Apply model-specific configurations
        self._configure_openai_params(additional_params)
        self._configure_anthropic_params(additional_params)
        self._configure_google_params(additional_params)

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

    def _create_ssl_http_client(self) -> Optional[Any]:
        """Create custom HTTP client for SSL/PEM configuration (OpenAI-compatible providers)."""
        import ssl
        from pathlib import Path

        import httpx

        # SSL parameters
        ssl_verify: bool = (
            self.config.ssl_verify
            if self.config.ssl_verify is not None
            else True
        )
        ca_bundle_path: Optional[str] = self.config.ca_bundle_path
        client_pem: Optional[str] = self.config.client_pem

        # Validate SSL file paths
        if ca_bundle_path:
            ca_path = Path(ca_bundle_path)
            if not ca_path.exists():
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail="CA Bundle is not a valid path or does not exist",
                )

        if client_pem:
            client_pem_path = Path(client_pem)
            if not client_pem_path.exists():
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail="Client PEM is not a valid path or does not exist",
                )

        # Create SSL context and client if needed
        if ssl_verify:
            ctx = None
            if ca_bundle_path:
                ctx = ssl.create_default_context(cafile=ca_bundle_path)
            if client_pem:
                if ctx:
                    ctx.load_cert_chain(certfile=client_pem)
                else:
                    ctx = ssl.create_default_context()
                    ctx.load_cert_chain(certfile=client_pem)

            # Return custom client if SSL context was created
            if ctx:
                return httpx.Client(verify=ctx)
        else:
            # Return client with SSL verification disabled
            return httpx.Client(verify=False)

        return None

    def _configure_openai_params(self, params: dict[str, Any]) -> None:
        """Configure OpenAI-specific parameters."""
        if not (
            self.model.startswith("openai/")
            or self.model.startswith("openai_compatible/")
        ):
            return

        # Add custom HTTP client for SSL/PEM configuration
        # This applies to both openai/ and openai_compatible/ providers
        http_client = self._create_ssl_http_client()
        if http_client:
            params["http_client"] = http_client

        # OpenAI-specific features (only for openai/ models)
        if self.model.startswith("openai/") and self._is_openai_thinking_model(
            self.model
        ):
            params["reasoning_effort"] = self.DEFAULT_REASONING_EFFORT
            params.pop("temperature", None)
            # OpenAI thinking models don't accept max_tokens
            params.pop("max_tokens", None)

    def _configure_anthropic_params(self, params: dict[str, Any]) -> None:
        """Configure Anthropic-specific parameters."""
        if not self.model.startswith("anthropic/"):
            return

        # Override temperature for Anthropic models
        params["temperature"] = self._get_temperature(self.model)

        # Add extended thinking configuration for supported models
        if self._is_anthropic_thinking_model(self.model):
            params["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.DEFAULT_EXTENDED_THINKING_BUDGET_TOKENS,
            }

    def _configure_google_params(self, params: dict[str, Any]) -> None:
        """Configure Google-specific parameters."""
        if not self.model.startswith("google/"):
            return

        # Google models use fixed temperature
        params["temperature"] = 0
        # Google models don't accept max_tokens or api_timeout
        params.pop("max_tokens", None)
        params.pop("api_timeout", None)

        # Add thinking config for supported models
        if self._is_google_thinking_model(self.model):
            params["thinking_config"] = {
                "include_thoughts": True,
            }


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
