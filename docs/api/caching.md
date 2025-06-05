# Caching

marimo comes with utilities to cache intermediate computations. These utilities
come in two types: caching the return values of expensive functions in memory,
and caching the values of variables to disk.

## Caching expensive functions

Use [`mo.cache`][marimo.cache] to cache the return values of functions in
memory, based on the function arguments, closed-over values, and the notebook
code defining the function.

The resulting cache is similar to `functools.cache`, but with the benefit that
[`mo.cache`][marimo.cache] won't return stale values (because it keys on
closed-over values) and isn't invalidated when the cell defining the decorated
function is simply re-run (because it keys on notebook code). This means that
like marimo notebooks, [`mo.cache`][marimo.cache] has no hidden state
associated with the cached function, which makes you more productive while developing iteratively.

For a cache with bounded size, use [`mo.lru_cache`][marimo.lru_cache].

::: marimo.cache
::: marimo.lru_cache

## Caching variables to disk

Use [`mo.persistent_cache`][marimo.persistent_cache] to cache variables computed in an expensive block of
code to disk. The next time this block of code is run, if marimo detects a
cache hit, the code will be skipped and your variables will be loaded into
memory, letting you pick up where you left off.

!!! tip "Cache location"
    By default, caches are stored in `__marimo__/cache/`, in the directory of the
    current notebook. You can set a global cache directory by adding
    `persistent_cache_dir = "/your/cache/path"` to your marimo config file, or by setting the
    environment variable `MARIMO_PERSISTENT_CACHE_DIR`. For projects versioned with `git`, consider adding
    `**/__marimo__/cache/` to your `.gitignore`.

::: marimo.persistent_cache
