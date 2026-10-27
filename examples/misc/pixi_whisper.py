# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["marimo>=0.25.0", "openai-whisper>=20250625"]
#
# [tool.pixi.workspace]
# channels = ["conda-forge"]
#
# [tool.pixi.dependencies]
# ffmpeg = "*"
#
# [tool.pixi.target.linux.dependencies]
# pytorch-gpu = "*"
#
# [tool.pixi.target.win.dependencies]
# pytorch-gpu = "*"
#
# [tool.pixi.target.osx.dependencies]
# pytorch-cpu = "*"
# ///

import marimo

__generated_with = "0.25.0"
app = marimo.App(width="compact")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    With [Pixi installed](https://pixi.prefix.dev/latest/installation/), run:

    ```bash
    marimo edit --sandbox=pixi examples/misc/pixi_whisper.py
    ```

    Choose a recording to transcribe with Whisper. Pixi installs CUDA-enabled
    PyTorch on Linux and Windows, and CPU PyTorch on macOS. The first run
    downloads the model weights.
    """)
    return


@app.cell
def _():
    import torch
    import whisper

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model("tiny.en", device=device)
    return model, whisper


@app.cell
def _():
    import marimo as mo

    files = mo.ui.dropdown(
        {
            "The Ashiel Mystery": "https://librosa.org/data/audio/5703-47212-0000.ogg",
            "The Age of Chivalry": "https://librosa.org/data/audio/3436-172162-0000.ogg",
            "Sense and Sensibility": "https://librosa.org/data/audio/198-209-0000.ogg",
        },
        value="The Ashiel Mystery",
        label="Recording:",
    )
    files
    return files, mo


@app.cell
def _(files, mo, whisper):
    audio = whisper.load_audio(files.value)
    mo.audio(audio, rate=16000)
    return (audio,)


@app.cell
def _(audio, model):
    result = model.transcribe(audio, language="en", fp16=model.device.type == "cuda")
    result["text"]
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Audio: [LibriSpeech](https://www.openslr.org/12/), distributed by
    [librosa](https://librosa.org/doc/main/recordings.html) under
    [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
    *The Ashiel Mystery* is read by Garth Comira, *The Age of Chivalry*
    by Anders Lankford, and *Sense and Sensibility* by Heather Barnett.
    """)
    return


if __name__ == "__main__":
    app.run()
