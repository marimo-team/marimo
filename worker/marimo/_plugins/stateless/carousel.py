# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Sequence

from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.md import md
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin


@mddoc
def carousel(
    items: Sequence[object],
) -> Html:
    """Create a carousel of items.

    **Example.**

    ```python3
    mo.carousel([mo.md("..."), mo.ui.text_area()])
    ```

    **Args.**

    - `items`: A list of items.

    **Returns.**

    - An `Html` object.
    """
    item_content = "".join(
        [
            (md(item).text if isinstance(item, str) else as_html(item).text)
            for item in items
        ]
    )

    return Html(
        build_stateless_plugin(
            component_name="marimo-carousel",
            args={},
            slotted_html=item_content,
        )
    )
