---
description: "Serve a marimo notebook as a typed reactive backend. Stream variable updates over Server-Sent Events, prune the execution graph by subscription, and keep the editor open side-by-side for debugging."
---

# Run as a dataflow API

!!! warning "Experimental"
    The dataflow API is in active development. Wire shape, schema, and
    client surface may change between minor versions of marimo. Pin a marimo
    version when you ship.

`marimo edit` exposes any notebook with `mo.api.input(...)` declarations as
a typed reactive function over HTTP + Server-Sent Events. Pair it with the
bundled TypeScript client and you can build a custom frontend (React,
Svelte, Vue, raw `fetch`) that drives the notebook's inputs and renders
specific output variables — without surrendering the editor view.

## When to use it

- **You want a custom frontend.** `marimo run` already publishes the
  notebook *as* the app. Reach for the dataflow API instead when you want
  to render the notebook's outputs in your own UI.
- **You want fine-grained subscriptions.** Subscribe a component to a
  single variable; mounting and unmounting it adds and removes the
  variable from the kernel's pruning closure.
- **You want one source of truth.** The same notebook serves the editor
  for debugging *and* the API for production. Inputs propagate both
  directions in real time.

## The recipe

### 1. Declare inputs in the notebook

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
    rows = [r for r in load() if r["value"] >= threshold.value]
    if category.value != "all":
        rows = [r for r in rows if r["category"] == category.value]
    stats = {"count": len(rows)}
    return (stats,)
```

`mo.api.input(...)` returns a real `mo.ui` element — slider, dropdown,
switch, or text — inferred from the kwargs. The notebook is still fully
runnable in the editor; the API just promotes those elements to addressable
inputs.

Output variables are inferred automatically from the names returned by each
`@app.cell`. Use `typing.Annotated[..., mo.api.output(...)]` to attach a
description or kind hint, and `@mo.api.trigger(...)` to expose a
side-effect cell as an explicit `POST /trigger` target.

### 2. Launch the kernel

```bash
marimo edit notebook.py
```

The dataflow API is exposed on the same port as the editor at
`/api/v1/dataflow/*`. There is no separate "serve" mode — one process
runs both. Open the editor in a browser to debug; close it to run
headless and benefit from graph pruning.

### 3. Vendor the TypeScript client

```bash
marimo dataflow client > src/dataflow.tsx
```

This dumps a single zero-dependency TSX file into your project. It
peer-depends on `react` and re-exports a `DataflowProvider` plus a
fine-grained set of hooks built on `useSyncExternalStore`.

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

function Input({ input }) {
  const [value, setValue] = useDataflowInput(input.name, input.default);
  return (
    <input
      value={String(value ?? "")}
      onChange={(e) => setValue(e.target.value)}
    />
  );
}

function Stats() {
  // Mounting this hook subscribes to ``stats``; unmounting unsubscribes.
  // The kernel prunes cells whose outputs nobody is currently subscribed to.
  const stats = useDataflowValue<{ count: number }>("stats");
  return stats ? <pre>{JSON.stringify(stats, null, 2)}</pre> : <p>loading…</p>;
}
```

A complete worked example lives in the marimo repo at
`examples/dataflow-react-demo/`.

### 5. Configure your dev server proxy

Vite, for instance:

```ts
// vite.config.ts
export default defineConfig({
  server: {
    proxy: { "/api": { target: "http://localhost:2718", changeOrigin: true } },
  },
});
```

## Python API reference

| API                   | Description                                                                                                                                  |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `mo.api.input(...)`   | Declare a remote-controllable UI element. Type is inferred: `min`+`max` → slider, `options=[...]` → dropdown, `default=bool` → switch, etc.  |
| `mo.api.output(...)`  | Optional `typing.Annotated` annotation to attach a description / kind hint to an output variable.                                            |
| `mo.api.trigger(...)` | Decorator marking a side-effect cell as an explicit `POST /trigger` target.                                                                  |

## Wire protocol

Full reference: `marimo/_dataflow/protocol.py`. Cheat sheet below.

### `GET /api/v1/dataflow/schema`

Returns JSON `DataflowSchema`:

```json
{
  "inputs": [
    {
      "name": "threshold",
      "kind": "integer",
      "default": 20,
      "constraints": { "min": 0, "max": 100, "ui": "slider" }
    }
  ],
  "outputs": [{ "name": "stats", "kind": "any" }],
  "triggers": [],
  "schemaId": "f3a1c2d8e4b9..."
}
```

`schemaId` is a content hash. Cache it client-side and compare on each
response — when the notebook structure changes (cells added, signatures
shift), `schemaId` changes and the client knows to refetch.

### `POST /api/v1/dataflow/run`

Request:

```json
{
  "inputs":    { "threshold": 50, "category": "A" },
  "subscribe": ["stats"]
}
```

If `subscribe` is empty the server defaults to *all* outputs. Subscribing
to a strict subset is what enables pruning: the kernel runs only cells
that feed the subscribed outputs.

Response: `text/event-stream` with the closed event union below.

| Event            | Fields                                                  | Meaning                                                            |
| ---------------- | ------------------------------------------------------- | ------------------------------------------------------------------ |
| `schema`         | `{schema, schemaId}`                                    | Initial schema for the run (sent if the client has none)           |
| `schema-changed` | `{schemaId}`                                            | Cached schema is stale; refetch via `GET /schema`                  |
| `run`            | `{runId, status: "started" \| "done", elapsedMs?}`      | Run lifecycle bookends                                             |
| `var`            | `{name, kind, value, encoding, runId, seq}`             | Streamed as soon as the producing cell finishes                    |
| `var-error`      | `{name, runId, error, traceback?}`                      | Cell failed while computing this variable                          |
| `superseded`     | `{runId}`                                               | A newer run displaced this one                                     |
| `trigger-result` | `{name, runId, status, error?}`                         | Result of a `mo.api.trigger`                                       |
| `heartbeat`      | `{timestamp}`                                           | Keep-alive                                                         |

`var` events stream as each cell finishes, not at end-of-run. Slow
downstream cells don't block fast upstream ones.

### `Kind` enum (closed)

`null`, `boolean`, `integer`, `number`, `string`, `bytes`, `datetime`,
`date`, `time`, `duration`, `list`, `dict`, `tuple`, `optional`, `union`,
`table`, `tensor`, `image`, `audio`, `video`, `html`, `pdf`,
`ui_element`, `any`.

## TypeScript client reference

The bundled client (`marimo dataflow client`) ships with one provider and
a fine-grained set of hooks. Each hook subscribes through
`useSyncExternalStore`, so a component re-renders only when the slice it
reads changes.

| Hook                              | Returns                                                                                              |
| --------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `useDataflowSchema()`             | The current `DataflowSchema`, or `null` until the first response                                     |
| `useDataflowValue<T>(name)`       | The current value of one variable. Mounting auto-subscribes; unmounting unsubscribes                 |
| `useDataflowVariable<T>(name)`    | Same, but returns the full `VarUpdate<T>` (run id, kind, ts) instead of just the value               |
| `useDataflowInput<T>(name, fallback)` | `[value, setValue]` two-way binding. Defaults flow from the schema; `fallback` is used until then    |
| `useDataflowStatus()`             | `RunStatus` — `loading`, `error`, `runId`, `elapsedMs`, `firstVarMs`, `subscriptionsResolvedMs`, `schemaId` |
| `useDataflowRun()`                | Imperative `() => void` to trigger a run (bypasses debounce)                                         |
| `useDataflowSubscriptions()`      | Names currently subscribed to (refcount > 0). Useful for debug surfaces                              |
| `useDataflowValuesSnapshot()`     | All variables received this session, keyed by name. Re-renders on *any* update — for debug only      |
| `useDataflowClient()`             | Escape hatch returning the underlying `DataflowClient`                                               |

`<DataflowProvider>` accepts:

```tsx
<DataflowProvider
  baseUrl="/api/v1/dataflow"
  autoRun           // re-run on input change (default true)
  debounceMs={150}  // coalesce slider drags
>
  …
</DataflowProvider>
```

## Side-by-side editor

The dataflow API and the editor websocket attach to the same `Session`
as distinct `SessionConsumer`s. Practical consequences:

- **Bidirectional input sync.** Drive a slider from the React app and the
  editor's slider updates in real time, and vice versa.
- **Editor disables pruning.** When the editor is open the kernel runs
  the *full* reactive graph so all cell outputs stay fresh for debugging.
  In the React client this means `RunStatus.elapsedMs` (kernel wall-clock)
  diverges from `subscriptionsResolvedMs` (when your subscribed variables
  arrived). Display the latter for "time-to-UI-ready".
- **Pruned again when the editor closes.** Headless `/run` requests run
  only the subgraph feeding the current subscription set.
- **Backfill on takeover.** Reattaching an editor to a previously-pruned
  session marks any skipped cells stale and re-runs them — the editor
  never shows a mix of fresh and stale outputs.

## CLI

```text
marimo dataflow client                # print TypeScript client to stdout
marimo dataflow client --path         # print path to bundled file
marimo dataflow agent                 # print agent recipe (AGENT.md)
marimo dataflow agent --path          # print path (for skill loaders)
```

The TypeScript client and `AGENT.md` ship inside the marimo wheel; any
environment with `marimo` installed can vendor them without a separate
download. See [`examples/dataflow-react-demo/`](https://github.com/marimo-team/marimo/tree/main/examples/dataflow-react-demo)
for an end-to-end demo.

## Pitfalls

- **Multi-file servers** must include `?file=path/to/notebook.py` on every
  request. Single-file `marimo edit` doesn't need it.
- **`baseUrl`** in `DataflowProvider` is relative to the page origin. In
  development, configure your bundler's proxy to route `/api/v1/dataflow`
  to marimo's port (`2718` by default).
- **The TS client is vendored, not a package.** Re-run
  `marimo dataflow client > src/dataflow.tsx` whenever you upgrade marimo
  — the kernel and client share a wire protocol whose stability is only
  guaranteed within a marimo minor version.
- **CORS.** Schema and run responses set `Access-Control-Allow-Origin: *`.
  If you front marimo with auth, override or strip that header.
