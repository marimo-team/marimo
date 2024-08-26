import marimo

__generated_with = "0.8.3"
app = marimo.App(width="medium", css_file="custom.css")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md(
        r"""
        # heading

        Here is a paragraph
        """
    )
    return


if __name__ == "__main__":
    app.run()
