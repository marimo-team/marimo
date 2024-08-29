import marimo

__generated_with = "0.8.3"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import time
    return mo, time


@app.cell
def __(time):
    time.sleep(1)
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        ### Realtime Markdown
        Everything you type should update the cell output in realtime, which is:

        1. cool,
        2. convenient, and
        3. awesome
        """
    )
    return


if __name__ == "__main__":
    app.run()
