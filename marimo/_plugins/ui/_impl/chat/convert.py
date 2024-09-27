from __future__ import annotations

from typing import Any, Callable, Dict, List

from marimo._plugins.ui._impl.chat.types import (
    ChatMessage,
    ChatModel,
    ChatModelConfig,
)


def convert_to_openai_messages(
    messages: List[ChatMessage],
) -> List[Dict[Any, Any]]:
    openai_messages: List[Dict[Any, Any]] = []

    for message in messages:
        parts: List[Dict[Any, Any]] = []

        parts.append({"type": "text", "text": message.content})

        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type.startswith("image"):
                    parts.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": attachment.url},
                        }
                    )

                elif attachment.content_type.startswith("text"):
                    parts.append({"type": "text", "text": attachment.url})

        openai_messages.append({"role": message.role, "content": parts})

    return openai_messages


def convert_to_anthropic_messages(
    messages: List[ChatMessage],
) -> List[Dict[Any, Any]]:
    anthropic_messages: List[Dict[Any, Any]] = []

    for message in messages:
        parts: List[Dict[Any, Any]] = []

        parts.append({"type": "text", "text": message.content})

        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type.startswith("image"):
                    parts.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": attachment.url},
                        }
                    )

                elif attachment.content_type.startswith("text"):
                    parts.append({"type": "text", "text": attachment.url})

        anthropic_messages.append({"role": message.role, "content": parts})

    return anthropic_messages


def model_from_callable(
    model: Callable[[List[ChatMessage], ChatModelConfig], str]
    | Callable[[List[ChatMessage]], str],
) -> ChatModel:
    class Model(ChatModel):
        def generate_text(
            self, message: List[ChatMessage], config: ChatModelConfig
        ) -> object:
            # If the model is a callable that takes a single argument,
            # call it with the message and config.
            if callable(model) and len(model.__code__.co_varnames) == 1:
                return model(message)  # type: ignore
            return model(message, config)  # type: ignore

    return Model()
