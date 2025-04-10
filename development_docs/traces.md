# Tracing and profiling

## Server traces

For debugging purposes, we emit OpenTelemetry traces from the server. We emit traces to `~/.marimo/traces/spans.jsonl`. We don't emit any sensitive information in the traces, and these traces stay local to your machine. The traces get wiped on each sever restart.

You can analyze the traces using tools like Jaeger or Zipkin, or our marimo notebook:

```bash
marimo edit scripts/analyze_traces.py
```

### Enable Traces

To enable traces, set the `MARIMO_TRACING` environment variable to `true`:

```bash
MARIMO_TRACING=true ./your_server_command
```

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
