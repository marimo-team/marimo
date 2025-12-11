# MF007: markdown-indentation

✨ **Formatting** 🛠️ Fixable

MF007: Markdown strings in `mo.md()` should be properly indented.

## What it does

Checks cells containing `mo.md()` calls to see if the markdown string
content has unnecessary leading whitespace that should be removed.

## Why is this bad?

Indented markdown strings:
- Are harder to read when viewing the source code
- Produce larger diffs when making changes
- Don't match the standard marimo formatting style
- Can be confusing when the indentation doesn't reflect the markdown structure

## Examples

**Problematic:**
```python
mo.md(
    r"""
    # Title

    Some content here.
    """
)
```

**Solution:**
```python
mo.md(r"""
# Title

Some content here.
""")
```

**Note:** This fix is automatically applied with `marimo check --fix`.

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
- [Best Practices](https://docs.marimo.io/guides/best_practices/)

