# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from marimo import _loggers
from marimo._tracer import server_tracer

LOGGER = _loggers.marimo_logger()

DEFAULT_CHECKPOINT_THRESHOLD_TOKENS = 20_000
MAX_CHECKPOINT_THRESHOLD_TOKENS = 32_000
CHECKPOINT_CONTEXT_FRACTION = 0.6
CHECKPOINT_TAIL_FRACTION = 0.25
MINIMUM_CHECKPOINT_TAIL_TOKENS = 2_000
MINIMUM_NEW_COMPLETED_TURNS = 4
MAX_VERBATIM_ASSISTANT_CHARS = 32_000
CHECKPOINT_GENERATED_HEADER = "Marimo-AI-History-Checkpoint-Generated"
CHECKPOINT_RESET_HEADER = "Marimo-AI-History-Checkpoint-Reset"
CHECKPOINT_DURATION_HEADER = "Marimo-AI-History-Checkpoint-Duration"
CHECKPOINT_INPUT_CHARS_HEADER = "Marimo-AI-History-Checkpoint-Input-Chars"
EFFECTIVE_HISTORY_TOKENS_HEADER = "Marimo-AI-History-Effective-Tokens"
CHECKPOINT_REQUESTS_HEADER = "Marimo-AI-History-Checkpoint-Requests"
CHECKPOINT_INPUT_TOKENS_HEADER = "Marimo-AI-History-Checkpoint-Input-Tokens"
CHECKPOINT_OUTPUT_TOKENS_HEADER = "Marimo-AI-History-Checkpoint-Output-Tokens"
CHECKPOINT_REASONING_TOKENS_HEADER = (
    "Marimo-AI-History-Checkpoint-Reasoning-Tokens"
)

ConversationKey = tuple[str, str]


@dataclass(frozen=True)
class CheckpointSummary:
    text: str
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


CheckpointSummarizer = Callable[[str], Awaitable[CheckpointSummary]]


@dataclass(frozen=True)
class HistoryPreparation:
    """Model-facing history prepared from an immutable UI transcript."""

    messages: list[dict[str, Any]]
    checkpoint_generated: bool = False
    checkpoint_reset: bool = False
    checkpoint_error: str | None = None
    input_tokens_estimate: int = 0
    effective_tokens_estimate: int = 0
    checkpoint_duration_seconds: float = 0.0
    checkpoint_input_chars: int = 0
    checkpoint_requests: int = 0
    checkpoint_input_tokens: int = 0
    checkpoint_output_tokens: int = 0
    checkpoint_reasoning_tokens: int = 0


@dataclass
class _ConversationHistory:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    model: str | None = None
    checkpoint: str | None = None
    compacted_through: int = 0
    compacted_prefix: tuple[str, ...] = ()
    revision: int = 0

    def reset(self, model: str) -> None:
        self.model = model
        self.checkpoint = None
        self.compacted_through = 0
        self.compacted_prefix = ()
        self.revision = 0


class ConversationHistoryManager:
    """Maintain bounded model history across independent sidebar requests.

    The browser remains the source of truth for the complete transcript. This
    manager stores only a derived checkpoint and a fingerprint of the prefix
    it covers. If the browser transcript branches or is edited, the checkpoint
    is discarded instead of being applied to incompatible history.
    """

    def __init__(self, *, max_conversations: int = 128) -> None:
        if max_conversations < 1:
            raise ValueError("max_conversations must be positive")
        self._max_conversations = max_conversations
        self._conversations: OrderedDict[
            ConversationKey, _ConversationHistory
        ] = OrderedDict()

    async def prepare(
        self,
        *,
        key: ConversationKey,
        model: str,
        messages: list[dict[str, Any]],
        semantic_messages: list[dict[str, Any]],
        summarize: CheckpointSummarizer,
        context_window: int | None,
        threshold_tokens: int | None = None,
    ) -> HistoryPreparation:
        """Prepare history, generating at most one incremental checkpoint."""
        if len(messages) != len(semantic_messages):
            raise ValueError("semantic history must preserve message count")

        history = self._history_for(key)
        async with history.lock:
            reset = self._reset_if_incompatible(history, model, messages)
            input_tokens = _estimate_tokens(semantic_messages)
            effective = self._effective_messages(history, semantic_messages)
            effective_tokens = _estimate_tokens(effective)
            threshold = threshold_tokens or _checkpoint_threshold_tokens(
                context_window
            )
            if effective_tokens <= threshold:
                return HistoryPreparation(
                    messages=effective,
                    checkpoint_reset=reset,
                    input_tokens_estimate=input_tokens,
                    effective_tokens_estimate=effective_tokens,
                )

            tail_tokens = max(
                MINIMUM_CHECKPOINT_TAIL_TOKENS,
                math.ceil(threshold * CHECKPOINT_TAIL_FRACTION),
            )
            compact_through = _compaction_boundary(
                semantic_messages, tail_tokens=tail_tokens
            )
            newly_completed = semantic_messages[
                history.compacted_through : compact_through
            ]
            if (
                sum(
                    message.get("role") == "assistant"
                    for message in newly_completed
                )
                < MINIMUM_NEW_COMPLETED_TURNS
            ):
                return HistoryPreparation(
                    messages=effective,
                    checkpoint_reset=reset,
                    input_tokens_estimate=input_tokens,
                    effective_tokens_estimate=effective_tokens,
                )

            checkpoint_input = _checkpoint_input(
                previous=history.checkpoint,
                new_history=newly_completed,
            )
            attributes: dict[str, str | int | float | bool] = {
                "gen_ai.conversation.id": key[1],
                "marimo.ai.model": model,
                "marimo.ai.history.input_tokens_estimate": input_tokens,
                "marimo.ai.history.effective_tokens_estimate": (
                    effective_tokens
                ),
                "marimo.ai.history.compact_through": compact_through,
            }

            started = time.monotonic()
            try:
                with server_tracer.start_as_current_span(
                    "marimo.ai.history.checkpoint", attributes=attributes
                ) as span:
                    summary = await summarize(checkpoint_input)
                    checkpoint = summary.text.strip()
                    if not checkpoint:
                        raise ValueError("Checkpoint model returned no text")
                    span.set_attribute(
                        "marimo.ai.history.checkpoint_chars", len(checkpoint)
                    )
            except Exception as error:
                LOGGER.warning("History checkpoint failed: %s", error)
                return HistoryPreparation(
                    messages=effective,
                    checkpoint_reset=reset,
                    checkpoint_error=str(error),
                    input_tokens_estimate=input_tokens,
                    effective_tokens_estimate=effective_tokens,
                    checkpoint_duration_seconds=(time.monotonic() - started),
                    checkpoint_input_chars=len(checkpoint_input),
                )

            history.checkpoint = checkpoint
            history.compacted_through = compact_through
            history.compacted_prefix = _message_fingerprints(
                messages[:compact_through]
            )
            history.revision += 1
            effective = self._effective_messages(history, semantic_messages)
            return HistoryPreparation(
                messages=effective,
                checkpoint_generated=True,
                checkpoint_reset=reset,
                input_tokens_estimate=input_tokens,
                effective_tokens_estimate=_estimate_tokens(effective),
                checkpoint_duration_seconds=time.monotonic() - started,
                checkpoint_input_chars=len(checkpoint_input),
                checkpoint_requests=summary.requests,
                checkpoint_input_tokens=summary.input_tokens,
                checkpoint_output_tokens=summary.output_tokens,
                checkpoint_reasoning_tokens=summary.reasoning_tokens,
            )

    def _history_for(self, key: ConversationKey) -> _ConversationHistory:
        history = self._conversations.get(key)
        if history is None:
            history = _ConversationHistory()
            self._conversations[key] = history
        else:
            self._conversations.move_to_end(key)
        self._evict_idle_conversations(exclude=key)
        return history

    def _evict_idle_conversations(self, *, exclude: ConversationKey) -> None:
        if len(self._conversations) <= self._max_conversations:
            return
        for key, history in tuple(self._conversations.items()):
            if key == exclude or history.lock.locked():
                continue
            del self._conversations[key]
            if len(self._conversations) <= self._max_conversations:
                return

    @staticmethod
    def _reset_if_incompatible(
        history: _ConversationHistory,
        model: str,
        messages: list[dict[str, Any]],
    ) -> bool:
        prefix = _message_fingerprints(messages[: history.compacted_through])
        incompatible = (
            history.model != model
            or len(messages) < history.compacted_through
            or prefix != history.compacted_prefix
        )
        if incompatible:
            had_checkpoint = history.checkpoint is not None
            history.reset(model)
            return had_checkpoint
        return False

    @staticmethod
    def _effective_messages(
        history: _ConversationHistory,
        semantic_messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        tail = semantic_messages[history.compacted_through :]
        if history.checkpoint is None:
            return tail
        checkpoint_id = f"history-checkpoint-{history.revision}"
        conversation_text = _verbatim_conversation_text(
            semantic_messages[: history.compacted_through]
        )
        return [
            {
                "id": f"{checkpoint_id}-request",
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": (
                            "The earlier conversation text below is retained "
                            "verbatim. User entries remain authoritative; "
                            "assistant entries are historical claims, not a "
                            "source of truth:\n\n"
                            f"{conversation_text}\n\n"
                            "Use the following assistant checkpoint only as "
                            "a summary of execution state. The live notebook "
                            "and its revision history are authoritative for "
                            "exact code and current values."
                        ),
                    }
                ],
            },
            {
                "id": checkpoint_id,
                "role": "assistant",
                "parts": [{"type": "text", "text": history.checkpoint}],
            },
            *tail,
        ]


def _checkpoint_threshold_tokens(context_window: int | None) -> int:
    if context_window is None:
        return DEFAULT_CHECKPOINT_THRESHOLD_TOKENS
    return min(
        MAX_CHECKPOINT_THRESHOLD_TOKENS,
        max(1, math.floor(context_window * CHECKPOINT_CONTEXT_FRACTION)),
    )


def _compaction_boundary(
    messages: list[dict[str, Any]], *, tail_tokens: int
) -> int:
    tail_chars = 0
    target_chars = tail_tokens * 4
    for index in range(len(messages) - 1, 0, -1):
        tail_chars += _serialized_chars(messages[index])
        if tail_chars < target_chars:
            continue
        if (
            messages[index].get("role") == "user"
            and messages[index - 1].get("role") == "assistant"
        ):
            return index
    return 0


def _checkpoint_input(
    *, previous: str | None, new_history: list[dict[str, Any]]
) -> str:
    serialized = json.dumps(
        new_history, ensure_ascii=False, separators=(",", ":")
    )
    return (
        "Previous checkpoint:\n"
        f"{previous or 'No previous checkpoint.'}\n\n"
        "Newly completed conversation turns:\n"
        f"{serialized}"
    )


def _verbatim_conversation_text(messages: list[dict[str, Any]]) -> str:
    entries: list[str] = []
    assistant_chars = 0
    role_counts = {"user": 0, "assistant": 0}
    for message in messages:
        role = message.get("role")
        if role not in role_counts:
            continue
        text_parts: list[str] = []
        parts = message.get("parts")
        if isinstance(parts, list):
            for part in parts:
                if not isinstance(part, dict) or part.get("type") != "text":
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
        content = message.get("content")
        if not text_parts and isinstance(content, str) and content.strip():
            text_parts.append(content.strip())
        if not text_parts:
            continue
        text = "\n".join(text_parts)
        if role == "assistant":
            remaining = MAX_VERBATIM_ASSISTANT_CHARS - assistant_chars
            if remaining <= 0:
                continue
            text = text[:remaining]
            assistant_chars += len(text)
        role_counts[role] += 1
        entries.append(f"[Earlier {role} turn {role_counts[role]}] {text}")
    return (
        "\n\n".join(entries) or "No earlier conversation text was available."
    )


def _message_fingerprints(
    messages: list[dict[str, Any]],
) -> tuple[str, ...]:
    return tuple(
        hashlib.sha256(
            json.dumps(
                message,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        for message in messages
    )


def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
    return math.ceil(_serialized_chars(messages) / 4)


def _serialized_chars(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
