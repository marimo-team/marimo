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
    def simple_echo_model(messages, config):
        return f"You said: {messages[-1].content}"

    chat = mo.ui.chat(
        simple_echo_model,
        prompts=["Hello", "How are you?"],
        show_configuration_controls=True
    )
    None
    return

@app.cell
def __():
    mo.ui.tabs(
        {
            "📈 Sales": bar,
            "📊 Data Explorer": chat,
            "💻 Settings": mo.ui.text(placeholder="Key"),
        }
    )
    return
```

///

::: marimo.ui.tabs
