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
def tabs(tabs: dict[str, object]) -> Html:
    """
    Tabs of UI elements.

    **Examples.**

    ```python
    tab1 = mo.vstack([
        "slider": mo.ui.slider(1, 10),
        "text": mo.ui.text(),
        "date": mo.ui.date()
    ]);
    tab2 = mo.vstack([{
        "slider": mo.ui.slider(1, 10),
        "text": mo.ui.text(),
        "date": mo.ui.date()
    ]);
    tabs = mo.ui.tabs({
        "Tab 1": tab1,
        "Tab 2": tab2
    })
    ```

    **Args.**

    - `tabs`: a dictionary of tab names to tab content; strings are interpreted
    as markdown

    **Returns.**

    - An `Html` object.
    """
    tab_items = "".join(
        [
            "<div data-kind='tab'>"
            + (md(tab).text if isinstance(tab, str) else as_html(tab).text)
            + "</div>"
            for tab in tabs.values()
        ]
    )
    tab_labels = list(md(label).text for label in tabs.keys())
    text, data_store = build_stateless_plugin(
        component_name="marimo-tabs",
        args={"tabs": tab_labels},
        slotted_html=tab_items,
    )
    # TODO: probably not the right place to set this
    get_context().cell_lifecycle_registry.add(UIDataLifecycleItem(data_store))
    return Html(text)
