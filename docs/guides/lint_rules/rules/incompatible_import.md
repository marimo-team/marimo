# MW001: incompatible-import

🌐 **WASM** ❌ Not Fixable

MW001: Importing modules unavailable in WASM/Pyodide.

## What it does

Checks each cell's imports against a blocklist of stdlib modules that
either don't exist in Pyodide or are stubs that fail at runtime.

## Why is this bad?

WASM notebooks run in the browser via Pyodide, which cannot support
modules that depend on OS-level process control, terminal I/O, or
native GUI toolkits. Importing these modules will raise ImportError
or produce broken stubs.

## Examples

**Problematic:**
```python
import subprocess

result = subprocess.run(["ls"])
```

**Problematic:**
```python
from multiprocessing import Pool
```

**Solution:**
Remove or replace the import with a WASM-compatible alternative.

## References

- https://pyodide.org/en/stable/usage/wasm-constraints.html

