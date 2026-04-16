# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

import marimo._output.data.data as mo_data
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import create_style, normalize_dimension
from marimo._plugins.core.media import io_to_data_url

Image = str | bytes | io.BytesIO | io.BufferedReader | Path
# Union[list, torch.Tensor, jax.numpy.ndarray,
#             np.ndarray, scipy.sparse.spmatrix]
Tensor = Any
ImageLike = Image | Tensor


def _normalize_image(
    src: ImageLike,
    vmin: float | None = None,
    vmax: float | None = None,
) -> Image:
    """Normalize an image-like object to a standard format.

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

    Args:
        src: An image-like object. This can be a list, array, tensor, or a
            file-like object.
        vmin: Minimum value for normalization. If provided along with `vmax`,
            values are clipped to [vmin, vmax] and scaled to [0, 255].
            Only applies to array inputs.
        vmax: Maximum value for normalization. See `vmin`.

    Returns:
        A BytesIO object or other Image type.

    Raises:
        ModuleNotFoundError: If the required `PIL` or `numpy` packages are not
            available.
        ValueError: If the input is not a valid image-like object.
    """
    if (
        isinstance(src, list)
        or hasattr(src, "__array__")
        or hasattr(src, "toarray")
    ):
        DependencyManager.pillow.require(
            "to render images from arrays in `mo.image`"
        )
        from PIL import Image as _Image

        if not hasattr(src, "__array_interface__"):
            DependencyManager.numpy.require(
                "to render images from generic arrays in `mo.image`"
            )
            import numpy

            # Capture those sparse cases
            if hasattr(src, "toarray"):
                src = src.toarray()
            src = numpy.array(src)

        # uint8 (typestr '|u1') is already in [0, 255]; use directly
        # see https://numpy.org/doc/stable/reference/arrays.interface.html
        is_uint8 = src.__array_interface__["typestr"] == "|u1"
        has_bounds = vmin is not None or vmax is not None

        if 0 in src.__array_interface__.get("shape", (0,)):
            raise ValueError(
                f"Cannot render an image from an array with a zero-size "
                f"dimension (shape {src.__array_interface__['shape']!r})."
            )

        if not is_uint8 or has_bounds:
            lo = float(vmin) if vmin is not None else float(src.min())
            hi = float(vmax) if vmax is not None else float(src.max())
            if has_bounds:
                if lo > hi:
                    raise ValueError(
                        f"vmin ({vmin}) must be less than or equal to "
                        f"vmax ({vmax})."
                    )
                # torch/jax/tf tensors lack __array_interface__ and are
                # converted to numpy above, so src is always an ndarray here.
                if not hasattr(src, "clip"):
                    raise ValueError(
                        f"Array of type {type(src)} does not support "
                        "clipping. Convert to a numpy array before passing "
                        "to `mo.image`."
                    )
                src = src.clip(lo, hi)
            denom = hi - lo
            if denom == 0:
                src = src - src  # zeros, preserving shape
            else:
                src = (src - lo) / denom * 255.0

        img = _Image.fromarray(src.astype("uint8"))
        # io.BytesIO is one of the Image types.
        normalized_src: Image = io.BytesIO()
        img.save(normalized_src, format="PNG")
        return normalized_src

    # Handle PIL Image objects
    if DependencyManager.pillow.imported():
        from PIL import Image as _Image

        if isinstance(src, _Image.Image):
            img_byte_arr = io.BytesIO()
            src.save(img_byte_arr, format=src.format or "PNG")
            img_byte_arr.seek(0)
            return img_byte_arr

    # Verify that this is a image object
    if not isinstance(src, (str, bytes, io.BytesIO, io.BufferedReader, Path)):
        raise ValueError(
            f"Expected an image object, but got {type(src)} instead."
        )
    return src


@mddoc
def image(
    src: ImageLike,
    alt: str | None = None,
    width: int | str | None = None,
    height: int | str | None = None,
    rounded: bool = False,
    style: dict[str, Any] | None = None,
    caption: str | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
) -> Html:
    """Render an image as HTML.

    Examples:
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
            caption="Marimo logo",
        )
        ```

        ```python3
        # Compare images with consistent intensity scaling
        import numpy as np

        dark = np.full((100, 100), 50)
        light = np.full((100, 100), 200)
        mo.hstack(
            [
                mo.image(dark, vmin=0, vmax=255),
                mo.image(light, vmin=0, vmax=255),
            ]
        )
        ```

    Args:
        src: a path or URL to an image, a file-like object (opened in binary
            mode), or array-like object. When `src` is array-like, `uint8`
            arrays are used as-is. Other dtypes are min-max normalized unless
            `vmin`/`vmax` are provided.
        alt: the alt text of the image
        width: the width of the image in pixels or a string with units
        height: the height of the image in pixels or a string with units
        rounded: whether to round the corners of the image
        style: a dictionary of CSS styles to apply to the image
        caption: the caption of the image
        vmin: minimum value for normalization when `src` is an array. Values
            below `vmin` are clipped. If `None`, defaults to the array
            minimum. Only used when `src` is array-like.
        vmax: maximum value for normalization when `src` is an array. Values
            above `vmax` are clipped. If `None`, defaults to the array
            maximum. Only used when `src` is array-like.

    Returns:
        `Html` object
    """
    # Convert to virtual file
    resolved_src: str | None
    src = _normalize_image(src, vmin=vmin, vmax=vmax)
    # TODO: Consider downsampling here. This is something matplotlib does
    # implicitly, and can potentially remove the bottle-neck of very large
    # images.
    if isinstance(src, (io.BufferedReader, io.BytesIO)):
        src.seek(0)
        resolved_src = mo_data.image(src.read()).url
    elif isinstance(src, bytes):
        resolved_src = mo_data.image(src).url
    elif isinstance(src, Path):
        resolved_src = mo_data.image(src.read_bytes(), ext=src.suffix).url
    elif isinstance(src, str) and os.path.isfile(
        expanded_path := os.path.expanduser(src)
    ):
        src = Path(expanded_path)
        resolved_src = mo_data.image(src.read_bytes(), ext=src.suffix).url
    else:
        resolved_src = io_to_data_url(src, fallback_mime_type="image/png")

    styles = create_style(
        {
            "width": normalize_dimension(width),
            "height": normalize_dimension(height),
            "border-radius": "4px" if rounded else None,
            **(style or {}),
        }
    )
    img = h.img(src=resolved_src, alt=alt, style=styles)
    if caption is not None:
        return Html(
            h.figure(
                [
                    img,
                    h.figcaption(
                        [caption],
                        style="color: var(--muted-foreground); "
                        "text-align: center; margin-top: 0.5rem;",
                    ),
                ],
                style="display: flex; flex-direction: column;",
            )
        )
    return Html(img)
