# Dataflow API

> **Status:** experimental. Phase 3 (editor parity) lands the dataflow API on
> top of marimo's real `Session`/`Kernel`. The protocol is functional;
> expect breaking changes until this notice is removed.

> **Demo:** [`examples/dataflow-react-demo`](../examples/dataflow-react-demo)
> drives the same kernel from a React frontend and `marimo edit` side by side.

The dataflow API exposes a marimo notebook as a typed reactive function. Custom
frontends (or any HTTP client) post a set of input values and receive streaming
updates for a chosen subset of the notebook's variables. The kernel runs only
the cells needed to produce those variables given those inputs; everything
else is pruned.

This document is the design contract and implementation plan. See
[`marimo/_dataflow/protocol.py`](../marimo/_dataflow/protocol.py) for the wire
shape and [`marimo/_server/api/endpoints/dataflow.py`](../marimo/_server/api/endpoints/dataflow.py)
for the HTTP surface.

---

## Goals

1. **Typed reactive function** — a notebook becomes a callable with a declared
   input/output schema. Inputs and outputs are first-class, not afterthoughts.
2. **Variable-level subscription** — the client says "I want `df` and `plot`,"
   and only the cells needed to compute those run.
3. **Stateless API, stateful implementation** — every request is a fat
   `{inputs, subscribe}` payload. The client doesn't manage sessions; the
   server transparently caches per-client kernels keyed on a session header
   for incremental updates.
4. **Editor parity** — opening the notebook editor against a live dataflow
   session shows the same outputs, including UI elements, intermediate cells,
   and debugging views. The editor is a *passive consumer* of the same kernel.
5. **Minimal protocol** — a custom frontend in any language should be able to
   implement a client in ~200 lines after reading one page of spec.

## Non-goals (for v1)

- Authentication / authorization beyond what the existing marimo server has.
- Multi-tenant kernel pooling. One kernel per session id.
- Streaming generator variables (a cell that yields over time). The protocol
  is designed to admit them but v1 stops at "value at end of run."
- Full schema migration. Schemas are immutable for the lifetime of a session.

---

## Protocol overview

Two endpoints under `/api/v1/dataflow/`:

| Method | Path                          | Purpose                                |
|--------|-------------------------------|----------------------------------------|
| GET    | `/api/v1/dataflow/schema`     | Static input/output/trigger schema     |
| POST   | `/api/v1/dataflow/run`        | Run with inputs, stream subscribed vars |
| POST   | `/api/v1/dataflow/triggers/{name}` | Fire a side-effect cell             |

Plus the existing editor websocket route, parameterised so the editor can
attach to a dataflow session as a kiosk consumer (see Phase 3 below).

### Inbound: `POST /api/v1/dataflow/run`

```jsonc
{
  "session_id": "s_abc123",          // optional; server generates if missing
  "inputs": { "x": 5, "df": {...} },
  "subscribe": ["result", "plot"],
  "encoding": {                       // per-variable wire format hints
    "result": "json",
    "plot":   "image/png"
  }
}
```

### Outbound: SSE stream of `DataflowEvent`

The minimal closed event union, emitted as named SSE events:

```ts
type DataflowEvent =
  | { type: "schema",          schema: Schema, schema_id: string }
  | { type: "schema-changed",  schema_id: string }
  | { type: "run",             run_id: string, status: "started" | "done", elapsed_ms?: number }
  | { type: "superseded",      run_id: string }
  | { type: "var",             name: string, kind: Kind, encoding: Encoding,
                               value?: JSONValue, ref?: BlobRef,
                               run_id: string, seq: number }
  | { type: "var-error",       name: string, error: ErrorPayload, run_id: string }
  | { type: "trigger-result",  name: string, status: "ok" | "error",
                               error?: ErrorPayload, run_id: string }
  | { type: "heartbeat",       timestamp: number };
```

This is shipped as `marimo._dataflow.protocol` and surfaces in the OpenAPI
schema as `DataflowEvent`. It is **deliberately separate** from the editor's
`NotificationMessage` union — the two protocols have different consumers,
different lifecycles, and different stability guarantees.

### Type system

A closed enum of `Kind`s:

```
null | boolean | integer | number | string | bytes |
datetime | date | time | duration |
list | dict | tuple | optional | union |
table | tensor |
image | audio | video | html | pdf |
ui_element |
any
```

Each schema entry pairs a `kind` with kind-specific fields (e.g. `arrow_schema_b64`
for `table`, `mimetype` for `image`, `dtype`+`shape` for `tensor`).

Encodings are advertised per-variable in the schema's `accepts` array; clients
opt into one in their subscribe request.

---

## Implementation plan

The work is split into four phases. Phases 1 and 2 are internal checkpoints
— the user has flagged that they don't need to be testable. Phase 3 is the
first end-to-end testable build. Phase 4 is the demo.

### Phase 1 — stateless POST returning JSON

Smallest possible vertical slice. No SSE, no sessions, no annotations. Just:

- `marimo/_dataflow/` package skeleton with `protocol.py`, `schema.py`, `pruning.py`.
- A `compute_dataflow_schema(app)` function that walks the graph and returns
  a `Schema` with inputs (= free variables) and outputs (= every cell `def`).
  Types default to `any` until phase 3 adds annotation parsing.
- A `compute_cells_to_run(graph, inputs, subscribed, dirty, last_inputs)`
  function that implements the algorithm from the design discussion:
  `needed = ancestors(defining_cells(subscribed))`,
  `affected = descendants(referring_cells(changed_inputs))`,
  pruned by `prune_cells_for_overrides`.
- A relaxed `prune_cells_for_overrides_for_subscription` variant that allows
  partial overrides as long as no surviving cell refers to the missing defs.
- `POST /api/v1/dataflow/run` that spins up an `AppKernelRunner` per request,
  runs the pruned cells, serialises subscribed defs, and returns a JSON object.

Validates the dataflow algorithm and the schema introspection. No public-facing
artefacts yet.

### Phase 2 — SSE streaming + session caching

- `DataflowConsumer` implementing `SessionConsumer` that receives kernel
  events, projects them through the schema into `DataflowEvent`s, and writes
  to an `asyncio.Queue` drained by an SSE handler.
- `DataflowSessionManager` that hands out sessions keyed on `session_id`.
  A request without a session id allocates one and returns it in the first
  SSE event. Session TTL.
- A new post-execution hook (`emit_subscribed_vars`) registered when the
  consumer attaches; it gates on `cell.defs & subscription_set` to keep
  wire traffic minimal.
- Last-Event-ID resume; heartbeats every 15s.

Validates the streaming protocol and incremental-update story.

### Phase 3 — testable end-to-end with editor parity

Public surface and the "open the editor against a live dataflow session"
workflow.

- `mo.api` module:
  - `mo.api.input(type, default=..., min=..., max=..., ui=...)` — declarative
    input. Returns a sentinel that resolves to the input's current value.
  - `mo.api.output(type, *, encoding=...)` — typed output annotation. Used
    via `Annotated[T, mo.api.output(...)]`.
  - `mo.api.trigger(description=...)` — declares a side-effect cell.
- Schema introspection becomes annotation-aware: `mo.api.input` declarations
  populate `schema.inputs` with kinds and defaults; `Annotated` outputs
  populate kinds and `accepts` lists; `mo.api.trigger` populates a separate
  `schema.triggers` list.
- `mo.ui.*` elements declared as `mo.api.input(..., ui=mo.ui.slider(...))`
  appear as `kind: "ui_element"` in the schema. Setting them via the dataflow
  API routes through the existing `Kernel.set_ui_element_value` so the editor
  view sees the slider move; conversely, slider drags in the editor emit
  dataflow `var` events for the React FE.
- Editor co-attachment: a query-string flag (`?session_id=...&attach_mode=observe`)
  on the existing edit websocket route lets the editor attach to an existing
  dataflow-allocated session as an additional `SessionConsumer`. This is
  basically the kiosk consumer pattern, repurposed.
- Per-kernel dual-consumer plumbing in `Kernel.run`: each cell run produces
  events for *all* attached consumers; the existing `EditorAdapter` (= the
  current `NotificationListenerExtension`) and the new `DataflowConsumer`
  pull the same events through different projections.

This is the first build the user can exercise end-to-end.

### Phase 4 — demo

A complete demonstration project under `examples/dataflow-react-demo/`:

- `notebook.py` — a marimo notebook with declared inputs (a slider for a
  threshold, a free-form text input, a file path), one expensive cell that
  loads a dataframe, a couple of cells that compute summaries, and a side
  chart cell. Outputs declared with `mo.api.output`.
- `frontend/` — a Vite + React app that:
  - GETs the schema, renders a form for inputs.
  - POSTs `/api/v1/dataflow/run` with a session id and subscribes to the
    summary + table outputs.
  - Renders streaming Arrow tables with `apache-arrow` and a chart with
    `vega-lite` (or similar; details TBD during implementation).
  - Exposes a "Open in editor" link that points at
    `http://localhost:2718/?session_id=<id>&attach_mode=observe`.
- README walking through `make demo-dataflow`.

---

## Architecture summary

```
        HTTP/SSE                      WS
   ┌─────────────────┐         ┌──────────────┐
   │  React frontend │         │ marimo editor│
   └────────┬────────┘         └──────┬───────┘
            │                         │
            │ POST /run               │ GET /ws
            │                         │
   ┌────────▼─────────┐       ┌───────▼────────┐
   │ DataflowConsumer │       │ EditorConsumer │
   └────────┬─────────┘       └────────┬───────┘
            │                          │
            └────────────┬─────────────┘
                         │
                  ┌──────▼──────┐
                  │   Session   │
                  │    Room     │
                  └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │   Kernel    │
                  │ (one per    │
                  │  session)   │
                  └─────────────┘
```

The `Room` already supports multi-consumer fan-out (it's how kiosk works).
Both consumers are attached to the same kernel; each receives every kernel
event and projects it through its own protocol. The protocols share *no*
wire format.

---

---

## Phase 2 plan — real kernel, runnable notebooks, cached schema

The Phase 1 implementation works end-to-end via curl and a React frontend, but
has three architectural shortcuts that block the larger goals:

1. **Notebooks aren't runnable on their own.** Inputs are detected as "free
   variables," which means a notebook with `threshold` and `category` ref'd but
   not defined is broken in the editor. This is bad UX.
2. **No persistent runtime.** Each `/run` request creates a fresh
   `AppScriptRunner` in a thread, re-imports modules, and discards globals.
   No caching, no incremental anything.
3. **Editor parity is impossible.** With per-request isolation, the editor and
   the dataflow API can't share state or reactively drive each other.

Phase 2 fixes 1 and 2 in one pass and lays the groundwork for editor parity
(deferred to phase 3 of phase 2 — see below).

### 2.1 — `mo.api.input(...)` becomes a UI element factory

`mo.api.input` no longer returns a metadata object; it returns a configured
`mo.ui.*` element. The element is the same object the cell author works with
in the editor; the dataflow API treats it as a remote-controllable input.

```python
# In a cell:
threshold = mo.api.input(min=0, max=100, default=50, description="Min value")
category = mo.api.input(options=["all", "A", "B", "C"], default="all")
```

- `mo.api.input(min=..., max=..., default=int_or_float)` → `mo.ui.slider` or
  `mo.ui.number` based on type.
- `mo.api.input(options=[...])` → `mo.ui.dropdown`.
- `mo.api.input(default="...", multiline=True)` → `mo.ui.text_area`.
- `mo.api.input(default=str)` → `mo.ui.text`.
- `mo.api.input(default=bool)` → `mo.ui.switch`.
- `mo.api.input(ui=mo.ui.slider(0, 100))` → use the explicit element verbatim.

The returned element carries a `_dataflow_input: bool = True` marker on its
`_ui_metadata` so the schema introspector can tell exposed inputs apart from
internal UI elements.

Inputs with options derived from data are natural — `options` can be any
expression that evaluates inside the cell, including a column from a dataframe
defined in another cell. Reactivity keeps the dropdown in sync with the data.

This single change means **a dataflow notebook is a fully runnable marimo
notebook** with interactive UI controls. Opening it in `marimo edit` shows the
sliders and dropdowns; cells downstream see real values. The dataflow API
just promotes those same UI elements to externally addressable inputs.

### 2.2 — Schema is kernel-derived, cached on file content hash

The schema is computed once per file by running the notebook with all inputs
at their defaults and introspecting the resulting `mo.ui` elements that carry
the `_dataflow_input` marker. The schema is cached against the file's content
hash and served instantly on subsequent calls.

```
GET /api/v1/dataflow/schema
  ↓
  if cache_hit(file_hash): return cached
  else:
    run = bootstrap_runner(file)
    run.execute_with_defaults()
    schema = build_schema_from_ui_elements(run.globals)
    cache[file_hash] = schema
    return schema
```

This buys us:

- Static-feeling contract: same code → same schema, no drift across requests.
- Dynamic constraints (dropdown options from a dataframe) work natively.
- AST-fragile cases (conditional input declarations, computed defaults)
  resolve deterministically based on the default-state run.

AST scanning is a sanity check, not a source of truth: we scan for
`mo.api.input(...)` call expressions to confirm the kernel-discovered inputs
match author intent and warn about declarations that didn't materialize
(e.g., inside a conditional that took the other branch with default inputs).

A future enhancement: persist the cached schema as a sidecar file alongside
the notebook (or embedded in the notebook header) so cold-start clients can
read it without bootstrapping a kernel at all.

### 2.3 — Persistent in-process runtime via `AppKernelRunner`

`DataflowSession` replaces its per-request `AppScriptRunner` with a long-lived
runtime built on `AppKernelRunner`, which already provides:

- Persistent kernel globals across calls.
- `set_ui_element_value()` with full reactive re-execution.
- Explicit `run(cells_to_run)` for our pruned-execution path.
- Output caching keyed on input defs.

Standalone server bootstrapping: `AppKernelRunner` requires a host
`KernelRuntimeContext` to exist. We provide one via a small bootstrap helper
that creates a synthetic host kernel context for the dataflow server process,
then instantiates one `AppKernelRunner` per file inside that host context.

Per-request flow becomes:

```python
# 1. Get or create runner for this file
runner = session_manager.get_runner(file_key)

# 2. For each input the client provided, push it to the kernel via
#    set_ui_element_value (which triggers reactive re-execution).
for name, value in body.inputs.items():
    ui_element_id = runner.input_ids[name]
    await runner.set_ui_element_value(
        UpdateUIElementCommand(object_ids=[ui_element_id], values=[value]),
        notify_frontend=False,
    )

# 3. Compute the pruned cell set for the subscribed vars
cells_to_run = compute_cells_to_run(
    runner.graph, runner.current_inputs, subscribed,
)

# 4. Run only those cells (set_ui_element_value already triggered re-exec
#    of affected cells; we run any additional ones that subscriptions need)
await runner.run(cells_to_run)

# 5. Pull subscribed var values out of runner.globals and emit VarEvents
for name in subscribed:
    yield make_var_event(name, runner.globals[name])
```

### 2.4 — Pruning preserved, mode-aware

Pruning is the production-path optimization. The runner picks an execution
strategy based on what's attached:

- **Dataflow consumer only** (typical prod): pruned execution. Only run cells
  in the transitive closure of subscribed variables.
- **Editor consumer also attached** (debug/dev): full reactive execution
  triggered naturally by `set_ui_element_value`. The dataflow consumer still
  filters its emissions to subscribed variables, but execution runs more cells
  so the editor sees the full picture. This means the dataflow client's
  observed behavior is *unchanged* — only the kernel's work scales up.

For Phase 2.x (now), the editor-attached path is not yet wired up, so we
always take the pruned path. Hooks are placed for Phase 3 to flip this on.

### 2.5 — Testing

- Unit: `mo.api.input` returns the expected `mo.ui` types for each kwarg shape.
- Unit: AST scan finds expected input names in canonical and tricky cases.
- Unit: schema cache invalidates on file content change.
- Integration: notebook is runnable in editor with `mo.api.input` defaults;
  same notebook served via dataflow API gives correct schema and run output.
- Integration: `set_ui_element_value`-driven re-execution updates only
  subscribed variables on the wire, even when the kernel runs more cells.

### Deferred to Phase 3 (genuine editor co-attachment)

The "open marimo edit on the same notebook and watch cell outputs change as
the dataflow API drives inputs" workflow requires bridging marimo's existing
`Session`/`Room` machinery with our `AppKernelRunner`-backed sessions. This
is the multi-consumer pattern from the original Phase 3 plan. It's
non-trivial because marimo's `Session` is tightly coupled to its
subprocess-kernel and websocket-consumer model, and we'd need a single
`Session` that hosts both an editor websocket consumer and a dataflow
consumer over the *same* `AppKernelRunner`.

Phase 2 lays the groundwork: the persistent runner is the shared kernel.
Phase 3 plumbs the editor websocket against it.

---

## Key code touchpoints

- `marimo/_dataflow/` (new package) — protocol, schema, pruning, consumer.
- `marimo/_runtime/dataflow/__init__.py` — relax `prune_cells_for_overrides`.
- `marimo/_runtime/runtime.py` — accept a "subscription set" for variable-
  scoped post-execution emits.
- `marimo/_session/model.py` — add `SessionMode.API`.
- `marimo/_server/api/endpoints/dataflow.py` (new) — HTTP surface.
- `marimo/_server/api/router.py` — mount the new router.
- `marimo/api.py` (new) — public `mo.api.input/output/trigger`.
- `marimo/__init__.py` — export `api`.
- `packages/openapi/api.yaml` — regenerate after each phase that adds models.
- `examples/dataflow-react-demo/` — phase 4.

---

## Phase 3 — unified on the real `Session`/`Kernel`

Phase 2's `DataflowRuntime` was a self-contained in-process execution
path. It worked, but it ran a parallel reactive engine that didn't know
about marimo's real `Session`/`Kernel`/`Room` — so an editor websocket
could never observe or drive its state. Phase 3 deletes
`DataflowRuntime` and re-implements the dataflow API on top of the
existing kernel.

Headless production and editor-attached debugging now differ only in
which consumers are attached to the room:

| Deployment | Editor mounted? | Cell exec strategy when dataflow runs |
|------------|-----------------|---------------------------------------|
| Prod / headless | No | Pruned to subscription closure |
| Dev / debug (`marimo edit notebook.py`) | Yes | Full reactive graph |

The decision is made by `DataflowFileBundle.run`: if the room contains
any consumer that isn't a dataflow primitive (anchor, SSE, schema
listener) the bundle sends an empty `subscribed` list, and the kernel
treats that as "no scope" and runs the full reactive set. The dataflow
SSE consumer still filters down to its subscriptions on the wire, so
the cost of editor-attached mode is bounded.

### 3.1 — Kernel additions

`marimo/_runtime/dataflow_callbacks.py` (`DataflowCallbacks`) owns the
per-consumer subscription registry, the cached `schema_id`, and the
on-finish hook that emits `dataflow-var` events. Four control commands
hit it:

- `SetDataflowSubscriptionsCommand(consumer_id, subscribed)`
- `RemoveDataflowSubscriptionsCommand(consumer_id)`
- `GetDataflowSchemaCommand` — triggers an explicit schema rebuild +
  broadcast. The bundle sends one of these on first attach.
- `ScopedRunCommand(consumer_id, run_id, inputs, subscribed)` — pushes
  UI overrides and runs reactively, optionally pruned.

Three new notifications carry kernel-derived values back over the
existing `Stream`/`Room` fan-out:

- `dataflow-schema` — public `DataflowSchema` plus the internal
  `input_object_ids` map the host uses to translate name-keyed wire
  requests into id-keyed `UpdateUIElementCommand`s.
- `dataflow-var` — serialized post-run value of a subscribed variable.
  Tagged with `consumer_id`; consumers filter to their own.
- `dataflow-var-error` — surfaced when a subscribed variable failed to
  materialize this run.

### 3.2 — Pruning, in the runner

The pruning algorithm lives in `marimo/_runtime/dataflow/`
(`cells_for_subscription`, `prune_cells_for_subscription`). Crucially
it runs **after** the runner's autorun expansion, not before:
`Runner.__init__` intersects the runner's expanded set with the scope
just before the topological sort. The kernel computes the scope in
`set_ui_element_value` whenever a `DataflowScope` is provided, and
otherwise runs the full reactive graph.

Cells that *define* an overridden input are explicitly excluded from
the scope so re-running them doesn't recreate the live `mo.api.input`
UI element and break the registry binding.

**Backfill on editor takeover.** Cells that the runner *would* have run
reactively but were dropped by the scope are marked `stale=True`. When
an editor websocket later attaches to the dataflow-anchored session
(`SessionConnector._resume_session`), it enqueues an
`ExecuteStaleCellsCommand` which catches up exactly those cells. The
result: a headless dataflow run with `prune=True` followed by an
editor connect produces a fully-fresh notebook view rather than mixing
fresh subscribed outputs with stale `display`/chart cells.

### 3.3 — Schema, cross-process

`compute_dataflow_schema_from_globals(graph, globals_)` walks the
kernel's own globals for `mo.api.input` UI elements (marked with
`DATAFLOW_INPUT_MARKER`) and pairs them with graph analysis to produce
a `DataflowSchema`. The host-side bundle requests one with
`GetDataflowSchemaCommand` after instantiate; the broadcast carries
both the public schema and the internal name → object_id map the
bundle needs to translate wire requests into kernel commands.

The schema is *not* cached in the dataflow layer — re-running the file
in the kernel re-broadcasts a new schema, and that's the only
invalidation we need.

### 3.4 — Host-side consumers

`marimo/_dataflow/consumer.py`:

- `DataflowAnchorConsumer` — phantom `main=True` consumer that satisfies
  `Room`'s "exactly one main consumer" invariant when the dataflow API
  creates a session ahead of any editor websocket.
- `DataflowSseConsumer` — per-request `main=False` consumer. Filters
  every `KernelMessage` to its own `consumer_id`, projects
  `dataflow-schema`/`dataflow-var`/`dataflow-var-error` into
  `DataflowEvent`s on an `asyncio.Queue` drained by the SSE response.
  Translates `CompletedRunNotification` into a `RunEvent(done)` to
  signal end-of-stream.

### 3.5 — `DataflowFileBundle` is now a `SessionManager` facade

`marimo/_dataflow/session.py`:

- `ensure_session()` looks up an existing session for the file via
  `SessionManager.get_session_by_file_key`; otherwise creates one with
  the anchor consumer attached and immediately fires an instantiate.
- `get_schema()` waits for the next `dataflow-schema` broadcast (or
  asks for one explicitly via `GetDataflowSchemaCommand`).
- `run(inputs, subscribed, ...)` attaches a fresh
  `DataflowSseConsumer`, decides whether to send a real scope based on
  the room's other consumers, queues a `ScopedRunCommand`, and yields
  the consumer's events as they arrive.

### 3.6 — CLI / server

The dataflow router is mounted on every `marimo edit` server; no flag
needed. Open `marimo edit notebook.py` and:

- The editor speaks the existing WS protocol on `/ws`.
- `POST /api/v1/dataflow/run` and `GET /api/v1/dataflow/schema` are
  available immediately.
- Both attach to the same `Session`/`Kernel`.

A future `marimo dataflow serve` subcommand will mount only the
dataflow router (no editor assets, no editor websocket) for production
deployments where shipping the editor is not desired.

### 3.7 — Demo

The demo's standalone `serve.py` is deleted. The README walks the user
through `marimo dataflow serve notebook.py` (prod) and
`marimo edit --enable-dataflow notebook.py` (with the React demo and
editor side-by-side). The React app gains an "Open in editor" link.

### 3.8 — Browser verification

The acceptance criterion:

1. Start `marimo edit --enable-dataflow examples/dataflow-react-demo/notebook.py`.
2. Open the React demo in tab A, the marimo editor in tab B.
3. Move a slider in A → A's output updates, B's slider moves, B's
   downstream cell outputs (including charts not subscribed by A)
   update — that's the "free debugging view."
4. Move a slider in B → B's outputs update reactively; A's subscribed
   variables update on the SSE stream.
5. Close B; A continues working unchanged.

### 3.9 — Sequencing within phase 3

1. New control commands + notification ops in `commands.py` /
   `notification.py`. Pure protocol additions.
2. `DataflowKernelExtension` post-execution hook + schema broadcast.
   Unit tests in-kernel (existing kernel test scaffolding).
3. Pruning gate in `ScopedRunCommand` handler. Unit tests for both
   gates (editor attached vs. not).
4. `DataflowSseConsumer` + integration test that drives a real
   `SessionImpl` end-to-end via the queue manager.
5. `DataflowFileBundle` rewire; delete `DataflowRuntime`.
6. CLI mounts (`--enable-dataflow` and `marimo dataflow serve`).
7. Demo cleanup; browser verify.
8. Docs update.
