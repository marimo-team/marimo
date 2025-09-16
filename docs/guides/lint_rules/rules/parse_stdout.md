# MF002: parse-stdout

✨ **Formatting** ❌ Not Fixable

MF002: Parse captured stdout during notebook loading.

## What it does

Captures and parses stdout output during notebook loading, looking for
structured warning messages that include file and line number references.
Creates diagnostics from any warnings or messages found.

## Why is this bad?

While stdout output doesn't prevent execution, it often indicates:
- Deprecation warnings from imported libraries
- Configuration issues
- Potential compatibility problems
- Code that produces unexpected side effects during import

## Examples

**Captured stdout:**
```
notebook.py:15: DeprecationWarning: 'imp' module is deprecated
```

**Result:** Creates a diagnostic pointing to line 15 with the deprecation warning.

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)

