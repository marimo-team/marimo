# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import re
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    cast,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

from marimo._ai._convert import (
    convert_to_anthropic_messages,
    convert_to_google_messages,
    convert_to_groq_messages,
    convert_to_openai_messages,
)
from marimo._ai._types import (
    ChatMessage,
    ChatModel,
    ChatModelConfig,
)
from marimo._dependencies.dependencies import DependencyManager

DEFAULT_SYSTEM_MESSAGE = (
    "You are a helpful assistant specializing in data science."
)


def _looks_like_streaming_error(e: Exception) -> bool:
    """Check if an exception appears to be related to streaming not being supported."""
    error_msg = str(e).lower()
    # Use word boundaries to match whole words only (not substrings like "downstream")
    return bool(
        re.search(r"\bstreaming\b", error_msg)
        or re.search(r"\bstream\b", error_msg)
    )


class simple(ChatModel):
    """
    Convenience class for wrapping a ChatModel or callable to
    take a single prompt

    Args:
        delegate: A callable that takes a
            single prompt and returns a response
    """

    def __init__(self, delegate: Callable[[str], object]):
        self.delegate = delegate

    def __call__(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> object:
        del config
        prompt = str(messages[-1].content)
        return self.delegate(prompt)


class openai(ChatModel):
    """
    OpenAI ChatModel with optional tool support.

    Args:
        model: The model to use.
            Can be found on the [OpenAI models page](https://platform.openai.com/docs/models)
        system_message: The system message to use
        api_key: The API key to use.
            If not provided, the API key will be retrieved
            from the OPENAI_API_KEY environment variable or the user's config.
        base_url: The base URL to use. Set this to use OpenAI-compatible providers:
            - DeepSeek: "https://api.deepseek.com"
            - Groq: "https://api.groq.com/openai/v1"
            - Together AI: "https://api.together.xyz/v1"
        tools: Optional list of Python functions to use as tools.
            Functions should have type hints and docstrings for automatic
            schema generation. Tool calls are handled automatically.

    Example with tools:
        ```python
        def get_weather(location: str, unit: str = "fahrenheit") -> dict:
            '''Get the current weather for a location.

    Args:
                location: The city and state, e.g. "San Francisco, CA"
                unit: Temperature unit, either "celsius" or "fahrenheit"
            '''
            return {"location": location, "temperature": 72, "unit": unit}

        chat = mo.ui.chat(
            mo.ai.llm.openai(
                "gpt-4.1",
                tools=[get_weather],
            ),
        )
        ```
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        tools: Optional[list[Callable[..., Any]]] = None,
    ):
        self.model = model
        self.system_message = system_message
        self.api_key = api_key
        self.base_url = base_url
        self.tools = tools or []
        # Build tool lookup dict
        self._tools_dict: dict[str, Callable[..., Any]] = {
            func.__name__: func for func in self.tools
        }

    @property
    def _require_api_key(self) -> str:
        # If the api key is provided, use it
        if self.api_key is not None:
            return self.api_key

        # Then check the environment variable
        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key is not None:
            return env_key

        # Then check the user's config
        try:
            from marimo._runtime.context.types import get_context

            api_key = get_context().marimo_config["ai"]["open_ai"]["api_key"]
            if api_key:
                return api_key
        except Exception:
            pass

        raise ValueError(
            "openai api key not provided. Pass it as an argument or "
            "set OPENAI_API_KEY as an environment variable"
        )

    def _stream_response(self, response: Any) -> Generator[str, None, None]:
        """Helper method for streaming - yields delta chunks.

        Each yield is a new piece of content (delta) to be accumulated
        by the consumer. This follows the standard OpenAI streaming pattern.
        """
        for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

    def __call__(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> object:
        DependencyManager.openai.require(
            "chat model requires openai. `pip install openai`"
        )
        from urllib.parse import parse_qs, urlparse

        from openai import (  # type: ignore[import-not-found]
            AzureOpenAI,
            OpenAI,
        )

        # Azure OpenAI clients are instantiated slightly differently
        # To check if we're using Azure, we check the base_url for the format
        # https://[subdomain].openai.azure.com/openai/deployments/[model]/chat/completions?api-version=[api_version]
        parsed_url = urlparse(self.base_url)
        if parsed_url.hostname and cast(str, parsed_url.hostname).endswith(
            ".openai.azure.com"
        ):
            self.model = cast(str, parsed_url.path).split("/")[3]
            api_version = parse_qs(cast(str, parsed_url.query))["api-version"][
                0
            ]
            client: AzureOpenAI | OpenAI = AzureOpenAI(
                api_key=self._require_api_key,
                api_version=api_version,
                azure_endpoint=f"{cast(str, parsed_url.scheme)}://{cast(str, parsed_url.hostname)}",
            )
        else:
            client = OpenAI(
                api_key=self._require_api_key,
                base_url=self.base_url or None,
            )

        openai_messages = convert_to_openai_messages(
            [ChatMessage(role="system", content=self.system_message)]
            + messages
        )

        # Try streaming first, fall back to non-streaming on error
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                max_completion_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                frequency_penalty=config.frequency_penalty,
                presence_penalty=config.presence_penalty,
                stream=True,
            )
            return self._stream_response(response)
        except Exception as e:
            # Some models (like o1-preview) don't support streaming
            # Fall back to non-streaming mode
            if _looks_like_streaming_error(e):
                non_stream_response = client.chat.completions.create(
                    model=self.model,
                    messages=openai_messages,
                    max_completion_tokens=config.max_tokens,
                    temperature=config.temperature,
                    top_p=config.top_p,
                    frequency_penalty=config.frequency_penalty,
                    presence_penalty=config.presence_penalty,
                    stream=False,
                )
                return non_stream_response.choices[0].message.content or ""
            raise


class anthropic(ChatModel):
    """
    Anthropic ChatModel

    Args:
        model: The model to use.
            Can be found on the [Anthropic models page](https://docs.anthropic.com/en/docs/about-claude/models)
        system_message: The system message to use
        api_key: The API key to use.
            If not provided, the API key will be retrieved
            from the ANTHROPIC_API_KEY environment variable
            or the user's config.
        base_url: The base URL to use
    """

    def supports_temperature(self, model: str) -> bool:
        # Reasoning models (>4.0) don't support temperature
        return model.startswith("claude-3")

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model = model
        self.system_message = system_message
        self.api_key = api_key
        self.base_url = base_url

    @property
    def _require_api_key(self) -> str:
        # If the api key is provided, use it
        if self.api_key is not None:
            return self.api_key

        # Then check the user's config
        try:
            from marimo._runtime.context.types import get_context

            api_key = get_context().marimo_config["ai"]["anthropic"]["api_key"]
            if api_key:
                return api_key
        except Exception:
            pass

        # Then check the environment variable
        env_key = os.environ.get("ANTHROPIC_API_KEY")
        if env_key is not None:
            return env_key

        raise ValueError(
            "anthropic api key not provided. Pass it as an argument or "
            "set ANTHROPIC_API_KEY as an environment variable"
        )

    def _stream_response(
        self, client: Any, params: Any
    ) -> Generator[str, None, None]:
        """Helper method for streaming - yields delta chunks.

        Each yield is a new piece of content (delta) to be accumulated
        by the consumer. This follows the standard Anthropic streaming pattern.
        """
        with client.messages.stream(**params) as stream:
            yield from stream.text_stream

    def __call__(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> object:
        DependencyManager.anthropic.require(
            "chat model requires anthropic. `pip install anthropic`"
        )
        from anthropic import Anthropic

        client = Anthropic(
            api_key=self._require_api_key,
            base_url=self.base_url,
        )

        anthropic_messages = convert_to_anthropic_messages(messages)
        params: dict[str, Any] = {
            "model": self.model,
            "system": self.system_message,
            "max_tokens": config.max_tokens or 4096,
            "messages": anthropic_messages,
        }
        if config.top_p is not None:
            params["top_p"] = config.top_p
        if config.top_k is not None:
            params["top_k"] = config.top_k
        if config.temperature is not None and self.supports_temperature(
            self.model
        ):
            params["temperature"] = config.temperature

        # Try streaming first, fall back to non-streaming on error
        try:
            # Note: client.messages.stream() doesn't take a 'stream' parameter
            # It's already a streaming method
            return self._stream_response(client, params)
        except Exception as e:
            # Fall back to non-streaming mode if streaming fails
            if _looks_like_streaming_error(e):
                response = client.messages.create(**params)
                return response.content[0].text
            raise


class google(ChatModel):
    """
    Google AI ChatModel

    Args:
        model: The model to use.
            Can be found on the [Gemini models page](https://ai.google.dev/gemini-api/docs/models/gemini)
        system_message: The system message to use
        api_key: The API key to use.
            If not provided, the API key will be retrieved
            from the GOOGLE_AI_API_KEY environment variable
            or the user's config.
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
    ):
        self.model = model
        self.system_message = system_message
        self.api_key = api_key

    @property
    def _require_api_key(self) -> str:
        # If the api key is provided, use it
        if self.api_key is not None:
            return self.api_key

        # Then check the user's config
        try:
            from marimo._runtime.context.types import get_context

            api_key = get_context().marimo_config["ai"]["google"]["api_key"]
            if api_key:
                return api_key
        except Exception:
            pass

        # Then check the environment variable
        env_key = os.environ.get("GOOGLE_AI_API_KEY")
        if env_key is not None:
            return env_key

        raise ValueError(
            "Google AI api key not provided. Pass it as an argument or "
            "set GOOGLE_AI_API_KEY as an environment variable"
        )

    def _stream_response(
        self, client: Any, google_messages: Any, generation_config: Any
    ) -> Generator[str, None, None]:
        """Helper method for streaming - yields delta chunks.

        Each yield is a new piece of content (delta) to be accumulated
        by the consumer. This follows the standard Google AI streaming pattern.
        """
        response = client.models.generate_content_stream(
            model=self.model,
            contents=google_messages,
            config=generation_config,
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text

    def __call__(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> object:
        DependencyManager.google_ai.require(
            "chat model requires google. `pip install google-genai`"
        )
        from google import genai  # type: ignore[import-not-found]

        client = genai.Client(api_key=self._require_api_key)

        google_messages = convert_to_google_messages(messages)

        # Build config once to avoid duplication
        generation_config = {
            "system_instruction": self.system_message,
            "max_output_tokens": config.max_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "top_k": config.top_k,
            "frequency_penalty": config.frequency_penalty,
            "presence_penalty": config.presence_penalty,
        }

        # Try streaming first, fall back to non-streaming on error
        try:
            return self._stream_response(
                client, google_messages, generation_config
            )
        except Exception as e:
            # Fall back to non-streaming mode if streaming fails
            if _looks_like_streaming_error(e):
                response = client.models.generate_content(
                    model=self.model,
                    contents=google_messages,
                    config=generation_config,  # type: ignore[arg-type]
                )
                return response.text
            raise


class groq(ChatModel):
    """
    Groq ChatModel

    Args:
        model: The model to use.
            Can be found on the [Groq models page](https://console.groq.com/docs/models)
        system_message: The system message to use
        api_key: The API key to use.
            If not provided, the API key will be retrieved
            from the GROQ_API_KEY environment variable or the user's config.
        base_url: The base URL to use
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model = model
        self.system_message = system_message
        self.api_key = api_key
        self.base_url = base_url

    @property
    def _require_api_key(self) -> str:
        # If the api key is provided, use it
        if self.api_key is not None:
            return self.api_key

        # Then check the environment variable
        env_key = os.environ.get("GROQ_API_KEY")
        if env_key is not None:
            return env_key

        # TODO(haleshot): Add config support later
        # # Then check the user's config
        # try:
        #     from marimo._runtime.context.types import get_context
        #
        #     api_key = get_context().user_config["ai"]["groq"]["api_key"]
        #     if api_key:
        #         return api_key
        # except Exception:
        #     pass

        raise ValueError(
            "groq api key not provided. Pass it as an argument or "
            "set GROQ_API_KEY as an environment variable"
        )

    def _stream_response(
        self, client: Any, groq_messages: Any, config: ChatModelConfig
    ) -> Generator[str, None, None]:
        """Helper method for streaming - yields delta chunks.

        Each yield is a new piece of content (delta) to be accumulated
        by the consumer. This follows the standard Groq streaming pattern.
        """
        stream = client.chat.completions.create(
            model=self.model,
            messages=groq_messages,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            top_p=config.top_p,
            stop=None,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

    def __call__(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> object:
        DependencyManager.groq.require(
            "chat model requires groq. `pip install groq`"
        )
        from groq import Groq  # type: ignore[import-not-found]

        client = Groq(api_key=self._require_api_key, base_url=self.base_url)

        groq_messages = convert_to_groq_messages(
            [ChatMessage(role="system", content=self.system_message)]
            + messages
        )

        # Try streaming first, fall back to non-streaming on error
        try:
            return self._stream_response(client, groq_messages, config)
        except Exception as e:
            # Fall back to non-streaming mode if streaming fails
            if _looks_like_streaming_error(e):
                response = client.chat.completions.create(
                    model=self.model,
                    messages=groq_messages,
                    max_tokens=config.max_tokens,
                    temperature=config.temperature,
                    top_p=config.top_p,
                    stop=None,
                    stream=False,
                )
                return response.choices[0].message.content or ""
            raise


class bedrock(ChatModel):
    """
    AWS Bedrock ChatModel

    Args:
        model: The model ID to use.
            Format: [<cross-region>.]<provider>.<model> (e.g., "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
        system_message: The system message to use
        region_name: The AWS region to use (e.g., "us-east-1")
        profile_name: The AWS profile to use for credentials (optional)
        credentials: AWS credentials (optional)
            Dict with keys: "aws_access_key_id" and "aws_secret_access_key"
            If not provided, credentials will be retrieved from the environment
            or the AWS configuration files.
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        region_name: str = "us-east-1",
        profile_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        if not model.startswith("bedrock/"):
            model = f"bedrock/{model}"
        self.model = model
        self.system_message = system_message
        self.region_name = region_name
        self.profile_name = profile_name
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

    def _setup_credentials(self) -> None:
        # Use profile name if provided, otherwise use API key
        if self.profile_name:
            os.environ["AWS_PROFILE"] = self.profile_name
        elif self.aws_access_key_id and self.aws_secret_access_key:
            os.environ["AWS_ACCESS_KEY_ID"] = self.aws_access_key_id
            os.environ["AWS_SECRET_ACCESS_KEY"] = self.aws_secret_access_key
        else:
            pass  # Use default credential chain

    def _stream_response(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> Generator[str, None, None]:
        """Helper method for streaming - yields delta chunks.

        Each yield is a new piece of content (delta) to be accumulated
        by the consumer. This follows the standard AWS Bedrock streaming pattern.
        """
        from litellm import completion as litellm_completion

        response = litellm_completion(
            model=self.model,
            messages=convert_to_openai_messages(
                [ChatMessage(role="system", content=self.system_message)]
                + messages
            ),
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            top_p=config.top_p,
            frequency_penalty=config.frequency_penalty,
            presence_penalty=config.presence_penalty,
            stream=True,
        )

        for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

    def __call__(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> object:
        DependencyManager.boto3.require(
            "bedrock chat model requires boto3. `pip install boto3`"
        )
        DependencyManager.litellm.require(
            "bedrock chat model requires litellm. `pip install litellm`"
        )
        self._setup_credentials()

        try:
            # Try streaming first, fall back to non-streaming on error
            try:
                return self._stream_response(messages, config)
            except Exception as stream_error:
                # Fall back to non-streaming if streaming fails
                if _looks_like_streaming_error(stream_error):
                    from litellm import completion as litellm_completion

                    response = litellm_completion(
                        model=self.model,
                        messages=convert_to_openai_messages(
                            [
                                ChatMessage(
                                    role="system",
                                    content=self.system_message,
                                )
                            ]
                            + messages
                        ),
                        max_tokens=config.max_tokens,
                        temperature=config.temperature,
                        top_p=config.top_p,
                        frequency_penalty=config.frequency_penalty,
                        presence_penalty=config.presence_penalty,
                        stream=False,
                    )
                    return response.choices[0].message.content or ""
                raise
        except Exception as e:
            # Handle common AWS exceptions with helpful messages
            error_msg = str(e)

            if "AccessDenied" in error_msg:
                raise ValueError(
                    f"Access denied to AWS Bedrock model {self.model}. "
                    "Make sure your credentials have the necessary permissions."
                ) from e
            elif (
                "ValidationException" in error_msg
                and "model id" in error_msg.lower()
            ):
                raise ValueError(
                    f"Model {self.model} not found or not enabled for your account. "
                    "Make sure you've enabled model access in the AWS Bedrock console."
                ) from e
            elif "ResourceNotFoundException" in error_msg:
                raise ValueError(
                    f"Model {self.model} not found in region {self.region_name}. "
                    "Check that the model ID is correct and available in this region."
                ) from e
            else:
                # Re-raise original exception if not handled
                raise


class pydantic_ai(ChatModel):
    """
    ChatModel using Pydantic AI with streaming and tool support.

    This class provides a simple interface to use Pydantic AI with marimo's
    chat UI. You can either pass a model string (like other mo.ai.llm classes)
    or a pre-configured Agent for full control.

    Args:
        model: Either a model string (e.g., "openai:gpt-4.1"), a Pydantic AI
            Model object, or a pre-configured pydantic_ai.Agent instance.
            When passing an Agent, other parameters are ignored.
        tools: List of tool functions for the model to use (ignored if Agent).
        instructions: System instructions for the model (ignored if Agent).
        model_settings: Model-specific settings (e.g., AnthropicModelSettings
            for thinking). Can be used with both model strings and Agents.
        **kwargs: Additional arguments passed to pydantic_ai.Agent constructor.
            See https://ai.pydantic.dev/agents/ for all options.

    Example - Simple usage (like other mo.ai.llm classes):
        ```python
        chat = mo.ui.chat(
            mo.ai.llm.pydantic_ai(
                "openai:gpt-4.1",
                tools=[get_weather, calculate],
                instructions="You are a helpful assistant.",
            )
        )
        ```

    Example - With thinking enabled:
        ```python
        from pydantic_ai.models.anthropic import AnthropicModelSettings

        chat = mo.ui.chat(
            mo.ai.llm.pydantic_ai(
                "anthropic:claude-sonnet-4-5",
                tools=[get_weather],
                instructions="Think step by step.",
                model_settings=AnthropicModelSettings(
                    max_tokens=8000,
                    anthropic_thinking={
                        "type": "enabled",
                        "budget_tokens": 4000,
                    },
                ),
            )
        )
        ```

    Example - Using a pre-configured Agent (full control):
        ```python
        from pydantic_ai import Agent

        # Create and fully configure your own Agent
        agent = Agent(
            "anthropic:claude-sonnet-4-5",
            tools=[get_weather],
            deps_type=MyDeps,
            output_type=MyOutput,
            # ... any other Agent options
        )

        chat = mo.ui.chat(mo.ai.llm.pydantic_ai(agent))
        ```

    Example - W&B Inference with custom model:
        ```python
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
        from pydantic_ai.profiles.openai import OpenAIModelProfile

        model = OpenAIChatModel(
            model_name="deepseek-ai/DeepSeek-R1-0528",
            provider=OpenAIProvider(
                api_key="your-wandb-key",
                base_url="https://api.inference.wandb.ai/v1",
            ),
            profile=OpenAIModelProfile(
                openai_chat_thinking_field="reasoning_content",
            ),
        )

        chat = mo.ui.chat(
            mo.ai.llm.pydantic_ai(model, instructions="Think step by step.")
        )
        ```
    """

    def __init__(
        self,
        model: Any,
        *,
        tools: Optional[list[Callable[..., Any]]] = None,
        instructions: Optional[str] = None,
        model_settings: Optional[Any] = None,
        **kwargs: Any,
    ):
        self._model_settings = model_settings
        self._agent: Any = None  # Lazy initialization
        self._model = model
        self._tools = tools
        self._instructions = instructions
        self._kwargs = kwargs

    def _get_agent(self) -> Any:
        """Get or create the Agent (lazy initialization)."""
        if self._agent is not None:
            return self._agent

        from pydantic_ai import Agent

        # Check if model is already an Agent (duck-type check)
        if hasattr(self._model, "run_stream_events"):
            self._agent = self._model
        else:
            # Create Agent with provided parameters
            self._agent = Agent(
                self._model,
                tools=self._tools or [],
                instructions=self._instructions,
                model_settings=self._model_settings,
                **self._kwargs,
            )
        return self._agent

    def __call__(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> AsyncGenerator[Any, None]:
        """Returns an async generator that handles streaming and tool calls."""
        DependencyManager.pydantic_ai.require(
            "pydantic_ai chat model requires pydantic-ai. `pip install pydantic-ai`"
        )
        return self._stream_response(messages, config)

    async def _stream_response(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> AsyncGenerator[Any, None]:
        """Async generator that streams text and tool call parts."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            ThinkingPart,
            ToolCallPart,
            ToolReturnPart,
        )
        from pydantic_ai.settings import ModelSettings

        # Get or create the agent
        agent = self._get_agent()

        # Use provided model_settings, or build default from config
        # Note: if Agent was passed directly, model_settings may have been
        # configured on the Agent itself, so we only use config as fallback
        model_settings = self._model_settings
        if model_settings is None:
            model_settings = ModelSettings(
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
            )

        # Convert marimo ChatMessages to Pydantic AI message history
        message_history = self._convert_messages_to_pydantic_ai(messages[:-1])

        # Get the current user prompt
        user_prompt = str(messages[-1].content) if messages else ""

        # Track state for structured response
        current_text = ""
        current_thinking = ""
        has_tool_calls = False
        has_thinking = False
        final_result: Any = None
        # Track tool calls as they happen
        pending_tool_calls: dict[str, dict[str, Any]] = {}

        def _build_current_parts() -> list[dict[str, Any]]:
            """Build the current parts list for yielding."""
            result: list[dict[str, Any]] = []
            if current_thinking:
                result.append({"type": "reasoning", "text": current_thinking})
            # Add completed tool calls
            result.extend(pending_tool_calls.values())
            if current_text:
                result.append({"type": "text", "text": current_text})
            return result

        # Use run_stream_events() to get all events in real-time
        # This includes thinking parts, text parts, tool calls, etc.
        # See: https://ai.pydantic.dev/agents/#streaming-events-and-final-output
        async for event in agent.run_stream_events(
            user_prompt,
            message_history=message_history if message_history else None,
            model_settings=model_settings,
        ):
            event_type = type(event).__name__

            # PartStartEvent - when a new part begins (thinking, text, tool call)
            if event_type == "PartStartEvent":
                part = getattr(event, "part", None)
                if part is not None:
                    part_type = type(part).__name__
                    # Thinking part started - yield immediately
                    if part_type == "ThinkingPart" or isinstance(
                        part, ThinkingPart
                    ):
                        has_thinking = True
                        content = getattr(part, "content", None)
                        current_thinking = content if content else ""
                        yield {"parts": _build_current_parts()}

                    # TextPart started - capture initial content
                    elif part_type == "TextPart":
                        initial_text = getattr(part, "content", "") or ""
                        if initial_text:
                            current_text += initial_text
                            if has_thinking or has_tool_calls:
                                yield {"parts": _build_current_parts()}
                            else:
                                yield initial_text

                    # Tool call started - show as "calling" state
                    elif part_type == "ToolCallPart" or isinstance(
                        part, ToolCallPart
                    ):
                        has_tool_calls = True
                        tool_name = getattr(part, "tool_name", "unknown")
                        tool_call_id = getattr(
                            part, "tool_call_id", f"call_{id(part)}"
                        )
                        tool_args = {}
                        if hasattr(part, "args"):
                            args = part.args
                            if hasattr(args, "args_dict"):
                                tool_args = args.args_dict
                            elif isinstance(args, dict):
                                tool_args = args

                        # Add as pending (calling state)
                        pending_tool_calls[tool_call_id] = {
                            "type": f"tool-{tool_name}",
                            "toolCallId": tool_call_id,
                            "state": "calling",
                            "input": tool_args,
                            "output": None,
                        }
                        yield {"parts": _build_current_parts()}

            # PartDeltaEvent - incremental content updates
            elif event_type == "PartDeltaEvent":
                delta = getattr(event, "delta", None)
                if delta is not None:
                    delta_type = type(delta).__name__
                    # Text delta - stream to UI
                    if delta_type == "TextPartDelta":
                        text_delta = getattr(delta, "content_delta", "") or ""
                        current_text += text_delta
                        # Always yield structured parts to preserve thinking/tools
                        if has_thinking or has_tool_calls:
                            yield {"parts": _build_current_parts()}
                        else:
                            yield text_delta
                    # Thinking delta - update thinking in real-time
                    elif delta_type == "ThinkingPartDelta":
                        thinking_delta = (
                            getattr(delta, "content_delta", "") or ""
                        )
                        current_thinking += thinking_delta
                        yield {"parts": _build_current_parts()}

            # ToolReturnEvent or similar - when tool returns a result
            elif event_type == "ToolReturnEvent":
                tool_call_id = getattr(event, "tool_call_id", None)
                tool_return = getattr(event, "content", None)
                if tool_call_id and tool_call_id in pending_tool_calls:
                    pending_tool_calls[tool_call_id]["state"] = (
                        "output-available"
                    )
                    pending_tool_calls[tool_call_id]["output"] = tool_return
                    yield {"parts": _build_current_parts()}

            # AgentRunResultEvent - final result with all messages
            elif event_type == "AgentRunResultEvent":
                final_result = getattr(event, "result", None)

        # After streaming, update tool calls with their outputs from final result
        if final_result is not None:
            try:
                # Use new_messages() to only get messages from THIS run
                # (not the history we passed in) - this prevents
                # tool calls from previous turns from being picked up
                new_msgs = getattr(final_result, "new_messages", None)
                if callable(new_msgs):
                    new_msgs = new_msgs()

                if new_msgs:
                    # Build a map of tool call id -> output
                    tool_outputs: dict[str, Any] = {}
                    for msg in new_msgs:
                        if isinstance(msg, ModelRequest):
                            for rp in msg.parts:
                                if isinstance(rp, ToolReturnPart):
                                    tc_id = getattr(rp, "tool_call_id", None)
                                    if tc_id:
                                        tool_outputs[tc_id] = rp.content

                    # Update pending tool calls with their outputs
                    for tc_id, output in tool_outputs.items():
                        if tc_id in pending_tool_calls:
                            pending_tool_calls[tc_id]["state"] = (
                                "output-available"
                            )
                            pending_tool_calls[tc_id]["output"] = output

                    # Check for any tool calls we missed during streaming
                    for msg in new_msgs:
                        if isinstance(msg, ModelResponse):
                            for part in msg.parts:
                                # Capture thinking if not already done
                                # (W&B and other OpenAI-compatible APIs may only
                                # include reasoning_content in final response,
                                # not streamed as events)
                                if isinstance(part, ThinkingPart):
                                    if not current_thinking:
                                        current_thinking = (
                                            getattr(part, "content", "") or ""
                                        )
                                        if current_thinking:
                                            has_thinking = True

                                # Handle tool calls we may have missed
                                elif isinstance(part, ToolCallPart):
                                    tool_call_id = getattr(
                                        part,
                                        "tool_call_id",
                                        f"call_{id(part)}",
                                    )
                                    if tool_call_id not in pending_tool_calls:
                                        tool_name = part.tool_name
                                        tool_args = {}
                                        if hasattr(part, "args"):
                                            args = part.args
                                            if hasattr(args, "args_dict"):
                                                tool_args = args.args_dict
                                            elif isinstance(args, dict):
                                                tool_args = args

                                        pending_tool_calls[tool_call_id] = {
                                            "type": f"tool-{tool_name}",
                                            "toolCallId": tool_call_id,
                                            "state": "output-available",
                                            "input": tool_args,
                                            "output": tool_outputs.get(
                                                tool_call_id
                                            ),
                                        }

                # Yield final structured response if we had thinking or tools
                # Include current_thinking check for APIs that only return
                # reasoning in final response (not streamed)
                if (
                    has_tool_calls
                    or has_thinking
                    or current_thinking
                    or pending_tool_calls
                ):
                    final_parts = _build_current_parts()

                    # Store pydantic-ai's ALL messages for history
                    # Using all_messages() instead of new_messages() ensures we accumulate
                    # the full conversation history with proper tool_use/tool_result pairing
                    # See: https://ai.pydantic.dev/message-history/
                    try:
                        # Use all_messages_json() to get complete history
                        messages_json = final_result.all_messages_json()
                        if messages_json:
                            final_parts.append(
                                {
                                    "type": "_pydantic_history",
                                    "messages_json": (
                                        messages_json.decode("utf-8")
                                        if isinstance(messages_json, bytes)
                                        else messages_json
                                    ),
                                }
                            )
                    except Exception:
                        # If we can't store history, continue without it
                        # (manual conversion will be used as fallback)
                        pass

                    if final_parts:
                        yield {"parts": final_parts}
            except Exception:
                # If we can't process structured messages, that's ok
                pass

    def _extract_stored_pydantic_messages(
        self, parts: Optional[list[Any]], type_adapter: Any
    ) -> Optional[list[Any]]:
        """Extract stored pydantic-ai messages from a message's parts.

        Returns the deserialized messages if found, None otherwise.
        """
        if not parts:
            return None

        for part in parts:
            part_type = (
                part.get("type", "")
                if isinstance(part, dict)
                else getattr(part, "type", "")
            )
            if part_type == "_pydantic_history":
                messages_json = (
                    part.get("messages_json", "")
                    if isinstance(part, dict)
                    else getattr(part, "messages_json", "")
                )
                if messages_json:
                    try:
                        # Deserialize using pydantic-ai's type adapter
                        result = type_adapter.validate_json(messages_json)
                        return result
                    except Exception as e:
                        import logging

                        logging.getLogger(__name__).debug(
                            f"Failed to deserialize pydantic messages: {e}"
                        )
                        return None
        return None

    def _convert_messages_to_pydantic_ai(
        self, messages: list[ChatMessage]
    ) -> list[Any]:
        """Convert marimo ChatMessages to Pydantic AI message history format.

        Strategy:
        1. Look for the LAST assistant message with stored pydantic-ai history
           (which contains the full conversation up to that point)
        2. If found, use that as the base and only add subsequent user messages
        3. If not found, fall back to manual conversion

        This ensures proper tool_use/tool_result pairing that Claude requires.
        See: https://ai.pydantic.dev/message-history/
        """
        from pydantic_ai.messages import (
            ModelMessagesTypeAdapter,
            ModelRequest,
            ModelResponse,
            TextPart as PydanticTextPart,
            ThinkingPart,
            ToolCallPart,
            ToolReturnPart,
            UserPromptPart,
        )

        # First pass: find the last assistant message with stored pydantic history
        last_stored_index = -1
        last_stored_messages: Optional[list[Any]] = None

        for i, msg in enumerate(messages):
            if msg.role == "assistant" and msg.parts:
                stored = self._extract_stored_pydantic_messages(
                    msg.parts, ModelMessagesTypeAdapter
                )
                if stored:
                    last_stored_index = i
                    last_stored_messages = stored

        # If we found stored history, use it as base and only add subsequent messages
        if last_stored_messages is not None:
            pydantic_messages: list[Any] = list(last_stored_messages)
            # Add any user messages that came AFTER the stored history
            for msg in messages[last_stored_index + 1 :]:
                if msg.role == "user":
                    pydantic_messages.append(
                        ModelRequest(
                            parts=[UserPromptPart(content=str(msg.content))]
                        )
                    )
            return pydantic_messages

        # No stored history found - fall back to manual conversion
        pydantic_messages = []

        for msg in messages:
            if msg.role == "user":
                pydantic_messages.append(
                    ModelRequest(
                        parts=[UserPromptPart(content=str(msg.content))]
                    )
                )
            elif msg.role == "assistant":
                # Check if this message has tool parts
                if msg.parts:
                    response_parts: list[Any] = []
                    tool_returns: list[Any] = []

                    for part in msg.parts:
                        part_type = (
                            part.get("type", "")
                            if isinstance(part, dict)
                            else getattr(part, "type", "")
                        )

                        if part_type == "text":
                            text = (
                                part.get("text", "")
                                if isinstance(part, dict)
                                else getattr(part, "text", "")
                            )
                            if text:
                                response_parts.append(
                                    PydanticTextPart(content=text)
                                )
                        elif part_type == "reasoning":
                            # Handle reasoning/thinking parts
                            reasoning_text = (
                                part.get("text", "")
                                if isinstance(part, dict)
                                else getattr(part, "text", "")
                            )
                            if reasoning_text:
                                response_parts.append(
                                    ThinkingPart(content=reasoning_text)
                                )
                        elif part_type.startswith("tool-"):
                            # This is a tool invocation
                            tool_name = part_type.replace("tool-", "")
                            tool_call_id = (
                                part.get("toolCallId")
                                or part.get("tool_call_id")
                                if isinstance(part, dict)
                                else (
                                    getattr(part, "toolCallId", None)
                                    or getattr(part, "tool_call_id", "")
                                )
                            )
                            tool_input = (
                                part.get("input", {})
                                if isinstance(part, dict)
                                else getattr(part, "input", {})
                            )
                            tool_output = (
                                part.get("output")
                                if isinstance(part, dict)
                                else getattr(part, "output", None)
                            )

                            # Add tool call to response
                            response_parts.append(
                                ToolCallPart(
                                    tool_name=tool_name,
                                    args=tool_input,
                                    tool_call_id=tool_call_id or "",
                                )
                            )

                            # Add tool return - always required by Claude
                            # Even if output is None, we need a tool_result
                            # Serialize dict outputs to JSON string
                            if tool_output is None:
                                serialized_output: Any = ""
                            elif isinstance(tool_output, dict):
                                serialized_output = json.dumps(tool_output)
                            else:
                                serialized_output = tool_output
                            tool_returns.append(
                                ToolReturnPart(
                                    tool_name=tool_name,
                                    content=serialized_output,
                                    tool_call_id=tool_call_id or "",
                                )
                            )

                    if response_parts:
                        pydantic_messages.append(
                            ModelResponse(parts=response_parts)
                        )

                    if tool_returns:
                        pydantic_messages.append(
                            ModelRequest(parts=tool_returns)
                        )
                else:
                    # Simple text response
                    pydantic_messages.append(
                        ModelResponse(
                            parts=[PydanticTextPart(content=str(msg.content))]
                        )
                    )

        return pydantic_messages
