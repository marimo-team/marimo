# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Sequence, cast

from marimo import _loggers
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.config.config import ConfigReader
from marimo._utils.platform import is_pyodide

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
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


def _set_tracer_provider() -> None:
    if is_pyodide() or GLOBAL_SETTINGS.TRACING is False:
        return

    DependencyManager.opentelemetry.require("for tracing.")

    from opentelemetry import trace
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

    class FileExporter(SpanExporter):
        def __init__(self, file_path: str) -> None:
            self.file_path: str = file_path
            # Clear file
            open(self.file_path, "w").close()

        def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
            try:
                with open(self.file_path, "a") as f:
                    for span in spans:
                        f.write(span.to_json(cast(Any, None)))
                        f.write("\n")
                return SpanExportResult.SUCCESS
            except Exception as e:
                LOGGER.exception(e)
                return SpanExportResult.FAILURE

        def shutdown(self) -> None:
            pass

    # Create a directory for logs if it doesn't exist
    config_ready = ConfigReader.for_filename(TRACE_FILENAME)
    if config_ready is None:
        raise FileNotFoundError(
            f"Could not local config file {TRACE_FILENAME}"
        )

    filepath = config_ready.filepath
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    # Create a file exporter
    file_exporter: FileExporter = FileExporter(filepath)

    provider = TracerProvider()
    processor = BatchSpanProcessor(file_exporter)
    provider.add_span_processor(processor)

    # Sets the global default tracer provider
    trace.set_tracer_provider(provider)


def create_tracer(trace_name: str) -> "trace.Tracer":
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
