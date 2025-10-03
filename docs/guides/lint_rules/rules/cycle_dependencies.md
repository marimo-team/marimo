# MB003: cycle-dependencies

🚨 **Breaking** ❌ Not Fixable

MB003: Cells have circular dependencies.

## What it does

Analyzes the dependency graph to detect circular references between cells,
where cells depend on each other in a way that creates an impossible
execution order.

## Why is this bad?

Circular dependencies prevent marimo from:
- Determining a valid execution order
- Running notebooks reproducibly
- Executing notebooks as scripts
- Providing reliable reactive updates

This is a breaking error because it makes the notebook non-executable.

## Examples

**Problematic:**
```python
# Cell 1
a = b + 1  # Reads b

# Cell 2
b = a + 1  # Reads a -> Cycle!
```

**Solution:**
```python
# Cell 1
a = 1

# Cell 2
b = a + 1  # Unidirectional dependency
```

## References

- [Cycles Guide](https://docs.marimo.io/guides/understanding_errors/cycles/)
- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)

