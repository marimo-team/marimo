# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest

from marimo._server.ai.tracing import (
    SpanInfo,
    build_attributes,
    trace_completion,
    trace_stream,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from opentelemetry.sdk.trace import ReadableSpan
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
    from opentelemetry.trace import Tracer


class _CollectingExporter:
    """Minimal span exporter that collects spans in a list."""

    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        from opentelemetry.sdk.trace.export import SpanExportResult

        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def force_flush(self, _timeout_millis: int = 0) -> bool:
        return True


def _setup_tracing() -> tuple[Tracer, _CollectingExporter]:
    """Build an isolated tracer backed by a collecting exporter."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    exporter = _CollectingExporter()
    provider = TracerProvider()
    # `cast` through `object` since the duck-typed exporter can't subclass the
    # `SpanExporter` ABC (opentelemetry is an optional dependency).
    provider.add_span_processor(
        SimpleSpanProcessor(cast("SpanExporter", cast(object, exporter)))
    )
    # Use the provider directly rather than the global tracer provider so each
    # test is isolated and we don't mutate global OTel state.
    return provider.get_tracer("marimo.server"), exporter


def _attributes(span: ReadableSpan) -> dict[str, object]:
    return dict(span.attributes or {})


async def _gen(*items: str) -> AsyncIterator[str]:
    for item in items:
        yield item


async def _failing_gen(*items: str) -> AsyncIterator[str]:
    for item in items:
        yield item
    raise RuntimeError("boom")


class TestBuildAttributes:
    def test_qualified_model_with_mode(self) -> None:
        attrs = build_attributes(
            SpanInfo(endpoint="chat", model="openai/gpt-4o", mode="manual")
        )
        assert attrs == {
            "marimo.ai.endpoint": "chat",
            "marimo.ai.provider": "openai",
            "marimo.ai.model": "gpt-4o",
            "marimo.ai.mode": "manual",
        }

    def test_without_mode_omits_mode_key(self) -> None:
        attrs = build_attributes(
            SpanInfo(endpoint="inline_completion", model="anthropic/claude-3")
        )
        assert attrs == {
            "marimo.ai.endpoint": "inline_completion",
            "marimo.ai.provider": "anthropic",
            "marimo.ai.model": "claude-3",
        }

    def test_includes_optional_fields_when_set(self) -> None:
        attrs = build_attributes(
            SpanInfo(
                endpoint="inline_completion",
                model="openai/gpt-4o",
                language="python",
                session_id="session-123",
                tool_count=3,
            )
        )
        assert attrs == {
            "marimo.ai.endpoint": "inline_completion",
            "marimo.ai.provider": "openai",
            "marimo.ai.model": "gpt-4o",
            "marimo.ai.language": "python",
            "marimo.ai.session_id": "session-123",
            "marimo.ai.tool_count": 3,
        }

    def test_tool_count_zero_is_recorded(self) -> None:
        attrs = build_attributes(
            SpanInfo(endpoint="chat", model="openai/gpt-4o", tool_count=0)
        )
        assert attrs["marimo.ai.tool_count"] == 0


@pytest.mark.requires("opentelemetry")
class TestTraceStream:
    async def test_passthrough_when_tracing_disabled(self) -> None:
        tracer, exporter = _setup_tracing()
        span_info = SpanInfo(endpoint="chat", model="openai/gpt-4o")

        with (
            patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", False),
            patch("marimo._server.ai.tracing.server_tracer", tracer),
        ):
            events = [e async for e in trace_stream(_gen("a", "b"), span_info)]

        assert events == ["a", "b"]
        assert exporter.spans == []

    async def test_passthrough_when_span_info_none(self) -> None:
        tracer, exporter = _setup_tracing()

        with (
            patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", True),
            patch("marimo._server.ai.tracing.server_tracer", tracer),
        ):
            events = [e async for e in trace_stream(_gen("a", "b"), None)]

        assert events == ["a", "b"]
        assert exporter.spans == []

    async def test_creates_span_with_attributes(self) -> None:
        tracer, exporter = _setup_tracing()
        span_info = SpanInfo(
            endpoint="chat", model="openai/gpt-4o", mode="manual"
        )

        with (
            patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", True),
            patch("marimo._server.ai.tracing.server_tracer", tracer),
        ):
            events = [e async for e in trace_stream(_gen("a", "b"), span_info)]

        assert events == ["a", "b"]
        assert len(exporter.spans) == 1
        span = exporter.spans[0]
        assert span.name == "marimo.ai.stream"
        assert _attributes(span) == {
            "marimo.ai.endpoint": "chat",
            "marimo.ai.provider": "openai",
            "marimo.ai.model": "gpt-4o",
            "marimo.ai.mode": "manual",
        }

    async def test_records_error_and_reraises(self) -> None:
        from opentelemetry.trace import StatusCode

        tracer, exporter = _setup_tracing()
        span_info = SpanInfo(endpoint="chat", model="openai/gpt-4o")

        with (
            patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", True),
            patch("marimo._server.ai.tracing.server_tracer", tracer),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                async for _ in trace_stream(_failing_gen("a"), span_info):
                    pass

        assert len(exporter.spans) == 1
        span = exporter.spans[0]
        assert span.status.status_code == StatusCode.ERROR
        assert any(e.name == "exception" for e in span.events)


@pytest.mark.requires("opentelemetry")
class TestTraceCompletion:
    def test_noop_when_tracing_disabled(self) -> None:
        tracer, exporter = _setup_tracing()
        span_info = SpanInfo(
            endpoint="inline_completion", model="openai/gpt-4o"
        )

        with (
            patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", False),
            patch("marimo._server.ai.tracing.server_tracer", tracer),
        ):
            with trace_completion(span_info):
                pass

        assert exporter.spans == []

    def test_creates_span_with_attributes(self) -> None:
        tracer, exporter = _setup_tracing()
        span_info = SpanInfo(
            endpoint="inline_completion", model="openai/gpt-4o"
        )

        with (
            patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", True),
            patch("marimo._server.ai.tracing.server_tracer", tracer),
        ):
            with trace_completion(span_info):
                pass

        assert len(exporter.spans) == 1
        span = exporter.spans[0]
        assert span.name == "marimo.ai.completion"
        assert _attributes(span) == {
            "marimo.ai.endpoint": "inline_completion",
            "marimo.ai.provider": "openai",
            "marimo.ai.model": "gpt-4o",
        }

    def test_records_error_and_reraises(self) -> None:
        from opentelemetry.trace import StatusCode

        tracer, exporter = _setup_tracing()
        span_info = SpanInfo(
            endpoint="inline_completion", model="openai/gpt-4o"
        )

        with (
            patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", True),
            patch("marimo._server.ai.tracing.server_tracer", tracer),
        ):
            with pytest.raises(RuntimeError, match="kaboom"):
                with trace_completion(span_info):
                    raise RuntimeError("kaboom")

        assert len(exporter.spans) == 1
        span = exporter.spans[0]
        assert span.status.status_code == StatusCode.ERROR
        assert any(e.name == "exception" for e in span.events)
