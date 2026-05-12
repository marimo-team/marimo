# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _reset_otel() -> None:
    """Reset the global OTel tracer provider so each test starts clean."""
    from opentelemetry import trace

    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = None


@pytest.mark.requires("opentelemetry")
class TestSetTracerProvider:
    """Tests for _set_tracer_provider() exporter selection."""

    def setup_method(self) -> None:
        _reset_otel()

    def teardown_method(self) -> None:
        _reset_otel()

    def test_http_otlp_exporter_when_generic_endpoint_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        try:
            import opentelemetry.exporter.otlp.proto.http.trace_exporter  # noqa: F401
        except ImportError:
            pytest.skip("opentelemetry-exporter-otlp-proto-http not installed")

        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "http://localhost:4318",
        )
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_PROTOCOL", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", raising=False)
        monkeypatch.setenv("OTEL_SERVICE_NAME", "test-marimo")

        mock_exporter_cls = MagicMock()
        mock_exporter_cls.return_value = MagicMock()

        from marimo._config.settings import GLOBAL_SETTINGS

        monkeypatch.setattr(GLOBAL_SETTINGS, "TRACING", True)

        with patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            mock_exporter_cls,
        ):
            from marimo._tracer import _set_tracer_provider

            _set_tracer_provider()

        mock_exporter_cls.assert_called_once_with()

    def test_http_otlp_exporter_when_trace_endpoint_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        try:
            import opentelemetry.exporter.otlp.proto.http.trace_exporter  # noqa: F401
        except ImportError:
            pytest.skip("opentelemetry-exporter-otlp-proto-http not installed")

        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            "http://localhost:4318/v1/traces",
        )
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_PROTOCOL", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", raising=False)
        mock_exporter_cls = MagicMock()
        mock_exporter_cls.return_value = MagicMock()

        from marimo._config.settings import GLOBAL_SETTINGS

        monkeypatch.setattr(GLOBAL_SETTINGS, "TRACING", True)

        with patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            mock_exporter_cls,
        ):
            from marimo._tracer import _set_tracer_provider

            _set_tracer_provider()

        mock_exporter_cls.assert_called_once_with()

    def test_grpc_otlp_exporter_when_protocol_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        try:
            import opentelemetry.exporter.otlp.proto.grpc.trace_exporter  # noqa: F401
        except ImportError:
            pytest.skip("opentelemetry-exporter-otlp-proto-grpc not installed")

        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "http://localhost:4317",
        )
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
        mock_exporter_cls = MagicMock()
        mock_exporter_cls.return_value = MagicMock()

        from marimo._config.settings import GLOBAL_SETTINGS

        monkeypatch.setattr(GLOBAL_SETTINGS, "TRACING", True)

        with patch(
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter",
            mock_exporter_cls,
        ):
            from marimo._tracer import _set_tracer_provider

            _set_tracer_provider()

        mock_exporter_cls.assert_called_once_with()

    def test_file_exporter_when_no_endpoint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_PROTOCOL", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", raising=False)

        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        from marimo._config.settings import GLOBAL_SETTINGS

        monkeypatch.setattr(GLOBAL_SETTINGS, "TRACING", True)

        from marimo._tracer import _set_tracer_provider

        _set_tracer_provider()

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)

        processors = provider._active_span_processor._span_processors  # type: ignore[attr-defined]
        assert len(processors) > 0
        processor = processors[0]
        assert isinstance(processor, BatchSpanProcessor)
        assert type(processor.span_exporter).__name__ == "FileExporter"

    def test_otlp_fallback_to_file_when_selected_exporter_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "http://localhost:4318",
        )

        from marimo._config.settings import GLOBAL_SETTINGS

        monkeypatch.setattr(GLOBAL_SETTINGS, "TRACING", True)

        # Import these BEFORE entering patch.dict("sys.modules", ...).
        # On exit, patch.dict clears sys.modules and restores the snapshot
        # taken at entry, which wipes any modules first loaded inside the
        # block. If opentelemetry.sdk.trace is only imported inside, the
        # post-block re-import creates a new TracerProvider class and
        # isinstance() against the provider built inside the block fails.
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        with patch.dict(
            "sys.modules",
            {"opentelemetry.exporter.otlp.proto.http.trace_exporter": None},
        ):
            from marimo._tracer import _set_tracer_provider

            _set_tracer_provider()

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)
        processors = provider._active_span_processor._span_processors  # type: ignore[attr-defined]
        assert len(processors) > 0
        processor = processors[0]
        assert isinstance(processor, BatchSpanProcessor)
        assert type(processor.span_exporter).__name__ == "FileExporter"

    def test_otlp_fallback_to_file_when_protocol_unsupported(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "http://localhost:4318",
        )
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/json")

        from marimo._config.settings import GLOBAL_SETTINGS

        monkeypatch.setattr(GLOBAL_SETTINGS, "TRACING", True)

        from marimo._tracer import _set_tracer_provider

        _set_tracer_provider()

        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)
        processors = provider._active_span_processor._span_processors  # type: ignore[attr-defined]
        assert len(processors) > 0
        processor = processors[0]
        assert isinstance(processor, BatchSpanProcessor)
        assert type(processor.span_exporter).__name__ == "FileExporter"

    def test_noop_when_tracing_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from opentelemetry import trace

        from marimo._config.settings import GLOBAL_SETTINGS

        monkeypatch.setattr(GLOBAL_SETTINGS, "TRACING", False)

        from marimo._tracer import _set_tracer_provider

        _set_tracer_provider()

        # Provider should still be the default proxy (nothing was set)
        provider = trace.get_tracer_provider()
        assert not hasattr(provider, "_active_span_processor")


@pytest.mark.requires("opentelemetry")
class TestCreateTracer:
    def test_returns_mock_when_tracing_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from marimo._config.settings import GLOBAL_SETTINGS
        from marimo._tracer import MockTracer, create_tracer

        monkeypatch.setattr(GLOBAL_SETTINGS, "TRACING", False)
        tracer = create_tracer("test")
        assert isinstance(tracer, MockTracer)

    def test_returns_real_tracer_when_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from marimo._config.settings import GLOBAL_SETTINGS
        from marimo._tracer import MockTracer, create_tracer

        monkeypatch.setattr(GLOBAL_SETTINGS, "TRACING", True)
        tracer = create_tracer("test.real")
        assert not isinstance(tracer, MockTracer)
