# Tabs

/// marimo-embed
    size: large

```python
@app.cell
def __():
    import matplotlib.pyplot as plt
    import numpy as np

    # Generate some random data
    categories = ["A", "B", "C", "D", "E"]
    values = np.random.rand(5)

    bar = plt.bar(categories, values)
    plt.title("Random Bar Chart")
    plt.xlabel("Categories")
    plt.ylabel("Values")
    None
    return

@app.cell
def __():
    mo.ui.tabs(
        {
            "📈 Sales": bar,
            "📊 Subscriptions": bar,
            "💻 Settings": mo.ui.text(placeholder="Key"),
        }
    )
    return
```

///

::: marimo.ui.tabs
