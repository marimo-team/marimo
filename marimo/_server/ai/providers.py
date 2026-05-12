# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Literal,
    TypeVar,
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
)
from marimo._dependencies.dependencies import Dependency, DependencyManager
from marimo._plugins.ui._impl.chat.chat import (
    AI_SDK_VERSION,
    require_vercel_ai_sdk_support,
)
from marimo._server.ai.config import AnyProviderConfig
from marimo._server.ai.ids import AiModelId
from marimo._server.ai.tools.tool_manager import get_tool_manager
from marimo._server.ai.tools.types import ToolDefinition
from marimo._server.models.completion import UIMessage as ServerUIMessage
from marimo._utils.http import HTTPStatus

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

    from openai import AsyncOpenAI
    from pydantic_ai import Agent, DeferredToolRequests, FunctionToolset
    from pydantic_ai.models import Model
    from pydantic_ai.models.bedrock import BedrockConverseModel
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.models.openai import (
        OpenAIChatModel,
        OpenAIResponsesModel,
        OpenAIResponsesModelSettings,
    )
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
    from pydantic_ai.ui.vercel_ai.request_types import UIMessage, UIMessagePart
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
        require_vercel_ai_sdk_support()

        self.model = model
        self.config = config
        self.provider = self.create_provider(config)

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
            model_settings=self._build_agent_settings(model),
            toolsets=[toolset] if tools else None,
            instructions=system_prompt,
            output_type=output_type,
        )

    def _build_agent_settings(self, model: Model) -> ModelSettings | None:
        """Settings applied at agent level on every request."""
        from pydantic_ai.settings import ModelSettings

        thinking = self._default_thinking(model)
        if thinking is None:
            return None
        if not (
            model.profile.supports_thinking
            or model.profile.thinking_always_enabled
        ):
            return None
        return ModelSettings(thinking=thinking)

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
        max_tokens: int,
        additional_tools: list[ToolDefinition],
        stream_options: StreamOptions | None = None,
    ) -> StreamingResponse:
        """Return a streaming response from the given messages. The response are AI SDK events."""
        from pydantic_ai.ui.vercel_ai import VercelAIAdapter
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

        adapter = VercelAIAdapter(
            agent=agent,
            run_input=run_input,
            accept=stream_options.accept,
            sdk_version=AI_SDK_VERSION,
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
        from pydantic_ai.ui.vercel_ai import VercelAIAdapter

        tools = (self.config.tools or []) + additional_tools
        agent = self.create_agent(
            max_tokens=max_tokens, tools=tools, system_prompt=system_prompt
        )

        async with agent.run_stream(
            user_prompt=user_prompt,
            message_history=VercelAIAdapter.load_messages(
                self.convert_messages(messages)
            ),
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
            # Upstream (pydantic-ai) defaults to us-central1 if not set
            location = os.getenv("GOOGLE_CLOUD_LOCATION") or None
            if location is None:
                LOGGER.info(
                    "GOOGLE_CLOUD_LOCATION is not set. "
                    "The upstream provider will default to 'us-central1'. "
                    "Set this env var if your project has region restrictions."
                )
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
            settings=GoogleModelSettings(max_tokens=max_tokens),
        )


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

    def create_provider(self, config: AnyProviderConfig) -> PydanticOpenAI:
        from pydantic_ai.providers.openai import (
            OpenAIProvider as PydanticOpenAI,
        )

        client = self.get_openai_client(config)
        return PydanticOpenAI(openai_client=client)

    def create_model(self, max_tokens: int) -> OpenAIResponsesModel:
        from pydantic_ai.models.openai import (
            OpenAIResponsesModel,
            OpenAIResponsesModelSettings,
        )

        return OpenAIResponsesModel(
            model_name=self.model,
            provider=self.provider,
            settings=OpenAIResponsesModelSettings(max_tokens=max_tokens),
        )

    def _build_agent_settings(self, model: Model) -> ModelSettings | None:
        # `reasoning.summary` is only valid for OpenAI reasoning models (gpt-5
        # and the o-series).
        settings = super()._build_agent_settings(model)
        if settings is not None and "thinking" in settings:
            extra: OpenAIResponsesModelSettings = {
                "openai_reasoning_summary": self.DEFAULT_REASONING_SUMMARY,
            }
            settings.update(extra)
        return settings

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


class CustomProvider(OpenAIClientMixin, PydanticProvider["Provider[Any]"]):
    """Support for custom providers which may or may not be OpenAI-compatible.

    Note:
        We need to use the specific provider and model classes, because Pydantic AI has tuned them to send & return messages correctly.
        We can also use `Agent("provider:model_name")` to avoid finding the provider ourselves. However, this does not let
        us create custom providers. They rely on env vars to be set.
    """

    def __init__(
        self,
        model_id: AiModelId,
        config: AnyProviderConfig,
        deps: list[Dependency] | None = None,
    ):
        self._provider_name = model_id.provider
        self._responses_compatible, self._chat_compatible = (
            self._get_openai_compatible_providers()
        )
        super().__init__(model_id.model, config, deps)

    def _get_openai_compatible_providers(self) -> tuple[set[str], set[str]]:
        """Get the sets of OpenAI-compatible providers from pydantic_ai.

        Returns:
            Tuple of (responses_compatible, chat_compatible) provider names.
        """
        from pydantic_ai.models import (
            OpenAIChatCompatibleProvider,
            OpenAIResponsesCompatibleProvider,
        )

        # These are TypeAliasType objects, so we need .__value__ to get the Literal
        responses_compatible = set(
            get_args(OpenAIResponsesCompatibleProvider.__value__)
        )
        chat_compatible = set(get_args(OpenAIChatCompatibleProvider.__value__))
        return responses_compatible, chat_compatible

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

    def create_provider(self, config: AnyProviderConfig) -> Provider[Any]:
        """Create a provider based on the provider name.

        1. Try to infer the provider class from the name
        2. For OpenAI-compatible providers, pass openai_client (with SSL settings)
        3. For other providers, try to create the provider directly with the credentials
        4. Fall back to OpenAIProvider if nothing else works or not found

        Reference: https://ai.pydantic.dev/models/openai/#openai-compatible-models
        """
        from pydantic_ai.providers import infer_provider_class
        from pydantic_ai.providers.openai import (
            OpenAIProvider as PydanticOpenAI,
        )

        # Try to infer the provider class
        try:
            provider_class = infer_provider_class(self._provider_name)
            LOGGER.debug(f"Inferred provider class: {provider_class.__name__}")
        except ValueError:
            # Unknown provider, fall back to OpenAI-compatible
            LOGGER.debug(
                f"Unknown provider: {self._provider_name}. Falling back to OpenAIProvider."
            )
            client = self.get_openai_client(config)
            return PydanticOpenAI(openai_client=client)

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
        self, provider_class: type[Provider[Any]], config: AnyProviderConfig
    ) -> Provider[Any]:
        """
        Create a custom provider based on the provider class. These providers are not OpenAI-compatible.
        Import on-demand to avoid requiring the provider packages to be installed.
        """

        provider_name = provider_class.__name__
        LOGGER.debug(f"Creating custom provider: {provider_name}")

        if provider_name == "CerebrasProvider":
            from pydantic_ai.providers.cerebras import CerebrasProvider

            return CerebrasProvider(api_key=config.api_key)
        if provider_name == "CohereProvider":
            from pydantic_ai.providers.cohere import CohereProvider

            return CohereProvider(api_key=config.api_key)
        if provider_name == "GroqProvider":
            from pydantic_ai.providers.groq import GroqProvider

            return GroqProvider(
                api_key=config.api_key, base_url=config.base_url
            )
        if provider_name == "HuggingFaceProvider":
            from pydantic_ai.providers.huggingface import HuggingFaceProvider

            if config.base_url:
                return HuggingFaceProvider(
                    api_key=config.api_key, base_url=config.base_url
                )
            return HuggingFaceProvider(api_key=config.api_key)
        if provider_name == "MistralProvider":
            from pydantic_ai.providers.mistral import MistralProvider

            return MistralProvider(api_key=config.api_key)

        LOGGER.warning(
            f"Unknown provider: {provider_name}. Create a GitHub issue to request support."
        )
        # Try returning provider directly (use env vars)
        try:
            return provider_class()
        except Exception as e:
            from pydantic_ai.providers.openai import (
                OpenAIProvider as PydanticOpenAI,
            )

            LOGGER.warning(
                f"Failed to create provider {provider_class.__name__}: {e}. "
                f"Falling back to OpenAIProvider."
            )
            client = self.get_openai_client(config)
            return PydanticOpenAI(openai_client=client)

    def create_model(self, max_tokens: int) -> OpenAIChatModel:
        """Default to OpenAIChatModel"""

        from pydantic_ai.models.openai import (
            OpenAIChatModel,
            OpenAIChatModelSettings,
        )

        return OpenAIChatModel(
            model_name=self.model,
            provider=self.provider,
            settings=OpenAIChatModelSettings(max_tokens=max_tokens),
        )

    def create_agent(
        self,
        max_tokens: int,
        tools: list[ToolDefinition],
        system_prompt: str,
    ) -> Agent[None, DeferredToolRequests | str]:
        """Create a Pydantic AI agent"""
        from pydantic_ai import Agent, UserError
        from pydantic_ai.models import infer_model
        from pydantic_ai.settings import ModelSettings

        try:
            model = infer_model(
                f"{self._provider_name}:{self.model}",
                provider_factory=lambda _: self.provider,
            )
        except UserError:
            LOGGER.debug(
                f"Model {self.model} not found in pydantic-ai's model registry. "
                "Falling back to OpenAIChatModel."
            )
            model = self.create_model(max_tokens)
        except Exception as e:
            LOGGER.error(
                f"Error creating model: {e}. Falling back to OpenAIChatModel."
            )
            model = self.create_model(max_tokens)

        agent_settings = ModelSettings(max_tokens=max_tokens)
        agent_settings.update(self._build_agent_settings(model) or {})

        toolset, output_type = self._get_toolsets_and_output_type(tools)
        return Agent(
            model,
            model_settings=agent_settings,
            toolsets=[toolset] if tools else None,
            instructions=system_prompt,
            output_type=output_type,
        )

    def _default_thinking(self, model: Model) -> ThinkingLevel | None:
        # Custom OpenAI-compatible endpoints (Together, vLLM, LM Studio, ...)
        # often don't honor `reasoning_effort`
        if self._is_openai_compatible():
            return None
        return super()._default_thinking(model)


class AnthropicProvider(PydanticProvider["PydanticAnthropic"]):
    # Temperature of 0.2 was recommended for coding and data science in these links:
    # https://community.openai.com/t/cheat-sheet-mastering-temperature-and-top-p-in-chatgpt-api/172683
    # https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-latency?utm_source=chatgpt.com
    DEFAULT_TEMPERATURE = 0.2

    # Extended thinking requires temperature of 1.
    # https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
    DEFAULT_EXTENDED_THINKING_TEMPERATURE = 1

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
        from pydantic_ai.profiles.anthropic import (
            AnthropicModelProfile,
            anthropic_model_profile,
        )

        settings: AnthropicModelSettings = {"max_tokens": max_tokens}

        # Anthropic extended thinking requires temperature=1; non-thinking
        # models keep our default coding temperature. Some adaptive-only
        # models (Opus 4.7+) reject sampling settings entirely — skip
        # `temperature` for them so pydantic-ai doesn't drop it with a warning.
        profile = AnthropicModelProfile.from_profile(
            anthropic_model_profile(self.model)
        )
        if not getattr(
            profile, "anthropic_disallows_sampling_settings", False
        ):
            settings["temperature"] = (
                self.DEFAULT_EXTENDED_THINKING_TEMPERATURE
                if profile.supports_thinking
                else self.DEFAULT_TEMPERATURE
            )

        return AnthropicModel(
            model_name=self.model,
            provider=self.provider,
            settings=settings,
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
            settings=BedrockModelSettings(max_tokens=max_tokens),
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
        return CustomProvider(model_id, config, [DependencyManager.openai])


async def merge_backticks(
    chunks: AsyncIterator[str],
) -> AsyncGenerator[str, None]:
    buffer: str | None = None

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
    buffer: str | None = None
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
                    chunk = chunk.removeprefix("\n")
                    break
            # If no language-specific fence was found, check for plain backticks
            else:
                if stripped_chunk.startswith("```"):
                    has_starting_backticks = True
                    chunk = stripped_chunk[3:]  # Remove the starting backticks
                    # Also remove starting newline if present
                    chunk = chunk.removeprefix("\n")

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
