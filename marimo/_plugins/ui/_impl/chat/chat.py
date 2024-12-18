# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Final, List, Optional, Union, cast

from marimo._ai.types import (
    ChatMessage,
    ChatModelConfig,
    ChatModelConfigDict,
)
from marimo._output.formatting import as_html
from marimo._output.md import md
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement
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
    """A chatbot UI element for interactive conversations.

    Define a chatbot by implementing a function that takes a list of ChatMessages and
    optionally a config object as input, and returns the chat response. The response
    can be any object, including text, plots, or marimo UI elements.

    Examples:
        Using a custom model:
        ```python
        def my_rag_model(messages, config):
            # Each message has a `content` attribute, as well as a `role`
            # attribute ("user", "system", "assistant");
            question = messages[-1].content
            docs = find_docs(question)
            prompt = template(question, docs, messages)
            response = query(prompt)
            if is_dataset(response):
                return dataset_to_chart(response)
            return response


        chat = mo.ui.chat(my_rag_model)
        ```

        Async functions and async generators are also supported:
        ```python
        async def my_rag_model(messages):
            return await my_async_function(messages)
        ```

        ```python
        async def my_rag_model(messages):
            for response in my_async_iterator(messages):
                yield response
        ```

        The last value yielded by the async generator is treated as the model
        response. ui.chat does not yet support streaming responses to the frontend.
        Please file a GitHub issue if this is important to you:
        https://github.com/marimo-team/marimo/issues

        Using a built-in model:
        ```python
        chat = mo.ui.chat(
            mo.ai.llm.openai(
                "gpt-4o",
                system_message="You are a helpful assistant.",
            ),
        )
        ```

        Using attachments:
        ```python
        chat = mo.ui.chat(
            mo.ai.llm.openai(
                "gpt-4o",
            ),
            allow_attachments=["image/png", "image/jpeg"],
        )
        ```

    Attributes:
        value (List[ChatMessage]): The current chat history, a list of ChatMessage objects.

    Args:
        model (Callable[[List[ChatMessage], ChatModelConfig], object]): A callable that
            takes in the chat history and returns a response.
        prompts (List[str], optional): Optional list of initial prompts to present to
            the user. Defaults to None.
        on_message (Callable[[List[ChatMessage]], None], optional): Optional callback
            function to handle new messages. Defaults to None.
        show_configuration_controls (bool, optional): Whether to show the configuration
            controls. Defaults to False.
        config (ChatModelConfigDict, optional): Optional configuration to override the
            default configuration. Keys include:
            - max_tokens
            - temperature
            - top_p
            - top_k
            - frequency_penalty
            - presence_penalty
            Defaults to None.
        allow_attachments (bool | List[str], optional): Allow attachments. True for any
            attachments types, or pass a list of mime types. Defaults to False.
        max_height (int, optional): Optional maximum height for the chat element.
            Defaults to None.
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
        allow_attachments: Union[bool, List[str]] = False,
        max_height: Optional[int] = None,
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
                "allow-attachments": allow_attachments,
                "max-height": max_height,
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

    async def _send_prompt(self, args: SendMessageRequest) -> str:
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

        if inspect.isawaitable(response):
            response = await response
        elif inspect.isasyncgen(response):
            # We support functions that stream the response with an async
            # generator; each yielded value is the latest representation of the
            # response, and the last value is the full value
            latest_response = None
            async for latest_response in response:  # noqa: B007
                # TODO(akshayka, mscolnick): Stream response to frontend
                # once bidirectional communication is implemented.
                #
                # RPCs don't yet support bidirectional communication, so we
                # just ignore all the initial responses; ideally we'd stream
                # the response back to the frontend.
                pass
            response = latest_response

        response_message = ChatMessage(role="assistant", content=response)
        self._chat_history = messages + [response_message]

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
        else:
            if isinstance(ctx, KernelRuntimeContext):
                ctx._kernel.enqueue_control_request(
                    SetUIElementValueRequest(
                        object_ids=[self._id],
                        values=[{"messages": self._chat_history}],
                    )
                )

        # Return the response as HTML
        # If the response is a string, convert it to markdown
        if isinstance(response, str):
            return md(response).text
        return as_html(response).text

    def _convert_value(self, value: Dict[str, Any]) -> List[ChatMessage]:
        if not isinstance(value, dict) or "messages" not in value:
            raise ValueError("Invalid chat history format")

        messages = value["messages"]
        return [from_chat_message_dict(msg) for msg in messages]
