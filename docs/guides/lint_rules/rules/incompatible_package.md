# MW003: incompatible-package

🌐 **WASM** ❌ Not Fixable

MW003: Packages in the dependency tree incompatible with WASM.

## What it does

Reads the notebook's PEP 723 `dependencies`, filters out requirements
whose PEP 508 markers exclude Emscripten (for example
`torch; sys_platform != 'emscripten'`), walks their transitive
dependency tree via installed metadata, then queries PyPI's JSON API
to check whether each package has a `py3-none-any`, `emscripten`, or
`wasm32` wheel available. Packages only in pyodide-lock.json are also accepted.

For a package that Pyodide ships, the version in pyodide-lock.json is
the only version the browser can install. If the notebook's specifier
excludes that version, the rule reports the mismatch.

## Why is this bad?

Pyodide can only install pure-Python wheels via micropip, or packages
that are pre-built in the Pyodide distribution. Packages with only
platform-specific native wheels will fail to install in the browser.

A specifier that excludes the Pyodide build cannot be honored there.
`marimo export html-wasm` rewrites it to the lockfile version, so the
pin in the source notebook is misleading; in the browser without that
rewrite, micropip rejects the whole install, including every other
dependency listed alongside it.

## Examples

**Problematic:**
```python
import jax  # jaxlib (transitive dep) has only native wheels
```

**Problematic:**
```python
# /// script
# dependencies = ["numpy==1.26.0"]  # Pyodide ships numpy 2.4.3
# ///
```

**Not flagged:**
```python
import numpy  # Native, but pre-built in Pyodide
```

**Not flagged:**
```python
import requests  # Pure Python wheel on PyPI
```

**Not flagged (PEP 723 metadata):**
```python
# /// script
# dependencies = ["jax; sys_platform != 'emscripten'"]
# ///
# jax is excluded from WASM checks via PEP 508 marker
```

## References

- https://pyodide.org/en/stable/usage/packages-in-pyodide.html
- https://peps.python.org/pep-0508/ (environment markers)
- https://peps.python.org/pep-0783/ (Emscripten wheels on PyPI)

