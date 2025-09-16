# MB002: multiple-definitions

🚨 **Breaking** ❌ Not Fixable

MB002: Multiple cells define the same variable.

## What it does

Analyzes the dependency graph to detect variables that are defined in more
than one cell, which violates marimo's fundamental constraint for reactive execution.

## Why is this bad?

Multiple definitions prevent marimo from:
- Determining the correct execution order
- Creating a reliable dependency graph
- Running notebooks as scripts
- Providing consistent reactive updates

This is a breaking error because it makes the notebook non-executable.

## Examples

**Problematic:**
```python
# Cell 1
x = 1

# Cell 2
x = 2  # Error: x defined in multiple cells
```

**Solution:**
```python
# Cell 1
x = 1

# Cell 2
y = 2  # Use different variable name
```

## References

- [Multiple Definitions Guide](https://docs.marimo.io/guides/understanding_errors/multiple_definitions/)
- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)

