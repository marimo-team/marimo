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
from marimo._plugins.stateless.image import ImageLike, _normalize_image


@mddoc
def image_compare(
    before_image: ImageLike,
    after_image: ImageLike,
    value: float = 50,
    direction: Literal["horizontal", "vertical"] = "horizontal",
    show_labels: bool = False,
    before_label: str = "Before",
    after_label: str = "After",
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
            show_labels=True,
            before_label="Original",
            after_label="Processed",
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
        show_labels: Whether to show labels on the images, defaults to False.
        before_label: Label for the "before" image, defaults to "Before".
        after_label: Label for the "after" image, defaults to "After".
        width: Width of the component in pixels or CSS units.
        height: Height of the component in pixels or CSS units.

    Returns:
        `Html` object with the image comparison slider.
    """
    # Process the before and after images
    before_src = _process_image_to_url(before_image)
    after_src = _process_image_to_url(after_image)

    normalized_value = max(0, min(100, float(value)))

    # Create container styles
    container_styles = {}
    if width is not None:
        container_styles["width"] = normalize_dimension(width)
    if height is not None:
        container_styles["height"] = normalize_dimension(height)

    if direction == "vertical" and "height" not in container_styles:
        container_styles["height"] = "400px"

    # Determine slots based on direction
    # In vertical mode we need to swap slots for correct display
    first_slot = "second" if direction == "vertical" else "first"
    second_slot = "first" if direction == "vertical" else "second"

    # Create HTML content
    html_content = f"""
    <script defer src="https://unpkg.com/img-comparison-slider@7/dist/index.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/img-comparison-slider@7/dist/styles.css" />
    <style>
      img-comparison-slider {{
        --divider-width: 2px;
        --divider-color: white;
        --default-handle-opacity: 1;
        {f"width: {container_styles.get('width', '100%')};" if width is not None else ""}
        {f"height: {container_styles.get('height', 'auto')};" if height is not None else ""}
        max-width: 100%;
        display: block;
      }}
    </style>
    <img-comparison-slider value="{normalized_value}" direction="{direction}" class="img-comparison-slider">
      <img slot="{first_slot}" src="{before_src}" />
      <img slot="{second_slot}" src="{after_src}" />
      {f'<div slot="{first_slot}-label" class="label">{before_label}</div>' if show_labels else ""}
      {f'<div slot="{second_slot}-label" class="label">{after_label}</div>' if show_labels else ""}
    </img-comparison-slider>
    """

    return Html(html_content)


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
            return io_to_data_url(src, fallback_mime_type="image/png")
    except Exception as e:
        # return an error message otherwise
        error_message = f"Error processing image: {str(e)}"
        # Using a comment instead of print for logging
        # print(f"Warning: {error_message}")
        return f"data:text/plain,{error_message}"
