# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import uuid
from abc import ABC, abstractmethod
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Literal,
    Optional,
    TypeVar,
    Union,
    cast,
)

from starlette.exceptions import HTTPException

from marimo import _loggers
from marimo._ai._convert import (
    convert_to_ai_sdk_messages,
    convert_to_anthropic_messages,
    convert_to_anthropic_tools,
    convert_to_google_messages,
    convert_to_google_tools,
    convert_to_openai_messages,
    convert_to_openai_tools,
)
from marimo._ai._types import ChatMessage
from marimo._config.config import (
    AiConfig,
    CompletionConfig,
    CopilotMode,
    MarimoConfig,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._server.api.status import HTTPStatus

if TYPE_CHECKING:
    from anthropic import (  # type: ignore[import-not-found]
        Client,
        Stream as AnthropicStream,
    )
    from anthropic.types import (  # type: ignore[import-not-found]
        RawMessageStreamEvent,
    )
    from google.genai.client import (  # type: ignore[import-not-found]
        Client as GoogleClient,
    )
    from google.genai.types import (  # type: ignore[import-not-found]
        GenerateContentConfig,
        GenerateContentResponse,
    )

    # Used for Bedrock, unified interface for all models
    from litellm import (  # type: ignore[attr-defined]
        CustomStreamWrapper as LitellmStream,
    )
    from litellm.types.utils import (
        ModelResponseStream as LitellmStreamResponse,
    )
    from openai import (  # type: ignore[import-not-found]
        OpenAI,
        Stream as OpenAiStream,
    )
    from openai.types.chat import (  # type: ignore[import-not-found]
        ChatCompletionChunk,
    )

    from marimo._server.ai.tools import Tool


ResponseT = TypeVar("ResponseT")
StreamT = TypeVar("StreamT")
FinishReason = Literal["tool_calls", "stop"]

# Types for extract_content method return
DictContent = tuple[
    dict[str, Any], Literal["tool_call_start", "tool_call_end"]
]
TextContent = tuple[str, Literal["text", "reasoning", "tool_call_delta"]]
ExtractedContent = Union[TextContent, DictContent]

# Types for format_stream method parameter
FinishContent = tuple[FinishReason, Literal["finish_reason"]]
# StreamContent
StreamTextContent = tuple[str, Literal["text", "reasoning"]]
StreamDictContent = tuple[
    dict[str, Any],
    Literal["tool_call_start", "tool_call_end", "tool_call_delta"],
]
StreamContent = Union[StreamTextContent, StreamDictContent, FinishContent]

LOGGER = _loggers.marimo_logger()

DEFAULT_MAX_TOKENS = 4096
DEFAULT_MODEL = "gpt-4o-mini"


@dataclass
class StreamOptions:
    text_only: bool = False
    format_stream: bool = False


@dataclass
class AnyProviderConfig:
    base_url: Optional[str]
    api_key: str
    ssl_verify: Optional[bool] = None
    ca_bundle_path: Optional[str] = None
    client_pem: Optional[str] = None
    tools: list[Tool] = field(default_factory=list)

    @staticmethod
    def for_openai(config: AiConfig) -> AnyProviderConfig:
        if "open_ai" not in config:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="OpenAI config not found",
            )
        key = _get_key(config["open_ai"], "OpenAI")
        return AnyProviderConfig(
            base_url=_get_base_url(config["open_ai"]),
            api_key=key,
            ssl_verify=config["open_ai"].get("ssl_verify", True),
            ca_bundle_path=config["open_ai"].get("ca_bundle_path", None),
            client_pem=config["open_ai"].get("client_pem", None),
            tools=_get_tools(config.get("mode", "manual")),
        )

    @staticmethod
    def for_anthropic(config: AiConfig) -> AnyProviderConfig:
        if "anthropic" not in config:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Anthropic config not found",
            )
        key = _get_key(config["anthropic"], "Anthropic")
        return AnyProviderConfig(
            base_url=_get_base_url(config["anthropic"]),
            api_key=key,
            tools=_get_tools(config.get("mode", "manual")),
        )

    @staticmethod
    def for_google(config: AiConfig) -> AnyProviderConfig:
        if "google" not in config:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Google config not found",
            )
        key = _get_key(config["google"], "Google AI")
        return AnyProviderConfig(
            base_url=_get_base_url(config["google"]),
            api_key=key,
            tools=_get_tools(config.get("mode", "manual")),
        )

    @staticmethod
    def for_bedrock(config: AiConfig) -> AnyProviderConfig:
        if "bedrock" not in config:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Bedrock config not found",
            )
        key = _get_key(config["bedrock"], "Bedrock")
        return AnyProviderConfig(
            base_url=_get_base_url(config["bedrock"], "Bedrock"),
            api_key=key,
            tools=_get_tools(config.get("mode", "manual")),
        )

    @staticmethod
    def for_completion(config: CompletionConfig) -> AnyProviderConfig:
        key = _get_key(config, "AI completion")
        return AnyProviderConfig(
            base_url=_get_base_url(config),
            api_key=key,
            tools=[],  # Inline completion never uses tools
        )

    @staticmethod
    def for_model(model: str, config: AiConfig) -> AnyProviderConfig:
        if _model_is_anthropic(model):
            return AnyProviderConfig.for_anthropic(config)
        elif _model_is_google(model):
            return AnyProviderConfig.for_google(config)
        elif _model_is_bedrock(model):
            return AnyProviderConfig.for_bedrock(config)
        else:
            return AnyProviderConfig.for_openai(config)


def _get_key(config: Any, name: str) -> str:
    if name == "Bedrock":
        if "profile_name" in config:
            profile_name = config.get("profile_name", "")
            return f"profile:{profile_name}"
        elif (
            "aws_access_key_id" in config and "aws_secret_access_key" in config
        ):
            return f"{config['aws_access_key_id']}:{config['aws_secret_access_key']}"
        else:
            return ""
    if "api_key" in config:
        key = config["api_key"]
        if key:
            return cast(str, key)
    raise HTTPException(
        status_code=HTTPStatus.BAD_REQUEST,
        detail=f"{name} API key not configured",
    )


def _get_base_url(config: Any, name: str = "") -> Optional[str]:
    if name == "Bedrock":
        if "region_name" in config:
            return cast(str, config["region_name"])
        else:
            return None
    elif "base_url" in config:
        return cast(str, config["base_url"])
    return None


def _get_tools(mode: CopilotMode) -> list[Tool]:
    if mode == "ask":
        # TODO: add tools
        return []
    else:  # manual mode = no tools
        return []


class CompletionProvider(Generic[ResponseT, StreamT], ABC):
    """Base class for AI completion providers."""

    def __init__(self, model: str, config: AnyProviderConfig):
        self.model = model
        self.config = config

    @abstractmethod
    def stream_completion(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        max_tokens: int,
    ) -> StreamT:
        """Create a completion stream."""
        pass

    @abstractmethod
    def extract_content(
        self, response: ResponseT, tool_call_id: Optional[str] = None
    ) -> Optional[ExtractedContent]:
        """Extract content from a response chunk."""
        pass

    @abstractmethod
    def get_finish_reason(self, response: ResponseT) -> Optional[FinishReason]:
        """Get the stop reason for a response."""
        pass

    def format_stream(self, content: StreamContent) -> str:
        """Format a response into stream protocol string."""
        content_text, content_type = content
        if content_type in [
            "text",
            "reasoning",
            "tool_call_start",
            "tool_call_delta",
            "tool_call_end",
            "finish_reason",
        ]:
            return convert_to_ai_sdk_messages(content_text, content_type)
        return ""

    def collect_stream(self, response: StreamT) -> str:
        """Collect a stream into a single string."""
        return "".join(self.as_stream_response(response))

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
        """Create type-safe StreamContent tuple."""
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

        # Fallback - convert to string content
        content_str = self._content_to_string(content_data)
        return (content_str, "text")

    def validate_tool_call_args(
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
        self, response: StreamT, options: Optional[StreamOptions] = None
    ) -> Generator[str, None, None]:
        """Convert a stream to a generator of strings."""
        original_content = ""
        buffer = ""
        options = options or StreamOptions()

        # Tool info collected from the first chunk
        tool_call_id: Optional[str] = None
        tool_call_name: Optional[str] = None
        # Tool args collected from the tool_call_delta chunks
        tool_call_args: str = ""
        # Finish reason collected from the last chunk
        finish_reason: Optional[FinishReason] = None

        for chunk in cast(Generator[ResponseT, None, None], response):
            # Always check for finish reason first, before checking content
            # Some chunks (like RawMessageDeltaEvent) contain finish reasons but no extractable content
            # If we check content first, these chunks get skipped and finish reason is never detected
            finish_reason = self.get_finish_reason(chunk) or finish_reason

            content = self.extract_content(chunk, tool_call_id)
            if not content:
                continue

            content_data, content_type = content

            if options.text_only and content_type != "text":
                continue

            # Tool handling
            if content_type == "tool_call_start" and isinstance(
                content_data, dict
            ):
                tool_call_id = content_data.get("toolCallId", None)
                tool_call_name = content_data.get("toolName", None)
                # Sometimes GoogleProvider emits the args in the tool_call_start chunk
                if content_data.get("args"):
                    # don't yield args in tool_call_start chunk
                    # it will throw an error in ai-sdk-ui
                    tool_call_args = content_data.pop("args")

            if content_type == "tool_call_delta" and isinstance(
                content_data, str
            ):
                if isinstance(self, GoogleProvider):
                    # For GoogleProvider, each chunk contains the full (possibly updated) args dict as a JSON string.
                    # Example: first chunk: {"location": "San Francisco"}
                    #          second chunk: {"location": "San Francisco", "zip": "94107"}
                    # We overwrite tool_call_args with the latest chunk.
                    tool_call_args = content_data
                else:
                    # For other providers, tool_call_args is built up incrementally from deltas.
                    tool_call_args += content_data
                # update tool_call_delta to ai-sdk-ui structure
                # based on https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol#tool-call-delta-part
                content_data = {
                    "toolCallId": tool_call_id,
                    "argsTextDelta": content_data,
                }

            content_str = self._content_to_string(content_data)

            if options.format_stream:
                stream_content = self._create_stream_content(
                    content_data, content_type
                )
                content_str = self.format_stream(stream_content)

            buffer += content_str
            original_content += content_str

            yield buffer
            buffer = ""

        # Handle tool call end after the stream is complete
        if tool_call_id and tool_call_name and not options.text_only:
            content_data = {
                "toolCallId": tool_call_id,
                "toolName": tool_call_name,
                "args": self.validate_tool_call_args(tool_call_args)
                or {},  # empty object if tool doesnt have args
            }
            content_type = "tool_call_end"
            yield self.format_stream((content_data, content_type))
            # Reset tool call state for next stream just in case
            tool_call_id = None
            tool_call_name = None
            tool_call_args = ""

        # Add a final finish reason chunk
        if finish_reason and not options.text_only:
            finish_content: FinishContent = (finish_reason, "finish_reason")
            yield self.format_stream(finish_content)
            # reset finish reason for next stream
            finish_reason = None

        LOGGER.debug(f"Completion content: {original_content}")


class OpenAIProvider(
    CompletionProvider[
        "ChatCompletionChunk", "OpenAiStream[ChatCompletionChunk]"
    ]
):
    # Medium effort provides a balance between speed and accuracy
    # https://openai.com/index/openai-o3-mini/
    DEFAULT_REASONING_EFFORT = "medium"

    def is_reasoning_model(self, model: str) -> bool:
        # only o-series models support reasoning
        return model.startswith("o")

    def get_client(self, config: AnyProviderConfig) -> OpenAI:
        DependencyManager.openai.require(why="for AI assistance with OpenAI")

        import ssl

        # library to check if paths exists
        from pathlib import Path
        from urllib.parse import parse_qs, urlparse

        # ssl related libs, httpx is a dependency of openai
        import httpx
        from openai import AzureOpenAI, OpenAI

        base_url = config.base_url or None
        key = config.api_key

        # Add SSL parameters/values
        ssl_verify: bool = config.ssl_verify or True
        ca_bundle_path: Optional[str] = config.ca_bundle_path
        client_pem: Optional[str] = config.client_pem

        # Check if ca_bundle_path and client_pem are valid files
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
        # Azure OpenAI clients are instantiated slightly differently
        parsed_url = urlparse(base_url)
        if parsed_url.hostname and cast(str, parsed_url.hostname).endswith(
            ".openai.azure.com"
        ):
            deployment_model = cast(str, parsed_url.path).split("/")[3]
            api_version = parse_qs(cast(str, parsed_url.query))["api-version"][
                0
            ]
            return AzureOpenAI(
                api_key=key,
                api_version=api_version,
                azure_deployment=deployment_model,
                azure_endpoint=f"{cast(str, parsed_url.scheme)}://{cast(str, parsed_url.hostname)}",
            )
        else:
            # the default httpx client uses ssl_verify=True by default under the hoood. We are checking if it's here, to see if the user overrides and uses false. If the ssl_verify argument isn't there, it is true by default
            if ssl_verify:
                ctx = None  # Initialize ctx to avoid UnboundLocalError
                client = None  # Initialize client to avoid UnboundLocalError
                if ca_bundle_path:
                    ctx = ssl.create_default_context(cafile=ca_bundle_path)
                if client_pem:
                    # if ctx already exists from caBundlePath argument
                    if ctx:
                        ctx.load_cert_chain(certfile=client_pem)
                    else:
                        ctx = ssl.create_default_context()
                        ctx.load_cert_chain(certfile=client_pem)

                # if ssl context was created by the above statements
                if ctx:
                    client = httpx.Client(verify=ctx)
                else:
                    pass
            else:
                client = httpx.Client(verify=False)

            # if client is created, either with a custom context or with verify=False, use it as the http_client object in `OpenAI`
            if client:
                return OpenAI(
                    default_headers={"api-key": key},
                    api_key=key,
                    base_url=base_url,
                    http_client=client,
                )
            # if not, return bog standard OpenAI object
            else:
                return OpenAI(
                    default_headers={"api-key": key},
                    api_key=key,
                    base_url=base_url,
                )

    def stream_completion(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        max_tokens: int,
    ) -> OpenAiStream[ChatCompletionChunk]:
        client = self.get_client(self.config)
        create_params = {
            "model": self.model,
            "messages": cast(
                Any,
                convert_to_openai_messages(
                    self._maybe_convert_roles(
                        [ChatMessage(role="system", content=system_prompt)]
                    )
                    + messages
                ),
            ),
            "max_completion_tokens": max_tokens,
            "stream": True,
            "timeout": 15,
            "tools": convert_to_openai_tools(self.config.tools),
        }
        if self.is_reasoning_model(self.model):
            create_params["reasoning_effort"] = self.DEFAULT_REASONING_EFFORT
        return cast(
            "OpenAiStream[ChatCompletionChunk]",
            client.chat.completions.create(**create_params),
        )

    def extract_content(
        self,
        response: ChatCompletionChunk,
        _tool_call_id: Optional[str] = None,
    ) -> Optional[ExtractedContent]:
        if (
            hasattr(response, "choices")
            and response.choices
            and response.choices[0].delta
        ):
            delta = response.choices[0].delta

            # Text content
            content = delta.content
            if content:
                return (content, "text")

            # Tool call:
            if delta.tool_calls:
                tool_calls = delta.tool_calls[0]

                # Start of tool call
                # id is only present for the first tool call chunk
                if (
                    tool_calls.id
                    and tool_calls.function
                    and tool_calls.function.name
                ):
                    tool_info = {
                        "toolCallId": tool_calls.id,
                        "toolName": tool_calls.function.name,
                    }
                    return (tool_info, "tool_call_start")

                # Delta of tool call
                # arguments is only present second chunk onwards
                if tool_calls.function and tool_calls.function.arguments:
                    return (tool_calls.function.arguments, "tool_call_delta")

        return None

    def get_finish_reason(
        self, response: ChatCompletionChunk
    ) -> Optional[FinishReason]:
        if (
            hasattr(response, "choices")
            and response.choices
            and response.choices[0].finish_reason
        ):
            return (
                "tool_calls"
                if response.choices[0].finish_reason == "tool_calls"
                else "stop"
            )
        return None

    def _maybe_convert_roles(
        self, messages: list[ChatMessage]
    ) -> list[ChatMessage]:
        # https://community.openai.com/t/o1-models-do-not-support-system-role-in-chat-completion/953880/3
        if self.model.startswith("o1") or self.model.startswith("o3"):

            def update_role(message: ChatMessage) -> ChatMessage:
                if message.role == "system":
                    return ChatMessage(role="user", content=message.content)
                return message

            return [update_role(message) for message in messages]

        return messages


class AnthropicProvider(
    CompletionProvider[
        "RawMessageStreamEvent", "AnthropicStream[RawMessageStreamEvent]"
    ]
):
    # Temperature of 0.2 was recommended for coding and data science in these links:
    # https://community.openai.com/t/cheat-sheet-mastering-temperature-and-top-p-in-chatgpt-api/172683
    # https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-latency?utm_source=chatgpt.com
    DEFAULT_TEMPERATURE = 0.2

    # Extended thinking defaults based on:
    # https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
    # Extended thinking requires temperature of 1
    DEFAULT_EXTENDED_THINKING_TEMPERATURE = 1
    EXTENDED_THINKING_MODEL_PREFIXES = [
        "claude-opus-4",
        "claude-sonnet-4",
        "claude-3-7-sonnet",
    ]
    # 1024 tokens is the minimum budget for extended thinking
    DEFAULT_EXTENDED_THINKING_BUDGET_TOKENS = 1024

    def is_extended_thinking_model(self, model: str) -> bool:
        return any(
            model.startswith(prefix)
            for prefix in self.EXTENDED_THINKING_MODEL_PREFIXES
        )

    def get_temperature(self) -> float:
        return (
            self.DEFAULT_EXTENDED_THINKING_TEMPERATURE
            if self.is_extended_thinking_model(self.model)
            else self.DEFAULT_TEMPERATURE
        )

    def get_client(self, config: AnyProviderConfig) -> Client:
        DependencyManager.anthropic.require(
            why="for AI assistance with Anthropic"
        )
        from anthropic import Client

        return Client(api_key=config.api_key)

    def stream_completion(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        max_tokens: int,
    ) -> AnthropicStream[RawMessageStreamEvent]:
        client = self.get_client(self.config)
        create_params = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": cast(
                Any,
                convert_to_anthropic_messages(messages),
            ),
            "tools": convert_to_anthropic_tools(self.config.tools),
            "system": system_prompt,
            "stream": True,
            "temperature": self.get_temperature(),
        }
        if self.is_extended_thinking_model(self.model):
            create_params["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.DEFAULT_EXTENDED_THINKING_BUDGET_TOKENS,
            }
        return cast(
            "AnthropicStream[RawMessageStreamEvent]",
            client.messages.create(**create_params),
        )

    def extract_content(
        self,
        response: RawMessageStreamEvent,
        _tool_call_id: Optional[str] = None,
    ) -> Optional[ExtractedContent]:
        from anthropic.types import (
            InputJSONDelta,
            RawContentBlockDeltaEvent,
            RawContentBlockStartEvent,
            TextDelta,
            ThinkingDelta,
            ToolUseBlock,
        )

        # # For content blocks
        # if isinstance(response, TextDelta):
        #     return (response.text, "text")
        # if isinstance(response, ThinkingDelta):
        #     return (response.thinking, "reasoning")
        # if isinstance(response, InputJSONDelta):
        #     return (response.partial_json, "tool_call_delta")

        # For streaming content
        if isinstance(response, RawContentBlockDeltaEvent):
            if isinstance(response.delta, TextDelta):
                return (response.delta.text, "text")
            if isinstance(response.delta, ThinkingDelta):
                return (response.delta.thinking, "reasoning")
            if isinstance(response.delta, InputJSONDelta):
                return (response.delta.partial_json, "tool_call_delta")

        # For the beginning of a tool use block
        if isinstance(response, RawContentBlockStartEvent):
            if isinstance(response.content_block, ToolUseBlock):
                tool_info = {
                    "toolCallId": response.content_block.id,
                    "toolName": response.content_block.name,
                }
                return (tool_info, "tool_call_start")

        return None

    def get_finish_reason(
        self, response: RawMessageStreamEvent
    ) -> Optional[FinishReason]:
        from anthropic.types import RawMessageDeltaEvent

        # Check for message_delta events which contain the stop_reason
        if isinstance(response, RawMessageDeltaEvent):
            if (
                hasattr(response, "delta")
                and hasattr(response.delta, "stop_reason")
                and response.delta.stop_reason
            ):
                stop_reason = response.delta.stop_reason
                # Anthropic uses "end_turn" for normal completion, "tool_use" for tool calls
                return "tool_calls" if stop_reason == "tool_use" else "stop"

        return None


class GoogleProvider(
    CompletionProvider["GenerateContentResponse", "GenerateContentResponse"]
):
    # Based on the docs:
    # https://cloud.google.com/vertex-ai/generative-ai/docs/thinking
    THINKING_MODEL_PREFIXES = [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
    ]

    def is_thinking_model(self, model: str) -> bool:
        return any(
            model.startswith(prefix) for prefix in self.THINKING_MODEL_PREFIXES
        )

    def get_config(
        self, system_prompt: str, max_tokens: int
    ) -> GenerateContentConfig:
        config = {
            "system_instruction": system_prompt,
            "temperature": 0,
            "max_output_tokens": max_tokens,
            "tools": convert_to_google_tools(self.config.tools),
        }
        if self.is_thinking_model(self.model):
            config["thinking_config"] = {
                "include_thoughts": True,
            }
        return cast("GenerateContentConfig", config)

    def get_client(self, config: AnyProviderConfig) -> GoogleClient:
        try:
            from google import genai
        except ImportError:
            DependencyManager.google_ai.require(
                why="for AI assistance with Google AI"
            )
            from google import genai  # type: ignore

        return genai.Client(api_key=config.api_key)

    def stream_completion(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        max_tokens: int,
    ) -> Iterator[GenerateContentResponse]:
        client = self.get_client(self.config)
        return cast(
            "Iterator[GenerateContentResponse]",
            client.models.generate_content_stream(
                model=self.model,
                contents=convert_to_google_messages(messages),
                config=self.get_config(
                    system_prompt=system_prompt, max_tokens=max_tokens
                ),
            ),
        )

    def _get_tool_call_id(self, tool_call_id: Optional[str]) -> Optional[str]:
        # Custom tools don't have an id, so we have to generate a random uuid
        # https://ai.google.dev/gemini-api/docs/function-calling?example=meeting
        if not tool_call_id:
            # generate a random uuid
            return str(uuid.uuid4())
        return tool_call_id

    def extract_content(
        self,
        response: GenerateContentResponse,
        tool_call_id: Optional[str] = None,
    ) -> Optional[ExtractedContent]:
        if not response.candidates:
            return None

        candidate = response.candidates[0]
        if not candidate or not candidate.content:
            return None

        if not candidate.content.parts:
            return None

        for part in candidate.content.parts:
            # Start of tool call
            # GoogleProvider may emit the function_call object in every chunk, not just the first.
            # We use tool_call_id to ensure we only emit one tool_call_start event per tool call.
            if part.function_call and not tool_call_id:
                tool_info = {
                    "toolCallId": self._get_tool_call_id(
                        part.function_call.id
                    ),
                    "toolName": part.function_call.name,
                    "args": json.dumps(part.function_call.args),
                }
                return (tool_info, "tool_call_start")
            # Tool call args (not delta)
            elif part.function_call and part.function_call.args:
                return (json.dumps(part.function_call.args), "tool_call_delta")

            # Skip non-text content
            elif part.text:
                # Reasoning content
                if part.thought:
                    return (part.text, "reasoning")
                else:
                    return (part.text, "text")
            else:
                continue
        return None

    def get_finish_reason(
        self, response: GenerateContentResponse
    ) -> Optional[FinishReason]:
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    return "tool_calls"
        if response.candidates and response.candidates[0].finish_reason:
            return "stop"
        return None


class BedrockProvider(
    CompletionProvider[
        "LitellmStreamResponse",
        "LitellmStream",
    ]
):
    def setup_credentials(self, config: AnyProviderConfig) -> None:
        # Use profile name if provided, otherwise use API key
        try:
            if config.api_key.startswith("profile:"):
                profile_name = config.api_key.replace("profile:", "")
                os.environ["AWS_PROFILE"] = profile_name
            elif len(config.api_key) > 0:
                # If access_key_id and secret_access_key is provided directly, use it
                aws_access_key_id = config.api_key.split(":")[0]
                aws_secret_access_key = config.api_key.split(":")[1]
                os.environ["AWS_ACCESS_KEY_ID"] = aws_access_key_id
                os.environ["AWS_SECRET_ACCESS_KEY"] = aws_secret_access_key
        except Exception as e:
            LOGGER.error(f"{config} Error setting up AWS credentials: {e}")
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Error setting up AWS credentials",
            ) from e

    def stream_completion(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        max_tokens: int,
    ) -> LitellmStream:
        DependencyManager.litellm.require(why="for AI assistance with Bedrock")
        DependencyManager.boto3.require(why="for AI assistance with Bedrock")
        from litellm import completion as litellm_completion

        self.setup_credentials(self.config)

        return litellm_completion(
            model=self.model,
            messages=cast(
                Any,
                convert_to_openai_messages(
                    [ChatMessage(role="system", content=system_prompt)]
                    + messages
                ),
            ),
            max_completion_tokens=max_tokens,
            stream=True,
            timeout=15,
            tools=convert_to_openai_tools(self.config.tools),
        )

    def extract_content(
        self,
        response: LitellmStreamResponse,
        _tool_call_id: Optional[str] = None,
    ) -> Optional[ExtractedContent]:
        if (
            hasattr(response, "choices")
            and response.choices
            and response.choices[0].delta
        ):
            delta = response.choices[0].delta

            # Text content
            content = delta.content
            if content:
                return (str(content), "text")

            # Tool call: LiteLLM follows OpenAI format for tool calls
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                tool_calls = delta.tool_calls[0]

                # Start of tool call
                # id is only present for the first tool call chunk
                if hasattr(tool_calls, "id") and tool_calls.id:
                    tool_info = {
                        "toolCallId": tool_calls.id,
                        "toolName": tool_calls.function.name,
                    }
                    return (tool_info, "tool_call_start")

                # Delta of tool call
                # arguments is only present second chunk onwards
                if (
                    hasattr(tool_calls, "function")
                    and tool_calls.function
                    and hasattr(tool_calls.function, "arguments")
                    and tool_calls.function.arguments
                ):
                    return (tool_calls.function.arguments, "tool_call_delta")

        return None

    def get_finish_reason(
        self, response: LitellmStreamResponse
    ) -> Optional[FinishReason]:
        if (
            hasattr(response, "choices")
            and response.choices
            and response.choices[0].finish_reason
        ):
            return (
                "tool_calls"
                if response.choices[0].finish_reason == "tool_calls"
                else "stop"
            )
        return None


def _model_is_google(model: str) -> bool:
    return model.startswith("google") or model.startswith("gemini")


def _model_is_anthropic(model: str) -> bool:
    return model.startswith("claude")


def _model_is_bedrock(model: str) -> bool:
    return model.startswith("bedrock/")


def get_completion_provider(
    config: AnyProviderConfig, model: str
) -> CompletionProvider[Any, Any]:
    if _model_is_anthropic(model):
        return AnthropicProvider(model, config)
    elif _model_is_google(model):
        return GoogleProvider(model, config)
    elif _model_is_bedrock(model):
        return BedrockProvider(model, config)
    else:
        return OpenAIProvider(model, config)


def get_model(config: AiConfig) -> str:
    model: str = config.get("open_ai", {}).get("model", DEFAULT_MODEL)
    if not model:
        model = DEFAULT_MODEL
    return model


def get_max_tokens(config: MarimoConfig) -> int:
    if "ai" not in config:
        return DEFAULT_MAX_TOKENS
    if "max_tokens" not in config["ai"]:
        return DEFAULT_MAX_TOKENS
    return config["ai"]["max_tokens"]


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
