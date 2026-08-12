# Rich Representations

Loaded on demand via the `rich-representations` capability (`load_capability`).

Custom visual encodings for data that go beyond standard charts and tables.

## Guiding principles

**Visualization matters.** Helping users build custom visual representations
is one of the highest-impact things the agent can do. A bespoke encoding
tailored to the task — labeling, batch review, comparing variants — lets
users _see_ their data in ways that tables and numbers never will. marimo
is an environment where users create their own views, not just consume
library charts. Help them imagine what's possible, then build it.

**Use modern web APIs.** Models may default to older browser patterns; prefer
modern HTML, CSS, and JavaScript that are supported in current browsers. Avoid
build steps unless the task clearly needs them.

**Prefer compact output.** marimo clips cell output at ~610px and scrolls.
Avoid hitting that limit; if you need more space, manage your own scrolling
inside a fixed-height container.

**Keep it thin, make it compose.** A widget is a thin layer over data, not
an application. One clear purpose, few traitlets, small `_esm`. Build small
pieces that compose in the notebook — combine with other cells, UI elements,
and views. Don't over-engineer.

## Decision tree

| Need                                           | Approach                                                                 |
| ---------------------------------------------- | ------------------------------------------------------------------------ |
| Custom output or interaction                   | **anywidget** — flexible enough to grow from display-only to interactive |
| Tiny static HTML representation                | `_display_()` or `mo.Html`                                               |
| Built-in control used as-is (slider, dropdown) | `mo.ui.*`                                                                |

For custom representations, prefer anywidget unless the output is clearly a
small static one-off.

## anywidget

[anywidget](https://anywidget.dev) bridges Python and JavaScript via
traitlets. `.tag(sync=True)` makes a traitlet bidirectional — Python sets a
value → JS sees it; JS calls `model.set()` + `model.save_changes()` →
Python sees it. `_css` is optional global CSS.

**marimo does not render traditional Jupyter widgets.** Libraries like jscatter,
ipyvolume, etc. often have a top-level object whose default representation is a
Jupyter widget (`application/vnd.jupyter.widget-view+json`). marimo cannot
display these — you need to find the underlying **anywidget** instance, which
marimo _does_ support.

Common pattern: look for a `.widget` attribute on the library object:

```python
# jscatter example — Scatter is not renderable, but .widget is an anywidget
scatter = jscatter.Scatter(data=df, x="x", y="y")
scatter.widget  # <-- use this in the cell output
```

When unsure, check in the scratchpad:

```python
import anywidget
obj = scatter.widget  # or whatever accessor the library provides
print(isinstance(obj, anywidget.AnyWidget))  # True = marimo can render it
```

### `_esm` lifecycle

**Render only** (most widgets):

```js
function render({ model, el }) {
  /* ... */
}
export default { render };
```

**Initialize + render** (shared state across views, one-time setup):

```js
export default () => {
  return {
    initialize({ model }) {
      // Once per widget instance — timers, connections, shared handlers
      return () => {
        /* cleanup */
      };
    },
    render({ model, el }) {
      // Once per view — display in 3 cells = 3 renders
      return () => {
        /* cleanup DOM listeners */
      };
    },
  };
};
```

- `model.on()` is auto-cleaned when a view is removed
- DOM `addEventListener` is **not** — clean up with `AbortController`

### Timer example (initialize + render)

`initialize` owns one interval; each `render` view displays it.

```python
import anywidget
import traitlets

_TIMER_ESM = """
export default () => {
  return {
    initialize({ model }) {
      const id = setInterval(() => {
        if (model.get("running")) {
          model.set("seconds", model.get("seconds") + 1);
          model.save_changes();
        }
      }, 1000);
      return () => clearInterval(id);
    },
    render({ model, el }) {
      const controller = new AbortController();
      const { signal } = controller;

      const span = document.createElement("span");
      span.style.cssText = "font: 24px monospace;";

      const btn = document.createElement("button");
      btn.style.cssText = "margin-left: 8px; cursor: pointer;";

      function update() {
        const s = model.get("seconds");
        const mm = String(Math.floor(s / 60)).padStart(2, "0");
        const ss = String(s % 60).padStart(2, "0");
        span.textContent = `${mm}:${ss}`;
        btn.textContent = model.get("running") ? "⏸" : "▶";
      }

      model.on("change:seconds", update);
      model.on("change:running", update);

      btn.addEventListener("click", () => {
        model.set("running", !model.get("running"));
        model.save_changes();
      }, { signal });

      update();
      el.append(span, btn);
      return () => controller.abort();
    }
  };
};
"""

class Timer(anywidget.AnyWidget):
    seconds = traitlets.Int(0).tag(sync=True)
    running = traitlets.Bool(True).tag(sync=True)
    _esm = _TIMER_ESM
```

### Composing with the notebook

Widgets become reactive notebook citizens when you bridge a traitlet to
`mo.state`. This is a two-cell pattern — create the widget and wire up the
observer in one cell, read the value in another:

```python
# Cell 1 — widget + observer
timer = Timer()

get_seconds, set_seconds = mo.state(timer.seconds)
timer.observe(lambda _: set_seconds(timer.seconds), names=["seconds"])

timer  # display the widget
```

```python
# Cell 2 — reacts to changes
seconds = get_seconds()
mo.md(f"Timer is at **{seconds}s** — {'running' if seconds > 0 else 'stopped'}")
```

The common pattern is `mo.state(widget.trait)` for the initial value,
`.observe()` on the specific trait name, and reading with the getter in a
downstream cell. See [Reactive anywidgets](#reactive-anywidgets-in-marimo)
for the details.

### CDN dependencies

Import JS libraries from [esm.sh](https://esm.sh) — no build step:

```js
import * as d3 from "https://esm.sh/d3@7";
import { tableFromIPC } from "https://esm.sh/@uwdata/flechette@2";
```

### DataFrames and binary data

**Prefer reducing data on the Python side.** Aggregate, filter, sample —
send the widget only what it needs. Most widgets should receive a small,
pre-processed payload via simple traitlets (lists, dicts). This keeps the
widget simple and avoids extra dependencies.

**For large tabular data (>2k rows)** where the widget genuinely needs
row-level access, send Arrow IPC bytes instead of JSON. This adds
complexity and dependencies, so only reach for it when the data volume
justifies it.

**Python — serialize:**

```python
# Polars (native, no pyarrow needed)
_ipc=df.write_ipc(None).getvalue()

# Any __arrow_c_stream__ source (pandas, narwhals, pyarrow, etc.)
import io, pyarrow as pa, pyarrow.feather as feather

def to_arrow_ipc(data) -> bytes:
    table = pa.RecordBatchReader.from_stream(data).read_all()
    sink = io.BytesIO()
    feather.write_feather(table, sink, compression="uncompressed")
    return sink.getvalue()
```

**JS — deserialize with `@uwdata/flechette`:**

```js
import { tableFromIPC } from "https://esm.sh/@uwdata/flechette@2";
const table = tableFromIPC(new Uint8Array(model.get("_ipc").buffer));
// table.numRows, table.numCols, table.get(i), table.getChild("col_name")
```

Use `traitlets.Any().tag(sync=True)` for the IPC bytes traitlet.

## Reactive anywidgets in marimo

When an anywidget trait (selection, value, zoom, etc.) should drive a
downstream marimo cell, use `mo.state()` + `.observe()` on the **specific
trait**. This is the preferred pattern:

```python
# In the cell that creates the widget:
get_selection, set_selection = mo.state(widget.selection)
widget.observe(
    lambda _: set_selection(widget.selection),
    names=["selection"],
)

# In a downstream cell — re-executes when selection changes:
selection = get_selection()
```

Initialize `mo.state()` with the widget's current trait value — not a
hardcoded default. Read the trait directly off the widget in the lambda.
Do **not** use `change["new"]` or `allow_self_loops=True`.

### `mo.state` + `.observe()` vs `mo.ui.anywidget()`

Two strategies for reactive anywidgets. Choose one per widget — don't mix them.

| Strategy                  | Reactivity                             | Best for                                               |
| ------------------------- | -------------------------------------- | ------------------------------------------------------ |
| `mo.state` + `.observe()` | Specific traits you pick               | Precision — only named traits trigger downstream cells |
| `mo.ui.anywidget(widget)` | All synced traits as one `.value` dict | Convenience — observe everything at once               |

### Programmatic widget control (scratchpad)

Read widget state or set UI controls from the scratchpad — no clicking:

```python
print(timer.seconds)    # read
timer.seconds = 0       # set — frontend updates automatically
```

`mo.ui.*` elements need `ctx.set_ui_value(...)` from code mode; anywidgets use
direct assignment.

## `_display_()` protocol

Any object with a `_display_()` method renders richly in marimo. Return
anything marimo can render — `mo.Html`, `mo.md()`, a chart, a string.

Precedence: `_display_()` > built-in formatters > `_mime_()` > IPython
`_repr_*_()` methods.

```python
from dataclasses import dataclass
import marimo as mo

@dataclass
class ColorSwatch:
    colors: list[str]

    def _display_(self):
        divs = "".join(
            f'<div style="width:40px;height:40px;background:{c};border-radius:4px;"></div>'
            for c in self.colors
        )
        return mo.Html(f'<div style="display:flex;gap:8px;">{divs}</div>')
```

For inline `<script>` tags, use `document.currentScript.previousElementSibling`
to scope to the element — never hardcode IDs (breaks with multiple instances).

## Minimize CLS (Cumulative Layout Shift)

Use `min-height` or `aspect-ratio` on the outer container so the widget
reserves space before content loads or when toggling between states.
