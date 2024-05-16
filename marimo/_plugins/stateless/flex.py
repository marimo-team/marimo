# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional

from marimo._output.builder import h
from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import create_style

if TYPE_CHECKING:
    from collections.abc import Sequence


def _flex(
    items: Sequence[object],
    direction: Literal["row", "column"],
    justify: Literal[
        "start", "center", "end", "space-between", "space-around"
    ],
    align: Optional[Literal["start", "end", "center", "stretch"]],
    wrap: bool,
    gap: float,
    child_flexes: Optional[Sequence[Optional[float]]],
) -> Html:
    justify_content_map = {
        "start": "flex-start",
        "center": "center",
        "end": "flex-end",
        "space-between": "space-between",
        "space-around": "space-around",
        None: "space-between",
    }
    align_items_map = {
        "start": "flex-start",
        "center": "center",
        "end": "flex-end",
        "stretch": "stretch",
        None: "normal",
    }
    style = create_style(
        {
            "display": "flex",
            "flex": "1",
            "flex-direction": direction,
            "justify-content": justify_content_map[justify],
            "align-items": align_items_map[align],
            "flex-wrap": "wrap" if wrap else "nowrap",
            "gap": f"{gap}rem",
        }
    )

    def create_style_for_item(idx: int) -> Optional[str]:
        if child_flexes is None:
            return ""
        child_flex = child_flexes[idx]
        if child_flex is None:
            return ""
        return create_style({"flex": f"{child_flex}"})

    grid_items = [
        h.div(as_html(item).text, style=create_style_for_item(i))
        for i, item in enumerate(items)
    ]
    return Html(h.div(grid_items, style=style))


@mddoc
def vstack(
    items: Sequence[object],
    *,
    align: Optional[Literal["start", "end", "center", "stretch"]] = None,
    justify: Literal[
        "start", "center", "end", "space-between", "space-around"
    ] = "start",
    gap: float = 0.5,
    heights: Optional[Literal["equal"] | Sequence[float]] = None,
) -> Html:
    """Stack items vertically, in a column.

    Combine with `hstack` to build a grid of items.

    **Example.**

    ```python3
    # Build a column of items
    mo.vstack([mo.md("..."), mo.ui.text_area()])
    ```

    ```python3
    # Build a grid.
    mo.vstack(
        [
            mo.hstack([mo.md("..."), mo.ui.text_area()]),
            mo.hstack([mo.ui.checkbox(), mo.ui.text(), mo.ui.date()]),
        ]
    )
    ```

    **Args.**

    - `items`: A list of items.
    - `align`: Align items horizontally: start, end, center, or stretch.
    - `justify`: Justify items vertically: start, center, end,
    - `gap`: Gap between items as a float in rem. 1rem is 16px by default.
    - `heights`: "equal" to give items equal height;
        or a list of relative heights with same length as `items`,
        eg, [1, 2] means the second item is twice as tall
        as the first; or `None` for a sensible default

    **Returns.**

    - An `Html` object.
    """
    return _flex(
        items,
        direction="column",
        justify=justify,
        align=align,
        wrap=False,
        gap=gap,
        child_flexes=[1 for _ in range(len(items))]
        if heights == "equal"
        else heights,
    )


@mddoc
def hstack(
    items: Sequence[object],
    *,
    justify: Literal[
        "start", "center", "end", "space-between", "space-around"
    ] = "space-between",
    align: Optional[Literal["start", "end", "center", "stretch"]] = None,
    wrap: bool = False,
    gap: float = 0.5,
    widths: Optional[Literal["equal"] | Sequence[float]] = None,
) -> Html:
    """Stack items horizontally, in a row.

    Combine with `vstack` to build a grid.

    **Example.**

    ```python3
    # Build a row of items
    mo.hstack([mo.md("..."), mo.ui.text_area()])
    ```

    ```python3
    # Build a grid.
    mo.hstack(
        [
            mo.vstack([mo.md("..."), mo.ui.text_area()]),
            mo.vstack([mo.ui.checkbox(), mo.ui.text(), mo.ui.date()]),
        ]
    )
    ```

    **Args.**

    - `items`: A list of items.
    - `justify`: Justify items horizontally: start, center, end,
        space-between, or space-around.
    - `align`: Align items vertically: start, end, center, or stretch.
    - `wrap`: Wrap items or not.
    - `gap`: Gap between items as a float in rem. 1rem is 16px by default.
    - `widths`: "equal" to give items equal width; or a list of relative widths
      with same length as `items`, eg, [1, 2] means the second item is twice as
      wide as the first; or `None` for a sensible default

    **Returns.**

    - An `Html` object.
    """
    return _flex(
        items,
        direction="row",
        justify=justify,
        align=align,
        wrap=wrap,
        gap=gap,
        child_flexes=[1 for _ in range(len(items))]
        if widths == "equal"
        else widths,
    )


# TODO(akshayka): Implement as a stateless plugin in frontend.
# Unused, but may be nice to keep around in case we want to add `mo.grid`
def _spaced(
    items: Sequence[object],
    justify: Literal["left", "right", "center", "normal"] = "center",
    items_per_row: Optional[int] = None,
    column_gap: float = 1,
    row_gap: float = 1,
) -> Html:
    """Space items evenly in row-major order.

    A grid built with this function has a fixed number of items per row.
    For more flexibility, use `hstack` and `vstack`.

    **Args.**

    - `items`: Items to arrange
    - `justify`: Justify items normally, left, right, or center.
    - `items_per_row`: Number of items to place in each row
    - `column_gap`: Minimum gap in rem between columns
    - `row_gap`: Minimum gap in rem between rows

    **Returns.**

    - An `Html` object.
    """
    items_per_row = len(items) if items_per_row is None else items_per_row
    style = create_style(
        {
            "display": "grid",
            "grid-template-columns": f"repeat({items_per_row}, 1fr)",
            "column-gap": f"{column_gap}rem",
            "row-gap": f"{row_gap}rem",
            "justify-items": justify,
            "overflow": "auto",
        }
    )
    grid_items = [h.div(as_html(item).text) for item in items]
    return Html(h.div(grid_items, style=style))
