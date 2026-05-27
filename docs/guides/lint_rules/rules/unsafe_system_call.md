# MW002: unsafe-system-call

🌐 **WASM** ❌ Not Fixable

MW002: System calls that fail in WASM/Pyodide.

## What it does

Walks the AST of each cell looking for calls to functions like
`os.system()`, `os.fork()`, `signal.signal()`, and
`breakpoint()` that have no meaningful implementation in WASM.

## Why is this bad?

These functions depend on OS features (process spawning, signal
handling, debugger attachment) that don't exist in a browser
environment. They will raise `OSError`, `NotImplementedError`,
or hang silently.

## Examples

**Problematic:**
```python
import os

os.system("ls")
```

**Problematic:**
```python
breakpoint()
```

**Solution:**
Remove or guard these calls behind a WASM detection check.

## References

- https://pyodide.org/en/stable/usage/wasm-constraints.html

