import marimo

__generated_with = "0.13.12"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(
        """
    ```
    >>> # pycon (omitted)
    >>> def foo():
    >>>    pass
    ```

    ```
    # python (omitted)
    def foo():
        return range(1, 100)
    return x + y
    ```

    ```pycon
    >>> def foo():
    >>>    pass
    ```

    ```python
    # python
    def foo():
        pass
    x + y
    ```
    """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    ```js
    // js
    const myVar = "";
    ```

    ```
    import { foo } from "bar";
    // js omitted
    var myVar = "";
    ```
    """
    )
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
