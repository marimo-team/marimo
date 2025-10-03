import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(r"""# hello""")
    return


@app.cell
def _(mo):
    mo.md(r"""This is `inline code`""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ```python
    def fibonacci(n):
        if n <= 0:
            return []
        elif n == 1:
            return [0]
        elif n == 2:
            return [0, 1]

        fib_sequence = [0, 1]
        for i in range(2, n):
            fib_sequence.append(fib_sequence[i-1] + fib_sequence[i-2])

        return fib_sequence
    ```
    """
    )
    return


@app.cell(hide_code=True)
def _(code_block, mo):
    mo.md(
        rf"""
    ```
    # Example usage:
    # print(fibonacci(10))
    ```

    **Nested code block**
    {code_block}
    """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    code_block = mo.md("""
    ```python
    def add(x: int, y: int):
        return x + y
    ```
    """)
    return (code_block,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
