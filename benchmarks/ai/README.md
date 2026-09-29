# Editor AI benchmarks

This package runs local, production-path evaluations of marimo's editor AI.
It starts a headless `marimo edit` server, opens a real notebook session, and
sends the same `/api/ai/chat` requests as the chat sidebar.

The runner loads the repository `.env` before importing marimo so tracing is
initialized with the configured OpenTelemetry environment. It never writes
environment variables or request headers to benchmark artifacts. Set
`WANDB_API_KEY` and the OpenTelemetry variables used by marimo before running
it, either directly or in `.env`.

Install the small data-analysis dependency group once:

```bash
uv sync --group ai-eval
```

Each trial uses an empty temporary user config, so personal MCP servers and
editor preferences cannot affect latency or model behavior. The subprocess
still inherits environment variables used for W&B and OpenTelemetry.

List the W&B Inference model IDs available to the configured account:

```bash
uv run --group ai-eval python -m benchmarks.ai models
```

Some W&B accounts do not grant access to the model-catalog endpoint. In that
case, pass a known W&B Inference model ID directly to `run`.

Run the quick suite with the production baseline harness:

```bash
uv run --group ai-eval python -m benchmarks.ai run --model <model-id>
```

The full suite contains three short, four medium, and three long scenarios.
It covers prescribed generation, targeted edits, reactive dependencies,
unsafe joins, dirty dates, missing dimensions, requirement revisions, and
long-conversation context retention:

```bash
uv run --group ai-eval python -m benchmarks.ai run \
  --model <model-id> \
  --suite full
```

The capability suite exercises editor operations that data-analysis cases do
not cover: isolated local-package installation and replacement, live UI-state
updates, and cell presentation and ordering. Package trials run the server in
a disposable child virtual environment, so they cannot modify the repository
environment:

```bash
uv run --group ai-eval python -m benchmarks.ai run \
  --model <model-id> \
  --suite capabilities \
  --variant baseline \
  --variant hybrid_balanced
```

`hybrid_balanced` exposes exploratory execution, typed inspection, atomic cell
patches, cell execution, and grouped operations for packages, live UI state,
and cell configuration.

Run one scenario:

```bash
uv run --group ai-eval python -m benchmarks.ai run \
  --model <model-id> \
  --scenario retail_investigation_short
```

Compare the production harness with the hybrid tool strategy. Repeated
trials expose model variance and are aggregated by scenario and variant in
`summary.json`:

```bash
uv run --group ai-eval python -m benchmarks.ai run \
  --model <model-id> \
  --suite full \
  --variant baseline \
  --variant hybrid_balanced \
  --repeat 3
```

Ongoing strategy results and decisions are recorded in
[`RESULTS.md`](RESULTS.md).

Explicit `--scenario` arguments override the suite selection. A practical
iteration loop is to use the quick suite while changing infrastructure, then
run selected long scenarios, and only use the full repeated matrix for a
candidate worth comparing.

Trials use isolated temporary workspaces and server processes. Run independent
trials concurrently with a bounded worker count when the model endpoint allows
it:

```bash
uv run --group ai-eval python -m benchmarks.ai run \
  --model <model-id> \
  --suite full \
  --variant baseline \
  --variant hybrid_balanced \
  --jobs 2
```

Output lines include the trial number when jobs overlap. Results are written in
the original scenario, variant, and repetition order regardless of completion
order. The default remains `--jobs 1`.

Results are written to `.ai-eval-runs/`. Local artifacts contain the candidate
model, scenario hash, variant configuration, repetition count, deterministic
scores, source contracts, final notebooks, diffs, conversation IDs, one
Logfire trace ID per turn, token usage, raw and effective history sizes, full
assistant-message sizes, and per-tool input/output sizes. Raw history is the UI
payload sent by the client; effective history is what remains after server-side
compaction. Usage includes model requests, input tokens, output tokens,
reasoning tokens, cache reads, and cache writes. A turn's usage is the sum over
every model request in its agent loop; output tokens include reasoning tokens
when the model provider reports reasoning as a subset of output. Each result
also retains the observed `analysis_summary`, which lets grading rules be
audited or recalculated without interpreting notebook output. Trial artifacts
are nested under scenario, variant, and repetition. Full model and tool
trajectories remain in Logfire.

Each turn is a complete, server-owned trace rooted at `POST /api/ai/chat`.
Streaming, model, and tool spans are children of that request span. Long
conversations are correlated by `gen_ai.conversation.id` and
`marimo.ai.session_id` instead of holding one trace open across user think
time. Root spans also include `marimo.ai.eval.run_id`,
`marimo.ai.eval.scenario_id`, and `marimo.ai.eval.turn`. Search Logfire for the
run ID printed in the artifact directory name to see every turn in a run.
Spans also contain `marimo.ai.eval.trial_id`, `marimo.ai.eval.variant_id`, and
`marimo.ai.eval.repetition`, so humans can isolate a single comparison.
`manifest.json`, `summary.json`, and the CLI output include the exact Logfire
filter. The benchmark also prints each turn's trace ID as soon as it completes.
