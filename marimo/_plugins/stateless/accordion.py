# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.md import md
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._plugins.stateless.lazy import lazy as lazy_ui


@mddoc
def accordion(
    items: dict[str, object], multiple: bool = False, lazy: bool = False
) -> Html:
    """
    Accordion of one or more items.

    **Example.**

    ```python3
    mo.accordion(
        {"Tip": "Use accordions to let users reveal and hide content."}
    )
    ```

    Accordion content can be lazily loaded:

    ```python3
    mo.accordion({"View total": expensive_item}, lazy=True)
    ```

    where `expensive_item` is the item to render, or a callable that
    returns the item to render.

    **Args.**

    - `items`: a dictionary of item names to item content; strings are
      interpreted as markdown
    - `multiple`: whether to allow multiple items to be open simultaneously
    - `lazy`: a boolean, whether to lazily load the accordion content.
              This is a convenience that wraps each accordion in a `mo.lazy`
              component.

    **Returns.**

    - An `Html` object.
    """

    def render_content(tab: object) -> str:
        if lazy:
            return lazy_ui(tab).text
        if isinstance(tab, str):
            return md(tab).text
        return as_html(tab).text

    item_labels = list(md(label).text for label in items.keys())
    item_content = "".join(
        ["<div>" + render_content(item) + "</div>" for item in items.values()]
    )
    return Html(
        build_stateless_plugin(
            component_name="marimo-accordion",
            args={"labels": item_labels, "multiple": multiple},
            slotted_html=item_content,
        )
    )
