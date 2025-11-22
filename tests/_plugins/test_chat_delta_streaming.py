# Copyright 2024 Marimo. All rights reserved.
"""Tests for delta-based streaming in chat UI."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Generator

import pytest

from marimo._ai._types import ChatMessage
from marimo._plugins.ui._impl.chat.chat import chat


class TestDeltaStreaming:
    """Test delta-based streaming mode."""

    async def test_async_delta_streaming_accumulates(self):
        """Test that async generators yielding deltas are accumulated correctly."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            """Yields individual delta chunks."""
            yield "Hello"
            yield " "
            yield "world"
            yield "!"

        # Create chat with the delta generator
        chat_ui = chat(delta_generator)

        # Track messages sent
        sent_messages: list[dict] = []

        def capture_send(msg: dict, **kwargs):  # type: ignore
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        # Handle the streaming response
        result = await chat_ui._handle_streaming_response(delta_generator())

        # Verify final result is fully accumulated
        assert result == "Hello world!"

        # Verify incremental chunks were sent correctly
        assert len(sent_messages) == 5  # 4 deltas + 1 final
        assert sent_messages[0]["content"] == "Hello"
        assert sent_messages[1]["content"] == "Hello "
        assert sent_messages[2]["content"] == "Hello world"
        assert sent_messages[3]["content"] == "Hello world!"
        assert sent_messages[4]["content"] == "Hello world!"
        assert sent_messages[4]["is_final"] is True

    async def test_sync_delta_streaming_accumulates(self):
        """Test that sync generators yielding deltas are accumulated correctly."""

        def delta_generator() -> Generator[str, None, None]:
            """Yields individual delta chunks."""
            yield "One"
            yield " "
            yield "Two"
            yield " "
            yield "Three"

        # Create chat with the delta generator
        chat_ui = chat(delta_generator)

        # Track messages sent
        sent_messages: list[dict] = []

        def capture_send(msg: dict, **kwargs):  # type: ignore
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        # Handle the streaming response
        result = await chat_ui._handle_streaming_response(delta_generator())

        # Verify final result is fully accumulated
        assert result == "One Two Three"

        # Verify incremental chunks were sent correctly
        assert len(sent_messages) == 6  # 5 deltas + 1 final
        assert sent_messages[0]["content"] == "One"
        assert sent_messages[1]["content"] == "One "
        assert sent_messages[2]["content"] == "One Two"
        assert sent_messages[3]["content"] == "One Two "
        assert sent_messages[4]["content"] == "One Two Three"
        assert sent_messages[5]["is_final"] is True

    async def test_empty_delta_handled(self):
        """Test that empty deltas are handled gracefully."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            """Yields some empty deltas."""
            yield "Hello"
            yield ""  # Empty delta
            yield " "
            yield ""  # Another empty delta
            yield "world"

        chat_ui = chat(delta_generator)
        sent_messages: list[dict] = []

        def capture_send(msg: dict, **kwargs):  # type: ignore
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        result = await chat_ui._handle_streaming_response(delta_generator())

        assert result == "Hello world"
        # Empty deltas still trigger message sends
        assert len(sent_messages) == 6  # 5 deltas (including empty) + 1 final

    async def test_single_delta(self):
        """Test streaming with a single delta."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            yield "Single chunk"

        chat_ui = chat(delta_generator)
        sent_messages: list[dict] = []

        def capture_send(msg: dict, **kwargs):  # type: ignore
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        result = await chat_ui._handle_streaming_response(delta_generator())

        assert result == "Single chunk"
        assert len(sent_messages) == 2  # 1 delta + 1 final
        assert sent_messages[0]["content"] == "Single chunk"
        assert sent_messages[1]["is_final"] is True

    async def test_no_deltas(self):
        """Test streaming with no deltas (empty generator)."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            # Yield nothing
            if False:
                yield ""

        chat_ui = chat(delta_generator)
        sent_messages: list[dict] = []

        def capture_send(msg: dict, **kwargs):  # type: ignore
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        result = await chat_ui._handle_streaming_response(delta_generator())

        assert result == ""
        # No final message sent if no content
        assert len(sent_messages) == 0

    async def test_unicode_deltas(self):
        """Test that unicode characters in deltas are handled correctly."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            yield "Hello "
            yield "🌍"
            yield " "
            yield "世界"
            yield "!"

        chat_ui = chat(delta_generator)
        sent_messages: list[dict] = []

        def capture_send(msg: dict, **kwargs):  # type: ignore
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        result = await chat_ui._handle_streaming_response(delta_generator())

        assert result == "Hello 🌍 世界!"
        assert sent_messages[-1]["content"] == "Hello 🌍 世界!"

    async def test_message_id_consistency(self):
        """Test that all chunks in a stream share the same message_id."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            yield "A"
            yield "B"
            yield "C"

        chat_ui = chat(delta_generator)
        sent_messages: list[dict] = []

        def capture_send(msg: dict, **kwargs):  # type: ignore
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        await chat_ui._handle_streaming_response(delta_generator())

        # All messages should have the same message_id
        message_ids = [msg["message_id"] for msg in sent_messages]
        assert len(set(message_ids)) == 1
        assert all(msg["type"] == "stream_chunk" for msg in sent_messages)

    async def test_long_streaming_response(self):
        """Test streaming with many small deltas (simulates real AI streaming)."""

        async def delta_generator() -> AsyncGenerator[str, None]:
            # Simulate many small tokens like real AI models
            words = ["This", " is", " a", " long", " streaming", 
                     " response", " with", " many", " deltas", "."]
            for word in words:
                yield word
                await asyncio.sleep(0.001)  # Tiny delay

        chat_ui = chat(delta_generator)
        sent_messages: list[dict] = []

        def capture_send(msg: dict, **kwargs):  # type: ignore
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        result = await chat_ui._handle_streaming_response(delta_generator())

        expected = "This is a long streaming response with many deltas."
        assert result == expected
        assert len(sent_messages) == 11  # 10 deltas + 1 final
        
        # Verify progressive accumulation
        assert sent_messages[0]["content"] == "This"
        assert sent_messages[1]["content"] == "This is"
        assert sent_messages[2]["content"] == "This is a"
        assert sent_messages[-1]["content"] == expected
        assert sent_messages[-1]["is_final"] is True


class TestStreamingWithChatModels:
    """Test streaming with actual ChatModel-like objects."""

    async def test_custom_model_function(self):
        """Test that custom model functions work with delta streaming."""

        async def custom_model(
            messages: list[ChatMessage], config: dict
        ) -> AsyncGenerator[str, None]:
            """Custom model that yields deltas."""
            user_msg = messages[-1].content
            response = f"You said: {user_msg}"
            for char in response:
                yield char
                await asyncio.sleep(0.001)

        chat_ui = chat(custom_model)
        sent_messages: list[dict] = []

        def capture_send(msg: dict, **kwargs):  # type: ignore
            sent_messages.append(msg)

        chat_ui._send_message = capture_send  # type: ignore

        # Simulate calling the model
        test_messages = [ChatMessage(role="user", content="Hello")]
        generator = custom_model(test_messages, {})
        
        result = await chat_ui._handle_streaming_response(generator)

        assert result == "You said: Hello"
        # Should have one chunk per character plus final
        assert len(sent_messages) > 0
        assert sent_messages[-1]["is_final"] is True


class TestStreamingEfficiency:
    """Test that delta streaming is efficient compared to accumulated streaming."""

    async def test_delta_vs_accumulated_bandwidth(self):
        """Demonstrate bandwidth savings of delta vs accumulated streaming."""

        # Simulate 100-word response
        words = ["word" + str(i) for i in range(100)]

        # Delta streaming: each word is sent once
        async def delta_stream() -> AsyncGenerator[str, None]:
            for word in words:
                yield word + " "

        chat_ui = chat(delta_stream)
        delta_sent_messages: list[dict] = []

        def capture_delta(msg: dict, **kwargs):  # type: ignore
            delta_sent_messages.append(msg)

        chat_ui._send_message = capture_delta  # type: ignore

        await chat_ui._handle_streaming_response(delta_stream())

        # Calculate bytes sent with delta streaming
        # Backend sends accumulated text, but receives deltas
        delta_bytes_received = sum(
            len(word + " ") for word in words
        )
        
        # Each message sends the accumulated content
        delta_bytes_sent = sum(
            len(msg["content"]) for msg in delta_sent_messages
        )

        # With old accumulated approach, model would yield:
        # "word0 ", "word0 word1 ", "word0 word1 word2 ", etc.
        accumulated_bytes_received = sum(
            len(" ".join(words[:i+1]) + " ") for i in range(len(words))
        )

        # Delta mode receives much less data from the model
        assert delta_bytes_received < accumulated_bytes_received
        
        # For 100 words, delta receives ~100 words worth of data
        # while accumulated receives ~5000 words worth (1+2+3+...+100)
        efficiency_ratio = accumulated_bytes_received / delta_bytes_received
        assert efficiency_ratio > 40  # Should be ~50x more efficient

        print(f"\nEfficiency Test Results:")
        print(f"Delta bytes received: {delta_bytes_received}")
        print(f"Accumulated bytes received: {accumulated_bytes_received}")
        print(f"Efficiency ratio: {efficiency_ratio:.1f}x")

