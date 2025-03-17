# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar, cast

from starlette.exceptions import HTTPException

from marimo import _loggers
from marimo._ai._convert import (
    convert_to_anthropic_messages,
    convert_to_google_messages,
    convert_to_openai_messages,
)
from marimo._ai._types import ChatMessage
from marimo._config.config import AiConfig, MarimoConfig
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
    from google.generativeai import (  # type: ignore[import-not-found]
        GenerativeModel,
    )
    from google.generativeai.types import (  # type: ignore[import-not-found]
        GenerateContentResponse,
    )
    from openai import (  # type: ignore[import-not-found]
        OpenAI,
        Stream as OpenAiStream,
    )
    from openai.types.chat import (  # type: ignore[import-not-found]
        ChatCompletionChunk,
    )


ResponseT = TypeVar("ResponseT")
StreamT = TypeVar("StreamT")

LOGGER = _loggers.marimo_logger()

DEFAULT_MAX_TOKENS = 4096
DEFAULT_MODEL = "gpt-4o-mini"


class CompletionProvider(Generic[ResponseT, StreamT], ABC):
    """Base class for AI completion providers."""

    def __init__(self, model: str, config: AiConfig):
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
    def extract_content(self, response: ResponseT) -> str | None:
        """Extract content from a response chunk."""
        pass

    def as_stream_response(
        self, response: StreamT
    ) -> Generator[str, None, None]:
        """Convert a stream to a generator of strings."""
        original_content = ""
        buffer = ""

        for chunk in cast(Generator[ResponseT, None, None], response):
            content = self.extract_content(chunk)
            if not content:
                continue

            buffer += content
            original_content += content

            yield buffer
            buffer = ""

        LOGGER.debug(f"Completion content: {original_content}")

    def collect_stream(self, response: StreamT) -> str:
        """Collect a stream into a single string."""
        return "".join(self.as_stream_response(response))

    def make_stream_response(
        self, response: StreamT
    ) -> Generator[str, None, None]:
        """Convert a stream to a generator of strings, handling code blocks."""
        original_content = ""
        buffer = ""
        in_code_fence = False

        for chunk in cast(Generator[ResponseT, None, None], response):
            content = self.extract_content(chunk)
            if not content:
                continue

            buffer += content
            original_content += content
            first_newline = buffer.find("\n")

            # Open code-fence, with no newline
            # wait for the next newline
            if (
                buffer.startswith("```")
                and first_newline == -1
                and not in_code_fence
            ):
                continue

            if (
                buffer.startswith("```")
                and first_newline > 0
                and not in_code_fence
            ):
                # And also ends with ```
                if buffer.endswith("```"):
                    yield buffer[first_newline + 1 : -3]
                    buffer = ""
                    in_code_fence = False
                    continue

                yield buffer[first_newline + 1 :]
                buffer = ""
                in_code_fence = True
                continue

            if buffer.endswith("```") and in_code_fence:
                yield buffer[:-3]
                buffer = ""
                in_code_fence = False
                continue

            yield buffer
            buffer = ""

        LOGGER.debug(f"Completion content: {original_content}")


class OpenAIProvider(
    CompletionProvider[
        "ChatCompletionChunk", "OpenAiStream[ChatCompletionChunk]"
    ]
):
    def get_client(self, config: AiConfig) -> OpenAI:
        DependencyManager.openai.require(why="for AI assistance with OpenAI")

        from urllib.parse import parse_qs, urlparse

        from openai import AzureOpenAI, OpenAI

        if "open_ai" not in config or "api_key" not in config["open_ai"]:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="OpenAI API key not configured",
            )

        key: str = config["open_ai"]["api_key"]
        if not key:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="OpenAI API key not configured",
            )

        base_url: Optional[str] = config["open_ai"].get("base_url", None)
        if not base_url:
            base_url = None

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
        return client.chat.completions.create(
            model=self.model,
            messages=cast(
                Any,
                convert_to_openai_messages(
                    [ChatMessage(role="system", content=system_prompt)]
                    + messages
                ),
            ),
            max_tokens=max_tokens,
            stream=True,
            timeout=15,
        )

    def extract_content(self, response: ChatCompletionChunk) -> str | None:
        if (
            hasattr(response, "choices")
            and response.choices
            and response.choices[0].delta
        ):
            return response.choices[0].delta.content
        return None


class AnthropicProvider(
    CompletionProvider[
        "RawMessageStreamEvent", "AnthropicStream[RawMessageStreamEvent]"
    ]
):
    def get_client(self, config: AiConfig) -> Client:
        DependencyManager.anthropic.require(
            why="for AI assistance with Anthropic"
        )
        from anthropic import Client

        if "anthropic" not in config or "api_key" not in config["anthropic"]:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Anthropic API key not configured",
            )

        key: str = config["anthropic"]["api_key"]
        if not key:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Anthropic API key not configured",
            )

        return Client(api_key=key)

    def stream_completion(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        max_tokens: int,
    ) -> AnthropicStream[RawMessageStreamEvent]:
        client = self.get_client(self.config)
        return client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=cast(
                Any,
                convert_to_anthropic_messages(messages),
            ),
            system=system_prompt,
            stream=True,
            temperature=0,
        )

    def extract_content(self, response: RawMessageStreamEvent) -> str | None:
        from anthropic.types import RawContentBlockDeltaEvent, TextDelta

        if isinstance(response, TextDelta):
            return response.text  # type: ignore

        if isinstance(response, RawContentBlockDeltaEvent):
            if isinstance(response.delta, TextDelta):
                return response.delta.text  # type: ignore

        return None


class GoogleProvider(
    CompletionProvider["GenerateContentResponse", "GenerateContentResponse"]
):
    def get_client(
        self, config: AiConfig, model: str, system_prompt: str
    ) -> GenerativeModel:
        try:
            import google.generativeai as genai
        except ImportError:
            DependencyManager.google_ai.require(
                why="for AI assistance with Google AI"
            )
            import google.generativeai as genai  # type: ignore

        if "google" not in config or "api_key" not in config["google"]:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Google AI API key not configured",
            )

        key: str = config["google"]["api_key"]
        if not key:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Google AI API key not configured",
            )

        genai.configure(api_key=key)
        return genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=DEFAULT_MAX_TOKENS,
                temperature=0,
            ),
        )

    def stream_completion(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        max_tokens: int,
    ) -> GenerateContentResponse:
        client = self.get_client(self.config, self.model, system_prompt)
        return client.generate_content(
            contents=convert_to_google_messages(messages),
            stream=True,
            generation_config={
                "max_output_tokens": max_tokens,
            },
        )

    def extract_content(self, response: GenerateContentResponse) -> str | None:
        if hasattr(response, "text"):
            return response.text
        return None


def get_completion_provider(
    config: AiConfig, model_override: Optional[str] = None
) -> CompletionProvider[Any, Any]:
    model = model_override or get_model(config)

    if model.startswith("claude"):
        return AnthropicProvider(model, config)
    elif model.startswith("google") or model.startswith("gemini"):
        return GoogleProvider(model, config)
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
