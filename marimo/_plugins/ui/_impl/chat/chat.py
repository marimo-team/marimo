# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Final, Optional, Union, cast

from marimo._ai._types import (
    ChatMessage,
    ChatModelConfig,
    ChatModelConfigDict,
)
from marimo._ai.llm._impl import pydantic_ai
from marimo._output.formatting import as_html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.chat.utils import from_chat_message_dict
from marimo._runtime.commands import UpdateUIElementCommand
from marimo._runtime.context import get_context
from marimo._runtime.context.types import ContextNotInitializedError
from marimo._runtime.functions import EmptyArgs, Function

DEFAULT_CONFIG = ChatModelConfigDict(
    max_tokens=4096,
    temperature=0.5,
    top_p=1,
    top_k=40,
    frequency_penalty=0,
    presence_penalty=0,
)


@dataclass
class SendMessageRequest:
    messages: list[ChatMessage]
    config: ChatModelConfig


@dataclass
class GetChatHistoryResponse:
    messages: list[ChatMessage]


@dataclass
class DeleteChatMessageRequest:
    index: int


@mddoc
class chat(UIElement[dict[str, Any], list[ChatMessage]]):
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

        Regular (sync) generators for streaming:
        ```python
        def my_streaming_model(messages, config):
            for chunk in process_stream():
                yield chunk  # Each yield updates the UI
        ```

        Async generators for streaming with async operations:
        ```python
        async def my_async_streaming_model(messages, config):
            async for chunk in async_process_stream():
                yield chunk  # Each yield updates the UI
        ```

        The last value yielded by the generator is treated as the model
        response. Streaming responses are automatically streamed to the frontend
        as they are generated.

        Using a built-in model:
        ```python
        from pydantic_ai import Agent

        chat = mo.ui.chat(
            mo.ai.llm.pydantic_ai(
                Agent(
                    "openai:gpt-5",
                    system_prompt="You are a helpful assistant.",
                )
            ),
        )
        ```

        Using attachments:
        ```python
        chat = mo.ui.chat(
            mo.ai.llm.pydantic_ai(
                Agent(
                    "openai:gpt-5",
                    system_prompt="You are a helpful assistant.",
                )
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
            - max_tokens. The maximum number of tokens to generate. Defaults to 100.
            - temperature. Defaults to 0.5.
            - top_p. Defaults to 1.
            - top_k. Defaults to 40.
            - frequency_penalty. Defaults to 0.
            - presence_penalty. Defaults to 0.
        allow_attachments (bool | List[str], optional): Allow attachments. True for any
            attachments types, or pass a list of mime types. Defaults to False.
        max_height (int, optional): Optional maximum height for the chat element.
            Defaults to None.
    """

    _name: Final[str] = "marimo-chatbot"

    def __init__(
        self,
        model: Callable[[list[ChatMessage], ChatModelConfig], object],
        *,
        prompts: Optional[list[str]] = None,
        on_message: Optional[Callable[[list[ChatMessage]], None]] = None,
        show_configuration_controls: bool = False,
        config: Optional[ChatModelConfigDict] = DEFAULT_CONFIG,
        allow_attachments: Union[bool, list[str]] = False,
        max_height: Optional[int] = None,
    ) -> None:
        self._model = model
        self._chat_history: list[ChatMessage] = []
        self._frontend_managed = False

        if isinstance(model, pydantic_ai):
            self._frontend_managed = True

        if config is None:
            config = DEFAULT_CONFIG
        else:
            # overwrite defaults with user config
            config = {**DEFAULT_CONFIG, **config}

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
                "frontend-managed": self._frontend_managed,
            },
            functions=(
                Function(
                    name="get_chat_history",
                    arg_cls=EmptyArgs,
                    function=self._get_chat_history,
                ),
                Function(
                    name="delete_chat_history",
                    arg_cls=EmptyArgs,
                    function=self._delete_chat_history,
                ),
                Function(
                    name="delete_chat_message",
                    arg_cls=DeleteChatMessageRequest,
                    function=self._delete_chat_message,
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

    def _delete_chat_history(self, _args: EmptyArgs) -> None:
        self._value = self._chat_history = []

    def _delete_chat_message(self, args: DeleteChatMessageRequest) -> None:
        index = args.index
        if index < 0 or index >= len(self._chat_history):
            raise ValueError("Invalid message index")

        del self._chat_history[index]
        self._value = self._chat_history

    def _send_chat_message(
        self,
        *,
        message_id: str,
        content: str | dict[str, Any] | None,
        is_final: bool,
    ) -> None:
        """Helper method to send a chat message to the frontend."""
        self._send_message(
            {
                "type": "stream_chunk",
                "message_id": message_id,
                "content": content,
                "is_final": is_final,
            },
            buffers=None,
        )

    async def _handle_streaming_response(self, response: Any) -> str | None:
        """Handle streaming from both sync and async generators.

        Generators should yield delta chunks (new content only), which this
        method accumulates and sends to the frontend as complete text.
        This follows the standard streaming pattern used by OpenAI, Anthropic,
        and other AI providers. For frontend-managed streaming, the response is set on the frontend,
        so we don't need to return anything.
        """
        message_id = str(uuid.uuid4())
        accumulated_text = ""

        if self._frontend_managed:
            async for delta in response:
                self._send_chat_message(
                    message_id=message_id, content=delta, is_final=False
                )
            # Send final message to indicate streaming is complete
            self._send_chat_message(
                message_id=message_id, content=None, is_final=True
            )
            return None

        # Use async for if it's an async generator, otherwise regular for
        if inspect.isasyncgen(response):
            async for delta in response:
                # Accumulate each delta chunk
                delta_str = str(delta)
                accumulated_text += delta_str
                self._send_chat_message(
                    message_id=message_id,
                    content=accumulated_text,
                    is_final=False,
                )
        else:
            for delta in response:
                # Accumulate each delta chunk
                delta_str = str(delta)
                accumulated_text += delta_str
                self._send_chat_message(
                    message_id=message_id,
                    content=accumulated_text,
                    is_final=False,
                )

        # Send final message to indicate streaming is complete
        if accumulated_text:
            self._send_chat_message(
                message_id=message_id, content=accumulated_text, is_final=True
            )
        return accumulated_text

    def _update_chat_history(self, chat_history: list[ChatMessage]) -> None:
        self._chat_history = chat_history
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
            from marimo._runtime.context.kernel_context import (
                KernelRuntimeContext,
            )

            if isinstance(ctx, KernelRuntimeContext):
                ctx._kernel.enqueue_control_request(
                    UpdateUIElementCommand(
                        object_ids=[self._id],
                        values=[{"messages": self._chat_history}],
                        request=None,
                    )
                )

    async def _send_prompt(self, args: SendMessageRequest) -> str | None:
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
        elif inspect.isasyncgen(response) or inspect.isgenerator(response):
            # We support functions that stream the response with generators
            # (both sync and async); each yielded value is the latest
            # representation of the response, and the last value is the full value
            response = await self._handle_streaming_response(response)

        if self._frontend_managed:
            # For frontend-managed streaming, the response is set on the frontend,
            # so we don't need to return anything.
            return None

        response_message = ChatMessage(role="assistant", content=response)
        chat_history = messages + [response_message]
        self._update_chat_history(chat_history)

        # Return the response as HTML
        # If the response is a string, convert it to markdown
        if isinstance(response, str):
            return response
        return as_html(response).text

    def _convert_value(self, value: dict[str, Any]) -> list[ChatMessage]:
        if not isinstance(value, dict) or "messages" not in value:
            raise ValueError("Invalid chat history format")

        messages = value["messages"]

        if self._frontend_managed:
            from pydantic_ai.ui.vercel_ai.request_types import UIMessagePart

            # The frontend sends messages as UIMessage dicts so we use pydantic-ai to cast them
            # as Vercel messages
            return [
                ChatMessage.create(
                    role=msg.get("role", "user"),
                    message_id=msg.get("id"),
                    content=None,
                    parts=msg.get("parts", []),
                    part_validator_class=UIMessagePart,
                )
                for msg in messages
            ]

        return [from_chat_message_dict(msg) for msg in messages]
