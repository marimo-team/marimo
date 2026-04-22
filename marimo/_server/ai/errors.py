# Copyright 2026 Marimo. All rights reserved.
"""Translate AI provider errors into user-actionable messages.

The AI streaming path in ``endpoints/ai.py`` catches every exception raised
during a chat/completion call and stringifies it into the error channel of
the AI SDK stream protocol. Provider SDKs throw wildly different messages
for the same underlying problem ("context window exceeded" looks completely
different coming from OpenAI, Anthropic, Google, and Bedrock), and raw SDK
strings aren't useful to a notebook author. This module maps them into a
small, stable set of categories with messages that tell the user what to
do next.

Kept intentionally tiny and dependency-free so it's trivially unit-testable
and cheap to extend as new provider quirks surface.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

AiErrorCategory = Literal[
    "context_length",
    "timeout",
    "auth",
    "rate_limit",
    "unknown",
]


@dataclass(frozen=True)
class TranslatedAiError:
    category: AiErrorCategory
    message: str
    # Keep the raw provider string so power users / bug reports can still
    # inspect it via the server log (we log originals, not translations).
    original: str


# Each pattern list is matched case-insensitively against ``str(error)``.
# Order matters: the first category to match wins. Keep patterns specific
# enough not to false-positive (e.g. "timeout" matches too broadly if a
# user's prompt legitimately contains the word).
_CONTEXT_LENGTH_PATTERNS = (
    "context_length_exceeded",
    "maximum context length",
    "prompt is too long",
    "input length and max_tokens exceed",
    "context window",
    "too many tokens",
    "reduce the length of the messages",
    "content size exceeds",
)

_TIMEOUT_PATTERNS = (
    "context deadline exceeded",
    "deadlineexceeded",
    "request timed out",
    "read timed out",
    "timed out after",
    "timeout exceeded",
)

_AUTH_PATTERNS = (
    "invalid api key",
    "invalid_api_key",
    "incorrect api key",
    "authentication failed",
    "authenticationerror",
    "not authorized",
    "unauthorized",
    "401",
    "403",
)

_RATE_LIMIT_PATTERNS = (
    "rate limit",
    "rate_limit",
    "too many requests",
    "429",
    "quota exceeded",
    "resource exhausted",
)


def translate_ai_error(error: BaseException) -> TranslatedAiError:
    """Classify a provider / MCP / transport error and return a friendly message.

    Falls back to the original string when no pattern matches, so this is
    always safe to call — the worst case is we return what we would have
    shown anyway.
    """
    raw = str(error)
    lowered = raw.lower()

    if isinstance(error, asyncio.TimeoutError):
        return TranslatedAiError(
            category="timeout",
            message=(
                "The AI provider took too long to respond. If this "
                "involved an MCP tool, its timeout may be too short for "
                "the operation — increase ``timeout`` on the MCP server "
                "in your marimo.toml."
            ),
            original=raw,
        )

    if _any_match(lowered, _CONTEXT_LENGTH_PATTERNS):
        return TranslatedAiError(
            category="context_length",
            message=(
                "This conversation has grown past the model's context "
                "window. Start a new chat, switch to a longer-context "
                "model, or remove attachments and earlier messages."
            ),
            original=raw,
        )

    if _any_match(lowered, _TIMEOUT_PATTERNS):
        return TranslatedAiError(
            category="timeout",
            message=(
                "The AI provider took too long to respond. Try again, or "
                "increase the MCP ``timeout`` in your marimo.toml if a "
                "tool call stalled."
            ),
            original=raw,
        )

    if _any_match(lowered, _AUTH_PATTERNS):
        return TranslatedAiError(
            category="auth",
            message=(
                "The AI provider rejected the request as unauthenticated. "
                "Check your API key in Settings → AI, or your provider's "
                "login state."
            ),
            original=raw,
        )

    if _any_match(lowered, _RATE_LIMIT_PATTERNS):
        return TranslatedAiError(
            category="rate_limit",
            message=(
                "The AI provider is rate-limiting requests. Wait a moment "
                "before retrying, or switch to a different model."
            ),
            original=raw,
        )

    return TranslatedAiError(category="unknown", message=raw, original=raw)


def _any_match(haystack: str, patterns: tuple[str, ...]) -> bool:
    return any(p in haystack for p in patterns)
