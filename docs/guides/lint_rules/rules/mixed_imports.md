# MR005: mixed-imports

**Runtime**. Not automatically fixable.

MR005: Imports mixed with literal configuration assignments.

## What it does

Detects cells containing imports and assignments of literal values to
simple names. Setup cells, cells containing other statements and cells
whose assignments depend on imported names are excluded.

## Why is this bad?

marimo handles import-only cells incrementally: adding a new import does
not rerun cells that depend on unchanged imports. Adding a configuration
assignment to the same cell disables this optimization. Editing that cell
can then rerun expensive computations that depend on its imports, even
when those imports have not changed.

Keep imports in their own cell and configuration in a separate cell to
preserve incremental imports. No automatic fix is provided because
splitting cells changes when their code runs. If grouping the statements
is intentional, ignore `MR005` in your lint configuration.

## Examples

**Problematic:**
```python
import math

THRESHOLD = 10
```

**Solution:**
```python
# One cell
import math
```

```python
# Another cell
THRESHOLD = 10
```

## References

- [Reactivity](https://docs.marimo.io/guides/reactivity/)
