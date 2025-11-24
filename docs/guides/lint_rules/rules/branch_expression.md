# MR002: branch-expression

⚠️ **Runtime** ❌ Not Fixable

MR002: Branch statements ending with expressions that won't be displayed.

## Why is this bad?

When expressions are nested inside branches at the end of a cell:
- The expressions execute but produce no visible output
- Users may expect to see the result (like `mo.md()` calls) but won't
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
        "Just right"  # Won't be displayed
```

**Problematic:**
```python
if invalid:
    mo.md("Error message")  # Won't be displayed even without else clause
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
    result = expr()
else:
    result = other()
result
```

In the case where no output is expected:

**Alternative Solution:**
```python
# Use a dummy variable to indicate intentional suppression
if condition:
    _ = print("Result A")
else:
    _ = print("Result B")
```

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
- [Reactivity](https://docs.marimo.io/guides/reactivity/)

