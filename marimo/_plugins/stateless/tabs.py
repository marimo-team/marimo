# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._impl.tabs import tabs as tabs_impl
from marimo._utils.deprecated import deprecated

if TYPE_CHECKING:
    from collections.abc import Mapping


@mddoc
@deprecated("mo.tabs is deprecated. Use mo.ui.tabs instead")
def tabs(tabs: Mapping[str, object]) -> Html:
    """Deprecated: Use `mo.ui.tabs` instead.

    Tabs of UI elements.

    Args:
        tabs: a mapping of tab names to tab content; strings are interpreted
            as markdown

    Returns:
        An `Html` object.

    Example:
        ```python
        tab1 = mo.vstack([mo.ui.slider(1, 10), mo.ui.text(), mo.ui.date()])
        tab2 = mo.vstack(
            [
                {
                    "slider": mo.ui.slider(1, 10),
                    "text": mo.ui.text(),
                    "date": mo.ui.date(),
                }
            ]
        )
        tabs = mo.tabs({"Tab 1": tab1, "Tab 2": tab2})
        ```
    """
    return tabs_impl(tabs)
