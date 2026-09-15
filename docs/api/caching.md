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
def compute_embedding(data: str, embedding_dimension: int, model: str) -> np.ndarray:
    ...
```

///

/// tab | `mo.cache` (async)

```python
import marimo as mo

@mo.cache
async def fetch_data(url: str, params: dict) -> dict:
    response = await http_client.get(url, params=params)
    return response.json()
```

///

/// tab | `mo.persistent_cache` (async)

```python
import marimo as mo

@mo.persistent_cache
async def compute_embedding(data: str, embedding_dimension: int, model: str) -> np.ndarray:
    response = await llm_client.get_embeddings(data, model)
    return response.embeddings
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

!!! note "Async functions are fully supported"
    All cache decorators (`mo.cache`, `mo.lru_cache`, `mo.persistent_cache`) work
    seamlessly with both synchronous and asynchronous functions. When multiple
    concurrent calls are made to a cached async function with the same arguments,
    only one execution occurs—the rest await the result. This prevents race conditions
    and duplicate work.

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

## Automatic cell caching

`mo.cache` and `mo.persistent_cache` are opt-in per function or code block. marimo
also has a notebook-wide mechanism that automatically attempts to cache
**every** executed cell, not just the ones you have explicitly decorated.

Enable it with:

```toml title="pyproject.toml"
[tool.marimo.runtime]
cache_cells = true
```

!!! tip "Configuring for your project"
    Set the above snippet in your notebook's `pyproject.toml` as shown above,
    or directly in your notebooks' PEP 723 metadata.

With `cache_cells` enabled, marimo attempts to save and restore every cell's
state on notebook restart. On a cache hit, marimo skips re-running the cell and
hydrates its variables from a stored stub instead. If a stub cannot be hydrated
(for example, its value is not hashable or serializable), marimo invalidates
the cache for that cell and its producing ancestors, then re-runs them live.
You do not need to clear anything manually.

!!! warning "Experimental"
    UI elements defined by a cached cell are not currently restored from
    cache on a cache hit, which forces a live re-run of that cell. Smarter
    caching (skipping cells where caching itself is slow) and
    surfacing more information about cache hits and misses in the UI are
    planned but not yet implemented.

Cached cell execution is also what powers [cached WASM
exports](../guides/exporting/webassembly_html.md#exporting-with-cached-execution),
which let you publish notebooks whose expensive or browser-incompatible cells
were computed elsewhere beforehand.

!!! tip "Further reading"
    For more on the design of marimo's caching, see our SciPy paper
    (currently under peer review):
    [github.com/scipy-conference/scipy_proceedings/pull/1262](https://github.com/scipy-conference/scipy_proceedings/pull/1262)

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

## Cache signing and trust

Restoring a persistent cache entry deserializes it with `pickle`, which runs
whatever code the entry tells it to. Reading a cache someone else wrote therefore
means running code they chose.

The lazy loader defends against that. It signs each entry it writes with an
[Ed25519](https://ed25519.cr.yp.to/) signing key, and checks the signature before
restoring one. An entry that does not verify against a key you trust is
recomputed instead of loaded.

Signing applies to `method="lazy"` only:

```python
with mo.persistent_cache("my_cache", method="lazy"):
    ...
```

The default, `method="pickle"`, neither signs on write nor verifies on read, so a
cache it wrote carries no provenance at all. Prefer the lazy loader for any cache
that might be read on a machine other than the one that wrote it.

On a local cache you configure nothing: the lazy loader signs with a
machine-local key it creates on first use, so your own entries verify and a cache
written elsewhere does not.

### Sharing a cache between machines

To read entries written on another machine — a continuous integration (CI) job
that populates a shared store, or a colleague's cache — name whose key you trust.
A key is identified by its *fingerprint*: `"SHA256:"` followed by base64, in the
style of a Secure Shell (SSH) key fingerprint.

```toml title="~/.config/marimo/marimo.toml"
[signing]
# This machine's signing identity.
private_key_path = "~/.marimo/cache_key.pem"

[signing.trusted_signers]
# fingerprint = label. The label is a note to yourself; only the
# fingerprint decides anything.
"SHA256:kV9x2c...q8" = "CI cache key"
"SHA256:abc9f1...4d" = "Alice"
```

Two environment variables set the same thing without a config file:
`MARIMO_CACHE_SIGNING_PRIVATE_KEY` holds a signing identity, and
`MARIMO_CACHE_SIGNING_PUBLIC_KEY` adds one trusted key. Both take the key itself
in Privacy-Enhanced Mail (PEM) form, not a path.

!!! danger "Trusting a key grants code execution"
    Restoring a cache entry deserializes it with `pickle`, so trusting a
    fingerprint lets whoever holds that key run arbitrary code on your machine.
    There is no narrower "cache-only" version of this grant. Add a fingerprint
    only if you would run a script that person handed you.

### Verification settings

```toml title="~/.config/marimo/marimo.toml"
[cache]
verification = "on"  # "off" | "on" | "strict"
```

| Cache entry | `off` | `on` (default) | `strict` |
|---|---|---|---|
| Trusted key, valid signature | served | served | served |
| Foreign key, bad signature, or unsigned | served **unchecked** | **miss** — recomputed | **raises** |
| On write | not signed | signed | signed |

`off` is the only setting that hands you unverified bytes while signing is
available. Under `on`, an entry that cannot be verified is treated as a cache
miss, so the cost of a foreign entry is recomputing it. Under `strict` the read
raises instead. Prefer `strict` in continuous integration, where a cache that
quietly stops hitting is a problem you would rather be told about.

Without the `cryptography` package marimo can neither sign nor verify, so
`strict` raises as soon as the cache is created. Under `on` what happens depends
on where the entries live. A cache directory on your own filesystem is still
served, because reading it already takes the same file access as reading the
notebook. A shared or remote store is the case signing protects, so there every
read misses and every write is skipped. Install `marimo[recommended]` to get
`cryptography`.

Notebooks running in the browser under WebAssembly never verify. Their cache
blobs come from the same origin as the notebook code, so swapping one already
requires control of the notebook itself.

### Where trust can be configured

`[signing]` and `[cache].verification` are read from your user configuration
only — the file at `~/.config/marimo/marimo.toml` or `~/.marimo.toml`. marimo
ignores them in `pyproject.toml`, in notebook script metadata, and in a
`.marimo.toml` that sits inside a project directory.

Those three files travel with the code. A repository that could name its own
signing key as trusted, or turn verification off, could commit a poisoned cache
entry that runs the first time you open the notebook — the attack signing exists
to prevent.

`[cache].store` is different: a `pyproject.toml` may still choose the store,
because the bytes a store returns are verified before anything is deserialized.
The one loader that does not verify, `method="pickle"`, refuses a store chosen by
a project and falls back to the default. A `.marimo.toml` inside a project cannot
set the store at all, because it loads at the same precedence as your user
configuration and so cannot be told apart from it later.

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
| Supports async functions? | ✅ | ❌ |
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


