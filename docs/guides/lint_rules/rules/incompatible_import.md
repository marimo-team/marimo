# MW001: incompatible-import

🌐 **WASM** ❌ Not Fixable

MW001: Importing modules unavailable in WASM/Pyodide.

## What it does

Checks each cell's imports against stdlib modules that don't work in
Pyodide, plus multiprocessing exports and submodules that require shared
memory, managers, pipes, or native synchronization.

## Why is this bad?

WASM notebooks run in the browser via Pyodide, which cannot support
modules that depend on OS-level process control, terminal I/O, native
GUI toolkits, shared memory, pipes, or native synchronization. These
imports can raise ImportError or fail at runtime. WASM-compatible
multiprocessing adapters such as `Process`, `Queue`, `SimpleQueue`,
`Pool`, and `ProcessPoolExecutor` remain allowed.

## Examples

**Problematic:**
```python
import subprocess

result = subprocess.run(["ls"])
```

**Problematic:**
```python
from multiprocessing import Pipe
```

**Solution:**
Remove the import or replace it with a WASM-compatible alternative.

## References

- https://pyodide.org/en/stable/usage/wasm-constraints.html
