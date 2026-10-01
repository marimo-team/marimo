# /// script
# requires-python = ">=3.12"
# dependencies = ["marimo>=0.25.0"]
#
# [tool.pixi.workspace]
# channels = ["conda-forge"]
#
# [tool.pixi.dependencies]
# ffmpeg = "*"
# ///

import marimo

__generated_with = "0.25.0"
app = marimo.App(width="compact")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    With [Pixi installed](https://pixi.prefix.dev/latest/installation/), run:

    ```bash
    marimo edit --sandbox=pixi examples/misc/pixi_ffmpeg.py
    ```
    """)
    return


@app.cell
def _():
    import marimo as mo

    pitch = mo.ui.slider(220, 880, step=20, value=440, label="Pitch (Hz)")
    pitch
    return mo, pitch


@app.cell
def _(mo, pitch):
    import io
    import subprocess

    tone = subprocess.run(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={pitch.value}:duration=2",
            "-f",
            "wav",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    )
    mo.audio(io.BytesIO(tone.stdout))
    return


if __name__ == "__main__":
    app.run()
