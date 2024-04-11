# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable, Final, Optional

from marimo._output.formatting import as_html
from marimo._output.md import md
from marimo._output.rich_help import mddoc
from marimo._plugins.stateless.lazy import lazy as lazy_ui
from marimo._plugins.ui._core.ui_element import UIElement


@mddoc
class tabs(UIElement[str, str]):
    """Display objects in a tabbed view.

    **Examples.**

    Show content in tabs:

    ```python
    tab1 = mo.vstack([
        "slider": mo.ui.slider(1, 10),
        "text": mo.ui.text(),
        "date": mo.ui.date()
    ])

    tab2 = mo.md("You can show arbitrary content in a tab.")

    tabs = mo.ui.tabs({
        "Heading 1": tab1,
        "Heading 2": tab2
    })
    ```

    Control which tab is selected:

    ```python
    tabs = mo.ui.tabs(
        {"Heading 1": tab1, "Heading 2": tab2}, value="Heading 2"
    )
    ```

    Tab content can be lazily loaded:

    ```python
    tabs = mo.ui.tabs(
        {"Heading 1": tab1, "Heading 2": expensive_component}, lazy=True
    )
    ```

    **Attributes.**

    - `value`: A string, the name of the selected tab.

    **Initialization Args.**

    - `tabs`: a dictionary of tab names to tab content; strings are interpreted
              as markdown
    - `value`: the name of the tab to open; defaults to the first tab
    - `lazy`: a boolean, whether to lazily load the tab content.
              This is a convenience that wraps each tab in a `mo.lazy`
              component.
    """

    _name: Final[str] = "marimo-tabs"

    def __init__(
        self,
        tabs: dict[str, object],
        value: Optional[str] = None,
        lazy: bool = False,
        *,
        label: str = "",
        on_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        def render_content(tab: object) -> str:
            if lazy:
                return lazy_ui(tab).text
            if isinstance(tab, str):
                return md(tab).text
            return as_html(tab).text

        tab_items = "".join(
            [
                "<div data-kind='tab'>" + render_content(tab) + "</div>"
                for tab in tabs.values()
            ]
        )

        self._tab_keys = list(tabs.keys())
        tab_labels = list(md(label).text for label in tabs.keys())

        index = (
            str(self._tab_keys.index(value))
            if value in self._tab_keys and tabs
            else None
        )

        super().__init__(
            component_name=self._name,
            initial_value=index or "",
            label=label,
            args={"tabs": tab_labels},
            on_change=on_change,
            slotted_html=tab_items,
        )

    def _convert_value(self, value: str) -> str:
        if not value:
            return self._tab_keys[0]
        index = int(value)
        return self._tab_keys[index]
