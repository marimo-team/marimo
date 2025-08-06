# Working with expensive notebooks

marimo provides tools to control when cells run. Use these tools to
prevent expensive cells, which may call APIs or take a long time to run, from
accidentally running.

## Stop execution with `mo.stop`

Use [`mo.stop`][marimo.stop] to stop a cell from executing if a condition
is met:

```python
# if condition is True, the cell will stop executing after mo.stop() returns
mo.stop(condition)
# this won't be called if condition is True
expensive_function_call()
```

Use [`mo.stop`][marimo.stop] with
[`mo.ui.run_button()`][marimo.ui.run_button] to require a button press for
expensive cells:

/// marimo-embed
    size: medium

```python
@app.cell
def __():
    run_button = mo.ui.run_button()
    run_button
    return

@app.cell
def __():
    mo.stop(not run_button.value, mo.md("Click 👆 to run this cell"))
    mo.md("You clicked the button! 🎉")
    return
```

///

## Configure how marimo runs cells

### Disabling cell autorun

If you habitually work with very expensive notebooks, you can
[disable automatic
execution](../guides/configuration/runtime_configuration.md#disable-autorun-on-cell-change-lazy-execution). When
automatic execution is disabled, when you run a cell, marimo
marks dependent cells as stale instead of running them automatically.

### Disabling autorun on startup

marimo autoruns notebooks on startup, with `marimo edit notebook.py` behaving
analogously to `python notebook.py`. This can also be disabled through the
[notebook settings](../guides/configuration/runtime_configuration.md#on-startup).

### Disable individual cells

marimo lets you temporarily disable cells from automatically running. This is
helpful when you want to edit one part of a notebook without triggering
execution of other parts. See the
[reactivity guide](../guides/reactivity.md#disabling-cells) for more info.

## Automatic snapshotting as HTML or ipynb

To keep a record of your cell outputs while working on your
notebook, you can configure notebooks to automatically save as HTML or ipynb
through the notebook menu (these files are saved in addition to the
notebook's `.py` file). Snapshots are saved to a folder called
`__marimo__` in the notebook directory.

Learn more about exporting notebooks in our [exporting guide](../guides/exporting.md).

## Caching

marimo provides two decorators to cache the return values of expensive functions:

1. In-memory caching with [`mo.cache`][marimo.cache]
2. Disk caching with [`mo.persistent_cache`][marimo.persistent_cache]

Both utilities can be used as decorators or context managers.

/// tab | `mo.cache`

```python
import marimo as mo

@mo.cache
def compute_embedding(data: str, embedding_dimension: int, model: str) -> np.ndarray:
    ...
```

///

/// tab | `mo.persistent_cache`

```python
import marimo as mo

@mo.persistent_cache
def compute_embedding(data: str, embedding_dimension: int, model: str) -> np.ndarray
    ...
```

///


See our [guide on caching](../api/caching.md) for details, including how the cache
key is constructed, and limitations.

## Lazy-load expensive UIs

Lazily render UI elements that are expensive to compute using
`marimo.lazy`.

For example,

```python
import marimo as mo

data = db.query("SELECT * FROM data")
mo.lazy(mo.ui.table(data))
```

In this example, `mo.ui.table(data)` will not be rendered on the frontend until is it in the viewport.
For example, an element can be out of the viewport due to scroll, inside a tab that is not selected, or inside an accordion that is not open.

However, in this example, data is eagerly computed, while only the rendering of the table is lazy. It is possible to lazily compute the data as well: see the next example.

```python
import marimo as mo

def expensive_component():
    import time
    time.sleep(1)
    data = db.query("SELECT * FROM data")
    return mo.ui.table(data)

accordion = mo.accordion({
    "Charts": mo.lazy(expensive_component)
})
```

In this example, we pass a function to `mo.lazy` instead of a component. This
function will only be called when the user opens the accordion. In this way,
`expensive_component` lazily computed and we only query the database when the
user needs to see the data. This can be useful when the data is expensive to
compute and the user may not need to see it immediately.
