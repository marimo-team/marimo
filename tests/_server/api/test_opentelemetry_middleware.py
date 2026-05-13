# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import Request


def _reset_otel() -> None:
    """Reset the global OTel tracer provider so each test starts clean."""
    from opentelemetry import trace

    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = None


class _CollectingExporter:
    """Minimal span exporter that collects spans in a list."""

    def __init__(self) -> None:
        self.spans: list[Any] = []

    def export(self, spans: Sequence[Any]) -> Any:
        from opentelemetry.sdk.trace.export import SpanExportResult

        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 0) -> bool:  # noqa: ARG002
        return True


def _setup_tracing() -> tuple[Any, _CollectingExporter]:
    """Set up OTel with a collecting exporter, return (tracer, exporter)."""
    _reset_otel()

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    exporter = _CollectingExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    tracer = trace.get_tracer("marimo.server")
    return tracer, exporter


def _make_app(tracing: bool = True) -> Starlette:
    """Build a minimal Starlette app with OpenTelemetryMiddleware."""
    from marimo._server.api.middleware import OpenTelemetryMiddleware

    async def homepage(request: Request) -> PlainTextResponse:  # noqa: ARG001
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", homepage)])

    with patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", tracing):
        app.add_middleware(OpenTelemetryMiddleware)

    return app


@pytest.mark.requires("opentelemetry")
class TestOpenTelemetryMiddleware:
    def setup_method(self) -> None:
        _reset_otel()

    def teardown_method(self) -> None:
        _reset_otel()

    def test_extracts_traceparent_creates_child_span(self) -> None:
        from opentelemetry import trace
        from opentelemetry.trace import TraceFlags

        tracer, exporter = _setup_tracing()

        parent_trace_id = "0af7651916cd43dd8448eb211c80319c"
        parent_span_id = "b7ad6b7169203331"
        traceparent = f"00-{parent_trace_id}-{parent_span_id}-01"

        with (
            patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", True),
            patch("marimo._server.api.middleware.server_tracer", tracer),
        ):
            app = _make_app(tracing=True)
            client = TestClient(app)
            response = client.get("/", headers={"traceparent": traceparent})

        assert response.status_code == 200
        assert len(exporter.spans) == 1

        span = exporter.spans[0]
        assert span.name == "GET /"
        assert span.kind == trace.SpanKind.SERVER

        span_context = span.parent
        assert span_context is not None
        assert format(span_context.trace_id, "032x") == parent_trace_id
        assert format(span_context.span_id, "016x") == parent_span_id
        assert span_context.trace_flags == TraceFlags(1)

    def test_root_span_when_no_traceparent(self) -> None:
        tracer, exporter = _setup_tracing()

        with (
            patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", True),
            patch("marimo._server.api.middleware.server_tracer", tracer),
        ):
            app = _make_app(tracing=True)
            client = TestClient(app)
            response = client.get("/")

        assert response.status_code == 200
        assert len(exporter.spans) == 1
        assert exporter.spans[0].parent is None

    def test_noop_when_tracing_disabled(self) -> None:
        tracer, exporter = _setup_tracing()

        with (
            patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", False),
            patch("marimo._server.api.middleware.server_tracer", tracer),
        ):
            app = _make_app(tracing=False)
            client = TestClient(app)
            response = client.get("/")

        assert response.status_code == 200
        assert len(exporter.spans) == 0

    def test_span_records_status_code(self) -> None:
        tracer, exporter = _setup_tracing()

        with (
            patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", True),
            patch("marimo._server.api.middleware.server_tracer", tracer),
        ):
            app = _make_app(tracing=True)
            client = TestClient(app)
            client.get("/")

        assert len(exporter.spans) == 1
        attrs = dict(exporter.spans[0].attributes or {})
        assert attrs["http.status_code"] == 200
        assert attrs["http.method"] == "GET"
        assert attrs["http.target"] == "/"


@pytest.mark.requires("opentelemetry")
class TestTracePropagationThroughRealApp:
    """Integration tests using create_starlette_app + setup_mcp_server.

    These verify that OpenTelemetryMiddleware actually intercepts
    requests to MCP endpoints in the real application middleware stack,
    not a hand-built analogue that could drift from production.
    """

    def setup_method(self) -> None:
        _reset_otel()

    def teardown_method(self) -> None:
        _reset_otel()

    def _create_real_app(self) -> Starlette:
        """Build the real Starlette app and mount MCP, just like start.py."""
        from marimo._server.main import create_starlette_app
        from tests._server.mocks import get_mock_session_manager

        app = create_starlette_app(
            base_url="",
            enable_auth=False,
            skew_protection=False,
        )

        session_manager = get_mock_session_manager()
        app.state.session_manager = session_manager

        if "mcp" in sys.modules or _has_mcp():
            from marimo._mcp.setup import setup_mcp_server

            setup_mcp_server(app, "tools")

        return app

    def test_mcp_request_produces_span_with_traceparent(self) -> None:
        if not _has_mcp():
            pytest.skip("mcp package not installed")

        from opentelemetry.trace import TraceFlags

        tracer, exporter = _setup_tracing()

        parent_trace_id = "0af7651916cd43dd8448eb211c80319c"
        parent_span_id = "b7ad6b7169203331"
        traceparent = f"00-{parent_trace_id}-{parent_span_id}-01"

        with (
            patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", True),
            patch("marimo._server.api.middleware.server_tracer", tracer),
        ):
            app = self._create_real_app()
            client = TestClient(app, raise_server_exceptions=False)
            client.get(
                "/mcp/server",
                headers={"traceparent": traceparent},
            )

        mcp_spans = [s for s in exporter.spans if "/mcp" in (s.name or "")]
        assert len(mcp_spans) >= 1, (
            f"Expected a span for /mcp/server, got: {[s.name for s in exporter.spans]}"
        )

        span = mcp_spans[0]
        assert span.parent is not None, "Span should be a child, not a root"
        assert format(span.parent.trace_id, "032x") == parent_trace_id
        assert format(span.parent.span_id, "016x") == parent_span_id
        assert span.parent.trace_flags == TraceFlags(1)

    def test_mcp_request_root_span_without_traceparent(self) -> None:
        if not _has_mcp():
            pytest.skip("mcp package not installed")

        tracer, exporter = _setup_tracing()

        with (
            patch("marimo._config.settings.GLOBAL_SETTINGS.TRACING", True),
            patch("marimo._server.api.middleware.server_tracer", tracer),
        ):
            app = self._create_real_app()
            client = TestClient(app, raise_server_exceptions=False)
            client.get("/mcp/server")

        mcp_spans = [s for s in exporter.spans if "/mcp" in (s.name or "")]
        assert len(mcp_spans) >= 1, (
            f"Expected a span for /mcp/server, got: {[s.name for s in exporter.spans]}"
        )
        assert mcp_spans[0].parent is None


def _has_mcp() -> bool:
    try:
        import mcp  # noqa: F401

        return True
    except ImportError:
        return False
