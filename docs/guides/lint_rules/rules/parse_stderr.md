# MF003: parse-stderr

✨ **Formatting** ❌ Not Fixable

MF003: Parse captured stderr during notebook loading.

## What it does

Captures stderr output during notebook loading and creates diagnostics
from any error messages or warnings. This helps identify potential
issues that don't prevent parsing but may affect runtime behavior.

## Why is this bad?

Stderr output during parsing often indicates:
- Syntax warnings (like invalid escape sequences)
- Import warnings or errors
- Deprecation notices from libraries
- Configuration issues that might affect execution

While these don't break the notebook, they can lead to unexpected
behavior or indicate code that needs updating.

## Examples

**Captured stderr:**
```
notebook.py:68: SyntaxWarning: invalid escape sequence '\l'
```

**Result:** Creates a diagnostic pointing to line 68 about the invalid escape sequence.

**Common issues:**
- Raw strings needed: `r"\path\to\file"` instead of `"\path\to\file"`
- Deprecated library usage
- Missing import dependencies

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
- [Python Warning Categories](https://docs.python.org/3/library/warnings.html#warning-categories)

