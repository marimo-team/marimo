# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
#
# [tool.marimo.server]
# transport = "sse"
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.23.13"
app = marimo.App()


@app.cell(hide_code=True)
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # SSE transport smoke test

    This notebook sets `transport = "sse"` via inline
    `[tool.marimo.server]` metadata, selecting the **experimental**
    server-sent-events transport for the kernel connection instead of the
    default websocket. In deployments, the equivalent is the
    `MARIMO_SERVER_TRANSPORT=sse` environment variable.

    To verify:

    1. Open with `marimo edit marimo/_smoke_tests/inline_sse_transport.py`
       (or `marimo run ...`).
    2. In the browser devtools **Network** tab, confirm that **no `/ws`
       connection opens** and that a `/sse` request is streaming with
       content-type `text/event-stream`.
    3. The notebook should load and cells below should run — client→kernel
       traffic goes over HTTP POST while kernel→client updates arrive over
       the SSE stream.
    4. Kill the server: the "disconnected / shutdown" UX should appear.
       Restart it: the client should reconnect and resume the session.

    Note: with the SSE transport, RTC is auto-disabled and the terminal /
    LSP features still require websockets.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # A reactive slider to confirm UI element updates round-trip over
    # POST (input) + SSE (output).
    slider = mo.ui.slider(1, 100, value=10, label="value")
    slider
    return (slider,)


@app.cell(hide_code=True)
def _(mo, slider):
    mo.md(f"""
    Slider value is **{slider.value}** — squared is **{slider.value**2}**.
    """)
    return


if __name__ == "__main__":
    app.run()
