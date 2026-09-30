from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from benchmarks.ai.models import TokenUsage
from benchmarks.ai.vercel_stream import serialized_chars
from marimo._server.ai.tools.code_mode import compact_hybrid_history

_WANDB_BASE_URL = "https://api.inference.wandb.ai/v1/"


@dataclass(frozen=True)
class CheckpointPreparation:
    messages: list[dict[str, Any]]
    generated: bool = False
    duration_seconds: float = 0.0
    input_chars: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)


class IncrementalCheckpointCompactor:
    """Build reusable summaries of completed turns above a payload budget."""

    def __init__(
        self,
        *,
        model: str,
        threshold_chars: int = 80_000,
        recent_messages: int = 5,
        minimum_completed_turns: int = 2,
    ) -> None:
        if recent_messages < 1 or recent_messages % 2 == 0:
            raise ValueError("recent_messages must be a positive odd number")
        if minimum_completed_turns < 1:
            raise ValueError("minimum_completed_turns must be positive")
        self._model = model.removeprefix("wandb/")
        self._threshold_chars = threshold_chars
        self._recent_messages = recent_messages
        self._minimum_new_messages = minimum_completed_turns * 2
        self._checkpoint: str | None = None
        self._compacted_through = 0

    def prepare(self, messages: list[dict[str, Any]]) -> CheckpointPreparation:
        semantic_messages = compact_hybrid_history(messages)
        effective = self._effective_messages(semantic_messages)
        if serialized_chars(effective) <= self._threshold_chars:
            return CheckpointPreparation(messages=effective)

        # A chat request contains complete user/assistant pairs followed by the
        # current user message. Retaining an odd number leaves the checkpoint
        # boundary between complete turns.
        compact_through = max(0, len(messages) - self._recent_messages)
        if (
            compact_through - self._compacted_through
            < self._minimum_new_messages
        ):
            return CheckpointPreparation(messages=effective)

        new_history = semantic_messages[
            self._compacted_through : compact_through
        ]
        input_text = self._checkpoint_input(new_history)
        started = time.monotonic()
        checkpoint, usage = self._generate_checkpoint(input_text)
        self._checkpoint = checkpoint
        self._compacted_through = compact_through
        effective = self._effective_messages(semantic_messages)
        return CheckpointPreparation(
            messages=effective,
            generated=True,
            duration_seconds=time.monotonic() - started,
            input_chars=len(input_text),
            usage=usage,
        )

    def _effective_messages(
        self, semantic_messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        tail = semantic_messages[self._compacted_through :]
        if self._checkpoint is None:
            return tail
        return [
            {
                "id": f"checkpoint-request-{uuid.uuid4().hex[:12]}",
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": (
                            "Use this automatic checkpoint as context for "
                            "the completed earlier tasks. The live notebook "
                            "is authoritative for current code and values."
                        ),
                    }
                ],
            },
            {
                "id": f"checkpoint-{uuid.uuid4().hex[:12]}",
                "role": "assistant",
                "parts": [{"type": "text", "text": self._checkpoint}],
            },
            *tail,
        ]

    def _checkpoint_input(self, new_history: list[dict[str, Any]]) -> str:
        previous = self._checkpoint or "No previous checkpoint."
        history = json.dumps(
            new_history, ensure_ascii=False, separators=(",", ":")
        )
        return (
            "Previous checkpoint:\n"
            f"{previous}\n\n"
            "Newly completed conversation turns:\n"
            f"{history}"
        )

    def _generate_checkpoint(self, input_text: str) -> tuple[str, TokenUsage]:
        api_key = os.environ.get("WANDB_API_KEY")
        if not api_key:
            raise RuntimeError("WANDB_API_KEY is not configured")
        messages = cast(
            list[ChatCompletionMessageParam],
            [
                {
                    "role": "system",
                    "content": (
                        "Create a compact checkpoint for an AI notebook "
                        "editor. Preserve user requirements, corrections, "
                        "decisions, completed work, stable notebook cell or "
                        "artifact identifiers, and unresolved work. Do not "
                        "copy notebook source or large tool output: the live "
                        "notebook and bounded revision history are available. "
                        "Distinguish completed tasks from active work. Return "
                        "only concise Markdown with factual bullet points."
                    ),
                },
                {"role": "user", "content": input_text},
            ],
        )
        response = OpenAI(
            api_key=api_key,
            base_url=_WANDB_BASE_URL,
            timeout=180,
        ).chat.completions.create(
            model=self._model,
            max_tokens=4096,
            messages=messages,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Checkpoint model returned no text")
        raw_usage = response.usage
        details = raw_usage.completion_tokens_details if raw_usage else None
        usage = TokenUsage(
            requests=1,
            input_tokens=raw_usage.prompt_tokens if raw_usage else 0,
            output_tokens=raw_usage.completion_tokens if raw_usage else 0,
            reasoning_tokens=(details.reasoning_tokens or 0 if details else 0),
        )
        return content.strip(), usage


class HarnessCheckpointCompactor:
    """Persist Harness-compacted model history across sidebar requests."""

    def __init__(
        self,
        *,
        model: str,
        threshold_chars: int = 60_000,
        minimum_completed_turns: int = 2,
    ) -> None:
        self._model = model.removeprefix("wandb/")
        self._threshold_chars = threshold_chars
        self._keep_tokens = max(2_000, threshold_chars // 8)
        self._minimum_new_messages = minimum_completed_turns * 2
        self._compacted_through = 0
        self._compacted_messages: list[dict[str, Any]] = []

    def prepare(self, messages: list[dict[str, Any]]) -> CheckpointPreparation:
        semantic_messages = compact_hybrid_history(messages)
        effective = [
            *self._compacted_messages,
            *semantic_messages[self._compacted_through :],
        ]
        if serialized_chars(effective) <= self._threshold_chars:
            return CheckpointPreparation(messages=effective)
        if (
            len(messages) - self._compacted_through
            < self._minimum_new_messages
        ):
            return CheckpointPreparation(messages=effective)

        input_chars = serialized_chars(effective)
        started = time.monotonic()
        compacted, usage = asyncio.run(self._compact(effective))
        if usage.requests == 0:
            return CheckpointPreparation(messages=effective)
        self._compacted_messages = compacted
        self._compacted_through = len(messages)
        return CheckpointPreparation(
            messages=compacted,
            generated=True,
            duration_seconds=time.monotonic() - started,
            input_chars=input_chars,
            usage=usage,
        )

    async def _compact(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], TokenUsage]:
        from pydantic import TypeAdapter
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
        from pydantic_ai.ui.vercel_ai import VercelAIAdapter
        from pydantic_ai.ui.vercel_ai.request_types import UIMessage
        from pydantic_ai.usage import RunUsage
        from pydantic_ai_harness.compaction import (
            SummarizingCompaction,
            compact_now,
        )

        api_key = os.environ.get("WANDB_API_KEY")
        if not api_key:
            raise RuntimeError("WANDB_API_KEY is not configured")
        model = OpenAIChatModel(
            model_name=self._model,
            provider=OpenAIProvider(
                api_key=api_key,
                base_url=_WANDB_BASE_URL,
            ),
        )
        strategy = SummarizingCompaction(
            model=model,
            max_tokens=1,
            keep_tokens=self._keep_tokens,
            model_settings={
                "max_tokens": 4096,
                "thinking": False,
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            },
        )
        ui_messages = TypeAdapter(list[UIMessage]).validate_python(messages)
        model_messages = VercelAIAdapter.load_messages(ui_messages)
        raw_usage = RunUsage()
        compacted = await compact_now(
            strategy,
            model_messages,
            model=model,
            usage=raw_usage,
        )
        dumped = VercelAIAdapter.dump_messages(compacted, sdk_version=6)
        serialized = [
            message.model_dump(mode="json", by_alias=True, exclude_none=True)
            for message in dumped
        ]
        return serialized, TokenUsage(
            requests=raw_usage.requests,
            input_tokens=raw_usage.input_tokens,
            output_tokens=raw_usage.output_tokens,
            reasoning_tokens=raw_usage.details.get("reasoning_tokens", 0),
            cache_read_tokens=raw_usage.cache_read_tokens,
            cache_write_tokens=raw_usage.cache_write_tokens,
        )
