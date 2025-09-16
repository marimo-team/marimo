# MB004: setup-cell-dependencies

🚨 **Breaking** ❌ Not Fixable

MB004: Setup cell cannot have dependencies.

## What it does

Validates that the setup cell (if present) does not depend on variables
defined in other cells, ensuring proper execution order.

## Why is this bad?

Setup cell dependencies break marimo's execution model because:
- The setup cell must run first to initialize the notebook
- Dependencies on other cells would create impossible execution order
- It violates the setup cell's purpose as initialization code

This is a breaking error because it makes the notebook non-executable.

## Examples

**Problematic:**
```python
# Setup cell
y = x + 1  # Error: setup depends on other cells

# Cell 1
x = 1
```

**Solution:**
```python
# Setup cell
y = 1  # Setup defines its own variables

# Cell 1
x = y + 1  # Other cells can use setup variables
```

## References

- [Setup References Guide](https://docs.marimo.io/guides/understanding_errors/setup/)
- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)

