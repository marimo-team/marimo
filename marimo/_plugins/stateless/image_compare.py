# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Literal, Optional, Union

import marimo._output.data.data as mo_data
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import normalize_dimension
from marimo._plugins.core.media import io_to_data_url
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._plugins.stateless.image import ImageLike, _normalize_image


@mddoc
def image_compare(
    before_image: ImageLike,
    after_image: ImageLike,
    value: float = 50,
    direction: Literal["horizontal", "vertical"] = "horizontal",
    width: Optional[Union[int, str]] = None,
    height: Optional[Union[int, str]] = None,
) -> Html:
    """Render an image comparison slider to compare two images side by side.

    Examples:
        ```python3
        # Basic usage with two images
        mo.image_compare(before_image="before.jpg", after_image="after.jpg")
        ```

        ```python3
        # With custom settings
        mo.image_compare(
            before_image="original.png",
            after_image="processed.png",
            value=30,  # Initial slider position at 30%
            direction="vertical",
            width=500,
            height=400,
        )
        ```

    Args:
        before_image: The "before" image to show in the comparison slider.
            Can be a path, URL, or array-like object.
        after_image: The "after" image to show in the comparison slider.
            Can be a path, URL, or array-like object.
        value: Initial position of the slider (0-100), defaults to 50.
        direction: Orientation of the slider, either "horizontal" or "vertical".
            Defaults to "horizontal".
        width: Width of the component in pixels or CSS units.
        height: Height of the component in pixels or CSS units.

    Returns:
        `Html` object with the image comparison slider.
    """
    # Process the before and after images
    before_src = _process_image_to_url(before_image)
    after_src = _process_image_to_url(after_image)

    normalized_value = max(0, min(100, float(value)))

    # Prepare dimensions
    width_str = normalize_dimension(width) if width is not None else None
    height_str = normalize_dimension(height) if height is not None else None

    # Build the plugin arguments
    args = {
        "before-src": before_src,
        "after-src": after_src,
        "value": normalized_value,
        "direction": direction,
    }

    # Add optional dimensions
    if width_str is not None:
        args["width"] = width_str
    if height_str is not None:
        args["height"] = height_str

    return Html(
        build_stateless_plugin(
            component_name="marimo-image-comparison",
            args=args,
        )
    )


def _process_image_to_url(src: ImageLike) -> str:
    """Process an image-like object to a URL that can be used in an <img> tag.

    Args:
        src: An image-like object.

    Returns:
        A string URL that can be used in an <img> tag.
    """
    try:
        src = _normalize_image(src)

        # different types handling
        if isinstance(src, io.BufferedReader) or isinstance(src, io.BytesIO):
            src.seek(0)
            return mo_data.image(src.read()).url
        elif isinstance(src, bytes):
            return mo_data.image(src).url
        elif isinstance(src, Path):
            return mo_data.image(src.read_bytes(), ext=src.suffix).url
        elif isinstance(src, str) and os.path.isfile(
            expanded_path := os.path.expanduser(src)
        ):
            path = Path(expanded_path)
            return mo_data.image(path.read_bytes(), ext=path.suffix).url
        else:
            # If it's a URL or other string, try to use it directly
            result = io_to_data_url(src, fallback_mime_type="image/png")
            return (
                result
                if result is not None
                else f"data:text/plain,Unable to process image: {src}"
            )
    except Exception as e:
        # return an error message otherwise
        error_message = f"Error processing image: {str(e)}"
        # Using a comment instead of print for logging
        # print(f"Warning: {error_message}")
        return f"data:text/plain,{error_message}"
