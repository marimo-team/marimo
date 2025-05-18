import marimo

__generated_with = "0.11.31"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(
        """
        ## Markdown / Latex Highlighting

        ```ts
        console.log("highlight code fences")
        ```

        ```python
        def lang_python():
            pass
        ```

        ```
        def no_language():
            pass
        ```

        **bold**

        _italic_

        $\sigma\sqrt{100}$

        $$
        \sigma\sqrt{100}
        $$

        \[ \sigma\sqrt{100} \]

        \( \sigma\sqrt{100} \)
        """
    )
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
