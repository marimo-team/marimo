# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

if TYPE_CHECKING:
    from collections.abc import Generator

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
        stream: Whether to stream responses. Defaults to True.
            If the model doesn't support streaming, will automatically fall back to non-streaming.
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
        self.model = model
        self.system_message = system_message
        self.api_key = api_key
        self.base_url = base_url
        self.stream = stream

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

        # Try streaming first if enabled, fall back to non-streaming on error
        if self.stream:
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
                if "streaming" in str(e).lower() or "stream" in str(e).lower():
                    response = client.chat.completions.create(
                        model=self.model,
                        messages=openai_messages,
                        max_completion_tokens=config.max_tokens,
                        temperature=config.temperature,
                        top_p=config.top_p,
                        frequency_penalty=config.frequency_penalty,
                        presence_penalty=config.presence_penalty,
                        stream=False,
                    )
                    return response.choices[0].message.content or ""
                raise
        else:
            response = client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                max_completion_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                frequency_penalty=config.frequency_penalty,
                presence_penalty=config.presence_penalty,
                stream=False,
            )
            return response.choices[0].message.content or ""


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
        stream: Whether to stream responses. Defaults to True.
            If the model doesn't support streaming, will automatically fall back to non-streaming.
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
        self.model = model
        self.system_message = system_message
        self.api_key = api_key
        self.base_url = base_url
        self.stream = stream

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
        if config.temperature is not None:
            params["temperature"] = config.temperature

        # Try streaming first if enabled, fall back to non-streaming on error
        if self.stream:
            try:
                # Note: client.messages.stream() doesn't take a 'stream' parameter
                # It's already a streaming method
                return self._stream_response(client, params)
            except Exception as e:
                # Fall back to non-streaming mode if streaming fails
                if "streaming" in str(e).lower() or "stream" in str(e).lower():
                    response = client.messages.create(**params)
                    return response.content[0].text
                raise
        else:
            response = client.messages.create(**params)
            return response.content[0].text


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
        stream: Whether to stream responses. Defaults to True.
            If the model doesn't support streaming, will automatically fall back to non-streaming.
    """

    def __init__(
        self,
        model: str,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        api_key: Optional[str] = None,
        stream: bool = True,
    ):
        self.model = model
        self.system_message = system_message
        self.api_key = api_key
        self.stream = stream

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

        # Try streaming first if enabled, fall back to non-streaming on error
        if self.stream:
            try:
                return self._stream_response(
                    client, google_messages, generation_config
                )
            except Exception as e:
                # Fall back to non-streaming mode if streaming fails
                if "streaming" in str(e).lower() or "stream" in str(e).lower():
                    response = client.models.generate_content(
                        model=self.model,
                        contents=google_messages,
                        config=generation_config,
                    )
                    return response.text
                raise
        else:
            response = client.models.generate_content(
                model=self.model,
                contents=google_messages,
                config=generation_config,
            )
            return response.text


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
        stream: Whether to stream responses. Defaults to True.
            If the model doesn't support streaming, will automatically fall back to non-streaming.
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
        self.model = model
        self.system_message = system_message
        self.api_key = api_key
        self.base_url = base_url
        self.stream = stream

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

        # Try streaming first if enabled, fall back to non-streaming on error
        if self.stream:
            try:
                return self._stream_response(client, groq_messages, config)
            except Exception as e:
                # Fall back to non-streaming mode if streaming fails
                if "streaming" in str(e).lower() or "stream" in str(e).lower():
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
        else:
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
        stream: Whether to stream responses. Defaults to True.
            If the model doesn't support streaming, will automatically fall back to non-streaming.
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
        if not model.startswith("bedrock/"):
            model = f"bedrock/{model}"
        self.model = model
        self.system_message = system_message
        self.region_name = region_name
        self.profile_name = profile_name
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.stream = stream

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
            # Try streaming first if enabled, fall back to non-streaming on error
            if self.stream:
                try:
                    return self._stream_response(messages, config)
                except Exception as stream_error:
                    # Fall back to non-streaming if streaming fails
                    if (
                        "streaming" in str(stream_error).lower()
                        or "stream" in str(stream_error).lower()
                    ):
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
            else:
                from litellm import completion as litellm_completion

                response = litellm_completion(
                    model=self.model,
                    messages=convert_to_openai_messages(
                        [
                            ChatMessage(
                                role="system", content=self.system_message
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
