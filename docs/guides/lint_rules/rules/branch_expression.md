# MR002: branch-expression

⚠️ **Runtime** ❌ Not Fixable

MR002: Branch statements with output expressions that won't be displayed.

## Why is this bad?

When output expressions are nested inside branches at the end of a cell:
- The expressions execute but produce no visible output
- Users expect to see the result (like mo.md(), string literals, etc.)
- This can lead to confusion about whether code is running correctly
- It violates the principle of least surprise

This is a runtime issue because it causes unexpected behavior where the user's
intended output is silently ignored.

## Examples

**Problematic:**
```python
if condition:
    mo.md("Result A")  # Won't be displayed
else:
    mo.md("Result B")  # Won't be displayed
```

**Problematic:**
```python
match value:
    case 1:
        "Too short"  # Won't be displayed
    case _:
        value  # Won't be displayed
```

**Not flagged:**
```python
if condition:
    print("Debug message")  # Function calls
```

**Solution:**
```python
# Assign to a variable that marimo will display
result = mo.md("Result A") if condition else mo.md("Result B")
result
```

**Solution:**
```python
# Create a default variable for response.
result = None
if condition:
    result = expr
else:
    result = other
result
```

**Alternative Solution (if no output intended):**
```python
# Use a dummy variable to indicate intentional suppression
if condition:
    _ = expr
else:
    _ = other
```

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
- [Reactivity](https://docs.marimo.io/guides/reactivity/)

