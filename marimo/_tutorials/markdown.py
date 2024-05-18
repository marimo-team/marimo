# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.6.0"
app = marimo.App()


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        # Hello, Markdown!

        Use marimo's "`md`" function to write markdown. This function compiles Markdown into HTML that marimo can display.

        For example, here's the code that rendered the above title and 
        paragraph:

        ```python3
        mo.md(
            '''
            # Hello, Markdown!

            Use marimo's "`md`" function to embed rich text into your marimo
            apps. This function compiles your Markdown into HTML that marimo
            can display.
            '''
        )
        ```
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        rf"""
        **Tip: toggling between Markdown and Python views**

        Although markdown is written with `mo.md`, marimo provides a markdown view
        that hides this boilerplate from you. You can toggle between Markdown and 
        Python views by clicking the button in the top-right of this cell or entering 
        `Ctrl/Cmd+Shift+M`.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        ## LaTeX
        You can embed LaTeX in Markdown.

        For example,

        ```python3
        mo.md(r'$f : \mathbf{R} \to \mathbf{R}$')
        ```

        renders $f : \mathbf{R} \to \mathbf{R}$, while

        ```python3
        mo.md(
            r'''
            \[
            f: \mathbf{R} \to \mathbf{R}
            \]
            '''
        )
        ```

        renders the display math

        \[
        f: \mathbf{R} \to \mathbf{R}.
        \]
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.accordion(
        {
            "Tip: `r''` strings": mo.md(
                "Use `r''` strings to remove the need to escape backslashes"
                " when writing LaTeX."
            )
        }
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ## Interpolating Python values

        You can interpolate Python values into markdown using
        `f-strings` and marimo's ` as_html` function. This lets you create 
        markdown whose contents depend on data that changes at runtime.

        Here are some examples.
        """
    )
    return


@app.cell
def __(
    matplotlib_installed,
    missing_matplotlib_msg,
    missing_numpy_msg,
    mo,
    np,
    numpy_installed,
    plt,
):
    def _sine_plot():
        if not numpy_installed:
            return missing_numpy_msg
        if not matplotlib_installed:
            return missing_matplotlib_msg
        _x = np.linspace(start=0, stop=2 * np.pi)
        plt.plot(_x, np.sin(_x))
        return plt.gca()


    mo.md(
        f"""
        ### Plots
        A matplotlib figure:

        ```python3
        _x = np.linspace(start=0, stop=2*np.pi)
        sine_plot = plt.plot(_x, np.sin(_x))
        mo.md(f"{{mo.as_html(sine_plot)}}")
        ```
        yields

        {mo.as_html(_sine_plot())}
        """
    )
    return


@app.cell
def __(mo):
    leaves = mo.ui.slider(1, 32, label="🍃: ")

    mo.md(
        f"""
        ### UI elements

        A `marimo.ui` object:

        ```python3
        leaves = mo.ui.slider(1, 16, label="🍃: ")
        mo.md(f"{{leaves}}")
        ```

        yields

        {leaves}
        """
    )
    return leaves,


@app.cell
def __(leaves, mo):
    mo.md(f"Your leaves: {'🍃' * leaves.value}")
    return


@app.cell(hide_code=True)
def __(mo):
    mo.accordion(
        {
            "Tip: UI elements can format themselves": """
            marimo objects know how to format themselves, so you can omit the 
            call to `as_html`.
            """
        }
    )
    return


@app.cell
def __(missing_numpy_msg, mo, np, numpy_installed):
    def make_dataframe():
        try:
            import pandas as pd
        except ModuleNotFoundError:
            return mo.md("Oops! Looks like you don't have `pandas` installed.")

        if not numpy_installed:
            return missing_numpy_msg

        x = np.linspace(0, 2 * np.pi, 10)
        y = np.sin(x)
        return pd.DataFrame({"x": x, "sin(x)": y})


    mo.md(
        f"""
        ### Other objects

        Use `mo.as_html` to convert objects to HTML. This function
        generates rich HTML for many Python types, including:

        - lists, dicts, and tuples,
        - `pandas` dataframes and series,
        - `seaborn` figures,
        - `plotly` figures, and
        - `altair` figures.

        For example, here's a pandas dataframe:

        {mo.as_html(make_dataframe())}
        """
    )
    return make_dataframe,


@app.cell(hide_code=True)
def __(mo):
    mo.accordion(
        {
            "Tip: outputs are automatically converted to HTML": """
            `mo.as_html` is only needed when interpolating objects into 
            markdown; the last expression of a cell (its output) is 
            converted to HTML automatically.
            """
        }
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        ## Putting it all together

        Here's a more interesting example that puts together
        everything we've learned: rendering markdown with LaTeX that depends on
        the values of Python objects.
        """
    )
    return


@app.cell
def __(math, mo):
    amplitude = mo.ui.slider(1, 2, step=0.1, label="amplitude: ")
    period = mo.ui.slider(
        math.pi / 4,
        4 * math.pi,
        value=2 * math.pi,
        step=math.pi / 8,
        label="period: ",
    )
    return amplitude, period


@app.cell
def __(
    matplotlib_installed,
    missing_matplotlib_msg,
    missing_numpy_msg,
    np,
    numpy_installed,
    plt,
):
    import functools


    @functools.cache
    def plotsin(amplitude, period):
        if not numpy_installed:
            return missing_numpy_msg
        elif not matplotlib_installed:
            return missing_matplotlib_msg
        x = np.linspace(0, 2 * np.pi, 256)
        plt.plot(x, amplitude * np.sin(2 * np.pi / period * x))
        plt.ylim(-2.2, 2.2)
        return plt.gca()
    return functools, plotsin


@app.cell
def __(amplitude, mo, period):
    mo.md(
        f"""
        **A sin curve.**

        - {amplitude}
        - {period}
        """
    )
    return


@app.cell
def __(amplitude, mo, period, plotsin):
    mo.md(
        rf"""
        You're viewing the graph of

        \[
        f(x) = {amplitude.value}\sin((2\pi/{period.value:0.2f})x),
        \]

        with $x$ ranging from $0$ to $2\pi$.
        {mo.as_html(plotsin(amplitude.value, period.value))}
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    matplotlib_installed = False
    numpy_installed = False
    missing_numpy_msg = mo.md("Oops! Looks like you don't have `numpy` installed.")
    missing_matplotlib_msg = mo.md(
        "Oops! Looks like you don't have `matplotlib` installed."
    )

    try:
        import matplotlib.pyplot as plt

        matplotlib_installed = True
    except ModuleNotFoundError:
        pass

    try:
        import numpy as np

        numpy_installed = True
    except ModuleNotFoundError:
        pass
    return (
        matplotlib_installed,
        missing_matplotlib_msg,
        missing_numpy_msg,
        np,
        numpy_installed,
        plt,
    )


@app.cell(hide_code=True)
def __():
    import math

    import marimo as mo
    return math, mo


if __name__ == "__main__":
    app.run()
