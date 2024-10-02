# Performance

## Disable autorun

For expensive notebooks, you can [disable automatic execution](/guides/reactivity.md#runtime-configuration).

## Cache computations with `@mo.cache`

Use [`mo.cache`](#marimo.cache) to cache the return values of
expensive functions, based on their arguments:

```python
import mo

@mo.cache
def compute_predictions(problem_parameters):
  # do some expensive computations and return a value
  ...
```

When `compute_predictions` is called with a value of
`problem_parameters` it hasn't seen, it will compute the predictions and store
them in an in-memory cache. The next time it is called with the same
parameters, instead of recomputing the predictions, it will return the
previously computed value from the cache.

:::{dropdown} Comparison to `functools.cache`

`mo.cache` is like `functools.cache` but smarter. `functools` will sometimes
evict values from the cache when it doesn't need to.

In particular, consider the case when a cell defining a `@mo.cache`-d function
re-runs due to an ancestor of it running, or a UI element value changing.
`mo.cache` will use sophisticated analysis of the dataflow graph to determine
whether or not the decorated function has changed, and if it hasn't, it's
cache won't be invalidated. In contrast, on re-run a `functools` cache is
always invalidated, because `functools` has no knowledge about the structure
of marimo's dataflow graph.

Conversely, `mo.cache` knows to invalidate the cache if closed over variables
change, whereas `functools.cache` doesn't, yielding incorrect cache hits.

`mo.cache` is slightly slower than `functools.cache`, but in most applications
the overhead is negligible. For performance critical code, where the decorated
function will be called in a tight loop, prefer `functools.cache`.
:::

## Save/load from disk with `mo.persistent_cache`

Use `mo.persistent_cache` to cache variables to disk. The next time your
run your notebook, the cached variables will be loaded from disk instead of
being recomputed, letting you pick up where you left off.

Reserve this for expensive computations that you would like to persist across
notebook restarts. Cached outputs are automatically saved to `__marimo__/cache`.

**Example.**

```python
import marimo as mo

with mo.persistent_cache(name="my_cache"):
    # This block of code and its computed variables will be cached to disk
    # the first time it's run. The next time it's run, `my_variable`
    # will be loaded from disk.
    my_variable = some_expensive_function()
    ...
```

Roughly speaking, `mo.persistent_cache` registers a cache hit when the cell
is not stale, meaning its code hasn't changed and neither have its ancestors.
On cache hit the code block won't execute and instead variables will be loaded
into memory.

## Disable expensive cells

marimo lets you temporarily disable cells from automatically running. This is
helpful when you want to edit one part of a notebook without triggering
execution of other parts. See the
[reactivity guide](/guides/reactivity.md#disabling-cells) for more info.

## Lazy-load expensive elements or computations

You can lazily render UI elements that are expensive to compute using `marimo.lazy`.

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

accordion = mo.ui.accordion({
    "Charts": mo.lazy(expensive_component)
})
```

In this example, we pass a function to `mo.lazy` instead of a component. This function will only be called when the user opens the accordion. In this way, `expensive_component` lazily computed and we only query the database when the user needs to see the data. This can be useful when the data is expensive to compute and the user may not need to see it immediately.
