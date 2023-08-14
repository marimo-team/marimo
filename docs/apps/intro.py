import marimo

__generated_with = "0.0.6"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Welcome to marimo! 🌊🍃")
    return


@app.cell
def __(mo):
    slider = mo.ui.slider(1, 22)
    return slider,


@app.cell
def __(mo, slider):
    mo.md(
        f"""
        marimo is a Python library for creating reactive and interactive
        notebooks and apps.

        Unlike traditional notebooks, marimo notebooks **run
        automatically** when you modify them or
        interact with UI elements, like this slider: {slider}.

        {"##" + "🍃" * slider.value}
        """
    )
    return


@app.cell
def __(mo):
    mo.accordion(
        {
            "A notebook or an app?": (
                """
                Because marimo notebooks react to changes and UI interactions,
                they can also be thought of as apps: click
                the app window icon to see an "app view" that
                hides code.

                Depending on how you use marimo, you can think
                of marimo programs as notebooks, apps, or both.
                """
            )
        }
    )
    return


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
