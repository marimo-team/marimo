# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.5.2"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.sidebar(
        [
            mo.md("# marimo"),
            mo.nav_menu(
                {
                    "#/home": f"{mo.icon('lucide:home')} Home",
                    "#/about": f"{mo.icon('lucide:user')} About",
                    "#/sales": f"{mo.icon('lucide:bar-chart')} Sales",
                },
                orientation="vertical",
            ),
        ]
    )
    return


@app.cell
def __(mo):
    def render_home():
        return mo.md("""
         <p align="center">
          <img src="https://github.com/marimo-team/marimo/raw/main/docs/_static/marimo-logotype-thick.svg">
        </p>

        <p align="center">
          <em>A reactive Python notebook that's reproducible, git-friendly, and deployable as scripts or apps.</em>

        <p align="center">
          <a href="https://docs.marimo.io" target="_blank"><strong>Docs</strong></a> ·
          <a href="https://discord.gg/JE7nhX6mD8" target="_blank"><strong>Discord</strong></a> ·
          <a href="https://github.com/marimo-team/marimo/tree/main/examples" target="_blank"><strong>Examples</strong></a>
        </p>

        <p align="center">
        <a href="https://pypi.org/project/marimo/"><img src="https://img.shields.io/pypi/v/marimo?color=%2334D058&label=pypi" /></a>
        <a href="https://anaconda.org/conda-forge/marimo"/img><img src="https://img.shields.io/conda/vn/conda-forge/marimo.svg"></img></a>
        <a href="https://github.com/marimo-team/marimo/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/marimo"></img></a>
        </p>

        """)
    return render_home,


@app.cell
def __(mo):
    def render_about():
        return mo.md(
            """
        # About

        **marimo** is a reactive Python notebook: run a cell or interact with a UI
        element, and marimo automatically runs dependent cells, keeping code and outputs
        consistent. marimo notebooks are stored as pure Python, executable as scripts,
        and deployable as apps.

        **Highlights**.

        - **reactive**: run a cell, and marimo automatically runs all dependent cells
        - **interactive**: bind sliders, tables, plots, and more to Python — no callbacks required
        - **reproducible**: no hidden state, deterministic execution
        - **executable**: execute as a Python script, parametrized by CLI args
        - **shareable**: deploy as an interactive web app, or run in the browser via WASM
        - **git-friendly**: stored as `.py` files


        ## Community

        We're building a community. Come hang out with us!

        - 🌟 [Star us on GitHub](https://github.com/marimo-team/marimo)
        - 💬 [Chat with us on Discord](https://discord.gg/JE7nhX6mD8)
        - 📧 [Subscribe to our Newsletter](https://marimo.io/newsletter)
        - ☁️ [Join our Cloud Waitlist](https://marimo.io/cloud)
        - ✏️ [Start a GitHub Discussion](https://github.com/marimo-team/marimo/discussions)
        - 🐦 [Follow us on Twitter](https://twitter.com/marimo_io)
        - 🕴️ [Follow us on LinkedIn](https://www.linkedin.com/company/marimo-io)

        """
        )
    return render_about,


@app.cell
def __(mo):
    slider = mo.ui.slider(0, 100, value=20)
    return slider,


@app.cell
def __(mo, slider):
    def render_sales():
        import altair as alt
        import pandas as pd
        import numpy as np

        num = slider.value
        x = np.arange(num)
        y = np.random.randint(0, 100, num)
        df = pd.DataFrame({"x": x, "y": y})

        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x="x",
                y="y",
            )
        )

        return mo.md(
            f"""
        # Sales

        Number of points: {slider}

        {mo.as_html(mo.ui.altair_chart(chart))}
        """
        )
    return render_sales,


@app.cell
def __(mo, render_about, render_home, render_sales):
    mo.routes(
        {
            "#/home": render_home,
            "#/about": render_about,
            "#/sales": render_sales,
            mo.routes.CATCH_ALL: render_home,
        }
    )
    return


if __name__ == "__main__":
    app.run()
