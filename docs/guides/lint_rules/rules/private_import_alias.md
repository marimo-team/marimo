# MR004: private-import-alias

⚠️ **Runtime** ❌ Not Fixable

MR004: Import aliased to a private (underscore-prefixed) name.

## What it does

Scans import statements for an explicit `as` alias whose bound name starts
with an underscore. This pattern is an undesirable but common workaround for
marimo's global redefinition restriction with little tangible payoff.

## Why is this bad?

Aliasing an import to a private name doesn't give the benefits users
expect from it:

- Imported modules are registered in `sys.modules` regardless of the
  name they're bound to, so marimo's private-variable cleanup doesn't
  free any extra memory.
- Common imports like `numpy`, `pandas`, and `os` are usually needed in
  multiple cells, and giving them a private name defeats reuse while
  adding clutter.

If the goal is to avoid the import polluting cell-to-cell dependencies, the
fix is a setup cell, or import only cell instead. Setup cells run once,
ahead of every other cell, while import only cells don't trigger
re-execution of dependent cells (imports resolve independently of the
notebook's reactive dataflow). Both of these approaches are preferable to
aliasing imports to private names. You may even consider import only setup
cells!

## Examples

**Problematic:**
```python
import os as _os

_os.listdir(".")
```

```python
import os as _os

_os.getcwd()
```

**Problematic:**
```python
from collections import OrderedDict as _OrderedDict
```

**Solution:**
```python
# In the notebook's setup cell
# or any import only cell.
import os
from collections import OrderedDict
```

```python
os.listdir(".")
```

```python
os.getcwd()
```

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
- [Setup cell](https://docs.marimo.io/guides/understanding_errors/setup/)

