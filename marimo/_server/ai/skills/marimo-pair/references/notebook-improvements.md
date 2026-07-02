# Notebook Improvements

Loaded on demand via the `notebook-improvements` capability (`load_capability`).

When the user asks to improve, optimize, or clean up their notebook, scan the
current cells for these opportunities. Use your judgment — don't over-apply,
and if you're unsure whether a change is worthwhile, ask the user.

## Cell names

Low priority unless the user asks. `setup` and cells defining
functions/classes are auto-named by marimo. Beyond that, naming is optional.
Note that naming markdown cells clutters the UI by showing the cell header
that's normally hidden.

## Setup cell

A setup cell is named `"setup"` and is guaranteed to run before all other
cells. It's the place for module imports. Consolidating imports here keeps
the notebook clean and ensures every cell can rely on those modules being
available.

**The setup cell cannot reference other cells' variables.** It runs first, so
it must be self-contained: imports, constants, and definitions that depend only
on each other. Reading a name defined elsewhere (e.g. `df`, a UI element) fails
with `The setup cell cannot have references`.

First check if the notebook already has a cell named `"setup"`. If not, create
one and hoist scattered imports into it. `name="setup"` auto-positions the cell
first — no `before`/`after` needed:

```python
cid = ctx.create_cell('''import polars as pl
import marimo as mo
import anywidget
import traitlets''', name="setup")
ctx.run_cell(cid)
```

If a setup cell already exists, `create_cell(name="setup")` raises `ValueError`;
use `ctx.edit_cell("setup", code=...)` and `ctx.run_cell("setup")` instead.

## Lift reusable functions into their own cells

When a cell contains a single function or class that doesn't reference
variables from other cells, marimo treats it specially — it can be written as
a standalone definition and reused outside the notebook. These functions can
use modules from the setup cell.

Look for functions that **could belong in a library**: data loading, transforms,
parsers, domain logic, custom widgets. If someone might reasonably `import` it
from another module, it's a good candidate to lift into its own cell.

Don't lift everything — notebook-specific wiring (UI layout, display logic,
cell-level orchestration) should stay where it is. Use `_prefix` for
cell-internal helpers that aren't meant to be reused.

```python
# before: useful logic buried in a larger cell
objects = pl.read_csv("https://example.com/objects.csv")
artists = pl.read_csv("https://example.com/artists.csv")

def top_counts(df, col, n=5):
    return df.group_by(col).len().sort("len", descending=True).head(n)

result = top_counts(objects.join(artists, on="id"), "category")
```

```python
# after: top_counts is general-purpose — give it its own cell

# cell 1
def top_counts(df, col, n=5):
    return df.group_by(col).len().sort("len", descending=True).head(n)
```

```python
# cell 2
result = top_counts(df, "category")
```

## `mo.persistent_cache`

`@mo.persistent_cache` caches a function's result to disk so it isn't
recomputed on subsequent runs. The cache persists across kernel restarts.

```python
@mo.persistent_cache
def load_data():
    objects = pl.read_csv("https://example.com/objects.csv")
    artists = pl.read_csv("https://example.com/artists.csv")
    return objects.join(artists, on="id", how="left")

df = load_data()
```

Good candidates: data loading, ETL, expensive computation that rarely changes.
Don't over-optimize — if you're unsure, suggest it to the user rather than
applying it.
