# MR003: reusable-definition-order

⚠️ **Runtime** ⚠️ Unsafe Fixable

MR003: Reusable definitions depending on later reusable definitions.

## What it does

marimo serializes reusable definitions in notebook order. This rule runs
full-notebook top-level extraction and flags reusable definitions that fail
specifically because another reusable definition is declared later.

The notebook still runs, but the affected definition is no longer reusable
for export or import into another notebook or Python module.

## Why is this bad?

When a reusable definition depends on another reusable definition declared
later in the notebook:

- the definition cannot be serialized as reusable
- imports from other notebooks or Python modules may fail
- the notebook order no longer reflects the dependency order needed for
  reuse

This is a runtime issue because it affects reusability and portability,
not basic notebook execution.

## Examples

**Problematic:**
```python
@app.function
def uses_offset(x: int = offset()) -> int:
    return x + 1


@app.function
def offset() -> int:
    return 1
```

**Problematic:**
```python
@app.class_definition
class Wrapped:
    @decorate
    def value(self) -> int:
        return 1


@app.function
def decorate(fn):
    return fn
```

**Not flagged:**
```python
@app.cell
def _(scale):
    def local_only(x: int = scale) -> int:
        return x + 1
    return
```

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
- [setup](https://docs.marimo.io/guides/understanding_errors/setup/)
- [Reusing functions](https://docs.marimo.io/guides/reusing_functions/)

## Solution

Move the referenced reusable definitions earlier in the notebook so they
appear before the reusable definition that depends on them.

```python
@app.function
def offset() -> int:
    return 1


@app.function
def uses_offset(x: int = offset()) -> int:
    return x + 1
```

## Unsafe fix

This rule can be fixed with:

```bash
marimo check --fix --unsafe-fixes my_notebook.py
```

The unsafe fix reorders the provider cells earlier in the notebook. This
is marked unsafe because changing cell order changes the document
structure, even when the resulting notebook is still valid.

Setup cells are not moved by this fix.

