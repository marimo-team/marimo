# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from marimo._config.config import CopilotMode
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._server.ai.ids import AiModelId
from marimo._tracer import server_tracer

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Generator

    from opentelemetry.trace import Span
    from opentelemetry.util.types import AttributeValue
    from pydantic_ai.ui.vercel_ai.response_types import BaseChunk


@dataclass
class SpanInfo:
    endpoint: Literal["completion", "chat", "inline_completion", "invoke_tool"]
    model: str  # qualified "<provider>/<model>"
    mode: CopilotMode | None = None
    language: str | None = None
    session_id: str | None = None
    tool_count: int | None = None


def build_attributes(span_info: SpanInfo) -> dict[str, AttributeValue]:
    model_id = AiModelId.from_model(span_info.model)
    attributes: dict[str, AttributeValue] = {
        "marimo.ai.endpoint": span_info.endpoint,
        "marimo.ai.provider": model_id.provider,
        "marimo.ai.model": model_id.model,
    }
    if span_info.mode:
        attributes["marimo.ai.mode"] = span_info.mode
    if span_info.language:
        attributes["marimo.ai.language"] = span_info.language
    if span_info.session_id:
        attributes["marimo.ai.session_id"] = span_info.session_id
    if span_info.tool_count is not None:
        attributes["marimo.ai.tool_count"] = span_info.tool_count
    return attributes


def _record_error(span: Span, e: Exception) -> None:
    from opentelemetry.trace.status import Status, StatusCode

    span.set_status(Status(StatusCode.ERROR, str(e)))
    span.record_exception(e)


async def trace_stream(
    stream: AsyncIterator[BaseChunk], span_info: SpanInfo | None
) -> AsyncIterator[BaseChunk]:
    """Wrap a streaming response in a `marimo.ai.stream` span.

    The span stays open for the lifetime of the stream so that pydantic-ai's
    `gen_ai.*` spans nest underneath it and the span duration reflects the full
    streaming latency.
    """
    if not GLOBAL_SETTINGS.TRACING or span_info is None:
        async for event in stream:
            yield event
        return

    with server_tracer.start_as_current_span(
        "marimo.ai.stream", attributes=build_attributes(span_info)
    ) as span:
        try:
            async for event in stream:
                yield event
        except Exception as e:
            _record_error(span, e)
            raise


@contextmanager
def trace_completion(
    span_info: SpanInfo | None,
) -> Generator[None, None, None]:
    """Wrap a non-streaming completion in a `marimo.ai.completion` span."""
    if not GLOBAL_SETTINGS.TRACING or span_info is None:
        yield
        return

    with server_tracer.start_as_current_span(
        "marimo.ai.completion", attributes=build_attributes(span_info)
    ) as span:
        try:
            yield
        except Exception as e:
            _record_error(span, e)
            raise
