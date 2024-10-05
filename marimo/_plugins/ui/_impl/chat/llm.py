# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Callable, List, Optional, cast

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.chat.convert import (
    convert_to_anthropic_messages,
    convert_to_google_messages,
    convert_to_openai_messages,
)
from marimo._plugins.ui._impl.chat.types import (
    ChatMessage,
    ChatModel,
    ChatModelConfig,
)

DEFAULT_SYSTEM_MESSAGE = (
    "You are a helpful assistant specializing in data science."
)


class simple(ChatModel):
    """
    Convenience class for wrapping a ChatModel or callable to
    take a single prompt

    **Args:**

    - delegate: A callable that takes a
        single prompt and returns a response
    """

    def __init__(self, delegate: Callable[[str], object]):
        self.delegate = delegate

    def __call__(
        self, messages: List[ChatMessage], config: ChatModelConfig
    ) -> object:
        del config
        prompt = messages[-1].content
        return self.delegate(prompt)


class openai(ChatModel):
    """
    OpenAI ChatModel

    **Args:**

    - model: The model to use.
        Can be found on the [OpenAI models page](https://platform.openai.com/docs/models)
    - system_message: The system message to use
    - api_key: The API key to use.
        If not provided, the API key will be retrieved
        from the OPENAI_API_KEY environment variable or the user's config.
    - base_url: The base URL to use
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

            api_key = get_context().user_config["ai"]["open_ai"]["api_key"]
            if api_key:
                return api_key
        except Exception:
            pass

        raise ValueError(
            "openai api key not provided. Pass it as an argument or "
            "set OPENAI_API_KEY as an environment variable"
        )

    def __call__(
        self, messages: List[ChatMessage], config: ChatModelConfig
    ) -> object:
        DependencyManager.openai.require(
            "chat model requires openai. `pip install openai`"
        )
        from openai import OpenAI  # type: ignore[import-not-found]
        from openai.types.chat import (  # type: ignore[import-not-found]
            ChatCompletionMessageParam,
        )

        client = OpenAI(
            api_key=self._require_api_key,
            base_url=self.base_url,
        )

        openai_messages = convert_to_openai_messages(
            [ChatMessage(role="system", content=self.system_message)]
            + messages
        )
        response = client.chat.completions.create(
            model=self.model,
            messages=cast(List[ChatCompletionMessageParam], openai_messages),
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            top_p=config.top_p,
            frequency_penalty=config.frequency_penalty,
            presence_penalty=config.presence_penalty,
            stream=False,
        )

        choice = response.choices[0]
        content = choice.message.content
        return content or ""


class anthropic(ChatModel):
    """
    Anthropic ChatModel

    **Args:**

    - model: The model to use.
    - system_message: The system message to use
    - api_key: The API key to use.
        If not provided, the API key will be retrieved
        from the ANTHROPIC_API_KEY environment variable
        or the user's config.
    - base_url: The base URL to use
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
        self.system_message = system_message

    @property
    def _require_api_key(self) -> str:
        # If the api key is provided, use it
        if self.api_key is not None:
            return self.api_key

        # Then check the user's config
        try:
            from marimo._runtime.context.types import get_context

            api_key = get_context().user_config["ai"]["anthropic"]["api_key"]
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

    def __call__(
        self, messages: List[ChatMessage], config: ChatModelConfig
    ) -> object:
        DependencyManager.anthropic.require(
            "chat model requires anthropic. `pip install anthropic`"
        )
        from anthropic import (  # type: ignore[import-not-found]
            NOT_GIVEN,
            Anthropic,
        )
        from anthropic.types.message_param import (  # type: ignore[import-not-found]
            MessageParam,
        )

        client = Anthropic(
            api_key=self._require_api_key,
            base_url=self.base_url,
        )

        anthropic_messages = convert_to_anthropic_messages(messages)
        response = client.messages.create(
            model=self.model,
            system=self.system_message,
            max_tokens=config.max_tokens or 1000,
            messages=cast(List[MessageParam], anthropic_messages),
            top_p=config.top_p if config.top_p is not None else NOT_GIVEN,
            top_k=config.top_k if config.top_k is not None else NOT_GIVEN,
            stream=False,
            temperature=config.temperature
            if config.temperature is not None
            else NOT_GIVEN,
        )

        content = response.content
        if len(content) > 0:
            if content[0].type == "text":
                return content[0].text
            elif content[0].type == "tool_use":
                return content
        return ""


class google(ChatModel):
    """
    Google AI ChatModel

    **Args:**

    - model: The model to use.
    - system_message: The system message to use
    - api_key: The API key to use.
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

            api_key = get_context().user_config["ai"]["google"]["api_key"]
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

    def __call__(
        self, messages: List[ChatMessage], config: ChatModelConfig
    ) -> object:
        DependencyManager.google_ai.require(
            "chat model requires google. `pip install google-generativeai`"
        )
        import google.generativeai as genai  # type: ignore[import-not-found]

        genai.configure(api_key=self._require_api_key)
        client = genai.GenerativeModel(
            model_name=self.model,
            generation_config=genai.GenerationConfig(
                max_output_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                top_k=config.top_k,
                frequency_penalty=config.frequency_penalty,
                presence_penalty=config.presence_penalty,
            ),
        )

        google_messages = convert_to_google_messages(messages)
        response = client.generate_content(google_messages)

        content = response.text
        return content or ""
