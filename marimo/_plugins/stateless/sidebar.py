# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output import md
from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._plugins.stateless.flex import vstack


@mddoc
def sidebar(
    item: object,
) -> Html:
    """
    Displays content in a sidebar. This is a special layout component that
    will display the content in a sidebar layout, rather than below/above
    the cell.

    This component still needs to be the last expression in the cell,
    in order to display correctly.

    You may use more than one `mo.sidebar` - they will be displayed in the
    order they are called.

    **Examples.**

    ```python
    mo.sidebar(
        [
            mo.md("# marimo"),
            mo.nav_menu(
                {
                    "#home": f"{mo.icon('lucide:home')} Home",
                    "#about": f"{mo.icon('lucide:user')} About",
                    "#contact": f"{mo.icon('lucide:phone')} Contact",
                    "Links": {
                        "https://twitter.com/marimo_io": "Twitter",
                        "https://github.com/marimo-team/marimo": "GitHub",
                    },
                },
                orientation="vertical",
            ),
        ]
    )
    ```

    **Args.**

    - `item`: the content to display in the sidebar

    **Returns.**

    - An `Html` object.
    """

    # If its a string, wrap in md
    if isinstance(item, str):
        item = md.md(item)
    # If its an array, wrap in vstack
    if isinstance(item, list):
        item = vstack(item)

    return Html(
        build_stateless_plugin(
            "marimo-sidebar",
            {},
            as_html(item).text,
        )
    )
