from __future__ import annotations

import os
from typing import Callable, List, Optional, cast

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.chat.convert import (
    convert_to_anthropic_messages,
    convert_to_openai_messages,
)
from marimo._plugins.ui._impl.chat.types import (
    ChatMessage,
    ChatModel,
    ChatModelConfig,
)


class simple(ChatModel):
    """
    Convenience class for wrapping a ChatModel or callable to
    take a single prompt
    """

    def __init__(self, delegate: Callable[[str], str]):
        self.delegate = delegate

    def generate_text(
        self, message: List[ChatMessage], config: ChatModelConfig
    ) -> object:
        del config
        prompt = message[-1].content
        return self.delegate(prompt)


class openai(ChatModel):
    def __init__(
        self,
        model: str,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @property
    def require_api_key(self) -> str:
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

    def generate_text(
        self, message: List[ChatMessage], config: ChatModelConfig
    ) -> object:
        DependencyManager.openai.require(
            "chat model requires openai. `pip install openai`"
        )
        from openai import OpenAI
        from openai.types.chat import ChatCompletionMessageParam

        client = OpenAI(
            api_key=self.require_api_key,
            base_url=self.base_url,
        )

        messages = convert_to_openai_messages(message)
        response = client.chat.completions.create(
            model=self.model,
            messages=cast(List[ChatCompletionMessageParam], messages),
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
    def __init__(
        self,
        model: str,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    def require_api_key(self) -> str:
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

    def generate_text(
        self, message: List[ChatMessage], config: ChatModelConfig
    ) -> object:
        DependencyManager.anthropic.require(
            "chat model requires anthropic. `pip install anthropic`"
        )
        from anthropic import NOT_GIVEN, Anthropic
        from anthropic.types.message_param import MessageParam

        client = Anthropic(
            api_key=self.require_api_key(),
            base_url=self.base_url,
        )

        messages = convert_to_anthropic_messages(message)
        response = client.messages.create(
            model=self.model,
            max_tokens=config.max_tokens or 1000,
            messages=cast(List[MessageParam], messages),
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
