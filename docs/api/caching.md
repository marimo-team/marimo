# Caching

marimo comes with utilities to cache intermediate computations. These utilities
come in two types: caching the return values of expensive functions in memory,
and caching the values of variables to disk.

## Caching expensive functions

Use [`mo.cache`](#marimo.cache) to cache the return values of functions in
memory, based on the function arguments, closed-over values, and the notebook
code defining the function.

The resulting cache is similar to `functools.cache`, but with the benefit that
[`mo.cache`](#marimo.cache) won't return stale values (because it keys on
closed-over values) and isn't invalidated when the cell defining the decorated
function is simply re-run (because it keys on notebook code). This means that
like marimo notebooks, [`mo.cache`](#marimo.cache) has no hidden state
associated with the memorized function, which makes you more productive while developing iteratively.

For a cache with bounded size, use [`mo.lru_cache`](#marimo.lru_cache).


```{eval-rst}
.. autofunction:: marimo.cache
```

```{eval-rst}
.. autofunction:: marimo.lru_cache
```

## Caching variables to disk

Use `mo.persistent_cache` to cache variables computed in an expensive block of
code to disk. The next time this block of code is run, if marimo detects a
cache hit, the code will be skipped and your variables will be loaded into
memory, letting you pick up where you left off.

```{eval-rst}
.. autofunction:: marimo.persistent_cache
```
