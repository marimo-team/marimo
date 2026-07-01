# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal, cast

from marimo import _loggers
from marimo._ai._types import (
    ChatMessage,
    ChatModelConfig,
    ChatModelConfigDict,
    TextPart,
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

if TYPE_CHECKING:
    from collections.abc import Callable

LOGGER = _loggers.marimo_logger()

DEFAULT_CONFIG = ChatModelConfigDict(
    max_tokens=4096,
    temperature=0.5,
    top_p=1,
    top_k=40,
    frequency_penalty=0,
    presence_penalty=0,
)

# The version of the Vercel AI SDK we use
AI_SDK_VERSION: Final[Literal[5, 6]] = 6
DONE_CHUNK: Final[str] = "[DONE]"


@dataclass
class SendMessageRequest:
    messages: list[ChatMessage]
    config: ChatModelConfig
    request_id: str | None = None


@dataclass
class GetChatHistoryResponse:
    messages: list[ChatMessage]


@dataclass
class DeleteChatMessageRequest:
    index: int


@dataclass
class CancelPromptRequest:
    request_id: str


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

    Cancellation:
        When the user clicks Stop in the UI, marimo cancels the in-flight
        model invocation. Async model code receives
        `asyncio.CancelledError` at the next `await`. Sync generators are
        closed instead, which raises `GeneratorExit` inside the generator
        rather than `CancelledError`. If your model holds resources such as
        HTTP clients, file handles, or database cursors, release them in a
        `try/finally` block so they are cleaned up promptly on cancellation;
        do not rely on catching `CancelledError` in sync generators.
        Async generators that catch and swallow `CancelledError` will not
        actually stop and may continue to consume tokens from upstream
        providers.

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
        disabled (bool, optional): Whether the chat input is disabled. When True,
            the user cannot type or send messages. Defaults to False.
    """

    _name: Final[str] = "marimo-chatbot"

    def __init__(
        self,
        model: Callable[[list[ChatMessage], ChatModelConfig], object],
        *,
        prompts: list[str] | None = None,
        on_message: Callable[[list[ChatMessage]], None] | None = None,
        show_configuration_controls: bool = False,
        config: ChatModelConfigDict | None = DEFAULT_CONFIG,
        allow_attachments: bool | list[str] = False,
        max_height: int | None = None,
        disabled: bool = False,
    ) -> None:
        self._model = model
        self._chat_history: list[ChatMessage] = []
        # Tracks in-flight _send_prompt tasks keyed by request_id, so that
        # _cancel_prompt can interrupt the model generation cleanly.
        self._in_flight: dict[str, asyncio.Task[None]] = {}

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
                "disabled": disabled,
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
                Function(
                    name="cancel_prompt",
                    arg_cls=CancelPromptRequest,
                    function=self._cancel_prompt,
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

    async def _handle_streaming_response(
        self,
        response: Any,
        *,
        message_id: str | None = None,
    ) -> None:
        """Handle streaming from both sync and async generators, and lists.

        Generators should yield delta chunks (new content only), which this
        method accumulates and sends to the frontend as complete text.
        This follows the standard streaming pattern used by OpenAI, Anthropic,
        and other AI providers. For frontend-managed streaming, the response is set on the frontend,
        so we don't need to return anything. If generators just yield strings, we update the chat history with the accumulated text.

        On cancellation, any open text/reasoning blocks are closed and a final
        chunk is emitted so the frontend stream tears down cleanly, then the
        CancelledError propagates.
        """
        if message_id is None:
            message_id = str(uuid.uuid4())

        def send_chunk(chunk: dict[str, Any]) -> None:
            self._send_chat_message(
                message_id=message_id, content=chunk, is_final=False
            )

        serializer = ChunkSerializer(on_send_chunk=send_chunk)
        accumulated_text = ""

        is_generator = inspect.isasyncgen(response) or inspect.isgenerator(
            response
        )

        try:
            if inspect.isasyncgen(response):
                async for delta in response:
                    if isinstance(delta, str):
                        accumulated_text += delta
                    serializer.handle_chunk(delta)
            else:
                for delta in response:
                    if isinstance(delta, str):
                        accumulated_text += delta
                    serializer.handle_chunk(delta)
                    # Yield to the event loop so cancellation can propagate
                    # promptly into sync generators that don't await.
                    await asyncio.sleep(0)
        except asyncio.CancelledError:
            # Close any open blocks on the wire so the frontend parser doesn't
            # see dangling text-delta / reasoning-delta chunks. Best-effort;
            # the frontend may have already torn down its controller.
            try:
                self._emit_cancellation_chunks(
                    serializer=serializer, message_id=message_id
                )
            except Exception:
                LOGGER.debug(
                    "Failed to emit cancellation chunks", exc_info=True
                )
            # Explicitly close the user-supplied generator so cleanup blocks
            # (HTTP sockets, file handles, try/finally in user code) run
            # promptly rather than waiting on GC finalizers.
            if inspect.isasyncgen(response):
                with contextlib.suppress(Exception):
                    await response.aclose()
            elif inspect.isgenerator(response):
                with contextlib.suppress(Exception):
                    response.close()
            raise

        # Generators that yield strings should update the 'content' field of the assistant message
        if accumulated_text and is_generator:
            self._add_assistant_message_to_chat_history(
                accumulated_text, accumulated_text
            )

        serializer.on_end()

        # Send final message to indicate streaming is complete
        self._send_chat_message(
            message_id=message_id,
            content=None,
            is_final=True,
        )

    def _emit_cancellation_chunks(
        self,
        *,
        serializer: ChunkSerializer,
        message_id: str,
    ) -> None:
        """Close open serializer blocks and emit a final chunk on cancellation."""
        # If pydantic-ai is available, prefer the protocol's AbortChunk to
        # signal "stream cut off, anything open is incomplete".
        abort_payload: dict[str, Any] | None = None
        if DependencyManager.pydantic_ai.imported():
            try:
                from pydantic_ai.ui.vercel_ai.response_types import (
                    AbortChunk,
                )

                abort_payload = json.loads(  # pyright: ignore[reportAny]
                    AbortChunk(reason="user_cancelled").encode(
                        sdk_version=AI_SDK_VERSION
                    )
                )
            except Exception:
                LOGGER.debug(
                    (
                        "Could not build AbortChunk; will fall back to explicit "
                        "end chunks for open blocks."
                    ),
                    exc_info=True,
                )

        if abort_payload is not None:
            serializer.close_open_blocks_when_cancelled()
            self._send_chat_message(
                message_id=message_id,
                content=abort_payload,
                is_final=False,
            )
        else:
            serializer.close_open_blocks_when_cancelled()

        self._send_chat_message(
            message_id=message_id, content=None, is_final=True
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

    async def _send_prompt(self, args: SendMessageRequest) -> None:
        request_id = args.request_id or str(uuid.uuid4())
        if args.request_id is None:
            LOGGER.debug(
                (
                    "send_prompt received without a request_id; "
                    "generated %s server-side."
                ),
                request_id,
            )

        task = asyncio.create_task(self._run_prompt(request_id, args))
        self._in_flight[request_id] = task
        try:
            await task
        except asyncio.CancelledError:
            # Note: if both `_cancel_prompt` and an outer kernel cancellation
            # fire near-simultaneously, we'll take the `pass` branch and the
            # outer cancel is effectively lost. That's acceptable in practice
            # because kernel shutdown tears the whole event loop down anyway.
            if task.done() and task.cancelled():
                # Inner task was cancelled (typically via _cancel_prompt).
                # The user-visible Stop happened; complete the RPC normally.
                pass
            else:
                # Outer task was cancelled (e.g., kernel shutdown). Make sure
                # the inner task is cleaned up, then propagate the cancel.
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(BaseException):
                        await task
                raise
        finally:
            self._in_flight.pop(request_id, None)

    async def _cancel_prompt(self, args: CancelPromptRequest) -> None:
        """Cancel an in-flight prompt by request_id. No-op if already done."""
        task = self._in_flight.get(args.request_id)
        if task is not None and not task.done():
            task.cancel()

    async def _run_prompt(
        self, request_id: str, args: SendMessageRequest
    ) -> None:
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
            await self._handle_streaming_response(
                response, message_id=request_id
            )
            # For streaming, we don't have a final response string to add to history
            # The frontend will add the accumulated message
            return

        if inspect.isawaitable(response):
            response = await response

        # Return the response as a string
        # If the response is a rich object, convert it to markdown
        response_str = (
            response if isinstance(response, str) else as_html(response).text
        )

        await self._handle_streaming_response(
            [response_str], message_id=request_id
        )
        # Update the chat history to trigger UI updates and on_message callback
        self._add_assistant_message_to_chat_history(response, response_str)

    def _add_assistant_message_to_chat_history(
        self, content: str | object, text: str
    ) -> None:
        assistant_message = ChatMessage(
            role="assistant",
            content=content,
            id=f"message_{uuid.uuid4().hex}",
            parts=[TextPart(type="text", text=text)],
        )
        self._chat_history.append(assistant_message)
        self._update_chat_history(self._chat_history)

    def _convert_value(self, value: dict[str, Any]) -> list[ChatMessage]:
        """Convert the frontend's chat history format to a list of ChatMessage objects."""
        if not isinstance(value, dict) or "messages" not in value:
            raise ValueError("Invalid chat history format")

        messages = value["messages"]

        part_validator_class = None
        if DependencyManager.pydantic_ai.imported():
            from pydantic_ai.ui.vercel_ai.request_types import UIMessagePart

            # The frontend sends messages as ChatMessage parts so we use pydantic-ai to cast them
            # as Vercel UIMessagePart
            part_validator_class = UIMessagePart

        def get_prev_content(idx: int) -> Any:
            # Only get the prev content if messages are the same size
            if len(messages) == len(self._chat_history):
                return self._chat_history[idx].content
            return None

        result: list[ChatMessage] = []
        for i, msg in enumerate(messages):
            prev_content = get_prev_content(i)
            if isinstance(msg, ChatMessage):
                if prev_content is not None:
                    msg.content = prev_content
                continue

            msg_id = msg.get("id")
            role = msg.get("role", "user")
            # Prefer the content in Python object format over the serialized content from the frontend,
            # since this is the most accurate representation of the message and more valuable to the user in Python-land.
            content = (
                prev_content
                if prev_content is not None
                else msg.get("content")
            )
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
    # Id of the implicit text block synthesized for plain-string yields.
    _text_id: str | None = None
    # Open block id -> kind, for blocks we've seen a `*-start` for but not
    # yet a `*-end`. Drained on end-of-stream and on cancellation.
    _open_blocks: dict[str, str] = field(default_factory=dict)

    # The AI SDK UI parser holds parts in `state: "streaming"` until a
    # matching `*-end` arrives — without one the part renders as still
    # in-progress. These are the only block kinds with that property in
    # ai@6.x; others either use a different lifecycle (e.g. tool-input
    # pairs with tool-output-available/-error and keys on `toolCallId`)
    # or are single-chunk events (file, source-url, data-*). Don't extend
    # without checking the SDK parser.
    _BLOCK_KINDS: ClassVar[tuple[str, ...]] = ("text", "reasoning")

    def handle_chunk(self, chunk: Any) -> None:
        """Handle a Vercel AI SDK chunk"""

        # Handle Pydantic AI's Vercel AI SDK chunks
        if DependencyManager.pydantic_ai.imported():
            from pydantic_ai.ui.vercel_ai.response_types import (
                BaseChunk,
            )

            if isinstance(chunk, BaseChunk):
                serialized = json.loads(
                    chunk.encode(sdk_version=AI_SDK_VERSION)
                )
                self._track_block_state(serialized)
                self.on_send_chunk(serialized)
                return

        # Handle plain text chunks
        if isinstance(chunk, str):
            # Coerce str subclasses (like weave's BoxedStr) to plain str
            chunk = str(chunk)
            if self._text_id is None:
                self._text_id = f"text_{uuid.uuid4().hex}"
                self._open_blocks[self._text_id] = "text"
                self.on_send_chunk({"type": "text-start", "id": self._text_id})
            self.on_send_chunk(
                {"type": "text-delta", "id": self._text_id, "delta": chunk}
            )
            return

        # Track block lifecycle for plain dict chunks before forwarding.
        if isinstance(chunk, dict):
            self._track_block_state(chunk)

        # Otherwise, we return the chunk as is
        self.on_send_chunk(chunk)

    def on_end(self) -> None:
        """Drain blocks still open at successful end-of-stream. Propagate exceptions."""
        self._drain_open_blocks(suppress_errors=False)

    def close_open_blocks_when_cancelled(self) -> None:
        self._drain_open_blocks(suppress_errors=True)

    def _drain_open_blocks(self, *, suppress_errors: bool) -> None:
        # Iterate over a copy since we mutate _open_blocks as we go.
        for block_id, kind in list(self._open_blocks.items()):
            end_chunk = {"type": f"{kind}-end", "id": block_id}
            if suppress_errors:
                try:
                    self.on_send_chunk(end_chunk)
                except Exception:
                    LOGGER.debug(
                        "Failed to emit %s for open block id=%s during drain",
                        end_chunk["type"],
                        block_id,
                        exc_info=True,
                    )
            else:
                self.on_send_chunk(end_chunk)
            self._open_blocks.pop(block_id, None)
        self._text_id = None

    def _track_block_state(self, chunk: dict[str, Any]) -> None:
        """Update _open_blocks based on a passing dict chunk's type."""
        chunk_type = chunk.get("type")
        chunk_id = chunk.get("id")
        if not isinstance(chunk_type, str) or not isinstance(chunk_id, str):
            return
        for kind in self._BLOCK_KINDS:
            if chunk_type == f"{kind}-start":
                self._open_blocks[chunk_id] = kind
                return
            if chunk_type == f"{kind}-end":
                self._open_blocks.pop(chunk_id, None)
                return
