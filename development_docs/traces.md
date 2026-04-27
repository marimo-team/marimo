# Tracing and profiling

## Server traces

For debugging purposes, we emit OpenTelemetry traces from the server. By
default, traces are written to a local JSONL file. When an OTLP endpoint is
configured, traces are exported via gRPC instead, letting marimo participate in
distributed tracing stacks such as Jaeger, Grafana Tempo, or GCP Cloud Trace.

### Prerequisites

Tracing requires the `otel` extra (or a development install, which includes
the same packages):

```bash
pip install "marimo[otel]"
```

### Enable Traces

Set `MARIMO_TRACING=true` to turn tracing on:

```bash
MARIMO_TRACING=true marimo run notebook.py
```

### Local file export (default)

With no additional configuration, spans are written to
`~/.marimo/traces/spans.jsonl` (the exact path depends on your platform's
XDG state directory). The file is cleared on each server restart and never
leaves your machine.

You can analyze local traces with Jaeger, Zipkin, or the bundled notebook:

```bash
marimo edit scripts/analyze_traces.py
```

### OTLP export

To export traces to a remote collector, set the standard OpenTelemetry
environment variables:

```bash
MARIMO_TRACING=true \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
OTEL_SERVICE_NAME=marimo \
marimo run notebook.py
```

| Variable | Purpose | Default |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | gRPC endpoint of an OTLP collector | _(unset — file export)_ |
| `OTEL_SERVICE_NAME` | `service.name` resource attribute | `marimo` |
| `OTEL_RESOURCE_ATTRIBUTES` | Comma-separated `key=value` pairs added to the resource | _(empty)_ |

If the gRPC exporter package is not installed, marimo logs a warning and falls
back to the local file exporter.

### Distributed trace propagation

The `OpenTelemetryMiddleware` extracts incoming W3C `traceparent` headers, so
when another service calls marimo (e.g., via the MCP HTTP endpoint), the
resulting spans are linked as children of the caller's trace. No extra
configuration is needed — propagation works automatically whenever tracing is
enabled.

## Profiling the kernel

You can generate profiling statistics of the kernel in edit mode using the
hidden --profile-dir command-line option:

```bash
marimo edit --profile-dir profiles/ notebook.py
```

If the notebook exits gracefully (i.e., is shut down manually), profiling
statistics will be written to the profiles/ directory. You can then use
standard tools to analyze the dumped statistics. To view flamegraphs,
we recommend snakeviz or tuna (`uvx snakeviz path_to_profile`)
