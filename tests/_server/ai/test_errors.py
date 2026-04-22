# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio

import pytest

from marimo._server.ai.errors import translate_ai_error


class TestContextLength:
    @pytest.mark.parametrize(
        "raw",
        [
            # OpenAI
            "openai.BadRequestError: This model's maximum context length is 128000 tokens",
            "Error code: 400 - {'error': {'code': 'context_length_exceeded'}}",
            "Please reduce the length of the messages",
            # Anthropic
            "prompt is too long: 200001 tokens > 200000 maximum",
            "input length and max_tokens exceed context limit",
            # Google
            "The total size of the request including the context window was exceeded",
            # Generic
            "content size exceeds model limits",
            "too many tokens in prompt",
        ],
    )
    def test_recognized_as_context_length(self, raw: str) -> None:
        result = translate_ai_error(RuntimeError(raw))
        assert result.category == "context_length"
        assert "context window" in result.message
        assert result.original == raw


class TestTimeout:
    def test_asyncio_timeout_error_instance(self) -> None:
        result = translate_ai_error(asyncio.TimeoutError())
        assert result.category == "timeout"
        assert "too long" in result.message

    @pytest.mark.parametrize(
        "raw",
        [
            # gRPC / Vertex
            "grpc: context deadline exceeded",
            "DeadlineExceeded: deadline exceeded after 30s",
            # Generic
            "Request timed out",
            "Read timed out after 60.0s",
            "Tool execution timed out after 30 seconds",
            "Timeout exceeded while calling OpenAI",
        ],
    )
    def test_recognized_as_timeout(self, raw: str) -> None:
        result = translate_ai_error(RuntimeError(raw))
        assert result.category == "timeout"

    def test_asyncio_timeout_takes_precedence_over_string_match(self) -> None:
        # Even if the exception's str is empty, isinstance check catches it.
        err = asyncio.TimeoutError()
        result = translate_ai_error(err)
        assert result.category == "timeout"


class TestAuth:
    @pytest.mark.parametrize(
        "raw",
        [
            "AuthenticationError: Invalid API key provided",
            "401 Unauthorized",
            "Error: Incorrect API key",
            "authentication failed for provider",
        ],
    )
    def test_recognized_as_auth(self, raw: str) -> None:
        result = translate_ai_error(RuntimeError(raw))
        assert result.category == "auth"
        assert "API key" in result.message or "login" in result.message


class TestRateLimit:
    @pytest.mark.parametrize(
        "raw",
        [
            "RateLimitError: Rate limit reached",
            "HTTP 429: Too Many Requests",
            "quota exceeded for project",
            "resource exhausted",
        ],
    )
    def test_recognized_as_rate_limit(self, raw: str) -> None:
        result = translate_ai_error(RuntimeError(raw))
        assert result.category == "rate_limit"


class TestUnknown:
    def test_unrecognized_error_falls_through_to_original(self) -> None:
        raw = "Something went completely sideways in the network stack"
        result = translate_ai_error(RuntimeError(raw))
        assert result.category == "unknown"
        # Must not mangle errors we don't recognize.
        assert result.message == raw
        assert result.original == raw

    def test_empty_error_message_is_preserved(self) -> None:
        result = translate_ai_error(RuntimeError(""))
        assert result.category == "unknown"
        assert result.message == ""


class TestPrecedence:
    def test_context_length_wins_over_timeout_when_both_strings_present(
        self,
    ) -> None:
        # A provider once returned "timeout: prompt is too long". Without
        # deterministic ordering the user would get the wrong guidance.
        raw = "timeout: prompt is too long"
        result = translate_ai_error(RuntimeError(raw))
        assert result.category == "context_length"

    def test_auth_wins_over_rate_limit_when_both_plausible(self) -> None:
        raw = "401 unauthorized (you may also have been rate limited)"
        result = translate_ai_error(RuntimeError(raw))
        assert result.category == "auth"
