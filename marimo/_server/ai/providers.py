# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Optional,
    TypeVar,
    cast,
)

from starlette.exceptions import HTTPException

from marimo import _loggers
from marimo._ai._convert import (
    convert_to_anthropic_messages,
    convert_to_google_messages,
    convert_to_openai_messages,
)
from marimo._ai._types import ChatMessage
from marimo._config.config import AiConfig, CompletionConfig, MarimoConfig
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


@dataclass
class AnyProviderConfig:
    base_url: Optional[str]
    api_key: str
    ssl_verify: Optional[bool] = None
    ca_bundle_path: Optional[str] = None
    client_pem: Optional[str] = None

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
        )

    @staticmethod
    def for_completion(config: CompletionConfig) -> AnyProviderConfig:
        key = _get_key(config, "AI completion")
        return AnyProviderConfig(
            base_url=_get_base_url(config),
            api_key=key,
        )

    @staticmethod
    def for_model(model: str, config: AiConfig) -> AnyProviderConfig:
        if model.startswith("claude"):
            return AnyProviderConfig.for_anthropic(config)
        elif model.startswith("google") or model.startswith("gemini"):
            return AnyProviderConfig.for_google(config)
        else:
            return AnyProviderConfig.for_openai(config)


def _get_key(config: Any, name: str) -> str:
    if "api_key" in config:
        key = config["api_key"]
        if key:
            return cast(str, key)
    raise HTTPException(
        status_code=HTTPStatus.BAD_REQUEST,
        detail=f"{name} API key not configured",
    )


def _get_base_url(config: Any) -> Optional[str]:
    if "base_url" in config:
        return cast(str, config["base_url"])
    return None


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
    def get_client(self, config: AnyProviderConfig) -> OpenAI:
        DependencyManager.openai.require(why="for AI assistance with OpenAI")

        import ssl

        # library to check if paths exists
        from pathlib import Path
        from urllib.parse import parse_qs, urlparse

        # ssl related libs, httpx is a dependency of openai
        import httpx
        from openai import AzureOpenAI, OpenAI

        base_url = config.base_url
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
            return response.text  # type: ignore[no-any-return]

        if isinstance(response, RawContentBlockDeltaEvent):
            if isinstance(response.delta, TextDelta):
                return response.delta.text  # type: ignore[no-any-return]

        return None


class GoogleProvider(
    CompletionProvider["GenerateContentResponse", "GenerateContentResponse"]
):
    def get_client(
        self, config: AnyProviderConfig, model: str, system_prompt: str
    ) -> GenerativeModel:
        try:
            import google.generativeai as genai
        except ImportError:
            DependencyManager.google_ai.require(
                why="for AI assistance with Google AI"
            )
            import google.generativeai as genai  # type: ignore

        genai.configure(api_key=config.api_key)
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
            return response.text  # type: ignore[no-any-return]
        return None


def get_completion_provider(
    config: AnyProviderConfig, model: str
) -> CompletionProvider[Any, Any]:
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
