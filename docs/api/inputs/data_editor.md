# Data editor

/// marimo-embed-file
    size: xlarge
    filepath: examples/ui/data_editor.py
///

## Dropdown columns

Use `column_types` to restrict a column to a fixed set of string values. The
first option is used when adding a row.

```python
editor = mo.ui.data_editor(
    [{"priority": "low"}, {"priority": "high"}],
    column_types={"priority": ["low", "medium", "high"]},
)
```

::: marimo.ui.data_editor

## Checkbox columns

Use `column_types` to display a column with checkboxes, even when its values
would otherwise be inferred as strings or numbers:

```python
editor = mo.ui.data_editor(
    [{"task": "Review", "done": "yes"}, {"task": "Ship", "done": "no"}],
    column_types={"done": "boolean"},
)
```
