# Button

!!! tip "Looking for a submit/run button?"
    If you're looking for a button to trigger computation on click, consider
    using [`mo.ui.run_button`](../api/inputs/run_button.md).

```python
    @app.cell
    def __():
        mo.ui.button(label="Click me")
        return
```

::: marimo.ui.button
