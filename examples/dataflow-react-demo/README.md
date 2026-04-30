# marimo Dataflow API Demo

A marimo notebook served as a typed reactive backend for a custom React
frontend. The same notebook is fully runnable in `marimo edit` — the only
change is that `mo.api.input(...)` UI elements are remote-controllable
from outside the kernel.

> User-facing docs: [`docs/guides/dataflow_api.md`](../../docs/guides/dataflow_api.md).
> Agent skill: install with `gh skill install marimo-team/marimo dataflow`,
> or print it via `marimo dataflow skill`.

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
# 1. Start the marimo editor (this also exposes the dataflow API).
cd examples/dataflow-react-demo
marimo edit notebook.py --port 2718

# 2. In another terminal, start the React frontend.
cd frontend
pnpm install
pnpm dev

# 3. Open both:
#    - http://localhost:2718  ← marimo editor
#    - http://localhost:5173  ← React app
```

Drive the slider in either UI and watch the other update.

## TypeScript client

`frontend/src/dataflow.tsx` is a **symlink** into the marimo source tree
(`marimo/_dataflow/clients/typescript/dataflow.tsx`) so the demo always
exercises the same code that ships in the wheel. If you copy this demo
out of the marimo repo the symlink will dangle — replace it with:

```bash
marimo dataflow client > src/dataflow.tsx
```

!!! note "Windows contributors"
    Symlinks on Windows require developer mode (or admin) plus
    `git config core.symlinks=true`. If your clone has the demo file as
    a regular text file containing the relative path, run the command
    above to materialize a real copy.

## What this exercises

- **Variable-level subscriptions** — toggling the *Subscribe to
  `slow_threshold`* checkbox mounts/unmounts the corresponding hook,
  which adds/removes the variable from the server-side subscription set.
  With the editor closed, that prunes a 0.5s sleep cell out of every run.
- **Schema-driven frontend** — the app reads `kind` and `constraints.ui`
  off the schema and renders the appropriate control (slider, dropdown,
  text).
- **Editor parity** — opening `marimo edit notebook.py` and the React app
  side-by-side keeps the slider, table, and stats in sync regardless of
  which surface drives the input. With the editor attached the kernel
  runs the full reactive graph for debug visibility; close the editor
  and pruning resumes.
- **Per-cell streaming** — `var` events arrive as soon as the producing
  cell finishes. The `Stats` card lights up before the slow cell
  finishes when both are subscribed.
- **Two timing axes** — `RunMeta` shows both *time-to-subscribed-vars*
  (when the UI is ready) and *full-run elapsed* (when the kernel
  finished every cell), which diverge when the editor disables pruning.
