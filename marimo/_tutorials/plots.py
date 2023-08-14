# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.0.5"
app = marimo.App()


@app.cell
def __(check_dependencies):
    check_dependencies()
    return


@app.cell
def __(mo):
    mo.md("# Plotting")
    return


@app.cell
def __(mo):
    mo.md(
        """
        marimo supports several popular plotting libraries, including matplotlib,
        plotly, seaborn, and altair. 

        This tutorial gives examples using matplotlib; other libraries are
        used similarly.
        """
    )
    return


@app.cell
def __(mo):
    mo.md("## Matplotlib")
    return


@app.cell
def __(mo):
    mo.md(
        """
        To show a plot, include it in the last expression of a cell (just
        like any other output).

        ```python3
        # create the plot in the last line of the cell
        import matplotlib.pyplot as plt
        plt.plot([1, 2])
        ```
        """
    )
    return


@app.cell
def __(plt):
    plt.plot([1, 2])
    return


@app.cell
def __(mo):
    mo.md(
        """
        ```python3
        # create a plot
        plt.plot([1, 2])
        # ... do some work ...
        # make plt.gca() the last line of the cell
        plt.gca()
        ```
        """
    )
    return


@app.cell
def __(plt):
    plt.plot([1, 2])
    # ... do some work ...
    # make plt.gca() the last line of the cell
    plt.gca()
    return


@app.cell
def __(mo, plt_show_explainer):
    mo.accordion(plt_show_explainer)
    return


@app.cell
def __(mo):
    mo.md(
        """
        **A new figure every cell.** Every cell starts with an empty figure for 
        the imperative `pyplot` API.
        """
    )
    return


@app.cell
def __(np):
    x = np.linspace(start=-4, stop=4, num=100, dtype=float)
    return x,


@app.cell
def __(plt, x):
    plt.plot(x, x)
    plt.plot(x, x**2)
    plt.gca()
    return


@app.cell
def __(plt, x):
    plt.plot(x, x**3)
    return


@app.cell
def __(mo):
    mo.md(
        """
        To build a figure over multiple cells, use the object-oriented API and
        create your own axis:
        """
    )
    return


@app.cell
def __(plt, x):
    _, axis = plt.subplots()
    axis.plot(x, x)
    axis.plot(x, x**2)
    axis
    return axis,


@app.cell
def __(axis, x):
    axis.plot(x, x**3)
    axis
    return


@app.cell
def __(mo):
    mo.md(
        """
        ### Draw plots interactively

        Draw plots interactively by parametrizing them with UI elements.
        """
    )
    return


@app.cell
def __(mo):
    exponent = mo.ui.slider(1, 5, value=1, step=1, label='exponent')

    mo.md(
        f"""
        **Visualizing powers.**

        {exponent}
        """
    )
    return exponent,


@app.cell
def __(exponent, mo, plt, x):
    import functools


    @functools.cache
    def _plot(exponent):
        plt.plot(x, x**exponent)
        return plt.gca()


    _tex = (
        f"$$f(x) = x^{exponent.value}$$" if exponent.value > 1 else "$$f(x) = x$$"
    )

    mo.md(
        f"""

        {_tex}
        
        {mo.as_html(_plot(exponent.value))}
        """
    )
    return functools,


@app.cell
def __(mo):
    mo.md("## Other libraries")
    return


@app.cell
def __(mo):
    mo.md(
        """
        marimo also supports these other plotting libraries:

        - Plotly
        - Seaborn
        - Altair

        Just output their figure objects as the last expression of a cell,
        or embed them in markdown with `mo.as_html`.

        If you would like another library to be integrated into marimo, please
        get in touch.
        """
    )
    return


@app.cell
def __(missing_packages, mo):
    module_not_found_explainer = mo.md(
        """
        ## Oops!

        It looks like you're missing a package that this tutorial 
        requires.

        Close marimo, install **`numpy`** and **`matplotlib`**, then 
        open this tutorial once more.

        If you use `pip`, run

        ```
        pip install numpy matplotlib
        ```

        at your command line.
        """
    ).callout(kind='warn')

    def check_dependencies():
        if missing_packages:
            return module_not_found_explainer
    return check_dependencies, module_not_found_explainer


@app.cell
def __():
    plt_show_explainer = {
        "Using `plt.show()`": """
        You can use `plt.show()` or `figure.show()` to display
        plots in the console area of a cell. Keep in mind that console
        outputs are not shown in the app view.
        """
    }
    return plt_show_explainer,


@app.cell
def __():
    try:
        import matplotlib
        import matplotlib.pyplot as plt
        import numpy as np
        missing_packages = False
    except ModuleNotFoundError:
        missing_packages = True

    if not missing_packages:
        matplotlib.rcParams['figure.figsize'] = (6, 2.4)
    return matplotlib, missing_packages, np, plt


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
