# /// script
# requires-python = ">=3.11"
# dependencies = []
#
# [tool.marimo.experimental]
# debugger = true
# ///

import marimo

__generated_with = "0.23.9"
app = marimo.App()

with app.setup:
    # Setup cell: runs first, frame-watched like any other cell.
    import time

    HEARTBEAT_DEMO_ITERS = 40


@app.cell
def _(mo):
    mo.md("""
    # 🐛 Debugger lifecycle test

    The experimental `debugger` flag is set in this notebook's script
    metadata (top of the file), so it's on for this notebook only.

    **What to try**
    - Click in the **leftmost gutter** of any cell to toggle a red
      breakpoint dot. Run the cell → it drops into `pdb` at that line.
    - Run the **slow loop** cell below and watch the **amber current-line
      highlight** move on the heartbeat (it updates on change, ~every
      75ms, not every line).
    - In a cell that raises, the traceback's **bug icon** now toggles a
      gutter breakpoint instead of inserting `breakpoint()`.
    """)
    return


@app.cell
def _():
    # Slow loop: run this and watch the current-line highlight track progress.
    total = 0
    for i in range(HEARTBEAT_DEMO_ITERS):
        total += i
        time.sleep(0.1)  # set a gutter breakpoint here to pause mid-loop
        time.sleep(0.1)  # set a gutter breakpoint here to pause mid-loop
    total
    return


@app.cell
def _():
    # Step-into target: set a breakpoint inside `fib` and call it.
    def fib(n):
        if n < 2:
            return n
        a, b = 0, 1
        for _ in range(n - 1):
            a, b = b, a + b  # good breakpoint line
        return b

    fib(2000000)
    return


@app.cell
def _():
    # Cell that raises — use the traceback bug icon to drop a breakpoint,
    # then re-run to inspect.
    def boom(x):
        y = x * 2
        return y / 0  # ZeroDivisionError

    boom(21)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
