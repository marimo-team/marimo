from __future__ import annotations

import os
from typing import List, Optional, cast

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.chat.convert import convert_to_openai_messages
from marimo._plugins.ui._impl.chat.types import (
    ChatClientMessage,
    ChatModel,
    ChatModelConfig,
)


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
        if self.api_key is not None:
            return self.api_key
        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key is not None:
            return env_key
        raise ValueError(
            "openai api key not provided. Pass it as an argument or "
            "set OPENAI_API_KEY as an environment variable"
        )

    def generate_text(
        self, message: List[ChatClientMessage], config: ChatModelConfig
    ) -> str:
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
