# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
import inspect
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Generic,
    Literal,
    TypeVar,
    cast,
    get_args,
)
from urllib.parse import parse_qs, urlparse

from starlette.exceptions import HTTPException

from marimo import _loggers
from marimo._ai._convert import extract_text
from marimo._ai._pydantic_ai_utils import (
    convert_to_pydantic_messages,
    form_toolsets,
    generate_id,
    profile_get,
)
from marimo._dependencies.dependencies import Dependency, DependencyManager
from marimo._plugins.ui._impl.chat.chat import (
    AI_SDK_VERSION,
)
from marimo._server.ai.config import AnyProviderConfig
from marimo._server.ai.constants import ANTHROPIC_DEFAULT_MAX_TOKENS
from marimo._server.ai.ids import AiModelId, AiProviderId
from marimo._server.ai.tools.tool_manager import get_tool_manager
from marimo._server.ai.tools.types import ToolDefinition
from marimo._server.ai.tracing import (
    SpanInfo,
    trace_completion,
    trace_stream,
)
from marimo._server.models.completion import UIMessage as ServerUIMessage
from marimo._utils.http import HTTPStatus
from marimo._utils.typing import override

if TYPE_CHECKING:
    from collections.abc import Sequence

    from openai import AsyncOpenAI
    from pydantic_ai import Agent, DeferredToolRequests, FunctionToolset
    from pydantic_ai.capabilities import AbstractCapability
    from pydantic_ai.models import Model
    from pydantic_ai.models.anthropic import AnthropicModelSettings
    from pydantic_ai.models.bedrock import (
        BedrockConverseModel,
        BedrockModelSettings,
    )
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.models.openai import (
        OpenAIResponsesModel,
        OpenAIResponsesModelSettings,
    )
    from pydantic_ai.models.openrouter import OpenRouterModelSettings
    from pydantic_ai.output import OutputSpec
    from pydantic_ai.providers import Provider
    from pydantic_ai.providers.anthropic import (
        AnthropicProvider as PydanticAnthropic,
    )
    from pydantic_ai.providers.bedrock import (
        BedrockProvider as PydanticBedrock,
    )
    from pydantic_ai.providers.google import GoogleProvider as PydanticGoogle
    from pydantic_ai.providers.openai import OpenAIProvider as PydanticOpenAI
    from pydantic_ai.settings import ModelSettings, ThinkingLevel
    from pydantic_ai.toolsets import AbstractToolset
    from pydantic_ai.ui.vercel_ai.request_types import UIMessage, UIMessagePart
    from starlette.requests import Request
    from starlette.responses import StreamingResponse

    from marimo._session import Session


LOGGER = _loggers.marimo_logger()


@dataclass
class StreamOptions:
    span_info: SpanInfo
    text_only: bool = False
    format_stream: bool = False
    accept: str | None = None


@dataclass(frozen=True)
class BaseModelSettings:
    max_tokens: int | None
    thinking: ThinkingLevel | None


ProviderT = TypeVar("ProviderT", bound="Provider", covariant=True)


class PydanticProvider(ABC, Generic[ProviderT]):
    def __init__(
        self,
        model: str,
        config: AnyProviderConfig,
        deps: list[Dependency] | None = None,
    ):
        """
        Initialize a Pydantic provider.

        Args:
            model: The model name.
            config: The provider config.
            deps: The dependencies to require.
        """
        DependencyManager.require_many(
            "for AI assistance",
            DependencyManager.pydantic_ai,
            *(deps or []),
            source="server",
        )

        self.model: str = model
        self.config: AnyProviderConfig = config
        self.provider: ProviderT = self.create_provider(config)

    @abstractmethod
    def create_provider(self, config: AnyProviderConfig) -> ProviderT:
        """Create a provider for the given config."""

    @abstractmethod
    def create_model(self) -> Model:
        """Create a Pydantic AI model for the given max tokens."""

    def create_agent(
        self,
        *,
        name: str,
        max_tokens: int | None,
        tools: list[ToolDefinition] | None = None,
        toolsets: Sequence[AbstractToolset[None]] | None = None,
        extra_capabilities: Sequence[AbstractCapability[None]] | None = None,
        system_prompt: str,
    ) -> Agent[None, DeferredToolRequests | str]:
        """Create a Pydantic AI agent."""
        from pydantic_ai import Agent

        model = self.create_model()
        capabilities = self._build_agent_capabilities(model)
        if extra_capabilities:
            capabilities.extend(extra_capabilities)
        agent_toolsets, output_type = self._resolve_agent_toolsets(
            tools or [], toolsets
        )

        return Agent(
            model,
            name=name,
            model_settings=self._build_model_settings(model, max_tokens),
            toolsets=agent_toolsets,
            instructions=system_prompt,
            capabilities=capabilities,
            output_type=output_type,
            deps_type=type(None),
        )

    def _build_model_settings(
        self, model: Model, max_tokens: int | None
    ) -> ModelSettings | None:
        """Settings applied at agent level on every request."""
        values = self._base_model_settings(model, max_tokens)
        settings: ModelSettings = {}

        if values.max_tokens is not None:
            settings["max_tokens"] = values.max_tokens
        if values.thinking is not None:
            settings["thinking"] = values.thinking
        return settings

    def _base_model_settings(
        self, model: Model, max_tokens: int | None
    ) -> BaseModelSettings:
        """Shared request setting values, before provider-specific keys."""
        thinking = self._default_thinking(model)
        if thinking is not None and not (
            profile_get(model.profile, "supports_thinking", False)
            or profile_get(model.profile, "thinking_always_enabled", False)
        ):
            thinking = None

        return BaseModelSettings(max_tokens=max_tokens, thinking=thinking)

    def _default_thinking(self, model: Model) -> ThinkingLevel | None:
        """Default unified thinking flag. Return None to skip."""
        del model
        return True

    def convert_messages(
        self, messages: list[ServerUIMessage]
    ) -> list[UIMessage]:
        """Convert server messages to Pydantic AI messages. We expect AI SDK messages"""
        return convert_to_pydantic_messages(messages)

    async def stream_completion(
        self,
        messages: list[ServerUIMessage],
        system_prompt: str,
        max_tokens: int | None,
        additional_tools: list[ToolDefinition],
        stream_options: StreamOptions,
    ) -> StreamingResponse:
        """Return a streaming response from the given messages. The response are AI SDK events."""
        tools = (self.config.tools or []) + additional_tools

        agent = self.create_agent(
            name=stream_options.span_info.endpoint,
            max_tokens=max_tokens,
            tools=tools,
            system_prompt=system_prompt,
        )
        stream_options.span_info.tool_count = len(tools) + len(
            agent.root_capability.capabilities
        )

        return self._vercel_streaming_response(agent, messages, stream_options)

    def _vercel_streaming_response(
        self,
        agent: Agent[None, DeferredToolRequests | str],
        messages: list[ServerUIMessage],
        stream_options: StreamOptions,
    ) -> StreamingResponse:
        """Run `agent` over `messages` and return an AI SDK streaming response."""
        from pydantic_ai.ui.vercel_ai import VercelAIAdapter
        from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage

        run_input = SubmitMessage(
            id=generate_id("submit-message"),
            trigger="submit-message",
            messages=self.convert_messages(messages),
        )
        adapter = VercelAIAdapter(
            agent=agent,
            run_input=run_input,
            accept=stream_options.accept,
            sdk_version=AI_SDK_VERSION,
        )
        event_stream = adapter.run_stream()
        event_stream = trace_stream(event_stream, stream_options.span_info)
        return adapter.streaming_response(event_stream)

    async def completion(
        self,
        messages: list[UIMessage],
        system_prompt: str,
        max_tokens: int,
        additional_tools: list[ToolDefinition],
        span_info: SpanInfo,
    ) -> str:
        """Return a string response from the given messages."""

        from pydantic_ai.ui.vercel_ai import VercelAIAdapter

        tools = (self.config.tools or []) + additional_tools
        agent = self.create_agent(
            name=span_info.endpoint,
            max_tokens=max_tokens,
            tools=tools,
            system_prompt=system_prompt,
        )
        span_info.tool_count = len(tools) + len(
            agent.root_capability.capabilities
        )

        with trace_completion(span_info):
            result = await agent.run(
                user_prompt=None,
                message_history=VercelAIAdapter.load_messages(messages),
            )

        return str(result.output)

    async def stream_completion_harness(
        self,
        messages: list[ServerUIMessage],
        *,
        system_prompt: str,
        session: Session,
        request: Request,
        max_tokens: int | None,
        stream_options: StreamOptions,
    ) -> StreamingResponse:
        """Return code-mode streaming responses"""
        from marimo._server.ai.tools.code_mode import (
            build_execute_code_toolset,
            references_capability,
        )

        agent = self.create_agent(
            name=stream_options.span_info.endpoint,
            max_tokens=max_tokens,
            tools=[],
            toolsets=[build_execute_code_toolset(session, request)],
            extra_capabilities=references_capability(),
            system_prompt=system_prompt,
        )

        # One for the execute code toolset, plus the agent's native capabilities
        stream_options.span_info.tool_count = 1 + len(
            agent.root_capability.capabilities
        )

        return self._vercel_streaming_response(agent, messages, stream_options)

    def _build_agent_capabilities(
        self, model: Model
    ) -> list[AbstractCapability[None]]:
        """
        Build agent capabilities for the given model.

        Referenced from https://pydantic.dev/docs/ai/core-concepts/capabilities#provider-adaptive-tools
        """
        from pydantic_ai.capabilities import WebFetch, WebSearch, XSearch
        from pydantic_ai.native_tools import (
            WebFetchTool,
            WebSearchTool,
            XSearchTool,
        )

        supported = profile_get(model.profile, "supported_native_tools", [])
        LOGGER.debug(f"Supported native tools: {supported} for model: {model}")
        capabilities: list[AbstractCapability[None]] = []

        if DependencyManager.duckduckgo_search.has():
            capabilities.append(WebSearch(local="duckduckgo"))
        elif WebSearchTool in supported:
            capabilities.append(WebSearch())

        if DependencyManager.markdownify.has():
            capabilities.append(WebFetch(local=True))
        elif WebFetchTool in supported:
            capabilities.append(WebFetch())

        if XSearchTool in supported:
            capabilities.append(XSearch())

        LOGGER.debug(f"Capabilities: {capabilities} for model: {model}")
        return capabilities

    def _resolve_agent_toolsets(
        self,
        tools: list[ToolDefinition],
        extra_toolsets: Sequence[AbstractToolset[None]] | None,
    ) -> tuple[
        list[AbstractToolset[None]] | None,
        OutputSpec[str | DeferredToolRequests],
    ]:
        all_toolsets: list[AbstractToolset[None]] = []
        if tools:
            toolset, output_type = self._get_toolsets_and_output_type(tools)
            all_toolsets.append(toolset)
        else:
            output_type = str

        if extra_toolsets:
            all_toolsets.extend(extra_toolsets)
        return all_toolsets or None, output_type

    def _get_toolsets_and_output_type(
        self, tools: list[ToolDefinition]
    ) -> tuple[FunctionToolset, OutputSpec[str | DeferredToolRequests]]:
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
    @override
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
            # Upstream (pydantic-ai) defaults to us-central1 if not set
            location = os.getenv("GOOGLE_CLOUD_LOCATION") or None
            if location is None:
                location_msg = (
                    "GOOGLE_CLOUD_LOCATION is not set. "
                    "The upstream provider will default to 'us-central1'. "
                    "Set this env var if your project has region restrictions."
                )
                LOGGER.info(location_msg)
            # The type stubs don't have an overload that combines vertexai
            # with project/location, but the runtime supports it
            provider: PydanticGoogle = PydanticGoogle(  # type: ignore[call-overload]
                vertexai=True,
                project=project,
                location=location,
            )
        else:
            # Try default initialization which may work with environment variables
            provider = PydanticGoogle()  # type: ignore[call-overload]
        return provider

    @override
    def create_model(self) -> GoogleModel:
        from pydantic_ai.models.google import GoogleModel

        return GoogleModel(model_name=self.model, provider=self.provider)


class OpenAIClientMixin:
    """Mixin providing OpenAI client creation logic for OpenAI-based providers."""

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
        extra_headers: dict[str, str] | None = config.extra_headers
        ca_bundle_path: str | None = config.ca_bundle_path
        client_pem: str | None = config.client_pem

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


class OpenAIProvider(OpenAIClientMixin, PydanticProvider["PydanticOpenAI"]):
    # https://openai.com/index/openai-o3-mini/
    # 'auto' lets OpenAI decide between detailed/concise based on the prompt;
    # marimo wants reasoning summaries surfaced for display.
    DEFAULT_REASONING_SUMMARY: Literal["detailed", "concise", "auto"] = "auto"

    @override
    def create_provider(self, config: AnyProviderConfig) -> PydanticOpenAI:
        from pydantic_ai.providers.openai import (
            OpenAIProvider as PydanticOpenAI,
        )

        client = self.get_openai_client(config)
        return PydanticOpenAI(openai_client=client)

    @override
    def create_model(self) -> OpenAIResponsesModel:
        from pydantic_ai.models.openai import (
            OpenAIResponsesModel,
        )

        return OpenAIResponsesModel(
            model_name=self.model, provider=self.provider
        )

    @override
    def _build_model_settings(
        self, model: Model, max_tokens: int | None
    ) -> ModelSettings | None:
        # `reasoning.summary` is only valid for OpenAI reasoning models (gpt-5
        # and the o-series).
        values = self._base_model_settings(model, max_tokens)
        settings: OpenAIResponsesModelSettings = {}

        if values.max_tokens is not None:
            settings["max_tokens"] = values.max_tokens

        if values.thinking is not None:
            settings["thinking"] = values.thinking
            settings["openai_reasoning_summary"] = (
                self.DEFAULT_REASONING_SUMMARY
            )

        return settings

    @override
    def _default_thinking(self, model: Model) -> ThinkingLevel | None:
        # OpenAI-compatible third-party endpoints (custom base_url) may not
        # accept `reasoning_effort` even when the model name looks like a
        # reasoning model. Suppress the unified thinking flag in that case.
        if (
            self.config.base_url
            and "api.openai.com" not in self.config.base_url
        ):
            return None
        return super()._default_thinking(model)


class AzureOpenAIProvider(OpenAIProvider):
    # Only custom Azure deployments support `reasoning_effort`, and we don't expose that config yet.
    # https://learn.microsoft.com/en-us/answers/questions/5519548/does-gpt-5-via-azure-support-reasoning-effort-and
    @override
    def _default_thinking(self, model: Model) -> ThinkingLevel | None:
        del model
        return None

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

    @override
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


def _normalize_base_url(base_url: str | None) -> str | None:
    """Normalize a base URL for cross-provider comparison.

    Strips the scheme, a trailing `/v1` path segment, and trailing slashes so
    that e.g. `https://api.provider.com` and `https://api.provider.com/v1/`
    compare equal.
    """
    if not base_url:
        return None
    normalized = base_url.strip().lower()
    normalized = normalized.removeprefix("https://").removeprefix("http://")
    normalized = normalized.rstrip("/").removesuffix("/v1")
    return normalized.rstrip("/") or None


def _try_infer_provider_class(
    provider_name: str,
) -> type[Provider] | None:
    """Resolve a pydantic-ai provider class by name, or `None` if unknown."""
    from pydantic_ai.providers import infer_provider_class

    try:
        return infer_provider_class(provider_name)
    except ValueError:
        return None


@functools.lru_cache(maxsize=1)
def _openai_compatible_provider_names() -> tuple[
    frozenset[str], frozenset[str]
]:
    """(responses-compatible, chat-compatible) provider names from pydantic-ai."""
    from pydantic_ai.models import (
        OpenAIChatCompatibleProvider,
        OpenAIResponsesCompatibleProvider,
    )

    # TypeAliasType objects; `.__value__` exposes the underlying Literal.
    return (
        frozenset(
            get_args(cast(object, OpenAIResponsesCompatibleProvider.__value__))
        ),
        frozenset(
            get_args(cast(object, OpenAIChatCompatibleProvider.__value__))
        ),
    )


@functools.lru_cache(maxsize=1)
def _known_provider_base_urls() -> dict[str, str]:
    """Map normalized base URLs to pydantic-ai provider names.

    Discovered from pydantic-ai's OpenAI-compatible providers so that a custom
    provider whose *name* we don't recognize, but whose *base URL* points at a
    known service (e.g. `https://api.deepseek.com`) points to the correct provider.
    """
    responses, chat = _openai_compatible_provider_names()
    mapping: dict[str, str] = {}
    # Sorted so that, if two providers normalize alike, the first wins.
    for name in sorted(responses | chat):
        provider_class = _try_infer_provider_class(name)
        if provider_class is None:
            continue
        try:
            base_url = object.__new__(provider_class).base_url
        except Exception as e:
            LOGGER.debug(
                f"Skipping provider '{name}' during base URL discovery: {e}"
            )
            continue
        normalized = _normalize_base_url(base_url)
        if normalized:
            mapping.setdefault(normalized, name)
    return mapping


def _infer_provider_name_from_base_url(base_url: str | None) -> str | None:
    """Resolve a known pydantic-ai provider name from a base URL, if any."""
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return None
    return _known_provider_base_urls().get(normalized)


class CustomProvider(OpenAIClientMixin, PydanticProvider["Provider"]):
    """Support for custom providers which may or may not be OpenAI-compatible.

    Note:
        We need to use the specific provider and model classes, because Pydantic AI has tuned them to send & return messages correctly.
        We can also use `Agent("provider:model_name")` to avoid finding the provider ourselves. However, this does not let
        us create custom providers. They rely on env vars to be set.
    """

    _responses_compatible: frozenset[str]
    _chat_compatible: frozenset[str]

    def __init__(
        self,
        model_id: AiModelId,
        config: AnyProviderConfig,
        deps: list[Dependency] | None = None,
    ):
        self._provider_name: AiProviderId = model_id.provider
        if _try_infer_provider_class(self._provider_name) is None:
            matched = _infer_provider_name_from_base_url(config.base_url)
            if matched is not None:
                match_msg = (
                    f"Custom provider '{self._provider_name}' matched known "
                    + f"provider '{matched}' by base URL; using its profile."
                )
                LOGGER.debug(match_msg)
                self._provider_name = AiProviderId(matched)
        self._responses_compatible, self._chat_compatible = (
            _openai_compatible_provider_names()
        )
        super().__init__(model_id.model, config, deps)

    def _is_openai_compatible(self) -> bool:
        """Check if the provider uses an OpenAI-compatible API."""
        provider = self._provider_name.lower()
        return (
            provider in self._responses_compatible
            or provider in self._chat_compatible
        )

    def _supports_responses_api(self) -> bool:
        """Check if the provider supports the OpenAI Responses API. We currently default to Pydantic's inferred model"""
        return self._provider_name.lower() in self._responses_compatible

    @override
    def create_provider(self, config: AnyProviderConfig) -> Provider:
        """Create a provider based on the provider name.

        1. Try to infer the provider class from the name
        2. For OpenAI-compatible providers, pass openai_client (with SSL settings)
        3. For other providers, try to create the provider directly with the credentials
        4. Fall back to OpenAIProvider if nothing else works or not found

        Reference: https://ai.pydantic.dev/models/openai/#openai-compatible-models
        """
        from pydantic_ai.providers.openai import (
            OpenAIProvider as PydanticOpenAI,
        )

        # Try to infer the provider class
        provider_class = _try_infer_provider_class(self._provider_name)
        if provider_class is None:
            # Unknown provider, fall back to OpenAI-compatible
            LOGGER.debug(
                f"Unknown provider: {self._provider_name}. Falling back to OpenAIProvider."
            )
            client = self.get_openai_client(config)
            return PydanticOpenAI(openai_client=client)

        LOGGER.debug(f"Inferred provider class: {provider_class.__name__}")

        if self._is_openai_compatible():
            client = self.get_openai_client(config)
            try:
                return provider_class(openai_client=client)  # type: ignore[call-arg]
            except TypeError:
                LOGGER.warning(
                    f"Provider {provider_class.__name__} doesn't accept openai_client"
                )

        return self._create_custom_provider(provider_class, config)

    def _create_custom_provider(
        self, provider_class: type[Provider], config: AnyProviderConfig
    ) -> Provider:
        """Instantiate a non-OpenAI-compatible pydantic-ai provider."""

        provider_name = provider_class.__name__
        LOGGER.debug(f"Creating custom provider: {provider_name}")

        params = inspect.signature(provider_class).parameters
        kwargs: dict[str, str] = {}
        if "api_key" in params and config.api_key:
            kwargs["api_key"] = config.api_key
        if "base_url" in params and config.base_url:
            kwargs["base_url"] = config.base_url

        try:
            return provider_class(**kwargs)
        except Exception as e:
            from pydantic_ai.providers.openai import (
                OpenAIProvider as PydanticOpenAI,
            )

            fallback_msg = (
                f"Failed to create provider {provider_name}: {e}. "
                f"Falling back to OpenAIProvider."
            )
            LOGGER.warning(fallback_msg)
            client = self.get_openai_client(config)
            return PydanticOpenAI(openai_client=client)

    @override
    def create_model(self) -> Model:
        """
        Infer the model from pydantic-ai's registry, falling back to a
        generic OpenAI-compatible chat model.
        """
        from pydantic_ai import UserError
        from pydantic_ai.models import infer_model
        from pydantic_ai.models.openai import OpenAIChatModel

        try:
            return infer_model(
                f"{self._provider_name}:{self.model}",
                provider_factory=lambda _: self.provider,
            )
        except UserError:
            model_not_found_msg = (
                f"Model {self.model} not found in pydantic-ai's model registry. "
                "Falling back to OpenAIChatModel."
            )
            LOGGER.debug(model_not_found_msg)
        except Exception as e:
            LOGGER.error(
                f"Error creating model: {e}. Falling back to OpenAIChatModel."
            )

        return OpenAIChatModel(model_name=self.model, provider=self.provider)

    @override
    def _build_model_settings(
        self, model: Model, max_tokens: int | None
    ) -> ModelSettings:
        values = self._base_model_settings(model, max_tokens)
        model_settings: ModelSettings = {}
        if values.max_tokens is not None:
            model_settings["max_tokens"] = values.max_tokens
        if values.thinking is not None:
            model_settings["thinking"] = values.thinking

        if self._provider_name == "openrouter":
            openrouter_settings: OpenRouterModelSettings = {}
            if values.max_tokens is not None:
                openrouter_settings["max_tokens"] = values.max_tokens
            if values.thinking is not None:
                openrouter_settings["thinking"] = values.thinking
            openrouter_settings["openrouter_cache_instructions"] = True
            openrouter_settings["openrouter_cache_messages"] = True
            openrouter_settings["openrouter_cache_tool_definitions"] = "1h"
            return openrouter_settings

        return model_settings

    @override
    def _default_thinking(self, model: Model) -> ThinkingLevel | None:
        # Custom OpenAI-compatible endpoints (Together, vLLM, LM Studio, ...)
        # often don't honor `reasoning_effort`
        if self._is_openai_compatible():
            return None
        return super()._default_thinking(model)


class AnthropicProvider(PydanticProvider["PydanticAnthropic"]):
    @override
    def create_provider(self, config: AnyProviderConfig) -> PydanticAnthropic:
        from pydantic_ai.providers.anthropic import (
            AnthropicProvider as PydanticAnthropic,
        )

        return PydanticAnthropic(api_key=config.api_key)

    @override
    def create_model(self) -> Model:
        from pydantic_ai.models.anthropic import AnthropicModel

        return AnthropicModel(model_name=self.model, provider=self.provider)

    @override
    def _build_model_settings(
        self, model: Model, max_tokens: int | None
    ) -> AnthropicModelSettings:
        # Anthropic provider needs to set the max tokens to 32768
        # https://github.com/marimo-team/marimo/pull/9703
        values = self._base_model_settings(
            model, max_tokens or ANTHROPIC_DEFAULT_MAX_TOKENS
        )
        settings: AnthropicModelSettings = {"anthropic_cache": True}
        if values.max_tokens is not None:
            settings["max_tokens"] = values.max_tokens
        if values.thinking is not None:
            settings["thinking"] = values.thinking
        return settings

    @override
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

    @override
    def create_provider(self, config: AnyProviderConfig) -> PydanticBedrock:
        from pydantic_ai.providers.bedrock import (
            BedrockProvider as PydanticBedrock,
        )

        self.setup_credentials(config)
        # For bedrock, the config sets the region name as the base_url
        return PydanticBedrock(region_name=config.base_url)

    @override
    def create_model(self) -> BedrockConverseModel:
        from pydantic_ai.models.bedrock import BedrockConverseModel

        return BedrockConverseModel(
            model_name=self.model, provider=self.provider
        )

    @override
    def _build_model_settings(
        self, model: Model, max_tokens: int | None
    ) -> BedrockModelSettings:
        values = self._base_model_settings(model, max_tokens)
        settings: BedrockModelSettings = {
            "bedrock_cache_instructions": True,
            "bedrock_cache_messages": True,
            "bedrock_cache_tool_definitions": "1h",
        }
        if values.max_tokens is not None:
            settings["max_tokens"] = values.max_tokens
        if values.thinking is not None:
            settings["thinking"] = values.thinking
        return settings


def get_completion_provider(
    config: AnyProviderConfig, model: str
) -> PydanticProvider[Provider]:
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
        return CustomProvider(model_id, config, [DependencyManager.openai])
