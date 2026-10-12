# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
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

    from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
    from opentelemetry.trace import Span, Tracer
    from starlette.requests import Request
    from starlette.responses import StreamingResponse
    from starlette.types import Message, Scope

    from marimo._config.config import CopilotMode


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


def _setup_tracing(
    provider: TracerProvider | None = None,
) -> tuple[Tracer, _CollectingExporter]:
    """Build an isolated tracer backed by a collecting exporter."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    exporter = _CollectingExporter()
    if provider is None:
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
    def test_table_filter_has_no_tools(self) -> None:
        assert build_attributes(
            SpanInfo(
                endpoint="table_filter", model="openai/test", tool_count=0
            )
        ) == {
            "marimo.ai.endpoint": "table_filter",
            "marimo.ai.provider": "openai",
            "marimo.ai.model": "test",
            "marimo.ai.tool_count": 0,
        }

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


@pytest.mark.requires("opentelemetry", "pydantic_ai")
@pytest.mark.parametrize("is_valid", [True, False])
async def test_table_filter_completion_records_result_or_error(
    is_valid: bool,
) -> None:
    from opentelemetry.trace import StatusCode
    from pydantic_ai.models.test import TestModel
    from pydantic_ai.profiles import ModelProfile

    from marimo._plugins.ui._impl.tables.filter_context import FilterContext
    from marimo._server.ai.config import AnyProviderConfig
    from marimo._server.ai.providers import OpenAIProvider
    from marimo._server.ai.table_filter import build_table_filter_prompt
    from marimo._server.ai.table_filter_output import TableFilterOutputError

    tracer, exporter = _setup_tracing()
    provider = OpenAIProvider(
        "test", AnyProviderConfig(api_key="test-key", base_url=None)
    )
    model = TestModel(
        custom_output_text=(
            '{"fql":"column_0=4","explanation":null}'
            if is_valid
            else '{"fql":null,"explanation":null}'
        ),
        profile=ModelProfile(supports_json_schema_output=True),
    )
    prompt = build_table_filter_prompt(
        FilterContext(row_count=None, columns=[], omissions=[]), "Keep four"
    )
    with (
        patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", True),
        patch("marimo._server.ai.tracing.server_tracer", tracer),
        patch.object(provider, "create_model", return_value=model),
    ):
        if is_valid:
            output = await provider.table_filter_completion(
                prompt,
                None,
                SpanInfo(endpoint="table_filter", model="openai/test"),
            )
            assert output.model_dump() == {
                "fql": "column_0=4",
                "explanation": None,
            }
        else:
            with pytest.raises(TableFilterOutputError):
                await provider.table_filter_completion(
                    prompt,
                    None,
                    SpanInfo(endpoint="table_filter", model="openai/test"),
                )

    assert [
        {
            "name": span.name,
            "attributes": _attributes(span),
            "status": span.status.status_code,
            "has_exception": any(
                event.name == "exception" for event in span.events
            ),
        }
        for span in exporter.spans
    ] == [
        {
            "name": "marimo.ai.completion",
            "attributes": {
                "marimo.ai.endpoint": "table_filter",
                "marimo.ai.provider": "openai",
                "marimo.ai.model": "test",
                "marimo.ai.tool_count": 0,
            },
            "status": StatusCode.UNSET if is_valid else StatusCode.ERROR,
            "has_exception": not is_valid,
        }
    ]


@pytest.mark.requires("opentelemetry", "pydantic_ai")
@pytest.mark.parametrize("mode", ["manual", "code_mode"])
@pytest.mark.parametrize("spec_version", ["2.3", "2.4"])
async def test_ai_stream_keeps_exportable_parent_tree(
    mode: CopilotMode, spec_version: str
) -> None:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from pydantic_ai import Agent, DeferredToolRequests
    from pydantic_ai.models.instrumented import InstrumentationSettings
    from pydantic_ai.models.test import TestModel
    from starlette.applications import Starlette
    from starlette.routing import Route

    from marimo._server.ai.config import AnyProviderConfig
    from marimo._server.ai.providers import OpenAIProvider, StreamOptions
    from marimo._server.api.middleware import OpenTelemetryMiddleware

    tracer_provider = TracerProvider()
    tracer, exporter = _setup_tracing(tracer_provider)
    response_started = asyncio.Event()
    tool_calls: list[str] = []

    async def lookup() -> str:
        assert request_span.is_recording()
        assert trace.get_current_span().is_recording()
        tool_calls.append("lookup")
        return "found"

    agent = Agent(
        TestModel(custom_output_text="done"),
        name="chat",
        tools=[lookup],
        output_type=[str, DeferredToolRequests],
    )
    agent.instrument = InstrumentationSettings(
        tracer_provider=tracer_provider, version=5
    )
    provider = OpenAIProvider(
        "test", AnyProviderConfig(api_key="test-key", base_url=None)
    )
    request_span: Span = trace.INVALID_SPAN
    messages: list[Message] = []

    async def endpoint(request: Request) -> StreamingResponse:
        del request
        nonlocal request_span
        request_span = trace.get_current_span()
        # Chat and code mode both use this production streaming path.
        response = provider._vercel_streaming_response(
            agent,
            [
                {
                    "id": "user-message",
                    "role": "user",
                    "parts": [{"type": "text", "text": "look it up"}],
                }
            ],
            StreamOptions(
                span_info=SpanInfo(
                    endpoint="chat", model="openai/test", mode=mode
                )
            ),
        )
        stream = response.body_iterator

        async def body() -> AsyncIterator[str | bytes | memoryview]:
            # BaseHTTPMiddleware ends the request span before forwarding
            # response headers. Waiting here makes that failure deterministic.
            await asyncio.wait_for(response_started.wait(), timeout=5)
            assert request_span.is_recording()
            assert trace.get_current_span() is request_span
            async for chunk in stream:
                yield chunk
            assert request_span.is_recording()

        response.body_iterator = body()
        return response

    async def receive() -> Message:
        # ASGI 2.3 listens for disconnects until streaming cancels the listener.
        await asyncio.wait_for(asyncio.Event().wait(), timeout=5)
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        messages.append(message)
        if message["type"] == "http.response.start":
            response_started.set()
        if message["type"] == "http.response.body":
            assert request_span.is_recording()

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": spec_version},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/ai/chat",
        "root_path": "",
        "query_string": b"",
        "headers": [],
    }
    app = Starlette(routes=[Route("/api/ai/chat", endpoint, methods=["POST"])])
    app.add_middleware(OpenTelemetryMiddleware)
    with (
        patch(
            "marimo._server.api.middleware.is_tracing_enabled",
            return_value=True,
        ),
        patch("marimo._server.api.middleware.server_tracer", tracer),
        patch("marimo._server.ai.tracing.server_tracer", tracer),
        patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", True),
    ):
        await app(scope, receive, send)

    assert tool_calls == ["lookup"]
    assert messages[-1] == {
        "type": "http.response.body",
        "body": b"",
        "more_body": False,
    }
    assert not request_span.is_recording()
    assert trace.get_current_span() is trace.INVALID_SPAN
    spans = exporter.spans
    roots = [span for span in spans if span.parent is None]
    assert [span.name for span in roots] == ["POST /api/ai/chat"]
    root_context = roots[0].context
    assert root_context is not None
    assert spans[-1] is roots[0]
    assert root_context == request_span.get_span_context()
    stream_span = next(
        span for span in spans if span.name == "marimo.ai.stream"
    )
    assert stream_span.parent == roots[0].context
    assert _attributes(stream_span)["marimo.ai.mode"] == mode
    operations = [
        (span.attributes or {}).get("gen_ai.operation.name") for span in spans
    ]
    assert "chat" in operations
    assert "execute_tool" in operations
    by_id = {}
    for span in spans:
        assert span.context is not None
        by_id[span.context.span_id] = span
    for child in spans:
        if child.parent is None:
            continue
        # Every exported child must have an exported parent with a lifetime
        # enclosing its own, including Pydantic AI's agent/model/tool spans.
        parent = by_id[child.parent.span_id]
        assert child.context is not None
        assert child.context.trace_id == root_context.trace_id
        assert parent.start_time is not None
        assert child.start_time is not None
        assert child.end_time is not None
        assert parent.end_time is not None
        assert (
            parent.start_time
            <= child.start_time
            <= child.end_time
            <= parent.end_time
        )
