# marimo Dataflow API Demo

A marimo notebook served as a typed reactive backend for a custom React
frontend via the **Dataflow API**. The same notebook is fully runnable in
`marimo edit` — the only change is that `mo.api.input(...)` UI elements are
remote-controllable from outside the kernel.

## Architecture

```
┌──────────────────┐                                ┌──────────────────────────┐
│  marimo editor   │   /ws (existing protocol)      │      marimo edit         │
│ (browser, :2718) │ ◄────────────────────────────► │                          │
└──────────────────┘                                │   ┌────────────────────┐ │
                                                    │   │  Persistent kernel │ │
┌──────────────────┐   POST /api/v1/dataflow/run    │   │   (notebook.py)    │ │
│   React frontend │ ◄────────────────────────────► │   └────────────────────┘ │
│   (Vite :5173)   │   GET  /api/v1/dataflow/schema │                          │
└──────────────────┘   (SSE for /run streaming)     └──────────────────────────┘
```

Both the editor websocket and the dataflow HTTP/SSE endpoints attach to the
same `Session`/`Kernel`. Slider drags from the editor and `POST /run`
requests from the React app drive the same reactive graph.

## Quick start

```bash
# 1. Start the marimo editor (this also exposes the dataflow API)
cd examples/dataflow-react-demo
marimo edit notebook.py --port 2718

# 2. In another terminal, start the React frontend
cd frontend
pnpm install
pnpm dev

# 3. Open both:
#    - http://localhost:2718  ← marimo editor
#    - http://localhost:5173  ← React app
```

Drive the slider in either UI and watch the other update.

## How it works

- **`notebook.py`** declares two `mo.api.input(...)` UI elements
  (`threshold`, `category`) plus regular cells that consume them and produce
  `stats`, `histogram`, `table`, etc. Any of those become subscribable
  outputs over the dataflow API.
- **`marimo edit notebook.py`** mounts the dataflow router on the standard
  edit server. The same `Session` is shared between the editor's websocket
  and dataflow HTTP requests; there's no separate process and no second
  reactive engine.
- **`GET /api/v1/dataflow/schema`** returns the kernel-derived schema —
  inputs (with kind, default, and constraints) and outputs.
- **`POST /api/v1/dataflow/run`** accepts an `{inputs, subscribe}` body,
  pushes the inputs into the kernel's UI elements, runs only the cells
  needed to produce the subscribed variables (when no editor is attached),
  and streams back one `var` event per subscription as Server-Sent Events.
- **Editor parity**: when an editor websocket is attached the kernel
  intentionally runs the *full* reactive graph on every dataflow request so
  every cell's output stays observable in the editor. Headless deployments
  (no editor) get the pruned execution path automatically.

## What this exercises

- **Variable-level subscriptions** — pruning ensures the kernel only does
  the work needed for subscribed outputs when no editor is attached.
- **Schema-driven frontend** — the React app reads `kind` and
  `constraints.ui` to render the right control (slider / dropdown / text).
- **Editor parity** — opening `marimo edit notebook.py` and the React app
  side-by-side keeps the slider, table, and stats in sync regardless of
  which surface drives the input.
