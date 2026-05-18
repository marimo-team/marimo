# Copyright 2026 Marimo. All rights reserved.
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "wigglystuff==0.5.0",
# ]
# ///

import marimo

__generated_with = "0.23.6"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # External dependencies

    marimo notebooks are Python scripts. That means you can use Python
    standards for scripts, including
    [PEP 723](https://peps.python.org/pep-0723/) inline metadata, to declare
    the Python version and packages that a notebook needs.
    """)
    return


@app.cell(hide_code=True)
def _(check_dependencies):
    check_dependencies()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    This notebook starts with a metadata block like this:

    ```python
    # /// script
    # requires-python = ">=3.12"
    # dependencies = [
    #     "marimo",
    #     "wigglystuff==0.5.0",
    # ]
    # ///
    ```

    Tools that understand PEP 723 can read this block and create an
    environment with the right dependencies. The rest of the file remains a
    regular Python script.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Once a dependency is declared, import it normally in a cell.

    Here we'll use `wigglystuff.Slider2D`, an anywidget, and wrap it with
    `mo.ui.anywidget` so marimo can make it reactive.
    """)
    return


@app.cell
def _(Slider2D, missing_packages, mo):
    if missing_packages:
        widget = None
    else:
        widget = mo.ui.anywidget(
            Slider2D(
                width=320,
                height=320,
                x_bounds=(-2.0, 2.0),
                y_bounds=(-1.0, 1.5),
            )
        )
        widget
    return (widget,)


@app.cell
def _(mo, widget):
    if widget is not None:
        mo.callout(
            f"x = {widget.x:.3f}, y = {widget.y:.3f}; "
            f"bounds {widget.x_bounds} / {widget.y_bounds}"
        )
    return


@app.cell(hide_code=True)
def _(missing_packages, mo):
    module_not_found_explainer = mo.md(
        """
        ## Oops!

        It looks like this environment is missing **wigglystuff**.

        Use the package manager panel on the left to install **wigglystuff**,
        then restart the tutorial. You can also start the notebook with a tool
        that reads PEP 723 script metadata.
        """
    ).callout(kind="warn")

    def check_dependencies():
        if missing_packages:
            return module_not_found_explainer

    return (check_dependencies,)


@app.cell
def _():
    import marimo as mo

    try:
        from wigglystuff import Slider2D

        missing_packages = False
    except ModuleNotFoundError:
        Slider2D = None
        missing_packages = True
    return Slider2D, missing_packages, mo


if __name__ == "__main__":
    app.run()
