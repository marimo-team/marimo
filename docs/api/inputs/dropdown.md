# Dropdown

/// marimo-embed

```python
@app.cell
def __():
    dropdown = mo.ui.dropdown(options=["Apples", "Oranges", "Pears"], label="choose fruit")
    dropdown_dict = mo.ui.dropdown(options={"Apples":1, "Oranges":2, "Pears":3},
                            value="Apples", # initial value
                            label="choose fruit with dict options")
    return

@app.cell
def __():
    mo.vstack([mo.hstack([dropdown, mo.md(f"Has value: {dropdown.value}")]),
    mo.hstack([dropdown_dict, mo.md(f"Has value: {dropdown_dict.value} and selected_key {dropdown_dict.selected_key}")]),
                ])
    return
```

///

::: marimo.ui.dropdown
