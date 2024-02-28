# Accordion

```{eval-rst}
.. marimo-embed::
    :size: medium

    @app.cell
    def __():
        mo.accordion(
            {
                "Door 1": mo.md("Nothing!"),
                "Door 2": mo.md("Nothing!"),
                "Door 3": mo.md(
                    "![goat](https://images.unsplash.com/photo-1524024973431-2ad916746881)"
                ),
            }
        )
        return
```

```{eval-rst}
.. autofunction:: marimo.accordion
```
