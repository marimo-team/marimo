# MR003: reusable-definition-order

⚠️ **Runtime** ⚠️ Unsafe Fixable

MR003: Invalid ordering of potentially reusable definitions.

## What it does

marimo serializes reusable definitions in notebook order. Like all python
scripts, a reusable function cannot refer to a variable that has _not yet
been defined_. While ordering in marimo normally doesn't matter, for reuse
as a module or script, dependent top level definitions must be ordered
correctly.

This rule flags and fixes function or class definitions that would normally
be saved as "reusable", but cannot due to cell ordering.

## Why is this bad?

When a reusable definition depends on another reusable definition declared
later in the notebook:

- the definition cannot be serialized as reusable
- imports from other notebooks or Python modules may fail

## Examples

**Problematic:**
```python
@app.function
def uses_offset(x: int = offset()) -> int:
    # This will run in marimo, but will cause an error if run as a script!
    # `offset` is not defined!
    return x + 1


@app.function
def offset() -> int:
    return 1
```

**Problematic:**
```python
@app.cell
def _():
    # This could be reusable if it was defined after `decorate`.
    class Wrapped:
        @decorate
        def value(self) -> int:
            return 1


@app.function
def decorate(fn):
    return fn
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

