# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import json
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Final, Optional, Union, cast

from marimo import _loggers

LOGGER = _loggers.marimo_logger()

from marimo._ai._types import (
    ChatMessage,
    ChatModelConfig,
    ChatModelConfigDict,
)
from marimo._output.formatting import as_html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.chat.utils import from_chat_message_dict
from marimo._runtime.context.types import ContextNotInitializedError
from marimo._runtime.functions import EmptyArgs, Function
from marimo._runtime.requests import SetUIElementValueRequest

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

    def _is_parts_response(self, value: Any) -> bool:
        """Check if a value is a structured response with parts."""
        return isinstance(value, dict) and "parts" in value

    def _build_stream_message(
        self,
        message_id: str,
        accumulated_text: str,
        parts: Optional[list[Any]],
        is_final: bool,
    ) -> dict[str, Any]:
        """Build a stream message for the frontend."""
        msg: dict[str, Any] = {
            "type": "stream_chunk",
            "message_id": message_id,
            "content": accumulated_text,
            "is_final": is_final,
        }
        if parts is not None:
            # Ensure parts are JSON-serializable by round-tripping through JSON
            # This handles any non-serializable types and ensures consistent format
            try:
                msg["parts"] = json.loads(json.dumps(parts))
            except (TypeError, ValueError) as e:
                LOGGER.warning("Failed to serialize parts: %s", e)
                # If parts can't be serialized, convert to string representation
                msg["parts"] = [{"type": "text", "text": str(parts)}]
        return msg

    async def _handle_streaming_response(
        self, response: Any
    ) -> Union[str, dict[str, Any]]:
        """Handle streaming from both sync and async generators.

        Generators can yield:
        1. String deltas (text chunks) - accumulated and sent as text
        2. Structured dicts with "parts" key - sent as-is with parts array

        For tool calls, yield structured responses like:
        ```python
        yield {
            "parts": [
                {"type": "text", "text": "Let me help..."},
                {
                    "type": "tool-my_tool",
                    "tool_call_id": "call_123",
                    "state": "calling",
                    "input": {"arg": "value"},
                },
            ]
        }
        ```

        This follows the standard streaming pattern used by OpenAI, Anthropic,
        and other AI providers.
        """
        message_id = str(uuid.uuid4())
        accumulated_text = ""
        last_parts: Optional[list[Any]] = None

        async def process_delta(delta: Any) -> None:
            nonlocal accumulated_text, last_parts

            is_parts = self._is_parts_response(delta)

            if is_parts:
                # Structured response with parts (may include tool calls)
                last_parts = delta["parts"]
                # Extract text content for accumulated_text
                text_content = ""
                for part in last_parts:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_content += part.get("text", "")
                accumulated_text = text_content
                self._send_message(
                    self._build_stream_message(
                        message_id, accumulated_text, last_parts, False
                    ),
                    buffers=None,
                )
            else:
                # Plain text delta - accumulate
                # Only convert to string if it's actually a string-like value
                if isinstance(delta, str):
                    accumulated_text += delta
                else:
                    # Log unexpected delta type
                    LOGGER.warning(
                        "Unexpected delta type %s, converting to string: %s",
                        type(delta).__name__,
                        delta,
                    )
                    accumulated_text += str(delta)
                self._send_message(
                    self._build_stream_message(
                        message_id, accumulated_text, None, False
                    ),
                    buffers=None,
                )

        # Use async for if it's an async generator, otherwise regular for
        if inspect.isasyncgen(response):
            async for delta in response:
                await process_delta(delta)
        else:
            for delta in response:
                await process_delta(delta)

        # Send final message to indicate streaming is complete
        if accumulated_text or last_parts:
            self._send_message(
                self._build_stream_message(
                    message_id, accumulated_text, last_parts, True
                ),
                buffers=None,
            )

        # Return structured response if we had parts, otherwise just text
        if last_parts is not None:
            return {"parts": last_parts}
        return accumulated_text

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
        elif inspect.isasyncgen(response) or inspect.isgenerator(response):
            # We support functions that stream the response with generators
            # (both sync and async); each yielded value is the latest
            # representation of the response, and the last value is the full value
            response = await self._handle_streaming_response(response)

        # Build the response message, handling structured responses with parts
        if self._is_parts_response(response):
            # Structured response with parts (tool calls, etc.)
            parts = response["parts"]  # type: ignore
            # Extract text content for the content field
            text_content = ""
            for part in parts:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_content += part.get("text", "")
            response_message = ChatMessage(
                role="assistant", content=text_content, parts=parts
            )
        else:
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
            from marimo._runtime.context.kernel_context import (
                KernelRuntimeContext,
            )

            if isinstance(ctx, KernelRuntimeContext):
                ctx._kernel.enqueue_control_request(
                    SetUIElementValueRequest(
                        object_ids=[self._id],
                        values=[{"messages": self._chat_history}],
                        request=None,
                    )
                )

        # Return the response as HTML
        # If the response is a string, convert it to markdown
        if isinstance(response, str):
            return response
        if self._is_parts_response(response):
            # For parts responses, return the text content
            parts = response["parts"]  # type: ignore
            text_content = ""
            for part in parts:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_content += part.get("text", "")
            return text_content
        return as_html(response).text

    def _convert_value(self, value: dict[str, Any]) -> list[ChatMessage]:
        if not isinstance(value, dict) or "messages" not in value:
            raise ValueError("Invalid chat history format")

        messages = value["messages"]
        return [from_chat_message_dict(msg) for msg in messages]
