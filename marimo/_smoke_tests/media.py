# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.4"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import requests
    from io import BytesIO
    return BytesIO, mo, requests


@app.cell
def __(mo):
    mic = mo.ui.microphone(label="What is your name?")
    mic
    return mic,


@app.cell
def __(mic, mo):
    mo.hstack(
        [mo.audio(mic.value), mo.download(data=mic.value, mimetype="audio/wav")]
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
def __(BytesIO, mo, requests):
    _src = (
        "https://images.pexels.com/photos/86596/owl-bird-eyes-eagle-owl-86596.jpeg"
    )
    _response = requests.get(_src)
    image_data = BytesIO(_response.content)

    mo.vstack(
        [
            mo.image(src=_src, rounded=True, height="300px"),
            # Note, chrome does not support cross-origin download, so this wont auto download until we proxy the download through the backend
            mo.download(data=_src, label="Download via URL"),
            mo.download(
                data=image_data,
                label="Download via BytesIO",
                mimetype="image/jpeg",
            ),
        ]
    )
    return image_data,


if __name__ == "__main__":
    app.run()
