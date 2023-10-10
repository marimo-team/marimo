# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.md import md
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._runtime.context import get_context
from marimo._runtime.data_store import UIDataLifecycleItem


@mddoc
def accordion(items: dict[str, object], multiple: bool = False) -> Html:
    """
    Accordion of one or more items.

    **Example.**

    ```python3
    mo.accordion({
        "Tip": "Use accordions to let users reveal and hide content."
    })
    ```

    **Args.**

    - `items`: a dictionary of item names to item content; strings are
      interpreted as markdown
    - `multiple`: whether to allow multiple items to be open simultaneously

    **Returns.**

    - An `Html` object.
    """
    item_labels = list(md(label).text for label in items.keys())
    item_content = "".join(
        [
            "<div>"
            + (md(item).text if isinstance(item, str) else as_html(item).text)
            + "</div>"
            for item in items.values()
        ]
    )
    text, data_store = build_stateless_plugin(
        component_name="marimo-accordion",
        args={"labels": item_labels, "multiple": multiple},
        slotted_html=item_content,
    )
    # TODO: probably not the right place to set this
    get_context().cell_lifecycle_registry.add(UIDataLifecycleItem(data_store))
    return Html(text)
