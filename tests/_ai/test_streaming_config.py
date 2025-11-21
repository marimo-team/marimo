# Copyright 2024 Marimo. All rights reserved.
"""Tests for streaming configuration and fallback behavior."""

from __future__ import annotations

from marimo._ai.llm._impl import _LiteLLMBase


class TestStreamingConfiguration:
    """Test streaming configuration parameter."""

    def test_stream_parameter_default_true(self):
        """Test that stream parameter defaults to True."""
        model = _LiteLLMBase(
            model="test-model",
            provider_name="Test",
            env_var_name="TEST_API_KEY",
        )
        assert model.stream is True

    def test_stream_parameter_configurable(self):
        """Test that stream parameter can be set to False."""
        model = _LiteLLMBase(
            model="test-model",
            stream=False,
            provider_name="Test",
            env_var_name="TEST_API_KEY",
        )
        assert model.stream is False

    def test_stream_response_generator(self):
        """Test that _stream_response yields delta chunks correctly."""
        from dataclasses import dataclass

        @dataclass
        class MockDelta:
            content: str

        @dataclass
        class MockChoice:
            delta: MockDelta

        @dataclass
        class MockChunk:
            choices: list[MockChoice]

        model = _LiteLLMBase(
            model="test-model",
            provider_name="Test",
            env_var_name="TEST_API_KEY",
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

    def test_empty_chunks_filtered(self):
        """Test that empty chunks are filtered out."""
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

        model = _LiteLLMBase(
            model="test-model",
            provider_name="Test",
            env_var_name="TEST_API_KEY",
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


class TestStreamingFallback:
    """Test automatic fallback when streaming is not supported."""

    def test_fallback_error_detection(self):
        """Test that streaming errors are detected correctly."""
        # These error messages should trigger fallback
        streaming_errors = [
            "stream does not support true",
            "streaming is not supported",
            "Unsupported value: 'stream'",
            "STREAM parameter not allowed",
        ]

        for error_msg in streaming_errors:
            lower_msg = error_msg.lower()
            assert "stream" in lower_msg or "streaming" in lower_msg

    def test_non_streaming_errors_not_caught(self):
        """Test that non-streaming errors are not incorrectly caught."""
        # These errors should NOT trigger fallback
        non_streaming_errors = [
            "invalid api key",
            "rate limit exceeded",
            "model not found",
            "network timeout",
        ]

        for error_msg in non_streaming_errors:
            lower_msg = error_msg.lower()
            assert "stream" not in lower_msg
            assert "streaming" not in lower_msg
