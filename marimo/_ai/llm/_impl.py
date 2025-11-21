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
        provider_name: str = "provider",
        env_var_name: str = "API_KEY",
        config_key: Optional[str] = None,
    ):
        self.model = model
        self.system_message = system_message
        self.api_key = api_key
        self.base_url = base_url
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
            f"chat model requires litellm. `pip install litellm`"
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
            "stream": True,
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
            # litellm passes this through to providers that support it
            params["top_k"] = config.top_k

        response = completion(**params)
        return self._stream_response(response)


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
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
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
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
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
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
    ):
        # litellm uses gemini/ prefix for Google AI
        if not model.startswith("gemini/"):
            model = f"gemini/{model}"

        super().__init__(
            model=model,
            system_message=system_message,
            api_key=api_key,
            base_url=None,
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
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        # litellm expects groq/ prefix
        if not model.startswith("groq/"):
            model = f"groq/{model}"

        super().__init__(
            model=model,
            system_message=system_message,
            api_key=api_key,
            base_url=base_url,
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
