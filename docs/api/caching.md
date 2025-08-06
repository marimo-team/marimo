# Caching

marimo comes with utilities to cache intermediate computations. These
utilities can be applied as decorators to functions to cache their
returned values; you can choose between saving caches in memory or to disk.

## Basic usage

marimo provides two decorators for caching the return values of expensive
functions:

1. [`mo.cache`][marimo.cache], which saves cached values to memory;
2. [`mo.persistent_cache`][marimo.persistent_cache], which saves cached values to disk.

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

Roughly speaking, the first time a cached function is called with a particular
sequence of arguments, the function will run and its return value will be
cached. The next time it is called with the same sequence of arguments (on
cache hit), the function body will be skipped and the return value will be
retrieved from cache instead.

The in-memory cache ([`mo.cache`][marimo.cache]) is faster and doesn't consume disk space, but
it is lost on notebook restart. The disk cache ([`mo.persistent_cache`][marimo.persistent_cache]) is
slower and consumes space on disk, but it persists across notebook runs,
letting you pick up where you left off.

(For an in-memory cache of bounded size, use [`mo.lru_cache`][marimo.lru_cache].)

!!! tip "Where persistent caches are stored"
    By default, persistent caches are stored in `__marimo__/cache/`, in the directory of the
    current notebook. For projects versioned with `git`, consider adding
    `**/__marimo__/cache/` to your `.gitignore`.

!!! tip "Caches are preserved even when a cell is re-run"
    If a cell defining a cached function is re-run, the cache will be preserved unless
    its source code (or the source code of the cell's ancestors) has changed.

### Persistent cache context manager

You can also use marimo's [`mo.persistent_cache`][marimo.persistent_cache] as a context manager:

```python
with mo.persistent_cache("my_cache_name"):
    X = my_expensive_computation(data, model)
```

The next time this block of code is run, if marimo detects a cache hit, the
code will be skipped and your variables will be loaded into memory. The cache
key for the context manager is computed in the same way as it is computed for
decorated functions.


## Cache key

Both `mo.cache` and `mo.persistent_cache` use the same mechanism for creating a
cache key, differing only in where the cache is stored. The cache key is based
on function arguments and closed-over variables.

### Function arguments
**Arguments must either be primitive, marimo UI elements, array-like, or pickleable:**

1. Primitive types (strings, bytes, numbers, None) are hashed.
2. marimo UI elements are hashed based on their value.
3. [Array-like objects](https://numpy.org/doc/stable/reference/arrays.interface.html#object.__array_interface__) are introspected, with their values being hashed.
4. All other objects are pickled.


### Closed-over variables
Syntactically closing over variables provides another way to parametrize
functions. In this example, the variable `x` is "closed over":

```python
x = 0
```

```python
def my_function():
    return x + 1
```

Closed-over variables are processed in the following way:

* marimo first attempts to hash or pickle the closed-over variables, just as it
does for arguments.
* If a closed-over variables cannot be hashed or pickled, then marimo uses the
source code that defines the value as part of the cache key; in particular, marimo
hashes the cell that defines the variable as well as the source code of that
cell's ancestors. This assumes that the variable's value is a deterministic
function of the source code that defines it, although certain side-effects
(specifically, if a cell raised an exception or loaded from another cache)
are taken into account.

Because marimo's cache key construction can fall back to source code for
closed-over variables, closing over variables lets you cache functions even in
the presence of non-hashable and non-pickleable arguments.

## Limitations

marimo's cache has some limitations:

- Side effects are not cached. This means that on a cache hit, side effects like printing, file I/O, or network requests will not occur.
- The source code of imported modules is not used when computing the cache key.
    - By setting `pin_modules` to `True`, you can ensure that the cache is invalidated when module versions change (`e.g.`, update when the module's `__version__` attribute changes).
    - This limitation does not apply if the external module is a marimo notebook.
- The return values of persistently cached functions must be serializable with pickle.

<!--!!! note "Persistent cache invalidation across marimo library versions"-->
<!--    marimo promises not to invalidate caches across patch (e.g. `0.x.y` ->-->
<!--    `0.x.z`) versions of the library. Between minor (`0.a.b` -> `0.c.0`) and major-->
<!--    (`0.a.b` -> `1.0.0`) versions of marimo, old persistent cache hits may become-->
<!--    invalid. A notice will be provided in the release notes when this occurs.-->
<!--    Overall, the caching mechanism is expected to be stable.-->
<!---->

!!! warning "Don't mutate variables"
    marimo works best when you don't mutate variables across cells. The same
    is true for caching, since the cache key may not always be able to take
    mutations into account.


### Decorators defined in other Python modules

Decorators defined in other Python modules that do not use `functools.wraps`
cannot be correctly cached. This can lead to confusing bugs like the example
below:


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

The fix is to make sure the decorator uses `functools.wraps`:

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
## Comparison with `functools.cache`

Here is a table comparing marimo's cache with `functools.cache`:

| Feature | marimo cache  | `functools.cache` |
|-------- | ------------------|-----------------|
| Cache return values in memory? | ✅ | ✅ |
| Cache return values to disk?| ✅ | ❌  |
| Preserved on cell re-runs? | ✅ | ❌ |
| Tracks closed-over variables | ✅ | ❌ |
| Allows unhashable arguments? | ✅ | ❌ |
| Allows Array-like arguments? | ✅ | ❌ |
| Suitable for lightweight functions (microseconds)? | ❌  | ✅ |


!!! tip "When to use `functools.cache`"
    Prefer `functools.cache` for extremely lightweight functions
    (that execute in less than a millisecond). Using memoization to calculate
    the Fibonacci sequence is a classic example of using `functools.cache`
    effectively. On a basic macbook in pure python, `fib(35)` takes 1 second to
    compute; with `mo.cache` it takes 0.000229 seconds; with `functools.cache`, it
    takes 0.000025 seconds (x9 faster!!). Although relatively small, the additional overhead of
    `mo.cache` (and more so `mo.persistent_cache`) is larger than
    `functools.cache`. If your function takes more than a few milliseconds to
    compute, the difference is negligible.


## Tips

### Isolate cached code blocks to their own cells

Isolating cached functions in separate cells improves cache reliability. When
dependencies and cached functions are in the same cell, any change to the cell
invalidates the cache, even if the cached function itself hasn't changed.
Separating them ensures the cache is only invalidated when the function
actually changes.

**Don't do this:**
```python
# Cell 1
llm_client = ...
@mo.cache
def prompt_llm(query, **kwargs):
    message = {"role": "user", "content": query}
    return llm_client.chat.completions.create(messages=[message], **kwargs)
```

**Do this instead:**

```python
# Cell 1
llm_client = ...
```

```python
# Cell 2
@mo.cache
def prompt_llm(query, **kwargs):
    message = {"role": "user", "content": query}
    return llm_client.chat.completions.create(messages=[message], **kwargs)
```

### Close over unhashable or un-pickleable arguments

The [cache key](#cache-key) is constructed in part by hashing or pickle-ing function arguments. When you call a cached function with arguments that cannot be processed in this way, an exception will be raised. To parametrize cached functions with unhashable or un-pickleable arguments, syntactically close over them instead.

**You can't do this:**
```python
# Cell 1
@mo.cache
def query_database(query, engine):
    return engine.execute(query)
```

```python
# This won't work because my_database_engine is not hashable
query_database("SELECT * FROM my_table", my_database_engine)
```

Instead, you can close over `my_database_engine`:

**Do this:**

```python
# Cell 1
my_database_engine = ...
```

```python
# Cell 2
@mo.cache
def query_database(query):
    return my_database_engine.execute(query)
```

### Close-over low-memory-footprint variables

Non-primitive closed-over variables are serialized for cache key generation.
When possible, compute derived values (like length) outside the cache block and
only use the small values inside.

**Don't do this:**
```python
with mo.persistent_cache("bad example"):
    length = len(my_very_large_dataset)
    ... # uses length
```

**Do this instead:**
```python
length = len(my_very_large_dataset)  # my_very_large_dataset is not needed for cache invalidation
```

```python
with mo.persistent_cache("good example"):
    ... # uses length
```


### Use `mo.watch.file` when working with files

**Don't do this:**
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
```

```python
# Cell 2
with mo.persistent_cache("my_file"):
    data = my_file.read()
    # Do something with data
```

## API

::: marimo.cache
::: marimo.lru_cache
::: marimo.persistent_cache


