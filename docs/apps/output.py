import marimo

__generated_with = "0.0.6"
app = marimo.App()


@app.cell
def __(tabs):
    tabs
    return


@app.cell
def __(array, ax, dictionary, mo, plots, table, text):
    tabs = mo.tabs(
        {
            "markdown": mo.md(
                """
                Use `mo.md` to write markdown, with support for LaTeX:

                \[
                e = \sum_{k=0}^{\infty} 1/k!.
                \]
                """
                + f"""
                You can even interpolate arbitrary Python values and marimo
                elements into your markdown. Try typing your name below:

                {mo.hstack([
                    text, mo.md("Hello, " + text.value + "!")
                ], justify="center")}
                """
            ).left(),
            "lists and dicts": mo.hstack(
                [array, dictionary], justify="space-around"
            ),
            "tables": mo.md(
                f"""
                {table}

                Employee of the month: {table.value[0]["first_name"] + "! 🎉" if table.value else ""}
                """
            ),
            "accordion": mo.accordion(
                {
                    "Tip!": f"""
                    Express yourself with outputs! Put anything in accordions,
                    like plots:

                    {mo.as_html(ax)}.
                    """
                }
            ),
            "rows and columns": plots,
            "and more ...": mo.md(
                "**Build anything you can imagine**. Check out our tutorials and examples for inspiration."
            ),
        }
    )
    return tabs,


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    text = mo.ui.text(value="stranger")
    return text,


@app.cell
def __(mo):
    slider = mo.ui.slider(2, 4, step=1)
    return slider,


@app.cell
def __(plt, slider, x):
    plt.figure(figsize=(2, 2))
    plt.plot(x, x**slider.value)
    ax = plt.gca()
    ax.set_xticks([])
    ax.set_yticks([])
    None
    return ax,


@app.cell
def __(ax, mo, slider):
    array = [slider, mo.md(f"$f(x) = x^{slider.value}$"), ax]
    return array,


@app.cell
def __(array, mo):
    dictionary = {"md": mo.md("nest lists and dicts!"), "list": array}
    return dictionary,


@app.cell
def __(mo):
    table = mo.ui.table(
        [
            {
                "first_name": "Michael",
                "last_name": "Scott",
                "skill": mo.ui.slider(1, 10, value=3),
                "favorite place": mo.image(src="https://picsum.photos/100"),
            },
            {
                "first_name": "Jim",
                "last_name": "Halpert",
                "skill": mo.ui.slider(1, 10, value=7),
                "favorite place": mo.image(src="https://picsum.photos/100"),
            },
        ],
        selection="single"
    )
    return table,


@app.cell
def __(mo, np, plt):
    def plot(x, y, title):
        plt.figure(figsize=(2, 2))
        plt.plot(x, y)
        plt.title(title)
        plt.tight_layout()
        return plt.gca()

    x = np.linspace(-2, 2, 100)
    linear = plot(x, x, "$x$")
    quadratic = plot(x, x**2, "$x^2$")
    sine = plot(x, np.sin(x), "$\sin(x)$")
    cos = plot(x, np.cos(x), "$\cos(x)$")
    exp = plot(x, np.exp(x), "$\exp(x)$")

    plots = mo.vstack([
        mo.hstack([linear, quadratic]),
        mo.hstack([sine, cos, exp])
    ], align="center")
    return cos, exp, linear, plot, plots, quadratic, sine, x


@app.cell
def __():
    import numpy as np
    return np,


@app.cell
def __():
    import matplotlib.pyplot as plt
    return plt,


if __name__ == "__main__":
    app.run()
