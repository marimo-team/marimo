# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Smoke test for stale <img> rendering when mo.Html re-runs with new src URLs.
#
# Repro: pick a set, run the cell, then change the radio to swap the
# URLs. Each <img> should display the newly selected image. Before the
# RenderHTML key-by-src fix, the prior images stayed painted.

import marimo

__generated_with = "0.23.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    sets = {
        "set A (cats)": [
            "https://placecats.com/200/200",
            "https://placecats.com/201/200",
            "https://placecats.com/202/200",
            "https://placecats.com/203/200",
            "https://placecats.com/204/200",
        ],
        "set B (bears)": [
            "https://placebear.com/200/200",
            "https://placebear.com/201/200",
            "https://placebear.com/202/200",
            "https://placebear.com/203/200",
            "https://placebear.com/204/200",
        ],
    }
    choice = mo.ui.radio(options=list(sets), value="set A (cats)")
    choice
    return choice, sets


@app.cell
def _(choice, mo, sets):
    urls = sets[choice.value]
    imgs = "".join(
        f'<img src="{u}" width="120" height="120" style="margin:4px"/>'
        for u in urls
    )
    mo.Html(f'<div>{imgs}</div>')
    return


@app.cell
def _(mo):
    mo.md("""
    ### What to check
    - Toggle the radio between the two sets repeatedly.
    - Each `<img>` should swap to the newly selected URL.
    - Open devtools and confirm the rendered `<img>` `src` attributes
      match the selected set, and that the painted images match too.
    """)
    return


if __name__ == "__main__":
    app.run()
