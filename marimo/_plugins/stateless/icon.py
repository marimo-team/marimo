# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal, Optional, Union

from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import create_style


@mddoc
def icon(
    icon_name: str,
    *,
    size: Optional[int] = None,
    color: Optional[str] = None,
    inline: bool = True,
    flip: Optional[
        Literal["horizontal", "vertical", "horizontal,vertical"]
    ] = None,
    rotate: Optional[Literal["90deg", "180deg", "270deg"]] = None,
    style: Optional[dict[str, Union[str, int, float, None]]] = None,
) -> Html:
    """
    Displays an icon. These icons are referenced by name from the
    [Iconify](https://iconify.design/) library.

    They are named in the format `icon-set:icon-name`, e.g.
    `lucide:leaf`.

    Icons are lazily loaded from a CDN, so they will not be loaded when
    not connected to the internet.

    These can be used in buttons, tabs, and other UI elements.

    **Examples.**

    ```python
    mo.md(f"# {mo.icon('lucide:leaf')} Leaf")

    mo.ui.button(
        label=f"{mo.icon('lucide:rocket')} Submit",
    )
    ```

    **Args.**

    - `icon_name`: the name of the icon to display
    - `size`: the size of the icon in pixels
    - `color`: the color of the icon
    - `inline`: whether to display the icon inline or as a block element
    - `flip`: whether to flip the icon horizontally, vertically, or both
    - `rotate`: whether to rotate the icon 90, 180, or 270 degrees
    - `style`: a dictionary of CSS styles to apply to the icon

    **Returns.**

    - An `Html` object.
    """

    if style is None:
        style = {}

    if color is not None:
        style["color"] = color

    return Html(
        h.component(
            "iconify-icon",
            [
                ("icon", icon_name),
                ("width", _space_to_string(size)),
                ("height", _space_to_string(size)),
                ("inline", "" if inline else None),
                ("flip", flip),
                ("rotate", rotate),
                ("style", create_style(style)),
            ],
        )
    )


def _space_to_string(value: Union[str, int, float, None]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    else:
        return f"{value}px"
