# Performance

## Cache computations with `@mo.save.cache`

You may use `mo.save.cache` to cache expensive computations, in a notebook aware manner.

```python
import mo

# Re-running the cell won't invalidate the cache if the function is the same.
# However, the cache will also automatically become invalidated if relevant
# state, ui, or code changes occur.
@mo.save.cache
def compute_predictions(problem_parameters):
 ...
```

Whenever `compute_predictions` is called with a value of `problem_parameters`
it has not seen, it will compute the predictions and store them in a cache. The
next time it is called with the same parameters, instead of recomputing the
predictions, it will return the previously computed value from the cache.

Alternatively, you may use Python's builtin `functools` library to cache
expensive computations. It is important to note that `mo.save.cache` is more
expensive than `functools.cache`, and there are certain instances where
`functools.cache` is more appropriate.

## Disable expensive cells

marimo lets you temporarily disable cells from automatically running. This is
helpful when you want to edit one part of a notebook without triggering
execution of other parts. See the
[reactivity guide](/guides/reactivity.md#disabling-cells) for more info.

## Disable notebook autorun

For expensive notebooks, you can [disable autorun](/guides/reactivity.md#runtime-configuration).

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
