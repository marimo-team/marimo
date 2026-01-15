# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Final, Optional, Union, cast

from marimo import _loggers
from marimo._ai._types import (
    ChatMessage,
    ChatModelConfig,
    ChatModelConfigDict,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatting import as_html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.commands import UpdateUIElementCommand
from marimo._runtime.context import get_context
from marimo._runtime.context.types import ContextNotInitializedError
from marimo._runtime.functions import EmptyArgs, Function

LOGGER = _loggers.marimo_logger()

DEFAULT_CONFIG = ChatModelConfigDict(
    max_tokens=4096,
    temperature=0.5,
    top_p=1,
    top_k=40,
    frequency_penalty=0,
    presence_penalty=0,
)

DONE_CHUNK: Final[str] = "[DONE]"


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

        Custom model with Vercel AI SDK streaming (reasoning, tool calls):
        ```python
        import pydantic_ai.ui.vercel_ai.response_types as vercel


        async def custom_model(messages, config):
            # Stream reasoning/thinking
            yield vercel.ReasoningStartChunk(id="reasoning-1")
            yield vercel.ReasoningDeltaChunk(
                id="reasoning-1", delta="Let me think..."
            )
            yield vercel.ReasoningEndChunk(id="reasoning-1")

            # Stream text response (can also use plain dicts)
            yield {"type": "text-start", "id": "text-1"}
            yield vercel.TextDeltaChunk(
                id="text-1", delta="Here is my answer."
            )
            yield vercel.TextEndChunk(id="text-1")

            yield vercel.FinishChunk(finish_reason="stop")


        chat = mo.ui.chat(custom_model)
        ```
        Refer to examples/ai/chat/pydantic-ai-chat.py for a complete example.

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

    async def _handle_streaming_response(self, response: Any) -> None:
        """Handle streaming from both sync and async generators.

        Generators should yield delta chunks (new content only), which this
        method accumulates and sends to the frontend as complete text.
        This follows the standard streaming pattern used by OpenAI, Anthropic,
        and other AI providers. For frontend-managed streaming, the response is set on the frontend,
        so we don't need to return anything.
        """
        message_id = str(uuid.uuid4())

        def send_chunk(chunk: dict[str, Any]) -> None:
            self._send_chat_message(
                message_id=message_id,
                content=chunk,
                is_final=False,
            )

        serializer = ChunkSerializer(on_send_chunk=send_chunk)

        if inspect.isasyncgen(response):
            async for delta in response:
                serializer.handle_chunk(delta)
        else:
            for delta in response:
                serializer.handle_chunk(delta)

        serializer.on_end()

        # Send final message to indicate streaming is complete
        self._send_chat_message(
            message_id=message_id,
            content=None,
            is_final=True,
        )

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

        self._chat_history = messages

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

        if inspect.isasyncgen(response) or inspect.isgenerator(response):
            # We support functions that stream the response with generators
            # (both sync and async)
            await self._handle_streaming_response(response)
            # For streaming, we don't have a final response string to add to history
            # The frontend will add the accumulated message
            return None

        if inspect.isawaitable(response):
            response = await response

        # Return the response as a string
        # If the response is a rich object, convert it to markdown
        response_str = (
            response if isinstance(response, str) else as_html(response).text
        )

        # Add assistant response to chat history
        assistant_message = ChatMessage(
            role="assistant", content=response, id=str(uuid.uuid4())
        )
        self._chat_history.append(assistant_message)

        # Update the chat history to trigger UI updates and on_message callback
        self._update_chat_history(self._chat_history)

        return response_str

    def _convert_value(self, value: dict[str, Any]) -> list[ChatMessage]:
        """Convert the frontend's chat history format to a list of ChatMessage objects."""
        if not isinstance(value, dict) or "messages" not in value:
            raise ValueError("Invalid chat history format")

        messages = value["messages"]

        part_validator_class = None
        if DependencyManager.pydantic_ai.imported():
            from pydantic_ai.ui.vercel_ai.request_types import (
                UIMessagePart,
            )

            # The frontend sends messages as ChatMessage parts so we use pydantic-ai to cast them
            # as Vercel UIMessagePart
            part_validator_class = UIMessagePart

        prev_msg_to_content: dict[str, Any] = {}
        for msg in self._chat_history:
            msg_id = msg.id
            content = msg.content
            if content is not None and msg_id:
                prev_msg_to_content[msg_id] = content

        result: list[ChatMessage] = []
        for msg in messages:
            msg_id = msg.get("id")
            role = msg.get("role", "user")
            # Prefer the content in Python object format over the serialized content from the frontend,
            # since this is the most accurate representation of the message and more valuable to the user in Python-land.
            content = prev_msg_to_content.get(msg_id, msg.get("content"))
            result.append(
                ChatMessage.create(
                    role=role,
                    message_id=msg_id,
                    content=content,
                    parts=msg.get("parts", []),
                    part_validator_class=part_validator_class,
                )
            )
        return result


@dataclass
class ChunkSerializer:
    on_send_chunk: Callable[[dict[str, Any]], None]
    _text_id: str | None = None

    def handle_chunk(self, chunk: Any) -> None:
        """Handle a Vercel AI SDK chunk"""

        # Handle Pydantic AI's Vercel AI SDK chunks
        if DependencyManager.pydantic_ai.imported():
            from pydantic_ai.ui.vercel_ai.response_types import (
                BaseChunk,
            )

            if isinstance(chunk, BaseChunk):
                # by_alias=True: Use camelCase keys expected by Vercel AI SDK.
                # exclude_none=True: Remove null values which cause validation errors.
                self.on_send_chunk(
                    chunk.model_dump(
                        mode="json", by_alias=True, exclude_none=True
                    )
                )
                return

        # Handle plain text chunks
        if isinstance(chunk, str):
            if self._text_id is None:
                self._text_id = f"text_{uuid.uuid4().hex}"
                self.on_send_chunk({"type": "text-start", "id": self._text_id})
            self.on_send_chunk(
                {"type": "text-delta", "id": self._text_id, "delta": chunk}
            )
            return

        # Otherwise, we return the chunk as is
        self.on_send_chunk(chunk)

    def on_end(self) -> None:
        if self._text_id is not None:
            self.on_send_chunk({"type": "text-end", "id": self._text_id})
