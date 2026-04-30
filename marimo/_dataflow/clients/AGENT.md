# Dataflow API — Agent Recipe

> **Status:** experimental. Wire shape may change between minor versions of marimo.

This file is the canonical instruction sheet for AI agents building on top of
marimo's dataflow API. Print it with `marimo dataflow agent` (the path is also
exposed via `marimo dataflow agent --path` for skill loaders that prefer file
references).

## When to use it

The dataflow API turns a marimo notebook into a typed reactive function that
streams variable updates over Server-Sent Events. Reach for it when you want to:

- **Serve a notebook as a backend** for a custom frontend (React, Svelte,
  raw fetch, anything that speaks SSE).
- **Subscribe to specific variables** rather than poll for full notebook
  outputs. The kernel prunes its execution graph to only the cells that feed
  what's currently subscribed.
- **Drive notebook inputs from your app** while keeping the editor open
  side-by-side for debugging. Inputs propagate both directions.

Don't reach for it when you want a self-contained app with no separate
frontend — `marimo run` already publishes the notebook as a web app.

## The recipe (5 steps)

### 1. Write a notebook with `mo.api.input`

```python
import marimo
app = marimo.App()


@app.cell
def inputs():
    import marimo as mo

    threshold = mo.api.input(min=0, max=100, default=20)
    category = mo.api.input(options=["all", "A", "B"], default="all")
    return category, mo, threshold


@app.cell
def stats(category, threshold):
    # Variable names declared at the top of the cell become outputs.
    rows = [r for r in load() if r["value"] >= threshold.value]
    if category.value != "all":
        rows = [r for r in rows if r["category"] == category.value]
    stats = {"count": len(rows), "mean": sum(r["value"] for r in rows) / max(len(rows), 1)}
    return (stats,)
```

`mo.api.input(...)` returns a real `mo.ui` element (slider, dropdown, switch,
text — inferred from the kwargs) that doubles as a remote-controllable input.
The notebook is still fully runnable in the editor; the API just promotes
those elements to addressable inputs.

### 2. Launch the kernel

```bash
marimo edit notebook.py
```

The dataflow API is exposed on the same port as the editor at
`/api/v1/dataflow/*`. There's no separate "serve" mode — one process runs
both. Open the editor in a browser to debug; close it to run headless.

### 3. Vendor the TypeScript client

```bash
marimo dataflow client > src/dataflow.tsx
```

Drop it in any React project (it's a single zero-dependency file, peer-deps
on `react`). It re-exports a `DataflowProvider` plus per-variable hooks that
use `useSyncExternalStore` for fine-grained re-renders.

### 4. Render against the schema

```tsx
import {
  DataflowProvider,
  useDataflowSchema,
  useDataflowInput,
  useDataflowValue,
} from "./dataflow";

export function App() {
  return (
    <DataflowProvider baseUrl="/api/v1/dataflow">
      <Inputs />
      <Stats />
    </DataflowProvider>
  );
}

function Inputs() {
  const schema = useDataflowSchema();
  return schema?.inputs.map((inp) => <Input key={inp.name} input={inp} />);
}

function Input({ input }: { input: { name: string; default?: unknown } }) {
  const [value, setValue] = useDataflowInput(input.name, input.default);
  return <input value={String(value ?? "")} onChange={(e) => setValue(e.target.value)} />;
}

function Stats() {
  // Mounting this hook subscribes to ``stats``; unmounting unsubscribes.
  // The kernel prunes cells whose outputs nobody is currently subscribed to.
  const stats = useDataflowValue<{ count: number; mean: number }>("stats");
  return stats ? <pre>{JSON.stringify(stats, null, 2)}</pre> : <p>loading…</p>;
}
```

### 5. Configure your dev server proxy

Vite example:

```ts
// vite.config.ts
export default defineConfig({
  server: {
    proxy: { "/api": { target: "http://localhost:2718", changeOrigin: true } },
  },
});
```

That's the whole story for the happy path. The rest of this file is reference.

---

## Python reference

| API                  | Description                                                         |
| -------------------- | ------------------------------------------------------------------- |
| `mo.api.input(...)`  | Declare a remote-controllable UI element (slider/number/dropdown/switch/text/text_area, inferred from kwargs). Returns a regular `mo.ui` element. |
| `mo.api.output(...)` | Optional `typing.Annotated` annotation to attach a description / kind hint to an output variable. |
| `mo.api.trigger(...)` | Decorator marking a side-effect cell as an explicit `POST /trigger` target. |

Outputs are inferred automatically: every name returned by an `@app.cell`
function becomes a candidate output. There is no opt-in step required.

## Wire protocol

Full reference: `marimo/_dataflow/protocol.py` (~200 lines, msgspec-typed).
Cheat sheet:

### `GET /api/v1/dataflow/schema`

Returns JSON `DataflowSchema`:

```json
{
  "inputs":   [{"name":"threshold","kind":"integer","default":20,"constraints":{"min":0,"max":100,"ui":"slider"}}],
  "outputs":  [{"name":"stats","kind":"any"}],
  "triggers": [],
  "schemaId": "f3a1c2d8e4b9..."
}
```

`schemaId` is a content hash. When the notebook structure changes (cells
added/removed, signatures change), the id changes — clients can compare it
to detect schema drift.

### `POST /api/v1/dataflow/run`

Request:

```json
{
  "inputs":    {"threshold": 50, "category": "A"},
  "subscribe": ["stats"]
}
```

If `subscribe` is empty the server defaults to *all* outputs. Subscribing to
a strict subset enables graph pruning: the kernel runs only the cells that
feed the subscribed outputs.

Response: `text/event-stream` with the closed event union:

| Event              | Fields                                                    |
| ------------------ | --------------------------------------------------------- |
| `schema`           | `{schema, schemaId}` — sent first if the client has no schema yet |
| `schema-changed`   | `{schemaId}` — the cached schema is stale; refetch it     |
| `run`              | `{runId, status: "started"|"done", elapsedMs?}`           |
| `var`              | `{name, kind, value, encoding, runId, seq}`               |
| `var-error`        | `{name, runId, error, traceback?}`                        |
| `superseded`       | `{runId}` — a newer run has displaced this one            |
| `trigger-result`   | `{name, runId, status, error?}`                           |
| `heartbeat`        | `{timestamp}`                                             |

`var` events stream as soon as the producing cell finishes — they don't wait
for the whole run to complete. This is what enables real-time updates for
fast cells while a slow downstream cell is still running.

### `Kind` enum (closed)

`null`, `boolean`, `integer`, `number`, `string`, `bytes`, `datetime`,
`date`, `time`, `duration`, `list`, `dict`, `tuple`, `optional`, `union`,
`table`, `tensor`, `image`, `audio`, `video`, `html`, `pdf`, `ui_element`,
`any`.

The TypeScript client maps these to a closed union plus an `(string & {})`
escape hatch for forward compatibility.

## Side-by-side editor

The dataflow API and the editor websocket attach to the **same** kernel as
distinct `SessionConsumer`s. Practical consequences:

- When you drive an input from the app, the editor's slider/dropdown updates
  in real time — the kernel propagates `notify_frontend=True`.
- When the editor is open, pruning is **disabled** so all cells run for
  debug visibility. You'll notice in the React app that the *full-run*
  `elapsedMs` becomes the slowest cell's wall-clock, even for variables you
  haven't subscribed to. Use `subscriptionsResolvedMs` from `RunStatus` to
  display time-to-UI-ready instead.
- Closing the editor switches the kernel back to pruned execution — the
  next `/run` takes only as long as the subgraph the app cares about.
- Reattaching an editor to a previously-pruned session triggers a backfill:
  cells skipped by the last pruned run are marked stale and re-executed
  on the editor's behalf, so the editor never shows stale outputs.

## Pitfalls

- **Multi-file servers** must include `?file=path/to/notebook.py` on every
  request. Single-file `marimo edit` doesn't need it.
- **`mo.ui.dropdown`** stores its value as a list internally. The API
  unwraps single-string requests automatically; if you pass a list it will
  also work.
- **`baseUrl`** in `DataflowProvider` is relative to the page origin. In
  dev, configure your bundler's proxy to route `/api/v1/dataflow` to
  marimo's port (default `2718`). In prod, you can either co-host marimo
  behind the same reverse-proxy or set an absolute URL.
- **CORS**: schema and run responses set `Access-Control-Allow-Origin: *`.
  If you front marimo with auth, strip or override that header.
- **The TS client is vendored, not a package.** Run
  `marimo dataflow client > src/dataflow.tsx` whenever you upgrade marimo
  — the kernel and client share a wire protocol whose stability is only
  guaranteed within a marimo minor version.

## Worked example

A complete runnable demo lives in the marimo repo at
`examples/dataflow-react-demo/`. It exercises every hook this file
mentions, plus a debug footer showing live subscriptions.
