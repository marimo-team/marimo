# Caching

marimo comes with utilities to cache intermediate computations. These utilities
come in two types: caching the return values of expensive functions in memory,
and caching the values of variables to disk.

## Caching expensive functions

Use [`mo.cache`](#marimo.cache) to cache the return values of functions in
memory, based on function arguments, closed-over values, and the notebook code
defining the function. The resulting cache is similar to `functools.cache`, but
with several benefits:

1. `mo.cache` persists its cache across cell re-runs, as long as (roughly
   speaking) the code defining the function and its references haven't changed;
2. `mo.cache` is invalidated when closed-over values change, while
   `functools.cache` returns stale values;
3. `mo.cache` does not require its arguments to be hashable;
4. `mo.cache` is not invalidated by comments and code formatting.

For a cache with bounded size, use [`mo.lru_cache`](#marimo.lru_cache).


```{eval-rst}
.. autofunction:: marimo.cache
```

```{eval-rst}
.. autofunction:: marimo.lru_cache
```

## Caching variables to disk

```{eval-rst}
.. autofunction:: marimo.persistent_cache
```
