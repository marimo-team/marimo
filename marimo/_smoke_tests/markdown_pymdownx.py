import marimo

__generated_with = "0.9.34"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(
        r"""
        Task List

        - item
        -   [X] item 1
            *   [X] item A
            *   [ ] item B
                more text
                +   [x] item a
                +   [ ] item b
                +   [x] item c
            *   [X] item C
            *   non item
        -   [ ] item 2
        -   [ ] item 3
        """
    )
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
