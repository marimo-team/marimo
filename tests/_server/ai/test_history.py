# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from marimo._server.ai.history import (
    CheckpointSummary,
    ConversationHistoryManager,
)


def _conversation(
    *, turns: int, marker: str = "original"
) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    for index in range(turns):
        messages.extend(
            [
                {
                    "id": f"user-{index}",
                    "role": "user",
                    "parts": [
                        {
                            "type": "text",
                            "text": f"request {index} {marker} " + "u" * 900,
                        }
                    ],
                },
                {
                    "id": f"assistant-{index}",
                    "role": "assistant",
                    "parts": [
                        {
                            "type": "text",
                            "text": f"result {index} " + "a" * 900,
                        }
                    ],
                },
            ]
        )
    messages.append(
        {
            "id": "current-user",
            "role": "user",
            "parts": [{"type": "text", "text": "next task"}],
        }
    )
    return messages


@pytest.mark.asyncio
async def test_checkpoint_is_reused_across_requests() -> None:
    manager = ConversationHistoryManager()
    messages = _conversation(turns=10)
    summarize = AsyncMock(
        return_value=CheckpointSummary("- completed the earlier work")
    )

    first = await manager.prepare(
        key=("session", "chat"),
        model="provider/model",
        messages=messages,
        semantic_messages=messages,
        summarize=summarize,
        context_window=None,
        threshold_tokens=2_000,
    )
    second = await manager.prepare(
        key=("session", "chat"),
        model="provider/model",
        messages=messages,
        semantic_messages=messages,
        summarize=summarize,
        context_window=None,
        threshold_tokens=2_000,
    )

    assert first.checkpoint_generated is True
    assert second.checkpoint_generated is False
    assert summarize.await_count == 1
    assert second.messages[1]["parts"] == [
        {"type": "text", "text": "- completed the earlier work"}
    ]
    assert "request 0 original" in second.messages[0]["parts"][0]["text"]
    assert "result 0" in second.messages[0]["parts"][0]["text"]


@pytest.mark.asyncio
async def test_checkpoint_updates_only_after_new_completed_turns() -> None:
    manager = ConversationHistoryManager()
    initial = _conversation(turns=10)
    summarize = AsyncMock(
        side_effect=[
            CheckpointSummary("first checkpoint"),
            CheckpointSummary("updated checkpoint"),
        ]
    )
    await manager.prepare(
        key=("session", "chat"),
        model="provider/model",
        messages=initial,
        semantic_messages=initial,
        summarize=summarize,
        context_window=None,
        threshold_tokens=2_000,
    )

    extended = _conversation(turns=14)
    result = await manager.prepare(
        key=("session", "chat"),
        model="provider/model",
        messages=extended,
        semantic_messages=extended,
        summarize=summarize,
        context_window=None,
        threshold_tokens=2_000,
    )

    assert result.checkpoint_generated is True
    assert summarize.await_count == 2
    assert (
        "Previous checkpoint:\nfirst checkpoint"
        in (summarize.await_args.args[0])
    )
    assert result.messages[1]["parts"] == [
        {"type": "text", "text": "updated checkpoint"}
    ]


@pytest.mark.asyncio
async def test_edited_prefix_invalidates_checkpoint() -> None:
    manager = ConversationHistoryManager()
    original = _conversation(turns=10)
    summarize = AsyncMock(
        side_effect=[
            CheckpointSummary("old checkpoint"),
            CheckpointSummary("new checkpoint"),
        ]
    )
    await manager.prepare(
        key=("session", "chat"),
        model="provider/model",
        messages=original,
        semantic_messages=original,
        summarize=summarize,
        context_window=None,
        threshold_tokens=2_000,
    )

    edited = _conversation(turns=10, marker="edited")
    result = await manager.prepare(
        key=("session", "chat"),
        model="provider/model",
        messages=edited,
        semantic_messages=edited,
        summarize=summarize,
        context_window=None,
        threshold_tokens=2_000,
    )

    assert result.checkpoint_reset is True
    assert result.checkpoint_generated is True
    assert "No previous checkpoint." in summarize.await_args.args[0]


@pytest.mark.asyncio
async def test_checkpoint_failure_preserves_usable_history() -> None:
    manager = ConversationHistoryManager()
    messages = _conversation(turns=10)

    result = await manager.prepare(
        key=("session", "chat"),
        model="provider/model",
        messages=messages,
        semantic_messages=messages,
        summarize=AsyncMock(side_effect=RuntimeError("provider unavailable")),
        context_window=None,
        threshold_tokens=2_000,
    )

    assert result.checkpoint_generated is False
    assert result.checkpoint_error == "provider unavailable"
    assert result.messages == messages


@pytest.mark.asyncio
async def test_short_history_does_not_call_summarizer() -> None:
    manager = ConversationHistoryManager()
    messages = _conversation(turns=1)
    summarize = AsyncMock()

    result = await manager.prepare(
        key=("session", "chat"),
        model="provider/model",
        messages=messages,
        semantic_messages=messages,
        summarize=summarize,
        context_window=128_000,
    )

    assert result.messages == messages
    summarize.assert_not_awaited()
