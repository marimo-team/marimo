# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Literal, cast

from marimo import _loggers
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.config.config import ConfigReader
from marimo._utils.platform import is_pyodide

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from opentelemetry import trace


class MockSpan:
    @contextmanager
    def as_current_span(self, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        yield self

    @contextmanager
    def set_attribute(self, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        yield

    @contextmanager
    def set_status(self, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        yield

    @contextmanager
    def update_name(self, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        yield

    @contextmanager
    def end(self, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        yield

    @contextmanager
    def add_event(self, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        yield

    @contextmanager
    def add_link(self, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        yield

    @contextmanager
    def set_attributes(self, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        yield

    @contextmanager
    def record_exception(self, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        yield


class MockTracer:
    @contextmanager
    def start_span(self, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs

        return MockSpan()

    @contextmanager
    def start_as_current_span(self, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        yield MockSpan()


TRACE_FILENAME = os.path.join("traces", "spans.jsonl")
OTLPProtocol = Literal["grpc", "http/protobuf"]


def _otlp_endpoint_configured() -> bool:
    return bool(
        os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    )


def _otlp_protocol() -> OTLPProtocol | None:
    protocol = (
        (
            os.environ.get("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL")
            or os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL")
            or "http/protobuf"
        )
        .strip()
        .lower()
    )
    protocol = protocol or "http/protobuf"

    if protocol in ("grpc", "http/protobuf"):
        return cast(OTLPProtocol, protocol)

    LOGGER.warning(
        "Unsupported OTLP protocol %r; expected 'grpc' or "
        "'http/protobuf'. Falling back to file export.",
        protocol,
    )
    return None


def _set_tracer_provider() -> None:
    if is_pyodide() or GLOBAL_SETTINGS.TRACING is False:
        return

    DependencyManager.opentelemetry.require("for tracing.")

    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        SpanExporter,
        SpanExportResult,
    )

    # If one already exists, return
    try:
        trace.get_tracer_provider()
    except Exception:
        return

    otlp_protocol = _otlp_protocol() if _otlp_endpoint_configured() else None
    OTLPSpanExporter: Any | None = None
    if otlp_protocol == "grpc":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter as GrpcOTLPSpanExporter,
            )

            OTLPSpanExporter = GrpcOTLPSpanExporter
        except ImportError:
            LOGGER.warning(
                "opentelemetry-exporter-otlp-proto-grpc not installed; "
                "install marimo[otel] for OTLP export. Falling back to file export.",
            )
    elif otlp_protocol == "http/protobuf":
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter as HttpOTLPSpanExporter,
            )

            OTLPSpanExporter = HttpOTLPSpanExporter
        except ImportError:
            LOGGER.warning(
                "opentelemetry-exporter-otlp-proto-http not installed; "
                "install marimo[otel] for OTLP export. Falling back to file export.",
            )

    if OTLPSpanExporter is not None:
        resource = Resource.create(
            {
                "service.name": "marimo",
            },
        )
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(),
            ),
        )
        LOGGER.debug(
            "OTel tracer: OTLP export via %s",
            otlp_protocol,
        )
    else:

        class FileExporter(SpanExporter):
            def __init__(self, file_path: Path) -> None:
                self.file_path = file_path
                self.file_path.write_bytes(b"")

            def export(
                self,
                spans: Sequence[ReadableSpan],
            ) -> SpanExportResult:
                try:
                    with self.file_path.open("a", encoding="utf-8") as f:
                        for span in spans:
                            f.write(span.to_json(cast(Any, None)))
                            f.write("\n")
                    return SpanExportResult.SUCCESS
                except Exception as e:
                    LOGGER.exception(e)
                    return SpanExportResult.FAILURE

            def shutdown(self) -> None:
                pass

        config_ready = ConfigReader.for_filename(TRACE_FILENAME)
        filepath = config_ready.filepath
        filepath.parent.mkdir(parents=True, exist_ok=True)

        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(FileExporter(filepath)))
        LOGGER.debug("OTel tracer: file export to %s", filepath)

    # Sets the global default tracer provider
    trace.set_tracer_provider(provider)


def create_tracer(trace_name: str) -> trace.Tracer:
    """
    Creates a tracer that logs to a file.

    This lazily loads opentelemetry.
    """

    # Don't load opentelemetry if we're in a Pyodide environment.
    if is_pyodide() or GLOBAL_SETTINGS.TRACING is False:
        return cast(Any, MockTracer())  # type: ignore[no-any-return]

    DependencyManager.opentelemetry.require("for tracing.")

    try:
        from opentelemetry import trace

        return trace.get_tracer(
            trace_name,
            attributes={
                "service.name": trace_name,
            },
        )

    except Exception as e:
        LOGGER.debug("Failed to create tracer: %s", e)

    return cast(Any, MockTracer())  # type: ignore[no-any-return]


try:
    _set_tracer_provider()
except Exception as e:
    LOGGER.debug("Failed to set tracer provider", exc_info=e)

server_tracer = create_tracer("marimo.server")
kernel_tracer = create_tracer("marimo.kernel")
