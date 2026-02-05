# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "chromadb==1.0.4",
#     "datasets==3.5.0",
#     "marimo",
#     "matplotlib==3.10.1",
#     "numpy==2.2.4",
#     "open-clip-torch==2.32.0",
#     "pillow==11.1.0",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Multimodal Retrieval

    Chroma supports multimodal collections, i.e. collections which contain, and can be queried by, multiple modalities of data.

    This notebook shows an example of how to create and query a collection with both text and images, using Chroma's built-in features.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Dataset

    We us a small subset of the [coco object detection dataset](https://huggingface.co/datasets/detection-datasets/coco), hosted on HuggingFace.

    We download a small fraction of all the images in the dataset locally, and use it to create a multimodal collection.
    """)
    return


@app.cell
def _():
    import os

    from datasets import load_dataset
    from matplotlib import pyplot as plt

    return load_dataset, os


@app.cell
def _(load_dataset, mo):
    with mo.status.spinner(title="Loading dataset"):
        dataset = load_dataset(
            path="detection-datasets/coco",
            name="default",
            split="train",
            streaming=True,
        )

    N_IMAGES = 20
    return N_IMAGES, dataset


@app.cell
def _(N_IMAGES, dataset, mo, os):
    # Write the images to a folder
    IMAGE_FOLDER = "images"
    os.makedirs(IMAGE_FOLDER, exist_ok=True)
    i = 0
    all_images = []
    with mo.status.spinner(title="Loading images"):
        for row in dataset.take(N_IMAGES):
            image = row["image"]
            all_images.append(image)
            image.save(f"images/{i}.jpg")
            i += 1
    return IMAGE_FOLDER, all_images


@app.cell(hide_code=True)
def _(mo):
    img_width = mo.ui.slider(
        label="Image width", start=100, stop=300, step=10, debounce=True
    )
    img_width
    return (img_width,)


@app.cell(hide_code=True)
def _(all_images, img_width, mo):
    import io


    def as_image(src):
        img_byte_arr = io.BytesIO()
        src.save(img_byte_arr, format=src.format or "PNG")
        img_byte_arr.seek(0)
        return mo.image(img_byte_arr, width=img_width.value)


    mo.hstack(
        [as_image(_img) for _img in all_images[10:]],
        wrap=True,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Ingesting multimodal data

    Chroma supports multimodal collections by referencing external URIs for data types other than text.
    All you have to do is specify a data loader when creating the collection, and then provide the URI for each entry.

    For this example, we are only adding images, though you can also add text.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Creating a multi-modal collection

    First we create the default Chroma client.
    """)
    return


@app.cell
def _():
    import chromadb

    client = chromadb.Client()
    return (client,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Next we specify an embedding function and a data loader.

    The built-in `OpenCLIPEmbeddingFunction` works with both text and image data. The `ImageLoader` is a simple data loader that loads images from a local directory.
    """)
    return


@app.cell
def _():
    from chromadb.utils.data_loaders import ImageLoader
    from chromadb.utils.embedding_functions import OpenCLIPEmbeddingFunction

    embedding_function = OpenCLIPEmbeddingFunction()
    image_loader = ImageLoader()
    return embedding_function, image_loader


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    We create a collection with the embedding function and data loader.
    """)
    return


@app.cell
def _(IMAGE_FOLDER, client, embedding_function, image_loader, os):
    collection = client.create_collection(
        name="multimodal_collection",
        embedding_function=embedding_function,
        data_loader=image_loader,
        get_or_create=True,
    )

    # Get the uris to the images
    image_uris = sorted(
        [
            os.path.join(IMAGE_FOLDER, image_name)
            for image_name in os.listdir(IMAGE_FOLDER)
        ]
    )
    ids = [str(i) for i in range(len(image_uris))]

    collection.add(ids=ids, uris=image_uris)
    return (collection,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Adding multi-modal data

    We add image data to the collection using the image URIs. The data loader and embedding functions we specified earlier will ingest data from the provided URIs automatically.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Querying a multi-modal collection

    We can query the collection using text as normal, since the `OpenCLIPEmbeddingFunction` works with both text and images.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    query = mo.ui.text_area(label="Query with text", full_width=True).form(
        bordered=False
    )
    mo.vstack([query, mo.md("Try: *animal* or *vehicle*")])
    return (query,)


@app.cell
def _(collection, mo, query):
    mo.stop(not query.value)
    _retrieved = collection.query(
        query_texts=[query.value], include=["data"], n_results=3
    )

    [mo.image(img, height=200) for img in _retrieved["data"][0]]
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    /// admonition | One more thing!
    We can also query by images directly, by using the `query_images` field in the `collection.query` method.
    ///
    """)
    return


@app.cell
def _(collection, mo, selected_image):
    mo.stop(not selected_image.value)
    import numpy as np
    from PIL import Image

    query_image = np.array(Image.open(selected_image.path()))
    selected = mo.as_html(mo.image(query_image))

    _retrieved = collection.query(
        query_images=[query_image], include=["data"], n_results=5
    )
    results = [mo.image(_img) for _img in _retrieved["data"][0][1:]]
    return results, selected


@app.cell(hide_code=True)
def _(IMAGE_FOLDER, mo):
    selected_image = mo.ui.file_browser(IMAGE_FOLDER, multiple=False)
    selected_image
    return (selected_image,)


@app.cell(hide_code=True)
def _(mo, results, selected):
    mo.hstack(
        [
            mo.vstack([mo.md("## Selected"), selected]),
            mo.vstack([mo.md("## Similar"), *results]),
        ],
        widths="equal",
        gap=4,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    This example was adapted from [multimodal_retrieval.ipynb](https://github.com/chroma-core/chroma/blob/main/examples/multimodal/multimodal_retrieval.ipynb), using `marimo convert`.
    """)
    return


if __name__ == "__main__":
    app.run()
