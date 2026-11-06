# Data editor

/// marimo-embed-file
    size: xlarge
    filepath: examples/ui/data_editor.py
///

## Configure column editors

Use `column_types` to show checkboxes with `"boolean"` or restrict a column to a
dropdown with a non-empty list of unique strings. New rows use the first
dropdown option.

```python
editor = mo.ui.data_editor(
    [{"task": "Review", "done": True, "priority": "high"}],
    column_types={
        "done": "boolean",
        "priority": ["low", "medium", "high"],
    },
)
```

::: marimo.ui.data_editor
