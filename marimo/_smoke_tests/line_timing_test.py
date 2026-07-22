# /// script
# requires-python = ">=3.11"
# dependencies = []
#
# [tool.marimo.experimental]
# line_timing = true
# ///

import marimo

__generated_with = "0.23.13"
app = marimo.App()

with app.setup(hide_code=True):
    import time
    import marimo as mo


@app.cell(hide_code=True)
def _():
    mo.md("""
    # ⏱️ Line timing test

    The experimental `line_timing` flag is set in this notebook's script
    metadata (top of the file), so it's on for this notebook only.

    **What to watch for**
    - While a cell runs, the currently executing line is highlighted
      **green**.
    - Once a line has been busy for ~500ms, a small dim **elapsed-time
      pill** appears at the end of the line and ticks until execution
      moves on.
    - Fast lines never show a timer — the highlight just steps through.
    - Everything clears when the cell finishes.
    """)
    return


@app.cell
def _():
    # Staged pipeline: the highlight steps through; the timer appears
    # only on the slow steps.
    time.sleep(0.2)  # fast: no timer
    time.sleep(0.8)  # timer appears at ~500ms
    time.sleep(2)  # counts to ~2s
    time.sleep(5)  # counts to ~5s
    return


@app.cell
def _():
    # Fast loop: the highlight bounces between lines, but no line stays
    # busy for 500ms, so the timer never flickers in.
    total = 0
    for i in range(100):
        total += i
        time.sleep(0.02)
    total
    return


@app.cell
def _():
    time.sleep(8)  # one long line: the timer ticks the whole way
    return


@app.cell(hide_code=True)
def _():
    mo.md("""
    Tip: also set `debugger = true` in the script metadata to verify that
    the green timing highlight wins over the amber debugger highlight and
    that the breakpoint gutter still works.
    """)
    return


if __name__ == "__main__":
    app.run()
