# Build notebooks

`marimo build` is a [dbt](https://www.getdbt.com/)-style precomputation
step for marimo notebooks. It walks your notebook's dependency graph,
runs every cell that does **not** depend on a runtime input, and
persists each cell's defined value to disk. The original cells are
replaced in a *compiled* copy of the notebook with tiny loaders that
read the precomputed artifact back. Cells that depend on a UI element
or other runtime input are preserved verbatim.

The result is a notebook that opens and renders in seconds even when
the original has expensive SQL, large dataframes, or remote API calls
behind it.

```bash
marimo build my_notebook.py
```

## When to reach for it

Reach for `marimo build` when:

- Your notebook reads from a slow source (a data warehouse, a
  remote API) and the result rarely changes between sessions.
- You want to ship a notebook to a teammate who doesn't have access
  to your warehouse credentials, but who should still be able to
  interact with the UI cells downstream.
- You're prototyping a dashboard and the input-free precomputation
  is far more expensive than the interactive part.

## What gets compiled

For each cell in your notebook, the build picks one of four outcomes:

- **Loader.** The cell ran cleanly during the build, its defined value
  was persistable (dataframe or JSON), and either the cell has an
  explicit (non-`_`-prefixed) name or some non-compilable cell still
  needs its value. The body is replaced with a one-line read from
  disk.
- **Elided.** The cell ran cleanly, its value was persistable, the
  function name starts with `_`, and no non-compilable cell needs
  it. The cell is removed entirely from the output.
- **Verbatim.** The cell either depends on a runtime input
  (`mo.ui.*`, `mo.cli_args`), defines no globals (a chart cell, a
  `print` for debugging), or defines a value that can't be persisted
  (a lambda, a module). The cell is preserved exactly as written and
  runs at notebook-load time.
- **Setup.** The `with app.setup` block is always emitted as-is.

A subtle but important point: **non-persistable values don't
"poison" their descendants.** If a cell binds a lambda and a child
cell uses that lambda to compute a persistable result, the child can
still be compiled — the build runs the parent at build time, the
child uses the parent's value to compute its own, and the child's
loader replaces the body with a static read. The parent stays
verbatim and re-runs at notebook-load time, but its value is no
longer needed.

## Worked example

Suppose you have this notebook:

```python title="notebook.py"
@app.cell
def _imports():
    import marimo as mo

    return (mo,)


@app.cell
def customers(mo):
    customers = mo.sql(
        "SELECT * FROM warehouse.customers", engine=warehouse
    )
    return (customers,)


@app.cell
def _users(mo):
    # Internal helper, only used downstream.
    users = mo.sql("SELECT * FROM warehouse.users", engine=warehouse)
    return (users,)


@app.cell
def orders_enriched(mo, customers, users):
    orders_enriched = mo.sql(
        "SELECT c.*, u.role FROM customers c JOIN users u ON c.id = u.id"
    )
    return (orders_enriched,)


@app.cell
def category(mo):
    category = mo.ui.dropdown(["a", "b"])
    return (category,)


@app.cell
def filtered(mo, orders_enriched, category):
    filtered = mo.sql(
        f"SELECT * FROM orders_enriched WHERE name = '{category.value}'"
    )
    return (filtered,)
```

After running `marimo build notebook.py`:

```text
__marimo_build__/notebook/
├── notebook.py
├── customers-a820aea54461.parquet
├── orders_enriched-172659e8ff35.parquet
└── .manifest.json
```

The compiled `notebook.py` looks like:

```python
@app.cell(hide_code=True)
def _marimo_build_loaders():
    def marimo_artifact_path(filename: str) -> str:
        from pathlib import Path
        return str(Path(__file__).resolve().parent / filename)

    # The notebook's loaders use marimo_artifact_path directly via SQL,
    # so the helper cell is just this one function. Notebooks with
    # Python dataframe / JSON loaders also get
    # ``marimo_load_parquet`` and ``marimo_load_json`` here.


@app.cell
def _imports():
    import marimo as mo

    return (mo,)


@app.cell
def customers(mo):
    customers = mo.sql(
        f"SELECT * FROM read_parquet('{marimo_artifact_path('customers-a820aea54461.parquet')}')"
    )
    return (customers,)


# `_users` is gone — its only consumer was orders_enriched, which is
# now a loader and no longer references it.


@app.cell
def orders_enriched(mo):
    orders_enriched = mo.sql(
        f"SELECT * FROM read_parquet('{marimo_artifact_path('orders_enriched-172659e8ff35.parquet')}')"
    )
    return (orders_enriched,)


@app.cell
def category(mo):
    category = mo.ui.dropdown(["a", "b"])
    return (category,)


@app.cell
def filtered(mo, orders_enriched, category):
    filtered = mo.sql(
        f"SELECT * FROM orders_enriched WHERE name = '{category.value}'"
    )
    return (filtered,)
```

Three things to notice:

1. `customers` and `orders_enriched` are now SQL cells that read from
   local parquet files via duckdb's `read_parquet` — the warehouse is
   no longer queried.
2. `_users` was eliminated entirely. It was an internal helper used
   only by `orders_enriched`, which itself became a loader, so nothing
   else in the file needs `_users`.
3. `category` and `filtered` are unchanged — they depend on the UI
   dropdown and are not safe to precompute.

## Output layout

By default `marimo build my_notebook.py` writes to
`<notebook_dir>/__marimo_build__/<stem>/`. Override with `--output-dir`:

```bash
marimo build my_notebook.py --output-dir build/
```

Each artifact is named `<def>-<hex12>.{parquet,json}`. The `<def>` is
the variable name being materialized (so multi-def cells get one file
per definition). The 12-hex suffix is a content-addressed hash —
changing a cell's source or any of its compilable ancestors produces
a new filename.

## Incremental rebuilds

`marimo build` is incremental by default. On every run:

1. Each compilable cell's hash is recomputed.
2. If the corresponding artifact already exists on disk, it is reused
   verbatim and the cell is reported as `cached`.
3. Otherwise, the cell is executed and its result written; the cell is
   reported as `compiled`.
4. Stale artifacts (top-level `*.parquet` / `*.json` files in the
   output directory that aren't referenced by the current build's
   manifest) are deleted.

Pass `--force` to ignore the cache and re-materialize everything.

## Failures

A cell that raises during precomputation aborts the build with a
non-zero exit code:

```text
Error: Cell 'customers' raised MarimoSQLException: IO Error: ...

Fix the cell, or wire its inputs through `mo.ui.*` / `mo.cli_args`
to mark it non-compilable so the build skips it.
```

The build deliberately does *not* swallow runtime errors and emit the
cell verbatim — that would silently ship a broken precomputation.

If a cell is *expected* to need runtime context (a credential, a UI
selection, a CLI arg), make it transitively depend on `mo.ui.*` or
`mo.cli_args`. Such cells are classified as non-compilable and skipped
by the build.

The one form of "graceful fallback" the build performs is for cells
whose defined value can't be persisted (a lambda, a module, a generator,
...). Those cells run successfully but their values aren't materialized,
and the cell is emitted verbatim in the compiled notebook. Crucially,
this is per-cell — descendants whose own defs *are* persistable are
still compiled.

## Hashing semantics

The hash for cell C is

```
sha256(source(C) + sorted(hash(p) for p in compilable_parents(C)))
```

That is, the cell's own source, plus a Merkle hash over its
compilable ancestors. **Non-compilable parents are excluded** (their
data is not materialized to disk, so they don't contribute identity to
the artifact).

This means:

- Editing a cell's source rematerializes it, plus every compilable
  descendant.
- Editing the source of a non-compilable parent (e.g. a UI cell) does
  *not* invalidate compilable artifacts. That parent's data wasn't
  used in the artifact in the first place.
- Changes in *external* state (e.g. data drift in `prod_wh.customers`)
  do *not* invalidate artifacts. If you need fresh data, use `--force`
  or delete the relevant file.

## Known limitations

- **Setup cell defs are not pruned.** If your notebook's setup cell
  creates a warehouse engine (Snowflake, Postgres, ...), the compiled
  notebook will still try to create that engine on import — even
  though the data has already been materialized locally. Make sure
  your deploy environment has the necessary credentials, or factor
  the engine creation out of the setup cell.
- **Only dataframe and JSON values are materialized.** Cells whose
  defined values are not dataframes (anything narwhals can wrap) or
  not JSON-serializable (anything `json.dumps` accepts) are emitted
  verbatim and run at notebook-load time.
- **`mo.sql` engines are not preserved.** A SQL cell that originally
  ran on Snowflake becomes a duckdb-backed `read_parquet` call in the
  compiled notebook. The data is local; the engine kwarg is dropped.
- **Reserved names.** The compiled notebook may add a hidden helper
  cell named `_marimo_build_loaders` that exports up to three names
  into module scope: `marimo_artifact_path`, `marimo_load_parquet`,
  and `marimo_load_json`. Only the helpers actually used by the
  compiled notebook are emitted. Don't use these names in your input
  notebook.
