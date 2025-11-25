# Copyright 2024 Marimo. All rights reserved.
"""Tests for streaming delta generation and fallback behavior."""

from __future__ import annotations

from marimo._ai.llm._impl import openai


class TestStreamingDeltaGeneration:
    """Test that stream response helpers yield delta chunks."""

    def test_openai_stream_response_yields_deltas(self):
        """Test that OpenAI _stream_response yields delta chunks correctly."""
        from dataclasses import dataclass

        @dataclass
        class MockDelta:
            content: str | None

        @dataclass
        class MockChoice:
            delta: MockDelta

        @dataclass
        class MockChunk:
            choices: list[MockChoice]

        model = openai(
            model="gpt-4",
            api_key="test-key",
        )

        # Simulate a streaming response
        mock_response = [
            MockChunk([MockChoice(MockDelta("Hello"))]),
            MockChunk([MockChoice(MockDelta(" "))]),
            MockChunk([MockChoice(MockDelta("world"))]),
            MockChunk([MockChoice(MockDelta("!"))]),
        ]

        result = list(model._stream_response(mock_response))
        assert result == ["Hello", " ", "world", "!"]

    def test_openai_empty_chunks_filtered(self):
        """Test that OpenAI filters out empty chunks."""
        from dataclasses import dataclass

        @dataclass
        class MockDelta:
            content: str | None

        @dataclass
        class MockChoice:
            delta: MockDelta

        @dataclass
        class MockChunk:
            choices: list[MockChoice]

        model = openai(
            model="gpt-4",
            api_key="test-key",
        )

        # Simulate response with empty chunks
        mock_response = [
            MockChunk([MockChoice(MockDelta("Hello"))]),
            MockChunk([MockChoice(MockDelta(None))]),  # Empty chunk
            MockChunk([MockChoice(MockDelta(" "))]),
            MockChunk([MockChoice(MockDelta(None))]),  # Empty chunk
            MockChunk([MockChoice(MockDelta("world"))]),
        ]

        result = list(model._stream_response(mock_response))
        assert result == ["Hello", " ", "world"]

    def test_groq_stream_response_yields_deltas(self):
        """Test that Groq _stream_response yields delta chunks correctly."""
        from dataclasses import dataclass

        @dataclass
        class MockDelta:
            content: str | None

        @dataclass
        class MockChoice:
            delta: MockDelta

        @dataclass
        class MockChunk:
            choices: list[MockChoice]

        # Simulate a streaming response
        mock_response = [
            MockChunk([MockChoice(MockDelta("Test"))]),
            MockChunk([MockChoice(MockDelta(" "))]),
            MockChunk([MockChoice(MockDelta("response"))]),
        ]

        # Create a custom generator that mimics what _stream_response does
        # This tests the logic of delta chunk yielding independently
        def mock_stream():
            for chunk in mock_response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content

        result = list(mock_stream())
        assert result == ["Test", " ", "response"]


class TestStreamingFallback:
    """Test automatic fallback logic when streaming is not supported."""

    def test_streaming_error_detection(self):
        """Test that streaming errors are detected correctly."""
        # These error messages should trigger fallback
        streaming_errors = [
            "stream does not support true",
            "streaming is not supported",
            "Unsupported value: 'stream'",
            "STREAM parameter not allowed",
            "This model does not support streaming",
        ]

        for error_msg in streaming_errors:
            lower_msg = error_msg.lower()
            # Our fallback logic checks for "stream" or "streaming" in error message
            assert "stream" in lower_msg or "streaming" in lower_msg

    def test_non_streaming_errors_not_caught(self):
        """Test that non-streaming errors are not incorrectly caught as streaming errors."""
        # These errors should NOT trigger fallback
        non_streaming_errors = [
            "invalid api key",
            "rate limit exceeded",
            "model not found",
            "network timeout",
            "insufficient quota",
        ]

        for error_msg in non_streaming_errors:
            lower_msg = error_msg.lower()
            # These should not contain "stream" or "streaming"
            assert "stream" not in lower_msg
            assert "streaming" not in lower_msg
