# MB001: unparsable-cells

🚨 **Breaking** ❌ Not Fixable

MB001: Cell contains unparsable code.

## What it does

Identifies cells that cannot be parsed into valid Python AST nodes, indicating
fundamental syntax or encoding problems that prevent the notebook from being loaded.

## Why is this bad?

Unparsable cells prevent the notebook from running as a script and will throw
errors when executed in notebook mode. While marimo can still open the notebook,
these cells cannot be run until the parsing issues are resolved.

## Examples

**Problematic:**
```python
# Cell with encoding issues or corrupt data
x = 1 \x00\x01\x02  # Binary data in source
```

**Problematic:**
```python
# Cell with fundamental syntax errors
def func(
    # Missing closing parenthesis and body
```

**Solution:**
```python
# Fix syntax errors and encoding issues
def func():
    return 42
```

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)

