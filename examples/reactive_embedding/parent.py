import marimo

__generated_with = "0.17.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    from child_1 import app as child_1_app
    from child_2 import app as child_2_app
    return child_1_app, child_2_app, mo


@app.cell
def _(mo):
    x_slider = mo.ui.slider(0, 20, 1, label="parent.x", full_width=True, show_value=True)
    return (x_slider,)


@app.cell
def _(x_slider):
    x = x_slider.value
    return (x,)


@app.cell
def _(mo):
    y_slider = mo.ui.slider(0, 20, 1, label="parent.y", full_width=True, show_value=True)
    return (y_slider,)


@app.cell
def _(y_slider):
    y = y_slider.value
    return (y,)


@app.cell
async def _(child_1_app, x):
    embed_1_result = await child_1_app.embed(
        expose={"x": x},
        namespace="parent",
        readonly=True
    )
    return (embed_1_result,)


@app.cell
async def _(child_2_app, x, y):
    embed_2_result = await child_2_app.embed(
        expose={"x": x, "y": y},
        namespace="parent",
        readonly=True
    )
    return (embed_2_result,)


@app.cell
def _(embed_1_result, embed_2_result, mo, x_slider, y_slider):
    mo.callout(
        mo.vstack([
            mo.md("### Parent"),
            x_slider,
            y_slider,
            mo.md(f"I see **child_1.v** = {embed_1_result.defs['v']}"),
            mo.md(f"I see **child_2.a** = {embed_2_result.defs['a']}"),
            embed_1_result.output,
            embed_2_result.output,
        ])
    )
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
