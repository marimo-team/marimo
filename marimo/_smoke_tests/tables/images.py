import marimo

__generated_with = "0.11.30"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl
    from PIL import Image
    import io
    import requests
    import pandas as pd


    def load_image(url):
        response = requests.get(url)
        img = Image.open(io.BytesIO(response.content))
        print(isinstance(img, bytes))
        return img


    df = pl.DataFrame(
        {
            "id": [1, 2, 3],
            "str": ["foo", "bar", "baz"],
            "image": [
                load_image("https://picsum.photos/400"),
                load_image("https://picsum.photos/400"),
                load_image("https://picsum.photos/400"),
            ],
        }
    )

    df
    return Image, df, io, load_image, pd, pl, requests


@app.cell
def _(df):
    df.to_pandas()
    return


@app.cell
def _(Image, io, requests):
    Image.open(io.BytesIO(requests.get("https://picsum.photos/200").content))
    return


if __name__ == "__main__":
    app.run()
