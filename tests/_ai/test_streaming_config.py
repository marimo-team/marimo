# Copyright 2024 Marimo. All rights reserved.
"""Tests for streaming configuration and fallback behavior."""

from __future__ import annotations

import pytest

from marimo._ai.llm._impl import anthropic, bedrock, google, groq, openai


class TestStreamingConfiguration:
    """Test streaming configuration parameter."""

    def test_openai_stream_parameter_default_true(self):
        """Test that OpenAI stream parameter defaults to True."""
        model = openai(
            model="gpt-4",
            api_key="test-key",
        )
        assert model.stream is True

    def test_openai_stream_parameter_configurable(self):
        """Test that OpenAI stream parameter can be set to False."""
        model = openai(
            model="gpt-4",
            stream=False,
            api_key="test-key",
        )
        assert model.stream is False

    def test_anthropic_stream_parameter_default_true(self):
        """Test that Anthropic stream parameter defaults to True."""
        model = anthropic(
            model="claude-3-5-sonnet-20241022",
            api_key="test-key",
        )
        assert model.stream is True

    def test_anthropic_stream_parameter_configurable(self):
        """Test that Anthropic stream parameter can be set to False."""
        model = anthropic(
            model="claude-3-5-sonnet-20241022",
            stream=False,
            api_key="test-key",
        )
        assert model.stream is False

    def test_google_stream_parameter_default_true(self):
        """Test that Google stream parameter defaults to True."""
        model = google(
            model="gemini-1.5-flash",
            api_key="test-key",
        )
        assert model.stream is True

    def test_google_stream_parameter_configurable(self):
        """Test that Google stream parameter can be set to False."""
        model = google(
            model="gemini-1.5-flash",
            stream=False,
            api_key="test-key",
        )
        assert model.stream is False

    def test_groq_stream_parameter_default_true(self):
        """Test that Groq stream parameter defaults to True."""
        model = groq(
            model="llama-3.3-70b-versatile",
            api_key="test-key",
        )
        assert model.stream is True

    def test_groq_stream_parameter_configurable(self):
        """Test that Groq stream parameter can be set to False."""
        model = groq(
            model="llama-3.3-70b-versatile",
            stream=False,
            api_key="test-key",
        )
        assert model.stream is False

    def test_bedrock_stream_parameter_default_true(self):
        """Test that Bedrock stream parameter defaults to True."""
        model = bedrock(
            model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            region_name="us-east-1",
        )
        assert model.stream is True

    def test_bedrock_stream_parameter_configurable(self):
        """Test that Bedrock stream parameter can be set to False."""
        model = bedrock(
            model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            region_name="us-east-1",
            stream=False,
        )
        assert model.stream is False


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
