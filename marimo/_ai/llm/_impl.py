# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Callable, Optional
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from collections.abc import Generator

from marimo._ai._convert import convert_to_openai_messages
from marimo._ai._types import (
    ChatMessage,
    ChatModel,
    ChatModelConfig,
)
from marimo._dependencies.dependencies import DependencyManager

DEFAULT_SYSTEM_MESSAGE = (
    "You are a helpful assistant specializing in data science."
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


class _LiteLLMBase(ChatModel):
    """
    Base class for ChatModel implementations using litellm.

    litellm provides a unified interface for 100+ LLM providers,
    reducing code duplication and dependency overhead.
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        stream: bool = True,
        provider_name: str = "provider",
        env_var_name: str = "API_KEY",
        config_key: Optional[str] = None,
    ):
        self.model = model
        self.system_message = system_message
        self.api_key = api_key
        self.base_url = base_url
        self.stream = stream
        self._provider_name = provider_name
        self._env_var_name = env_var_name
        self._config_key = config_key

    def _get_api_key(self) -> Optional[str]:
        """Get API key from various sources in order of precedence."""
        # 1. Explicitly provided
        if self.api_key is not None:
            return self.api_key

        # 2. Check environment variable
        env_key = os.environ.get(self._env_var_name)
        if env_key is not None:
            return env_key

        # 3. Check marimo config if config_key is provided
        if self._config_key:
            try:
                from marimo._runtime.context.types import get_context

                api_key = get_context().marimo_config["ai"][self._config_key][
                    "api_key"
                ]
                if api_key:
                    return api_key
            except Exception:
                pass

        return None

    def _stream_response(self, response: Any) -> Generator[str, None, None]:
        """Yield delta chunks from litellm stream.

        Each yield is a new piece of content (delta) to be accumulated
        by the consumer. This follows the standard streaming pattern.
        """
        for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

    def __call__(
        self, messages: list[ChatMessage], config: ChatModelConfig
    ) -> object:
        DependencyManager.litellm.require(
            "chat model requires litellm. `pip install litellm`"
        )
        from litellm import completion

        # Get API key
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError(
                f"{self._provider_name} api key not provided. "
                f"Pass it as an argument or set {self._env_var_name} "
                f"as an environment variable"
            )

        # Convert messages to OpenAI format (litellm expects this)
        openai_messages = convert_to_openai_messages(
            [ChatMessage(role="system", content=self.system_message)]
            + messages
        )

        # Build completion parameters
        params: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "stream": self.stream,
            "api_key": api_key,
        }

        # Add optional parameters
        if self.base_url:
            params["base_url"] = self.base_url
        if config.max_tokens:
            params["max_tokens"] = config.max_tokens
        if config.temperature is not None:
            params["temperature"] = config.temperature
        if config.top_p is not None:
            params["top_p"] = config.top_p
        if config.frequency_penalty is not None:
            params["frequency_penalty"] = config.frequency_penalty
        if config.presence_penalty is not None:
            params["presence_penalty"] = config.presence_penalty
        if config.top_k is not None:
            params["top_k"] = config.top_k

        # Try with streaming first, fall back to non-streaming if unsupported
        try:
            # Pass drop_params=True to automatically drop unsupported params
            response = completion(drop_params=True, **params)
            if self.stream:
                return self._stream_response(response)
            else:
                # Non-streaming response - return the content directly
                return response.choices[0].message.content
        except Exception as e:
            # If streaming fails due to model not supporting it, retry without streaming
            error_msg = str(e).lower()
            if self.stream and ("stream" in error_msg or "streaming" in error_msg):
                params["stream"] = False
                response = completion(drop_params=True, **params)
                return response.choices[0].message.content
            else:
                # Re-raise if it's a different error
                raise


class openai(_LiteLLMBase):
    """
    OpenAI ChatModel (powered by litellm)

    Args:
        model: The model to use.
            Can be found on the [OpenAI models page](https://platform.openai.com/docs/models)
        system_message: The system message to use
        api_key: The API key to use.
            If not provided, the API key will be retrieved
            from the OPENAI_API_KEY environment variable or the user's config.
        base_url: The base URL to use. Supports Azure OpenAI endpoints.
        stream: Whether to stream responses. Defaults to True.
            If the model doesn't support streaming, it will automatically fall back to non-streaming.
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        stream: bool = True,
    ):
        # Handle Azure OpenAI URL format
        # https://[subdomain].openai.azure.com/openai/deployments/[model]/...
        if base_url:
            parsed_url = urlparse(base_url)
            if parsed_url.hostname and parsed_url.hostname.endswith(
                ".openai.azure.com"
            ):
                # Extract deployment name and convert to azure/ prefix for litellm
                try:
                    deployment = parsed_url.path.split("/")[3]
                    api_version = parse_qs(parsed_url.query).get(
                        "api-version", [""]
                    )[0]
                    model = f"azure/{deployment}"
                    # Set Azure-specific env vars for litellm
                    if api_version:
                        os.environ["AZURE_API_VERSION"] = api_version
                    azure_endpoint = (
                        f"{parsed_url.scheme}://{parsed_url.hostname}"
                    )
                    os.environ["AZURE_API_BASE"] = azure_endpoint
                    # Clear base_url since we're using env vars
                    base_url = None
                except (IndexError, KeyError):
                    # If parsing fails, let litellm try to handle it
                    pass

        super().__init__(
            model=model,
            system_message=system_message,
            api_key=api_key,
            base_url=base_url,
            stream=stream,
            provider_name="OpenAI",
            env_var_name="OPENAI_API_KEY",
            config_key="open_ai",
        )


class anthropic(_LiteLLMBase):
    """
    Anthropic ChatModel (powered by litellm)

    Args:
        model: The model to use.
            Can be found on the [Anthropic models page](https://docs.anthropic.com/en/docs/about-claude/models)
        system_message: The system message to use
        api_key: The API key to use.
            If not provided, the API key will be retrieved
            from the ANTHROPIC_API_KEY environment variable
            or the user's config.
        base_url: The base URL to use
        stream: Whether to stream responses. Defaults to True.
            If the model doesn't support streaming, it will automatically fall back to non-streaming.
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        stream: bool = True,
    ):
        # litellm expects model names without provider prefix for anthropic
        # unless using anthropic/ prefix explicitly
        if not model.startswith("anthropic/"):
            model = f"anthropic/{model}"

        super().__init__(
            model=model,
            system_message=system_message,
            api_key=api_key,
            base_url=base_url,
            stream=stream,
            provider_name="Anthropic",
            env_var_name="ANTHROPIC_API_KEY",
            config_key="anthropic",
        )


class google(_LiteLLMBase):
    """
    Google AI ChatModel (powered by litellm)

    Args:
        model: The model to use.
            Can be found on the [Gemini models page](https://ai.google.dev/gemini-api/docs/models/gemini)
        system_message: The system message to use
        api_key: The API key to use.
            If not provided, the API key will be retrieved
            from the GOOGLE_AI_API_KEY environment variable
            or the user's config.
        stream: Whether to stream responses. Defaults to True.
            If the model doesn't support streaming, it will automatically fall back to non-streaming.
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
        stream: bool = True,
    ):
        # litellm uses gemini/ prefix for Google AI
        if not model.startswith("gemini/"):
            model = f"gemini/{model}"

        super().__init__(
            model=model,
            system_message=system_message,
            api_key=api_key,
            base_url=None,
            stream=stream,
            provider_name="Google AI",
            env_var_name="GOOGLE_AI_API_KEY",
            config_key="google",
        )


class groq(_LiteLLMBase):
    """
    Groq ChatModel (powered by litellm)

    Args:
        model: The model to use.
            Can be found on the [Groq models page](https://console.groq.com/docs/models)
        system_message: The system message to use
        api_key: The API key to use.
            If not provided, the API key will be retrieved
            from the GROQ_API_KEY environment variable or the user's config.
        base_url: The base URL to use
        stream: Whether to stream responses. Defaults to True.
            If the model doesn't support streaming, it will automatically fall back to non-streaming.
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        stream: bool = True,
    ):
        # litellm expects groq/ prefix
        if not model.startswith("groq/"):
            model = f"groq/{model}"

        super().__init__(
            model=model,
            system_message=system_message,
            api_key=api_key,
            base_url=base_url,
            stream=stream,
            provider_name="Groq",
            env_var_name="GROQ_API_KEY",
            config_key=None,  # No marimo config for Groq yet
        )


class bedrock(_LiteLLMBase):
    """
    AWS Bedrock ChatModel (powered by litellm)

    Args:
        model: The model ID to use.
            Format: [<cross-region>.]<provider>.<model>
            (e.g., "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
        system_message: The system message to use
        region_name: The AWS region to use (e.g., "us-east-1")
        profile_name: The AWS profile to use for credentials (optional)
        aws_access_key_id: AWS access key ID (optional)
        aws_secret_access_key: AWS secret access key (optional)
        stream: Whether to stream responses. Defaults to True.
            If the model doesn't support streaming, it will automatically fall back to non-streaming.
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
        stream: bool = True,
    ):
        # litellm expects bedrock/ prefix
        if not model.startswith("bedrock/"):
            model = f"bedrock/{model}"

        self.region_name = region_name
        self.profile_name = profile_name
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

        super().__init__(
            model=model,
            system_message=system_message,
            api_key=None,  # Bedrock uses AWS credentials, not API key
            base_url=None,
            stream=stream,
            provider_name="AWS Bedrock",
            env_var_name="AWS_ACCESS_KEY_ID",  # Not actually used
            config_key=None,
        )

    def _setup_credentials(self) -> None:
        """Setup AWS credentials for litellm."""
        # Use profile name if provided
        if self.profile_name:
            os.environ["AWS_PROFILE"] = self.profile_name
        # Use explicit credentials if provided
        elif self.aws_access_key_id and self.aws_secret_access_key:
            os.environ["AWS_ACCESS_KEY_ID"] = self.aws_access_key_id
            os.environ["AWS_SECRET_ACCESS_KEY"] = self.aws_secret_access_key
        # Otherwise, use default credential chain

        # Set region for litellm
        os.environ["AWS_REGION_NAME"] = self.region_name

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
            # Call parent implementation
            return super().__call__(messages, config)
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

    def _get_api_key(self) -> Optional[str]:
        """Override to skip API key check for Bedrock (uses AWS credentials)."""
        # Return a dummy value to bypass the API key check in parent
        return "not-used-for-bedrock"


class litellm(_LiteLLMBase):
    """
    Generic LiteLLM ChatModel - supports any litellm provider.

    Use this to access any of the 100+ providers supported by litellm
    without needing a specific marimo wrapper. Perfect for local models,
    niche providers, or experimental setups.

    Args:
        model: The full litellm model identifier with provider prefix.
            See https://docs.litellm.ai/docs/providers for the complete list.

    Examples:
            - "ollama/llama3" - Local Ollama
            - "together_ai/meta-llama/Llama-3-70b" - Together AI
            - "openrouter/anthropic/claude-3-opus" - OpenRouter
            - "replicate/meta/llama-2-70b-chat" - Replicate
            - "huggingface/meta-llama/Llama-2-70b-chat-hf" - Hugging Face
            - "vllm/mistralai/Mistral-7B-Instruct-v0.1" - vLLM
        system_message: The system message to use
        api_key: The API key (provider-specific, may not be needed for local providers)
        base_url: Optional base URL override (useful for local deployments)
        stream: Whether to stream responses. Defaults to True.
            If the model doesn't support streaming, it will automatically fall back to non-streaming.

    Examples:
        ```python
        import marimo as mo
        import os

        # Local Ollama (no API key needed)
        mo.ui.chat(mo.ai.llm.litellm("ollama/llama3"))

        # Together AI
        mo.ui.chat(
            mo.ai.llm.litellm(
                "together_ai/meta-llama/Llama-3-70b",
                api_key=os.environ["TOGETHER_API_KEY"],
            )
        )

        # OpenRouter (access to 100+ models with one API key)
        mo.ui.chat(
            mo.ai.llm.litellm(
                "openrouter/anthropic/claude-3-opus",
                api_key=os.environ["OPENROUTER_API_KEY"],
            )
        )

        # Replicate
        mo.ui.chat(
            mo.ai.llm.litellm(
                "replicate/meta/llama-2-70b-chat",
                api_key=os.environ["REPLICATE_API_KEY"],
            )
        )

        # Local vLLM server
        mo.ui.chat(
            mo.ai.llm.litellm(
                "openai/mistral-7b",  # Use openai/ prefix for OpenAI-compatible servers
                base_url="http://localhost:8000/v1",
            )
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
        stream: bool = True,
    ):
        # Extract provider from model string (e.g., "ollama/llama3" -> "ollama")
        provider = model.split("/")[0] if "/" in model else "unknown"

        # Determine environment variable name based on provider
        # Common patterns: OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
        env_var = f"{provider.upper()}_API_KEY"

        super().__init__(
            model=model,  # Use model as-is, with provider prefix
            system_message=system_message,
            api_key=api_key,
            base_url=base_url,
            stream=stream,
            provider_name=provider.title(),
            env_var_name=env_var,
            config_key=None,  # No marimo config for generic models
        )

    def _get_api_key(self) -> Optional[str]:
        """Override to be more lenient - some providers don't need API keys.

        Local providers like Ollama, vLLM, etc. often don't require API keys.
        """
        key = super()._get_api_key()

        # For local/self-hosted providers, API key is optional
        if key is None:
            provider = self.model.split("/")[0] if "/" in self.model else ""
            local_providers = {
                "ollama",
                "vllm",
                "koboldai",
                "petals",
                "text-generation-inference",
                "tgi",
                "llamacpp",
                "openrouter",  # openrouter can work with free tier
            }
            if provider.lower() in local_providers:
                return "not-required"  # Return dummy key for local providers

        return key
