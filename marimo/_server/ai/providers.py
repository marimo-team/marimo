# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Literal, Optional, TypeVar
from urllib.parse import parse_qs, urlparse

from starlette.exceptions import HTTPException

from marimo import _loggers
from marimo._ai._convert import extract_text
from marimo._ai._pydantic_ai_utils import (
    convert_to_pydantic_messages,
    form_toolsets,
    generate_id,
)
from marimo._dependencies.dependencies import Dependency, DependencyManager
from marimo._server.ai.config import AnyProviderConfig
from marimo._server.ai.ids import AiModelId
from marimo._server.ai.tools.tool_manager import get_tool_manager
from marimo._server.ai.tools.types import ToolDefinition
from marimo._server.models.completion import UIMessage as ServerUIMessage
from marimo._utils.http import HTTPStatus

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

    from anthropic.types.beta import BetaThinkingConfigParam
    from openai import AsyncOpenAI
    from openai.types.shared.reasoning_effort import ReasoningEffort
    from pydantic_ai import Agent, DeferredToolRequests, FunctionToolset
    from pydantic_ai.messages import ThinkingPart
    from pydantic_ai.models import Model
    from pydantic_ai.models.bedrock import BedrockConverseModel
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
    from pydantic_ai.providers import Provider
    from pydantic_ai.providers.anthropic import (
        AnthropicProvider as PydanticAnthropic,
    )
    from pydantic_ai.providers.bedrock import (
        BedrockProvider as PydanticBedrock,
    )
    from pydantic_ai.providers.google import GoogleProvider as PydanticGoogle
    from pydantic_ai.providers.openai import OpenAIProvider as PydanticOpenAI
    from pydantic_ai.ui.vercel_ai import VercelAIAdapter
    from pydantic_ai.ui.vercel_ai.request_types import UIMessage, UIMessagePart
    from pydantic_ai.ui.vercel_ai.response_types import BaseChunk
    from starlette.responses import StreamingResponse


LOGGER = _loggers.marimo_logger()


@dataclass
class StreamOptions:
    text_only: bool = False
    format_stream: bool = False
    accept: str | None = None


@dataclass
class ActiveToolCall:
    tool_call_id: str
    tool_call_name: str
    tool_call_args: str


ProviderT = TypeVar("ProviderT", bound="Provider[Any]")


class PydanticProvider(ABC, Generic[ProviderT]):
    def __init__(
        self,
        model: str,
        config: AnyProviderConfig,
        deps: list[Dependency] | None = None,
        provider_name: str | None = None,
    ):
        """
        Initialize a Pydantic provider.

        Args:
            model: The model name.
            config: The provider config.
            deps: The dependencies to require.
            provider_name: The name of the provider. If not provided, the name will be inferred from the provider created.
        """
        DependencyManager.require_many(
            "for AI assistance", DependencyManager.pydantic_ai, *(deps or [])
        )

        self.model = model
        self.config = config
        self.provider = self.create_provider(config)
        self.provider_name = provider_name or self.provider.name

    @abstractmethod
    def create_provider(self, config: AnyProviderConfig) -> ProviderT:
        """Create a provider for the given config."""

    @abstractmethod
    def create_model(self, max_tokens: int) -> Model:
        """Create a Pydantic AI model for the given max tokens."""

    def create_agent(
        self,
        max_tokens: int,
        tools: list[ToolDefinition],
        system_prompt: str,
    ) -> Agent[None, DeferredToolRequests | str]:
        """Create a Pydantic AI agent"""
        from pydantic_ai import Agent

        model = self.create_model(max_tokens)
        toolset, output_type = self._get_toolsets_and_output_type(tools)
        return Agent(
            model,
            toolsets=[toolset] if tools else None,
            instructions=system_prompt,
            output_type=output_type,
        )

    def get_vercel_adapter(self) -> type[VercelAIAdapter[Any, Any]]:
        """Return the Vercel AI adapter for the given provider."""
        from pydantic_ai.ui.vercel_ai import VercelAIAdapter

        return VercelAIAdapter

    def convert_messages(
        self, messages: list[ServerUIMessage]
    ) -> list[UIMessage]:
        """Convert server messages to Pydantic AI messages. We expect AI SDK messages"""
        return convert_to_pydantic_messages(messages)

    async def stream_completion(
        self,
        messages: list[ServerUIMessage],
        system_prompt: str,
        max_tokens: int,
        additional_tools: list[ToolDefinition],
        stream_options: Optional[StreamOptions] = None,
    ) -> StreamingResponse:
        """Return a streaming response from the given messages. The response are AI SDK events."""
        from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage

        tools = (self.config.tools or []) + additional_tools
        agent = self.create_agent(
            max_tokens=max_tokens, tools=tools, system_prompt=system_prompt
        )

        run_input = SubmitMessage(
            id=generate_id("submit-message"),
            trigger="submit-message",
            messages=self.convert_messages(messages),
        )

        # TODO: Text only and format stream are not supported yet
        stream_options = stream_options or StreamOptions()

        vercel_adapter = self.get_vercel_adapter()
        adapter = vercel_adapter(
            agent=agent, run_input=run_input, accept=stream_options.accept
        )
        event_stream = adapter.run_stream()
        return adapter.streaming_response(event_stream)

    async def stream_text(
        self,
        user_prompt: str,
        messages: list[ServerUIMessage],
        system_prompt: str,
        max_tokens: int,
        additional_tools: list[ToolDefinition],
    ) -> AsyncGenerator[str]:
        """Return a stream of text from the given messages."""

        tools = (self.config.tools or []) + additional_tools
        agent = self.create_agent(
            max_tokens=max_tokens, tools=tools, system_prompt=system_prompt
        )
        vercel_adapter = self.get_vercel_adapter()

        async with agent.run_stream(
            user_prompt=user_prompt,
            message_history=vercel_adapter.load_messages(
                self.convert_messages(messages)
            ),
            instructions=system_prompt,
        ) as result:
            async for message in result.stream_text(delta=True):
                yield message

    async def completion(
        self,
        messages: list[UIMessage],
        system_prompt: str,
        max_tokens: int,
        additional_tools: list[ToolDefinition],
    ) -> str:
        """Return a string response from the given messages."""

        from pydantic_ai.ui.vercel_ai import VercelAIAdapter

        tools = (self.config.tools or []) + additional_tools
        agent = self.create_agent(
            max_tokens=max_tokens, tools=tools, system_prompt=system_prompt
        )
        result = await agent.run(
            user_prompt=None,
            message_history=VercelAIAdapter.load_messages(messages),
            instructions=system_prompt,
        )

        return str(result.output)

    def _get_toolsets_and_output_type(
        self, tools: list[ToolDefinition]
    ) -> tuple[FunctionToolset, list[Any] | type[str]]:
        from pydantic_ai import DeferredToolRequests

        tool_manager = get_tool_manager()
        toolset, deferred_tool_requests = form_toolsets(
            tools, tool_manager.invoke_tool
        )
        output_type = (
            [str, DeferredToolRequests] if deferred_tool_requests else str
        )
        return toolset, output_type


class GoogleProvider(PydanticProvider["PydanticGoogle"]):
    def create_provider(self, config: AnyProviderConfig) -> PydanticGoogle:
        from pydantic_ai.providers.google import (
            GoogleProvider as PydanticGoogle,
        )

        if config.api_key:
            return PydanticGoogle(api_key=config.api_key)

        # Try to use environment variables and ADC
        # This supports Google Vertex AI usage without explicit API keys
        use_vertex = (
            os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true"
        )
        if use_vertex:
            project = os.getenv("GOOGLE_CLOUD_PROJECT")
            location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
            # The type stubs don't have an overload that combines vertexai
            # with project/location, but the runtime supports it
            provider: PydanticGoogle = PydanticGoogle(  # type: ignore[call-overload]
                vertexai=True,
                project=project,
                location=location,
            )
        else:
            # Try default initialization which may work with environment variables
            provider = PydanticGoogle()
        return provider

    def create_model(self, max_tokens: int) -> GoogleModel:
        from pydantic_ai.models.google import GoogleModel, GoogleModelSettings

        return GoogleModel(
            model_name=self.model,
            provider=self.provider,
            settings=GoogleModelSettings(
                max_tokens=max_tokens,
                # Works on non-thinking models too
                google_thinking_config={"include_thoughts": True},
            ),
        )


class OpenAIProvider(PydanticProvider["PydanticOpenAI"]):
    # Medium effort provides a balance between speed and accuracy
    # https://openai.com/index/openai-o3-mini/
    DEFAULT_REASONING_EFFORT: ReasoningEffort = "medium"
    DEFAULT_REASONING_SUMMARY: Literal["detailed", "concise", "auto"] = "auto"

    def create_provider(self, config: AnyProviderConfig) -> PydanticOpenAI:
        from pydantic_ai.providers.openai import (
            OpenAIProvider as PydanticOpenAI,
        )

        client = self.get_openai_client(config)
        return PydanticOpenAI(openai_client=client)

    def create_model(
        self, max_tokens: int
    ) -> OpenAIChatModel | OpenAIResponsesModel:
        from pydantic_ai.models.openai import (
            OpenAIChatModel,
            OpenAIChatModelSettings,
            OpenAIResponsesModel,
            OpenAIResponsesModelSettings,
        )

        is_reasoning_model = self._is_reasoning_model(self.model)
        supports_responses_api = self._supports_responses_api(
            self.provider_name, self.model
        )
        LOGGER.debug(
            f"Model {self.model} is reasoning model: {is_reasoning_model} and supports responses API: {supports_responses_api}"
        )

        if supports_responses_api:
            settings = (
                OpenAIResponsesModelSettings(
                    max_tokens=max_tokens,
                    openai_reasoning_summary=self.DEFAULT_REASONING_SUMMARY,
                    openai_reasoning_effort=self.DEFAULT_REASONING_EFFORT,
                )
                if is_reasoning_model
                else OpenAIResponsesModelSettings(max_tokens=max_tokens)
            )
            return OpenAIResponsesModel(
                model_name=self.model,
                provider=self.provider,
                settings=settings,
            )

        return OpenAIChatModel(
            model_name=self.model,
            provider=self.provider,
            settings=OpenAIChatModelSettings(
                max_tokens=max_tokens,
                openai_reasoning_effort=self.DEFAULT_REASONING_EFFORT
                if is_reasoning_model
                else None,
            ),
        )

    def _supports_responses_api(self, provider_name: str, model: str) -> bool:
        """
        Check if the model and provider supports the responses API.
        We should prefer responses API due to better performance and features.
        """
        del model

        if provider_name == "openai":
            return True
        return False

    def _is_reasoning_model(self, model: str) -> bool:
        """
        Check if reasoning_effort should be added to the request.
        Only add for actual OpenAI reasoning models, not for OpenAI-compatible APIs.

        OpenAI-compatible APIs (identified by custom base_url) may not support
        the reasoning_effort parameter even if the model name suggests it's a
        reasoning model.
        """
        import re

        # Check for reasoning model patterns: o{digit} or gpt-5, with optional openai/ prefix
        reasoning_patterns = [
            r"^openai/o\d",  # openai/o1, openai/o3, etc.
            r"^o\d",  # o1, o3, etc.
            r"^openai/gpt-5",  # openai/gpt-5*
            r"^gpt-5",  # gpt-5*
        ]

        is_reasoning_model_name = any(
            re.match(pattern, model) for pattern in reasoning_patterns
        )

        if not is_reasoning_model_name:
            return False

        # If using a custom base_url that's not OpenAI, don't assume reasoning is supported
        if (
            self.config.base_url
            and "api.openai.com" not in self.config.base_url
        ):
            return False

        return True

    def get_openai_client(self, config: AnyProviderConfig) -> AsyncOpenAI:
        import ssl
        from pathlib import Path

        import httpx
        from openai import AsyncOpenAI

        base_url = config.base_url or None
        key = config.api_key

        # Add SSL parameters/values
        ssl_verify: bool = (
            config.ssl_verify if config.ssl_verify is not None else True
        )
        extra_headers: Optional[dict[str, str]] = config.extra_headers
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
                client = httpx.AsyncClient(verify=ctx)
            else:
                pass
        else:
            client = httpx.AsyncClient(verify=False)

        # if client is created, either with a custom context or with verify=False, use it as the http_client object in `AsyncOpenAI`
        extra_headers = extra_headers or {}
        project = config.project or None
        if client:
            return AsyncOpenAI(
                default_headers={"api-key": key, **extra_headers},
                api_key=key,
                base_url=base_url,
                project=project,
                http_client=client,
            )

        # if not, return bog standard AsyncOpenAI object
        return AsyncOpenAI(
            default_headers={"api-key": key, **extra_headers},
            api_key=key,
            base_url=base_url,
            project=project,
        )


class AzureOpenAIProvider(OpenAIProvider):
    def _is_reasoning_model(self, model: str) -> bool:
        # https://learn.microsoft.com/en-us/answers/questions/5519548/does-gpt-5-via-azure-support-reasoning-effort-and
        # Only custom models support reasoning effort, we can expose this as a parameter in the future
        del model
        return False

    def _handle_azure_openai(self, base_url: str) -> tuple[str, str, str]:
        """Handle Azure OpenAI.
        Sample base URL: https://<your-resource-name>.openai.azure.com/openai/deployments/<deployment_name>?api-version=<api-version>

        Args:
            base_url (str): The base URL of the Azure OpenAI.

        Returns:
            tuple[str, str, str]: The API version, deployment name, and endpoint.
        """

        parsed_url = urlparse(base_url)

        deployment_name = parsed_url.path.split("/")[3]
        api_version = parse_qs(parsed_url.query)["api-version"][0]

        endpoint = f"{parsed_url.scheme}://{parsed_url.hostname}"
        return api_version, deployment_name, endpoint

    def get_openai_client(self, config: AnyProviderConfig) -> AsyncOpenAI:
        from openai import AsyncAzureOpenAI

        base_url = config.base_url or None
        key = config.api_key

        if base_url is None:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Base URL needed to get the endpoint",
            )

        api_version = None
        deployment_name = None
        endpoint = None

        if base_url:
            if "services.ai.azure.com" in base_url:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail="To use Azure AI Foundry, use the OpenAI-compatible provider instead.",
                )
            elif "openai.azure.com" in base_url:
                api_version, deployment_name, endpoint = (
                    self._handle_azure_openai(base_url)
                )
            else:
                LOGGER.warning(f"Unknown Azure OpenAI base URL: {base_url}")
                api_version, deployment_name, endpoint = (
                    self._handle_azure_openai(base_url)
                )

        return AsyncAzureOpenAI(
            api_key=key,
            api_version=api_version,
            azure_deployment=deployment_name,
            azure_endpoint=endpoint or "",
        )


class AnthropicProvider(PydanticProvider["PydanticAnthropic"]):
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
        "claude-haiku-4-5",
        "claude-3-7-sonnet",
    ]
    # 1024 tokens is the minimum budget for extended thinking
    DEFAULT_EXTENDED_THINKING_BUDGET_TOKENS = 1024

    def create_provider(self, config: AnyProviderConfig) -> PydanticAnthropic:
        from pydantic_ai.providers.anthropic import (
            AnthropicProvider as PydanticAnthropic,
        )

        return PydanticAnthropic(api_key=config.api_key)

    def create_model(self, max_tokens: int) -> Model:
        from pydantic_ai.models.anthropic import (
            AnthropicModel,
            AnthropicModelSettings,
        )

        is_thinking_model = self.is_extended_thinking_model(self.model)
        thinking_config: BetaThinkingConfigParam = {"type": "disabled"}
        if is_thinking_model:
            thinking_config = {
                "type": "enabled",
                "budget_tokens": self.DEFAULT_EXTENDED_THINKING_BUDGET_TOKENS,
            }

        return AnthropicModel(
            model_name=self.model,
            provider=self.provider,
            settings=AnthropicModelSettings(
                max_tokens=max_tokens,
                temperature=self.get_temperature(),
                anthropic_thinking=thinking_config,
            ),
        )

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

    def convert_messages(
        self, messages: list[ServerUIMessage]
    ) -> list[UIMessage]:
        return convert_to_pydantic_messages(messages, self.process_part)

    def process_part(self, part: UIMessagePart) -> UIMessagePart:
        """
        Anthropic does not support binary content for text files, so we convert to text parts.
        Ideally, we would use DocumentUrl parts with a url, but we only have the binary data from the frontend
        Refer to: https://ai.pydantic.dev/input/#user-side-download-vs-direct-file-url
        """
        from pydantic_ai.ui.vercel_ai.request_types import (
            FileUIPart,
            TextUIPart,
        )

        if isinstance(part, FileUIPart) and part.media_type.startswith("text"):
            return TextUIPart(
                type="text",
                text=extract_text(part.url),
                provider_metadata=part.provider_metadata,
            )
        return part

    def get_vercel_adapter(
        self,
    ) -> type[VercelAIAdapter[None, DeferredToolRequests | str]]:
        """
        Return a custom adapter that includes thinking signatures in ReasoningEndChunk.

        pydantic_ai's VercelAIEventStream.handle_thinking_end doesn't pass the signature
        from ThinkingPart to ReasoningEndChunk, which breaks Anthropic's extended thinking
        on follow-up messages (Anthropic requires signatures on thinking blocks).

        TODO: Remove this once https://github.com/pydantic/pydantic-ai/pull/3754 is released
        """
        from pydantic_ai import DeferredToolRequests
        from pydantic_ai.ui.vercel_ai import VercelAIAdapter
        from pydantic_ai.ui.vercel_ai._event_stream import VercelAIEventStream
        from pydantic_ai.ui.vercel_ai.response_types import ReasoningEndChunk

        AnthropicOutputType = DeferredToolRequests | str

        # Custom event stream that includes signature in ReasoningEndChunk
        class AnthropicVercelAIEventStream(
            VercelAIEventStream[None, AnthropicOutputType]
        ):
            async def handle_thinking_end(
                self, part: ThinkingPart, followed_by_thinking: bool = False
            ) -> AsyncIterator[BaseChunk]:
                """Override to include signature in provider_metadata."""
                try:
                    provider_metadata = None
                    if part.signature:
                        pydantic_ai_meta: dict[str, Any] = {
                            "signature": part.signature
                        }
                        if part.provider_name:
                            pydantic_ai_meta["provider_name"] = (
                                part.provider_name
                            )
                        if part.id:
                            pydantic_ai_meta["id"] = part.id
                        provider_metadata = {"pydantic_ai": pydantic_ai_meta}

                    yield ReasoningEndChunk(
                        id=self.message_id, provider_metadata=provider_metadata
                    )
                except Exception as e:
                    LOGGER.warning(
                        f"Error in AnthropicVercelAIEventStream.handle_thinking_end: {e}"
                    )
                    async for chunk in super().handle_thinking_end(
                        part, followed_by_thinking
                    ):
                        yield chunk

        # Custom adapter that uses the custom event stream
        class AnthropicVercelAIAdapter(
            VercelAIAdapter[None, AnthropicOutputType]
        ):
            def build_event_stream(self) -> AnthropicVercelAIEventStream:
                return AnthropicVercelAIEventStream(
                    self.run_input, accept=self.accept
                )

        return AnthropicVercelAIAdapter


class BedrockProvider(PydanticProvider["PydanticBedrock"]):
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

    def create_provider(self, config: AnyProviderConfig) -> PydanticBedrock:
        from pydantic_ai.providers.bedrock import (
            BedrockProvider as PydanticBedrock,
        )

        self.setup_credentials(config)
        # For bedrock, the config sets the region name as the base_url
        return PydanticBedrock(region_name=config.base_url)

    def create_model(self, max_tokens: int) -> BedrockConverseModel:
        from pydantic_ai.models.bedrock import (
            BedrockConverseModel,
            BedrockModelSettings,
        )

        return BedrockConverseModel(
            model_name=self.model,
            provider=self.provider,
            settings=BedrockModelSettings(
                max_tokens=max_tokens,
                # TODO: Add reasoning support
            ),
        )


def get_completion_provider(
    config: AnyProviderConfig, model: str
) -> PydanticProvider[Any]:
    model_id = AiModelId.from_model(model)

    if model_id.provider == "anthropic":
        return AnthropicProvider(
            model_id.model, config, [DependencyManager.anthropic]
        )
    elif model_id.provider == "google":
        return GoogleProvider(
            model_id.model, config, [DependencyManager.google_ai]
        )
    elif model_id.provider == "bedrock":
        return BedrockProvider(
            model_id.model, config, [DependencyManager.boto3]
        )
    elif model_id.provider == "azure":
        return AzureOpenAIProvider(model_id.model, config)
    elif model_id.provider == "openai":
        return OpenAIProvider(
            model_id.model, config, [DependencyManager.openai]
        )
    else:
        return OpenAIProvider(
            model_id.model,
            config,
            [DependencyManager.openai],
            provider_name=model_id.provider,
        )


async def merge_backticks(
    chunks: AsyncIterator[str],
) -> AsyncGenerator[str, None]:
    buffer: Optional[str] = None

    def only_whitespace_or_newlines(text: str) -> bool:
        return all(char.isspace() or char == "\n" for char in text)

    async for chunk in chunks:
        if buffer is None:
            buffer = chunk
            continue

        # Combine whitespace
        if only_whitespace_or_newlines(buffer):
            buffer += chunk
            continue

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


async def without_wrapping_backticks(
    chunks: AsyncIterator[str],
) -> AsyncGenerator[str, None]:
    """
    Removes the first and last backticks (```) from a stream of text chunks.

    This function removes opening backticks (with optional language identifier)
    from the start of the stream and closing backticks from the end of the stream.
    It does not remove backticks that appear in the middle of the content.

    Args:
        chunks: An async iterator of text chunks

    Yields:
        Text chunks with the first and last backticks removed if they exist
    """
    # First, merge backticks across chunks to avoid split patterns
    chunks = merge_backticks(chunks)

    # Supported language identifiers
    langs = ["python", "sql", "markdown"]

    first_chunk = True
    buffer: Optional[str] = None
    has_starting_backticks = False

    async for chunk in chunks:
        # Handle the first chunk
        if first_chunk:
            first_chunk = False
            stripped_chunk = chunk.lstrip()
            # Check for language-specific fences first
            for lang in langs:
                if stripped_chunk.startswith(f"```{lang}"):
                    has_starting_backticks = True
                    # Remove the starting backticks with lang
                    chunk = stripped_chunk[3 + len(lang) :]
                    # Also remove starting newline if present
                    if chunk.startswith("\n"):
                        chunk = chunk[1:]
                    break
            # If no language-specific fence was found, check for plain backticks
            else:
                if stripped_chunk.startswith("```"):
                    has_starting_backticks = True
                    chunk = stripped_chunk[3:]  # Remove the starting backticks
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
        # Some models add trailing space to the end of the response, so we strip to check for backticks
        stripped_buffer = buffer.rstrip()
        trailing_space = buffer[len(stripped_buffer) :]

        # Remove ending newline if present
        if has_starting_backticks:
            if stripped_buffer.endswith("\n```"):
                buffer = stripped_buffer[:-4] + trailing_space
            elif stripped_buffer.endswith("```"):
                buffer = stripped_buffer[:-3] + trailing_space
        yield buffer
