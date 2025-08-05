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
associated with the cached function, which makes you more productive while
developing iteratively. See [caching expectations](#caching-expectations) for more details.

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
    current notebook. For projects versioned with `git`, consider adding
    `**/__marimo__/cache/` to your `.gitignore`.

::: marimo.persistent_cache

## Caching expectations

The performance and reliability of your notebook may depend on the caching functionality—as such, it is important to understand the expectations of marimo's caching utilities.

`mo.cache` context blocks are designed to provide deterministic cache restoration when using marimo's APIs for state management.

- On cache hit, the cached values are restored and the code block is not executed, meaning no side effects like printing, file I/O, or network requests will occur.
- Rerunning a cell will not remove your cache, enabling cache hits on subsequent runs.
- Dynamic changes to the notebook will appropriately invalidate the cache, if either:
    1. the code in the defined block changes,
    2. the variables with basic data types used by your code block change,
    3. or the relevant code that defines complex datatype variables changes.
- External modules are assumed to not mutate variables in a way that would affect the cache.
    - By setting `pinned_version` to `True`, you can ensure that the cache is invalidated when module versions change.
    - This limitation does not apply if the external module is a marimo notebook.
- Return values must be serializable.

`mo.cache` decorators are meant to be drop-in replacements for `functools.cache`, adapted to a dynamic notebook environment. In addition to the expectations of context blocks, the additional limitations apply:

- The wrapped function should be valid in all cases where `functools.cache` applies.
- Some contexts will require dependent variables (`args`, referenced variables) to be pickleable (just like `functools.cache`).

!!! note "Persistent cache invalidation across marimo library versions" marimo
    promises not to invalidate cache hits across patch (e.g. `0.x.y` -> `0.x.z`)
    versions of the library. Between minor (`0.a.b` -> `0.c.0`) and major (`0.a.b`
    -> `1.0.0`) versions of marimo, old persistent cache hits may become invalid. A
    notice will be provided in the release notes when this occurs. Overall, the caching
    mechanism is expected to be stable.

!!! warning "Variable mutation outside marimo APIs"
    Note that directly mutating variable state outside of defining
    cells is possible in marimo, but highly discouraged. Caching utilities are
    designed to work within the scope of marimo's APIs, which track variable state
    and changes. If you mutate variables outside of marimo's APIs, the cache may
    not be invalidated correctly, leading to stale data.

## Comparison with functools.cache

| Feature | marimo context | marimo decorator | functools.cache |
|---------|----------------|------------------|-----------------|
| **Dynamic Redefinition** | ✅ Handles cell re-execution | ✅ Handles function redefinition | ❌ Clears on redefinition |
| **Global Scope Changes** | ✅ Tracks global dependencies | ✅ Tracks closure variables | ❌ Misses scope changes |
| **Execution Context** | ✅ Detects external code changes | ✅ Detects external code Changes | ❌ No context awareness |
| **Side Effect Handling** | ✅ Tracks  | ✅ Tracks  | ❌ No side effect awareness |
| **Hash Method** | ✅ Primitive hashing | ✅ Pickle + code hashing | ✅ Pickle hashing on just arguments |
| **Performance** | ⚠️ Use for expensive functions | ⚠️ Use for expensive functions | ✅ Memory-only |


!!! tip "`functools.cache` is still a useful tool"
    Using memoization to calculate the Fibonacci sequence is a classic example
    of using `functools.cache` effectively. On a basic macbook in pure python,
    fib(35) takes 1 second to compute, with `mo.cache` it takes only 0.000229
    seconds; with `functools.cache`, it takes only 0.000025 seconds. Although
    relatively small, the additional overhead of `mo.cache` (and more so
    `mo.persistent_cache`) is larger than `functools.cache`. But if your
    function takes more than a few milliseconds to compute, the difference is
    negligible.


## Tips for reliable caching

!!! tip "Isolate cached code blocks to their own cells"

    Isolating cached functions in separate cells improves cache reliability.
    When dependencies and cached functions are in the same cell, any change to the cell
    invalidates the cache, even if the cached function itself hasn't changed.
    Separating them ensures the cache is only invalidated when the function actually changes.

**Don't do this:**
```python
# Cell 1
my_database_engine = ...
@mo.cache
def query_database(query):
    return my_database_engine.execute(query)
```

**Do this instead:**
```python
# Cell 1
my_database_engine = ...

# Cell 2
@mo.cache
def query_database(query):
    return my_database_engine.execute(query)
```



!!! tip "For best performance, only introduce low memory footprint variables"

    Variables inside cache blocks are serialized for cache key generation.
    Large datasets increase serialization time and memory usage without providing
    cache benefits. Compute derived values (like length) outside the cache block
    and only use the small values inside.

**Don't do this:**
```python
with mo.persistent_cache("bad example"):
    length = len(my_very_large_dataset)
    ... # uses length
```

**Do this instead:**
```python
length = len(my_very_large_dataset)  # my_very_large_dataset is not needed for cache invalidation
with mo.persistent_cache("good example"):
    ... # uses length
```


!!! tip "Use marimo APIs where they exist"

    marimo's APIs are designed to work seamlessly with the caching system.
    They automatically handle cache invalidation when external resources change,
    ensuring your cached results stay fresh. Using standard Python APIs may
    miss changes that should invalidate the cache.

**Avoid this:**
```python
my_file = open("my_file.txt")
with mo.persistent_cache("my_file"):
    data = my_file.read()
    # Do something with data
my_file.close()
```

**Do this instead:**
```python
# Cell 1
my_file = mo.watch.file("my_file.txt")

# Cell 2
with mo.persistent_cache("my_file"):
    data = my_file.read()
    # Do something with data
```

This has the same issue as `functools.cache`. If you have the option to use a marimo API, do so, as some APIs provide cache-busting side-effect results like `mo.watch.file`.


## Pitfalls

!!! warning "External modules"

External modules are assumed to not mutate variables in a way that would affect
the cache. If you use an external module that changes the state of a variable,
the cache may not be invalidated correctly. Note that this does not apply to
imported marimo notebooks, which will still utilize intelligent cache
invalidation.

For example, consider the following code:

```python
# my_lib.py

def function_that_may_change():
    return "initial result"

def expensive_function():
    return function_that_may_change()
```

```python
# Cell 1
from my_lib import expensive_function

# Note: updating my_lib.py will not invalidate the cache
cached_function = mo.cache(expensive_function)
original_cached_result == cached_function()
```

Then consider we update `my_lib.py` to change the return value of `function_that_may_change`:

```python
# my_lib.py (updated)

def function_that_may_change():
    return "changed result"

def expensive_function():
    return function_that_may_change()
```

```python
# Cell 2
new_cached_result = cached_function()
# Note: the cache will may return the original result
# since expensive_function was not changed!
# original_cached_result == new_cached_result
```

`cache` only considers the provided function for external modules.
By setting `pin_modules=True`, you can modify the `__version__` of the module
to more aggressively invalidate the cache. Alternatively, consider making the
external module a marimo notebook, which will ensure that the cache is
invalidated when the module changes.

Your final option is just to clear the cache manually by clearing `__marimo__/cache/`.


!!! warning "Non-wrapping external decorators"

Likewise, can you determine the bug in the following code?

```python
# my_lib.py
def my_decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
```

```python
# Cell 1
from my_lib import my_decorator

@mo.cache
@my_decorator
def expensive_function():
    # ... some computation
    return "result1"

@mo.cache
@my_decorator
def another_expensive_function():
    # ... different computation
    return "result2"

# This assertion may unexpectedly pass due to cache collision!
assert expensive_function() == another_expensive_function(), "But why?"
```

Cache operates on the `wrapper` function, which is from an external module, and as such is assumed not to carry state. It is pythonic convention to use `functools.wraps` to ensure that the decorated function has the same signature and metadata as the original function.

```python
# my_lib.py (fixed)
from functools import wraps

def my_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
```

In this instance, the cache will work as expected because the decorated function has the same signature and metadata as the original function.
