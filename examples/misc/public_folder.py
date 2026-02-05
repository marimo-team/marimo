import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(r"""
    Load images under the public folder. This will search for files in the /public folder next to the notebook.

    <img src="/public/marimos.webp" width=100 />
    <img src="./public/marimos.webp" width=100 />
    <img src="public/marimos.webp" width=100 />
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
