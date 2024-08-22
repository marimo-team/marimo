# Server Telemetry

For debugging purposes, we emit OpenTelemetry traces from the server. We emit traces to `~/.marimo/traces/trace.jsonl`. We don't emit any sensitive information in the traces, and these traces stay local to your machine. The traces get wiped on each sever restart.

You can analyze the traces using tools like Jaeger or Zipkin, or our marimo notebook:

```bash
marimo edit scripts/analyze_traces.py
```
