# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
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

    def test_instruments_ai_with_built_provider(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Guards against dropping the _instrument_ai() call in
        # _set_tracer_provider().
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)

        from opentelemetry import trace

        # Import while tracing is disabled to avoid import-time instrumentation.
        import marimo._tracer as tracer_module
        from marimo._config.settings import GLOBAL_SETTINGS

        monkeypatch.setattr(GLOBAL_SETTINGS, "TRACING", True)

        with patch.object(tracer_module, "_instrument_ai") as mock_instrument:
            tracer_module._set_tracer_provider()

        mock_instrument.assert_called_once_with(trace.get_tracer_provider())


@pytest.mark.requires("opentelemetry")
class TestTracerResource:
    def setup_method(self) -> None:
        _reset_otel()

    def teardown_method(self) -> None:
        _reset_otel()

    def test_default_service_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
        monkeypatch.delenv("OTEL_RESOURCE_ATTRIBUTES", raising=False)

        from marimo._tracer import _tracer_resource

        resource = _tracer_resource()
        assert resource.attributes["service.name"] == "marimo"

    def test_service_name_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OTEL_SERVICE_NAME", "my-marimo")
        monkeypatch.delenv("OTEL_RESOURCE_ATTRIBUTES", raising=False)

        from marimo._tracer import _tracer_resource

        resource = _tracer_resource()
        assert resource.attributes["service.name"] == "my-marimo"

    def test_resource_attributes_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
        monkeypatch.setenv(
            "OTEL_RESOURCE_ATTRIBUTES",
            "deployment.environment=dev,service.version=1.2.3",
        )

        from marimo._tracer import _tracer_resource

        resource = _tracer_resource()
        assert resource.attributes["service.name"] == "marimo"
        assert resource.attributes["deployment.environment"] == "dev"
        assert resource.attributes["service.version"] == "1.2.3"

    def test_service_name_overrides_resource_attributes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OTEL_SERVICE_NAME", "from-env")
        monkeypatch.setenv(
            "OTEL_RESOURCE_ATTRIBUTES",
            "service.name=from-attrs",
        )

        from marimo._tracer import _tracer_resource

        resource = _tracer_resource()
        assert resource.attributes["service.name"] == "from-env"

    def test_file_exporter_applies_resource(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
        monkeypatch.setenv("OTEL_SERVICE_NAME", "file-export-marimo")
        monkeypatch.setenv(
            "OTEL_RESOURCE_ATTRIBUTES",
            "deployment.environment=test",
        )

        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        from marimo._config.settings import GLOBAL_SETTINGS
        from marimo._tracer import _set_tracer_provider

        monkeypatch.setattr(GLOBAL_SETTINGS, "TRACING", True)
        _set_tracer_provider()

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)
        assert (
            provider.resource.attributes["service.name"]
            == "file-export-marimo"
        )
        assert provider.resource.attributes["deployment.environment"] == "test"


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


class TestInstrumentAI:
    """Tests for _instrument_ai() pydantic_ai instrumentation."""

    def test_skips_when_pydantic_ai_not_installed(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from marimo._dependencies.dependencies import DependencyManager
        from marimo._tracer import _instrument_ai

        monkeypatch.setattr(
            DependencyManager.pydantic_ai, "has", lambda *_, **__: False
        )

        # Inject a fake module so we can prove it's never touched.
        fake_agent = MagicMock()
        fake_module = MagicMock()
        fake_module.Agent = fake_agent
        monkeypatch.setitem(sys.modules, "pydantic_ai", fake_module)

        _instrument_ai(MagicMock())

        fake_agent.instrument_all.assert_not_called()

    @pytest.mark.requires("pydantic_ai")
    def test_instruments_when_pydantic_ai_installed(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from marimo._dependencies.dependencies import DependencyManager
        from marimo._tracer import _instrument_ai

        monkeypatch.setattr(
            DependencyManager.pydantic_ai, "has", lambda *_, **__: True
        )

        from pydantic_ai.models.instrumented import InstrumentationSettings

        provider = MagicMock()
        with patch("pydantic_ai.Agent.instrument_all") as mock_instrument:
            _instrument_ai(provider)

        mock_instrument.assert_called_once()
        settings = mock_instrument.call_args.args[0]
        assert isinstance(settings, InstrumentationSettings)
        # InstrumentationSettings builds its tracer from the provider rather
        # than storing the provider itself, so assert the provider was used.
        assert settings.tracer is provider.get_tracer.return_value

    @pytest.mark.requires("pydantic_ai")
    def test_swallows_exceptions(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from marimo._dependencies.dependencies import DependencyManager
        from marimo._tracer import _instrument_ai

        monkeypatch.setattr(
            DependencyManager.pydantic_ai, "has", lambda *_, **__: True
        )

        # Should not raise even though instrument_all blows up.
        with patch(
            "pydantic_ai.Agent.instrument_all",
            side_effect=RuntimeError("boom"),
        ):
            _instrument_ai(MagicMock())
