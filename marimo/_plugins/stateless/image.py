# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
import os
from typing import Any, Optional, Union

import marimo._output.data.data as mo_data
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import create_style
from marimo._plugins.core.media import io_to_data_url

Image = Union[str, bytes, io.BytesIO, io.BufferedReader]
# Union[list, torch.Tensor, jax.numpy.ndarray,
#             np.ndarray, scipy.sparse.spmatrix]
Tensor = Any
ImageLike = Union[Image, Tensor]


def _normalize_image(src: ImageLike) -> Image:
    """
    Normalize an image-like object to a standard format.

    This function handles a variety of input types, including lists, arrays,
    and tensors, and converts them to a BytesIO object representing a PNG
    image.

    Typical convention for handling images is to use `PIL`, which is exactly
    what `matplotlib` does behind the scenes. `PIL` requires a `ndarray`
    (validated with the numpy specific `__array_interface__` attribute). In
    turn, numpy can cast lists, and objects with the `__array__` method (like
    jax, torch tensors). `scipy.sparse` breaks this convention but does have a
    `toarray` method, which is general enough that a specific check is
    performed here.

    **Args.**

    - `src`: An image-like object. This can be a list, array, tensor, or a
        file-like object.

    **Returns.**

    A BytesIO object or other Image type.

    **Raises.**

    - `ModuleNotFoundError`: If the required `PIL` or `numpy` packages are not
        available.
    - `ValueError`: If the input is not a valid image-like object.
    """
    if (
        isinstance(src, list)
        or hasattr(src, "__array__")
        or hasattr(src, "toarray")
    ):
        DependencyManager.require_pillow(
            "to render images from arrays in `mo.image`"
        )
        from PIL import Image as _Image

        if not hasattr(src, "__array_interface__"):
            DependencyManager.require_numpy(
                "to render images from generic arrays in `mo.image`"
            )
            import numpy

            # Capture those sparse cases
            if hasattr(src, "toarray"):
                src = src.toarray()
            src = numpy.array(src)
        src = (src - src.min()) / (src.max() - src.min()) * 255.0
        img = _Image.fromarray(src.astype("uint8"))
        # io.BytesIO is one of the Image types.
        normalized_src: Image = io.BytesIO()
        img.save(normalized_src, format="PNG")
        return normalized_src
    # Verify that this is a image object
    if not isinstance(src, (str, bytes, io.BytesIO, io.BufferedReader)):
        raise ValueError(
            f"Expected an image object, but got {type(src)} instead."
        )
    return src


@mddoc
def image(
    src: ImageLike,
    alt: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    rounded: bool = False,
    style: Optional[dict[str, Any]] = None,
) -> Html:
    """Render an image as HTML.

    **Examples.**

    ```python3
    # Render an image from a local file
    mo.image(src="path/to/image.png")
    ```

    ```python3
    # Render an image from a URL
    mo.image(
        src="https://marimo.io/logo.png",
        alt="Marimo logo",
        width=100,
        height=100,
        rounded=True,
    )
    ```

    **Args.**

    - `src`: a path or URL to an image, a file-like object
        (opened in binary mode), or array-like object.
    - `alt`: the alt text of the image
    - `width`: the width of the image in pixels
    - `height`: the height of the image in pixels
    - `rounded`: whether to round the corners of the image
    - `style`: a dictionary of CSS styles to apply to the image

    **Returns.**

    `Html` object
    """
    # Convert to virtual file
    resolved_src: Optional[str]
    src = _normalize_image(src)
    # TODO: Consider downsampling here. This is something matplotlib does
    # implicitly, and can potentially remove the bottle-neck of very large
    # images.
    if isinstance(src, io.BufferedReader) or isinstance(src, io.BytesIO):
        src.seek(0)
        resolved_src = mo_data.image(src.read()).url
    elif isinstance(src, bytes):
        resolved_src = mo_data.image(src).url
    elif isinstance(src, str) and os.path.isfile(src):
        with open(src, "rb") as f:
            resolved_src = mo_data.image(
                f.read(), ext=os.path.splitext(src)[1]
            ).url
    else:
        resolved_src = io_to_data_url(src, fallback_mime_type="image/png")

    styles = create_style(
        {
            "width": f"{width}px" if width is not None else None,
            "height": f"{height}px" if height is not None else None,
            "border-radius": "4px" if rounded else None,
            **(style or {}),
        }
    )
    img = h.img(src=resolved_src, alt=alt, style=styles)
    return Html(img)
