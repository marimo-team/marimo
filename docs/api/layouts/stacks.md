# Stacks

```{eval-rst}
.. marimo-embed::
    :size: large

    @app.cell
    def __():
        def create_box(num=1):
            box_size = 30 + num * 10
            return mo.Html(
                f"<div style='min-width: {box_size}px; min-height: {box_size}px; background-color: orange; text-align: center; line-height: {box_size}px'>{str(num)}</div>"
            )


        boxes = [create_box(i) for i in range(1, 5)]
        return

    @app.cell
    def __():
        justify = mo.ui.dropdown(
            ["start", "center", "end", "space-between", "space-around"],
            value="space-between",
            label="justify",
        )
        align = mo.ui.dropdown(
            ["start", "center", "end", "stretch"], value="center", label="align"
        )
        gap = mo.ui.number(start=0, step=0.25, stop=2, value=0.25, label="gap")
        wrap = mo.ui.checkbox(label="wrap")
        return

    @app.cell
    def __():
        horizontal = mo.hstack(
            boxes,
            align=align.value,
            justify=justify.value,
            gap=gap.value,
            wrap=wrap.value,
        )
        vertical = mo.vstack(
            boxes,
            align=align.value,
            gap=gap.value,
        )

        mo.vstack(
            [
                mo.hstack([justify, align, gap], justify="center"),
                horizontal,
                mo.md("-----------------------------"),
                vertical,
            ],
            align="stretch",
            gap=1,
        )
        return

```

```{eval-rst}
.. autofunction:: marimo.hstack
```

```{eval-rst}
.. autofunction:: marimo.vstack
```
