---
title: In Memory Cache
marimo-version: 0.12.9
---

```python {.marimo}
import marimo as mo
```

```python {.marimo}
@mo.cache
def sleep_for(t: int):
    import time

    print("Sleeping")
    time.sleep(t)
    return t
```

```python {.marimo hide_code="true"}
mo.md(
    """
    Use `mo.cache` to cache the outputs of expensive functions. The first
    time the function is called with unseen arguments, it will execute and
    return the computed value. Subsequent calls with the same arguments will
    return cached results.

    Experiment with the invocation below to get a feel for how this works.
    """
)
```

```python {.marimo}
sleep_for(1)
```