# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

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
    OpenAI ChatModel

    Args:
        model: The model to use.
            Can be found on the [OpenAI models page](https://platform.openai.com/docs/models)
        system_message: The system message to use
        api_key: The API key to use.
            If not provided, the API key will be retrieved
            from the OPENAI_API_KEY environment variable or the user's config.
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
    Universal ChatModel using Pydantic AI with automatic tool handling.

    Supports all major providers with streaming and tool execution handled
    automatically. This dramatically simplifies building chat UIs with tool
    calls compared to implementing the tool loop manually.

    Supported providers:
        - OpenAI: "openai:gpt-4.1", "openai:gpt-4o"
        - Anthropic: "anthropic:claude-sonnet-4-5", "anthropic:claude-3-5-haiku-latest"
        - Google: "google-gla:gemini-2.0-flash", "google-vertex:gemini-1.5-pro"
        - Groq: "groq:llama-3.3-70b-versatile"
        - Mistral: "mistral:mistral-large-latest"
        - And more (see Pydantic AI docs for full list)

    Args:
        model: Model identifier in the format "provider:model-name".
            See https://ai.pydantic.dev/models/ for all supported models.
        tools: List of tool functions to make available to the model.
            Functions should have docstrings describing their purpose.
            Parameter types and descriptions are extracted automatically.
        system_message: The system message to use for instructions.
        api_key: The API key for the provider. If not provided, the key
            will be retrieved from the appropriate environment variable
            (e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY).
        **kwargs: Additional arguments passed to pydantic_ai.Agent.

    Example:
        ```python
        def get_weather(location: str, unit: str = "fahrenheit") -> dict:
            '''Get the current weather for a location.

            Args:
                location: The city and state, e.g. "San Francisco, CA"
                unit: Temperature unit, either "celsius" or "fahrenheit"
            '''
            return {"location": location, "temperature": 72, "unit": unit}

        def calculate(expression: str) -> dict:
            '''Evaluate a mathematical expression.

            Args:
                expression: The math expression to evaluate, e.g. "2 + 2 * 3"
            '''
            return {"expression": expression, "result": eval(expression)}

        chat = mo.ui.chat(
            mo.ai.llm.pydantic_ai(
                "openai:gpt-4.1",
                tools=[get_weather, calculate],
                system_message="You are a helpful assistant.",
            ),
        )
        ```
    """

    def __init__(
        self,
        model: str,
        *,
        tools: Optional[list[Callable[..., Any]]] = None,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
        **kwargs: Any,
    ):
        self.model = model
        self.tools = tools or []
        self.system_message = system_message
        self.api_key = api_key
        self.kwargs = kwargs

    def _setup_api_key(self) -> None:
        """Set the API key environment variable based on the model provider."""
        if not self.api_key:
            return

        # Extract provider from model string (e.g., "openai:gpt-4.1" -> "openai")
        provider = self.model.split(":")[0].lower() if ":" in self.model else ""

        # Map providers to their environment variable names
        provider_env_vars: dict[str, str] = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google-gla": "GOOGLE_API_KEY",
            "google-vertex": "GOOGLE_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "groq": "GROQ_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "cohere": "CO_API_KEY",
        }

        env_var = provider_env_vars.get(provider)
        if env_var:
            os.environ[env_var] = self.api_key

    def __call__(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> AsyncGenerator[Any, None]:
        """Returns an async generator that handles streaming and tool calls."""
        DependencyManager.pydantic_ai.require(
            "pydantic_ai chat model requires pydantic-ai. `pip install pydantic-ai`"
        )
        # Set up API key environment variable before creating the agent
        self._setup_api_key()
        return self._stream_response(messages, config)

    async def _stream_response(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> AsyncGenerator[Any, None]:
        """Async generator that streams text and tool call parts."""
        from pydantic_ai import Agent
        from pydantic_ai.settings import ModelSettings
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            ToolCallPart,
            ToolReturnPart,
        )

        # Create the agent with tools
        agent: Agent[None, str] = Agent(
            self.model,
            tools=self.tools,
            instructions=self.system_message,
            defer_model_check=True,  # Don't validate model at init time
            **self.kwargs,
        )

        # Build model settings from config
        model_settings = ModelSettings(
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            top_p=config.top_p,
        )

        # Convert marimo ChatMessages to Pydantic AI message history
        message_history = self._convert_messages_to_pydantic_ai(messages[:-1])

        # Get the current user prompt
        user_prompt = str(messages[-1].content) if messages else ""

        async with agent.run_stream(
            user_prompt,
            message_history=message_history if message_history else None,
            model_settings=model_settings,
        ) as result:
            # Track tool calls and text parts
            parts: list[dict[str, Any]] = []
            current_text = ""
            has_tool_calls = False

            # Stream text deltas
            async for text_delta in result.stream_text(delta=True):
                current_text += text_delta
                yield text_delta

            # After streaming completes, check if there were tool calls
            # Use new_messages() to only get messages from THIS run,
            # not the entire history (which would duplicate tool calls)
            try:
                new_messages = result.new_messages()
                for msg in new_messages:
                    if isinstance(msg, ModelResponse):
                        for part in msg.parts:
                            if isinstance(part, ToolCallPart):
                                has_tool_calls = True
                                tool_name = part.tool_name
                                tool_call_id = (
                                    part.tool_call_id
                                    if hasattr(part, "tool_call_id")
                                    else f"call_{id(part)}"
                                )

                                # Find the corresponding result in new messages
                                tool_output = None
                                for result_msg in new_messages:
                                    if isinstance(result_msg, ModelRequest):
                                        for result_part in result_msg.parts:
                                            if isinstance(
                                                result_part, ToolReturnPart
                                            ) and getattr(
                                                result_part,
                                                "tool_call_id",
                                                None,
                                            ) == tool_call_id:
                                                tool_output = result_part.content

                                # Create tool part in marimo format
                                tool_part: dict[str, Any] = {
                                    "type": f"tool-{tool_name}",
                                    "toolCallId": tool_call_id,
                                    "state": "output-available",
                                    "input": (
                                        part.args.args_dict
                                        if hasattr(part, "args")
                                        and hasattr(part.args, "args_dict")
                                        else {}
                                    ),
                                    "output": tool_output,
                                }
                                parts.append(tool_part)

                # If we had tool calls, yield a structured response
                if has_tool_calls:
                    # Add text part if there was any text
                    if current_text.strip():
                        parts.insert(0, {"type": "text", "text": current_text})

                    # Get the final text response after tool execution
                    final_output = await result.get_output()
                    if final_output and final_output != current_text:
                        parts.append({"type": "text", "text": final_output})

                    yield {"parts": parts}
            except Exception:
                # If we can't get structured messages, just return text
                pass

    def _convert_messages_to_pydantic_ai(
        self, messages: list[ChatMessage]
    ) -> list[Any]:
        """Convert marimo ChatMessages to Pydantic AI message history format."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            UserPromptPart,
            TextPart as PydanticTextPart,
            ToolCallPart,
            ToolReturnPart,
        )

        pydantic_messages: list[Any] = []

        for msg in messages:
            if msg.role == "user":
                pydantic_messages.append(
                    ModelRequest(parts=[UserPromptPart(content=str(msg.content))])
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
                                response_parts.append(PydanticTextPart(content=text))
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

                            # Add tool return
                            if tool_output is not None:
                                tool_returns.append(
                                    ToolReturnPart(
                                        tool_name=tool_name,
                                        content=tool_output,
                                        tool_call_id=tool_call_id,
                                    )
                                )

                    if response_parts:
                        pydantic_messages.append(
                            ModelResponse(parts=response_parts)
                        )

                    if tool_returns:
                        pydantic_messages.append(ModelRequest(parts=tool_returns))
                else:
                    # Simple text response
                    pydantic_messages.append(
                        ModelResponse(
                            parts=[PydanticTextPart(content=str(msg.content))]
                        )
                    )

        return pydantic_messages
