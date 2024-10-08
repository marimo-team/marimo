# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.4.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        "This notebook covers a couple different cases for rendering plotly under different configs and with different renderers."
    )
    return


@app.cell
def __():
    import marimo as mo
    import plotly.io as pio

    pio.renderers.default = "notebook"
    pio.renderers["notebook"].config["scrollZoom"] = True
    pio.renderers["notebook"].config["editable"] = True
    return mo, pio


@app.cell
def __(pio):
    pio.renderers.default
    return


@app.cell
def __(pio):
    pio.renderers[pio.renderers.default].config
    return


@app.cell
def __(mo, pio):
    keys = list(pio.renderers.keys())


    def get_config(renderer):
        try:
            return str(renderer.config)
        except:
            return "none"


    printed_configs = [
        {"name": key, "config": get_config(pio.renderers[key])} for key in keys
    ]
    mo.ui.table(printed_configs)
    return get_config, keys, printed_configs


@app.cell
def __(pio):
    pio.renderers
    return


@app.cell
def __():
    import plotly.express as px

    x_data = [1, 2, 3, 4, 5, 6]
    y_data = [1, 2, 3, 2, 3, 4]
    fig = px.scatter(x=x_data, y=y_data)
    return fig, px, x_data, y_data


@app.cell
def __(fig):
    fig  # Uses the default renderer "notebook"
    return


@app.cell
def __(fig, mo):
    mo.ui.plotly(fig)  # Uses the default renderer "notebook"
    return


@app.cell
def __(fig, mo):
    mo.ui.plotly(fig, config={})  # Uses the empty config
    return


@app.cell
def __(fig, mo):
    mo.ui.plotly(fig, config={"staticPlot": True})  # Uses the passed config
    return


@app.cell
def __(fig, mo):
    mo.ui.plotly(fig, renderer_name="browser")  # Uses a pre-defined rendererer
    return


if __name__ == "__main__":
    app.run()
