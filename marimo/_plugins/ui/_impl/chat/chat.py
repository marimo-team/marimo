# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Final, List, Optional, cast

from marimo._output.formatting import as_html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.chat.types import (
    ChatMessage,
    ChatModelConfig,
    ChatModelConfigDict,
)
from marimo._plugins.ui._impl.chat.utils import from_chat_message_dict
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.context.types import ContextNotInitializedError
from marimo._runtime.functions import EmptyArgs, Function
from marimo._runtime.requests import SetUIElementValueRequest


@dataclass
class SendMessageRequest:
    messages: List[ChatMessage]
    config: ChatModelConfig


@dataclass
class GetChatHistoryResponse:
    messages: List[ChatMessage]


@mddoc
class chat(UIElement[Dict[str, Any], List[ChatMessage]]):
    """
    A chatbot UI element for interactive conversations.

    **Example - Using a custom model.**

    You can define a custom chat model Callable that takes in
    the history of messages and configuration.

    The response can be an object, a marimo UI element, or plain text.

    ```python
    def my_rag_model(messages, config):
        question = messages[-1].content
        docs = find_docs(question)
        prompt = template(question, docs, messages)
        response = query(prompt)
        if is_dataset(response):
            return dataset_to_chart(response)
        return response


    chat = mo.ui.chat(my_rag_model)
    ```

    **Example - Using a built-in model.**

    You can use a built-in model from the `mo.ai` module.

    ```python
    chat = mo.ui.chat(
        mo.ai.openai(
            "gpt-4o",
            system_message="You are a helpful assistant.",
        ),
    )
    ```

    **Attributes.**

    - `value`: the current chat history

    **Initialization Args.**

    - `model`: (Callable[[List[ChatMessage], ChatModelConfig], object]) a
        callable that takes in the chat history and returns a response
    - `prompts`: optional list of prompts to start the conversation
    - `on_message`: optional callback function to handle new messages
    - `show_configuration_controls`: whether to show the configuration controls
    - `config`: optional ChatModelConfigDict to override the default
        configuration keys include:
        - `max_tokens`
        - `temperature`
        - `top_p`
        - `top_k`
        - `frequency_penalty`
        - `presence_penalty`
    """

    _name: Final[str] = "marimo-chatbot"

    def __init__(
        self,
        model: Callable[[List[ChatMessage], ChatModelConfig], object],
        *,
        prompts: Optional[List[str]] = None,
        on_message: Optional[Callable[[List[ChatMessage]], None]] = None,
        show_configuration_controls: bool = False,
        config: Optional[ChatModelConfigDict] = None,
    ) -> None:
        self._model = model
        self._chat_history: List[ChatMessage] = []

        super().__init__(
            component_name=chat._name,
            initial_value={"messages": self._chat_history},
            on_change=on_message,
            label="",
            args={
                "prompts": prompts,
                "show-configuration-controls": show_configuration_controls,
                "config": cast(JSONType, config or {}),
            },
            functions=(
                Function(
                    name="get_chat_history",
                    arg_cls=EmptyArgs,
                    function=self._get_chat_history,
                ),
                Function(
                    name="send_prompt",
                    arg_cls=SendMessageRequest,
                    function=self._send_prompt,
                ),
            ),
        )

    def _get_chat_history(self, _args: EmptyArgs) -> GetChatHistoryResponse:
        return GetChatHistoryResponse(messages=self._chat_history)

    def _send_prompt(self, args: SendMessageRequest) -> str:
        messages = args.messages

        # If the model is a callable that takes a single argument,
        # call it with just the messages.
        response: object
        if (
            callable(self._model)
            and not isinstance(self._model, type)
            and len(inspect.signature(self._model).parameters) == 1
        ):
            response = self._model(messages)  # type: ignore
        else:
            response = self._model(messages, args.config)

        content = (
            as_html(response).text  # convert to html if not a string
            if not isinstance(response, str)
            else response
        )
        self._chat_history = messages + [
            ChatMessage(role="assistant", content=content)
        ]

        from marimo._runtime.context import get_context

        # The frontend doesn't manage state, so we have to manually enqueue
        # a control request.
        try:
            ctx = get_context()
        except ContextNotInitializedError:
            # For testing ... this should never happen in real usage.
            self._value = self._chat_history
            if self._on_change is not None:
                self._on_change(self._value)
        if isinstance(ctx, KernelRuntimeContext):
            ctx._kernel.enqueue_control_request(
                SetUIElementValueRequest(
                    object_ids=[self._id],
                    values=[{"messages": self._chat_history}],
                )
            )

        return content

    def _convert_value(self, value: Dict[str, Any]) -> List[ChatMessage]:
        if not isinstance(value, dict) or "messages" not in value:
            raise ValueError("Invalid chat history format")

        messages = value["messages"]
        return [from_chat_message_dict(msg) for msg in messages]
