# MF004: empty-cells

✨ **Formatting** ⚠️ Unsafe Fixable

MF004: Empty cells that can be safely removed.

## What it does

Detects cells that contain only:
- Whitespace characters (spaces, tabs, newlines)
- Comments (lines starting with #)
- Pass statements (`pass`)
- Any combination of the above

## Why is this bad?

Empty cells can:
- Create clutter in notebook structure
- Add unnecessary complexity to the execution graph
- Make notebooks harder to read and maintain
- Increase file size without adding value

While not functionally breaking, removing empty cells improves code
clarity and reduces visual noise.

## Examples

**Problematic:**
```python
# Cell 1: Only whitespace
```

**Problematic:**
```python
# Cell 2: Only comments
# This is just a comment
# Nothing else here
```

**Problematic:**
```python
# Cell 3: Only pass statement
pass
```

**Problematic:**
```python
# Cell 4: Mix of comments, whitespace, and pass
# Some comment

pass
# Another comment
```

**Note:** This fix requires `--unsafe-fixes` because removing cells changes
the notebook structure, and potentially removes user-intended content.

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
- [Best Practices](https://docs.marimo.io/guides/best_practices/)

