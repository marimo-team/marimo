from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from benchmarks.ai.models import TokenUsage, ToolCallMetrics


def serialized_chars(value: Any) -> int:
    """Return the compact JSON size used as a stable payload proxy."""
    return len(json.dumps(value, separators=(",", ":"), default=str))


def parse_sse(body: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for line in body.splitlines():
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            continue
        value = json.loads(data)
        if isinstance(value, dict):
            chunks.append(value)
    return chunks


def _value(chunk: dict[str, Any], camel: str, snake: str) -> Any:
    return chunk.get(camel, chunk.get(snake))


@dataclass
class AssistantMessageBuilder:
    """Reconstruct an AI SDK UI message from Vercel stream chunks."""

    message_id: str = "assistant"
    parts: list[dict[str, Any]] = field(default_factory=list)
    _streaming_parts: dict[str, dict[str, Any]] = field(default_factory=dict)
    _tools: dict[str, dict[str, Any]] = field(default_factory=dict)
    _has_complete_usage: bool = False
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str | None = None

    def add(self, chunk: dict[str, Any]) -> None:
        chunk_type = chunk.get("type")
        if chunk_type == "start":
            self.message_id = str(
                _value(chunk, "messageId", "message_id") or self.message_id
            )
        elif chunk_type == "start-step":
            self.parts.append({"type": "step-start"})
        elif chunk_type in ("text-start", "reasoning-start"):
            stream_id = str(chunk["id"])
            part_type = "text" if chunk_type == "text-start" else "reasoning"
            streaming_part: dict[str, Any] = {"type": part_type, "text": ""}
            self.parts.append(streaming_part)
            self._streaming_parts[stream_id] = streaming_part
        elif chunk_type in ("text-delta", "reasoning-delta"):
            stream_id = str(chunk["id"])
            existing_streaming_part = self._streaming_parts.get(stream_id)
            if existing_streaming_part is not None:
                existing_streaming_part["text"] += str(chunk.get("delta", ""))
        elif chunk_type == "tool-input-available":
            tool_call_id = str(_value(chunk, "toolCallId", "tool_call_id"))
            tool_name = str(_value(chunk, "toolName", "tool_name"))
            tool_part: dict[str, Any] = {
                "type": f"tool-{tool_name}",
                "toolCallId": tool_call_id,
                "state": "input-available",
                "input": chunk.get("input", {}),
            }
            self.parts.append(tool_part)
            self._tools[tool_call_id] = tool_part
        elif chunk_type == "tool-output-available":
            tool_call_id = str(_value(chunk, "toolCallId", "tool_call_id"))
            output_tool_part = self._tools.get(tool_call_id)
            if output_tool_part is not None:
                output_tool_part["state"] = "output-available"
                output_tool_part["output"] = chunk.get("output")
        elif chunk_type == "tool-output-error":
            tool_call_id = str(_value(chunk, "toolCallId", "tool_call_id"))
            error_tool_part = self._tools.get(tool_call_id)
            if error_tool_part is not None:
                error_tool_part["state"] = "output-error"
                error_tool_part["errorText"] = (
                    _value(chunk, "errorText", "error_text")
                    or "Tool call failed"
                )
        elif chunk_type == "error":
            message = _value(chunk, "errorText", "error_text") or chunk.get(
                "error"
            )
            raise RuntimeError(str(message or "AI stream failed"))
        elif chunk_type == "data-marimo-usage":
            usage = chunk.get("data")
            if isinstance(usage, dict):
                self.usage = _token_usage(usage)
                self._has_complete_usage = True
        elif chunk_type == "finish":
            self.finish_reason = str(
                _value(chunk, "finishReason", "finish_reason") or ""
            )
            usage = chunk.get("usage")
            if isinstance(usage, dict) and not self._has_complete_usage:
                self.usage = _token_usage(usage)

    def build(self) -> dict[str, Any]:
        return {
            "id": self.message_id,
            "role": "assistant",
            "parts": self.parts,
        }

    def text(self) -> str:
        return "\n".join(
            str(part["text"])
            for part in self.parts
            if part.get("type") == "text" and part.get("text")
        )

    @property
    def tool_calls(self) -> int:
        return len(self._tools)

    @property
    def tool_errors(self) -> int:
        return sum(
            part.get("state") == "output-error"
            or (
                isinstance(part.get("output"), dict)
                and (
                    part["output"].get("success") is False
                    or part["output"].get("is_error") is True
                )
            )
            for part in self._tools.values()
        )

    @property
    def tool_metrics(self) -> tuple[ToolCallMetrics, ...]:
        metrics: list[ToolCallMetrics] = []
        for part in self._tools.values():
            state = part.get("state")
            output = part.get("output")
            errored = state == "output-error" or (
                isinstance(output, dict)
                and (
                    output.get("success") is False
                    or output.get("is_error") is True
                )
            )
            output_value = (
                part.get("errorText") if state == "output-error" else output
            )
            metrics.append(
                ToolCallMetrics(
                    name=str(part.get("type", "tool-unknown")).removeprefix(
                        "tool-"
                    ),
                    input_chars=serialized_chars(part.get("input")),
                    output_chars=serialized_chars(output_value),
                    errored=errored,
                )
            )
        return tuple(metrics)


@dataclass
class StructuredCompletionBuilder:
    """Collect the last validated structured output from an AI SDK stream."""

    data_type: str
    data: dict[str, Any] | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str | None = None

    def add(self, chunk: dict[str, Any]) -> None:
        chunk_type = chunk.get("type")
        if chunk_type == self.data_type:
            data = chunk.get("data")
            if isinstance(data, dict):
                self.data = data
        elif chunk_type == "data-marimo-usage":
            usage = chunk.get("data")
            if isinstance(usage, dict):
                self.usage = _token_usage(usage)
        elif chunk_type == "error":
            message = _value(chunk, "errorText", "error_text") or chunk.get(
                "error"
            )
            raise RuntimeError(str(message or "AI stream failed"))
        elif chunk_type == "finish":
            self.finish_reason = str(
                _value(chunk, "finishReason", "finish_reason") or ""
            )

    def result(self) -> dict[str, Any]:
        if self.finish_reason != "stop":
            raise RuntimeError(
                "AI completion ended before final validation: "
                f"{self.finish_reason or 'missing finish event'}"
            )
        if self.data is None:
            raise RuntimeError("AI completion returned no structured output")
        return self.data


def _token_count(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, int):
            return value
    return 0


def _token_usage(usage: dict[str, Any]) -> TokenUsage:
    details = usage.get("details")
    if not isinstance(details, dict):
        details = {}
    return TokenUsage(
        requests=_token_count(usage, "requests", "requestCount"),
        input_tokens=_token_count(
            usage, "inputTokens", "promptTokens", "input_tokens"
        ),
        output_tokens=_token_count(
            usage, "outputTokens", "completionTokens", "output_tokens"
        ),
        reasoning_tokens=_token_count(
            usage, "reasoningTokens", "reasoning_tokens"
        )
        or _token_count(details, "reasoning_tokens", "reasoningTokens"),
        cache_read_tokens=_token_count(
            usage, "cacheReadTokens", "cache_read_tokens"
        ),
        cache_write_tokens=_token_count(
            usage, "cacheWriteTokens", "cache_write_tokens"
        ),
    )
