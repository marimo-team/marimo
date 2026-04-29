# marimo Dataflow API Demo

A marimo notebook served as a typed reactive backend for a custom React
frontend via the **Dataflow API**. The same notebook is fully runnable in
`marimo edit` — the only change is that `mo.api.input(...)` UI elements are
remote-controllable from outside the kernel.

## Architecture

```
┌──────────────────┐       SSE / JSON        ┌──────────────────────────┐
│   React Frontend │ ◄─────────────────────► │  Dataflow API server     │
│   (Vite :3000)   │   POST /run             │  (Starlette :2719)       │
│                  │   GET  /schema          │                          │
└──────────────────┘                         │  ┌────────────────────┐  │
                                             │  │  Persistent kernel │  │
                                             │  │  (notebook.py)     │  │
                                             │  └────────────────────┘  │
                                             └──────────────────────────┘
```

## Quick start

```bash
# 1. Start the dataflow API server
cd examples/dataflow-react-demo
uv run --with starlette --with uvicorn python serve.py

# 2. In another terminal, start the React frontend
cd frontend
pnpm install
pnpm dev

# 3. Open http://localhost:5173
```

You can also run the notebook directly in marimo's editor:

```bash
marimo edit notebook.py
```

The editor will render the slider and dropdown as normal `mo.ui` elements;
the dataflow API treats those same elements as remote-controllable inputs.

## How it works

- **`notebook.py`** declares two `mo.api.input(...)` UI elements
  (`threshold`, `category`) plus regular cells that consume them and produce
  `stats`, `histogram`, `table`, etc.
- **`serve.py`** spins up a standalone Starlette server that mounts the
  dataflow API endpoints against the notebook.
- **`GET /api/v1/dataflow/schema`** returns a kernel-derived schema —
  inputs (with kind, default, and constraints) and outputs. The server runs
  the notebook once with default values and introspects the resulting UI
  elements; subsequent calls hit a cache keyed on the notebook's content
  hash.
- **`POST /api/v1/dataflow/run`** accepts an `{inputs, subscribe}` body,
  pushes the inputs into the kernel's UI elements via `_update`, runs only
  the cells needed to produce the subscribed variables, and streams back
  one `var` event per subscription as Server-Sent Events.
- **Persistent kernel**: state lives across requests, so unprovided inputs
  retain their last value and intermediate computations are reused.

## What this exercises

- **Variable-level subscriptions** — pruning ensures the kernel only does
  the work needed for subscribed outputs.
- **Schema-driven frontend** — the React app reads `kind` and
  `constraints.ui` to render the right control (slider / dropdown / text).
- **Editor parity (Phase 3)** — opening `marimo edit notebook.py` against
  this notebook works today as a standalone notebook. Sharing a kernel
  between editor and dataflow API for live debugging is on the roadmap.
