# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.33"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import requests
    from io import BytesIO
    import base64
    return BytesIO, base64, mo, requests


@app.cell
def __(mo):
    mic = mo.ui.microphone(label="What is your name?")
    mic
    return mic,


@app.cell
def __(mic, mo):
    mo.hstack(
        [mo.audio(mic.value), mo.download(data=mic.value, mimetype="audio/x-wav")]
    )
    return


@app.cell
def __(mo):
    # Note, chrome does not support cross-origin download, so this wont auto download until we proxy the download through the backend
    _src = "https://samplelib.com/lib/preview/mp3/sample-3s.mp3"
    mo.hstack(
        [
            mo.audio(src=_src),
            mo.download(data=_src, label=""),
        ]
    )
    return


@app.cell
def __(BytesIO, base64, mo, requests):
    _src = (
        "https://images.pexels.com/photos/86596/owl-bird-eyes-eagle-owl-86596.jpeg"
    )
    _response = requests.get(_src)
    image_data = BytesIO(_response.content)
    base64str = (
        f"data:image/jpeg;base64,{base64.b64encode(_response.content).decode()}"
    )

    mo.vstack(
        [
            mo.image(src=_src, rounded=True, height=100),
            # Note, chrome does not support cross-origin download, so this wont auto download until we proxy the download through the backend
            mo.download(data=_src, label="Download via URL"),
            mo.image(src=image_data, rounded=True, height=100),
            mo.download(
                data=image_data,
                label="Download via BytesIO",
                mimetype="image/jpeg",
            ),
            mo.image(src=base64str, rounded=True, height=100),
            mo.download(
                data=base64str,
                label="Download via bytes",
                mimetype="image/jpeg",
            ),
        ]
    )
    return base64str, image_data


@app.cell
def __(mo):
    import os

    with open(os.path.realpath("docs/_static/array.png"), "rb") as f:
        _image = mo.image(src=f)
        _download = mo.download(
            data=f,
            label="Download local file",
        )

    mo.hstack([_image, _download])
    return f, os


@app.cell
def __(mo):
    mo.video(
        src="https://v3.cdnpk.net/videvo_files/video/free/2013-08/large_watermarked/hd0992_preview.mp4",
        rounded=True,
    )
    return


@app.cell
def __(mo):
    mo.video(
        src="https://v3.cdnpk.net/videvo_files/video/free/2013-08/large_watermarked/hd0992_preview.mp4",
        rounded=True,
        autoplay=True,
        muted=True,
        controls=False,
        width=300,
    )
    return


if __name__ == "__main__":
    app.run()
